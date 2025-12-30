import uuid
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.db.session import get_db
from src.db.models import Job, DiagnosticModel
from src.schemas.job import JobCreateRequest, JobResponse, JobStatusResponse
from src.services.queue import enqueue_job
from src.services.decision_engine import DecisionEngine
from src.schemas.manifest import ModelManifest, LOINCRequirement
from src.services.audit import record_audit_event

router = APIRouter()
logger = structlog.get_logger()

@router.post("/diagnose", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def request_diagnosis(
    payload: JobCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    logger.info("diagnosis_request_received", client_id=payload.client_id, target=payload.target_diagnosis)

    # 1. Select Manifest (Dynamic DB Lookup)
    # We look for the model with the highest accuracy for this target
    stmt = (
        select(DiagnosticModel)
        .where(DiagnosticModel.key == payload.target_diagnosis)
        .order_by(DiagnosticModel.accuracy.desc())
    )
    result = await db.execute(stmt)
    model_record = result.scalars().first()

    if not model_record:
        logger.warning("unknown_model_requested", target=payload.target_diagnosis)
        raise HTTPException(
            status_code=400, 
            detail=f"Unknown target diagnosis '{payload.target_diagnosis}'. No models registered."
        )

    # Convert DB JSONB to Pydantic Manifest
    # We construct the Manifest object dynamically
    try:
        reqs = [LOINCRequirement(**req) for req in model_record.required_fhir_resources.get("required_observations", [])]
        
        target_manifest = ModelManifest(
            target_diagnosis=model_record.key,
            minimum_accuracy=model_record.accuracy,
            required_observations=reqs
        )
    except Exception as e:
        logger.error("corrupt_model_manifest", model_id=str(model_record.id), error=str(e))
        raise HTTPException(status_code=500, detail="Internal Registry Error: Model Manifest is corrupt.")
        
    # 2. Run Decision Engine (Gap Analysis)
    try:
        is_ready, missing_reqs = DecisionEngine.analyze_gap(payload.fhir_bundle, target_manifest)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid FHIR Bundle format")
    except Exception as e:
        logger.error("decision_engine_error", error=str(e))
        raise HTTPException(status_code=500, detail="Internal Decision Engine Error")

    # 3. Handle Negotiation (The "Red Light")
    if not is_ready:
        logger.info("negotiation_required", missing_count=len(missing_reqs))

        # Record WHY we are rejecting this request
        try:
            await record_audit_event(
                db,
                event_type="DECISION_NEGOTIATION_REQUIRED",
                details={
                    "client_id": payload.client_id,
                    "target": payload.target_diagnosis,
                    "missing_codes": [req.code for req in missing_reqs],
                    "missing_display": [req.display for req in missing_reqs]
                }
            )
            await db.commit()
        except Exception as audit_err:
            # Log the actual DB error
            logger.error("audit_commit_failed", error=str(audit_err))

            # We don't stop the flow, but we might want to rollback the transaction 
            # to clean up the failed insert attempt before raising the HTTP 409
            await db.rollback()
        
        # We return 400 Bad Request because the client FAILED to provide required data.
        # In a chat flow, the bot reads this error and asks the user.
        return_msg = {
            "status": "NEGOTIATION_REQUIRED",
            "message": "Insufficient clinical data for this model.",
            "missing_data": [req.model_dump() for req in missing_reqs]
        }
        # Note: We are raising HTTPException to stop execution, but we pass the structured data in detail.
        # Ideally, we might want a custom 422 or 200-OK-with-Action, but 400 is semantically correct here.
        raise HTTPException(status_code=409, detail=return_msg) # 409 Conflict is often used for "State of resource incompatible"

    # 4. Create Job (The "Green Light")
    new_job = Job(
        client_id=payload.client_id,
        target_model_key=payload.target_diagnosis,
        fhir_bundle_input=payload.fhir_bundle,
        webhook_url=payload.webhook_url,
        status="QUEUED"
    )
    
    db.add(new_job)
    await db.commit()
    await db.refresh(new_job)

    # 5. Enqueue
    await enqueue_job(str(new_job.id), payload.model_dump())

    return JobResponse(
        job_id=new_job.id,
        status="QUEUED",
        created_at=new_job.created_at
    )

@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Polling Endpoint.
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalars().first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        result=job.result_payload,
        created_at=job.created_at,
        updated_at=job.updated_at
    )