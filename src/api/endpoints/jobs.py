import uuid
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.db.session import get_db
from src.db.models import Job, DiagnosticModel
from src.schemas.job import JobCreateRequest, JobResponse, JobStatusResponse
from src.services.queue import enqueue_job  # We will create this helper next

router = APIRouter()
logger = structlog.get_logger()

@router.post("/diagnose", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def request_diagnosis(
    payload: JobCreateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    1. Validate Client (Mocked for now).
    2. Check if Model exists.
    3. Persist Job in DB (QUEUED).
    4. Push to Redis.
    """
    
    # 1. Validate Target Model (Simple check for MVP)
    # In a real app, we'd query the DB to ensure 'payload.target_diagnosis' maps to a valid model
    # For Milestone 1, we assume if it's "sepsis", it's valid.
    if payload.target_diagnosis not in ["sepsis", "pneumonia", "test_model"]:
        raise HTTPException(status_code=400, detail="Unknown target diagnosis model")

    # 2. Create Job Record
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

    logger.info("job_persisted", job_id=str(new_job.id), client_id=payload.client_id)

    # 3. Enqueue to Redis (Async)
    try:
        await enqueue_job(str(new_job.id), payload.model_dump())
    except Exception as e:
        logger.error("redis_enqueue_failed", error=str(e))
        # If Redis fails, we should probably rollback or mark job as FAILED
        # For now, we return 500
        new_job.status = "FAILED"
        await db.commit()
        raise HTTPException(status_code=500, detail="Failed to queue job")

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