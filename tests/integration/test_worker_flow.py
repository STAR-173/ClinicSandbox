import pytest
from httpx import AsyncClient
from src.db.models import Job
from sqlalchemy import select

from src.worker.main import process_job

@pytest.mark.asyncio
async def test_end_to_end_job_processing(client: AsyncClient, db_session):
    # 1. Create Job
    payload = {
        "client_id": "integration_tester",
        "target_diagnosis": "sepsis",
        "fhir_bundle": {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": [
                {
                    "resource": {
                        "resourceType": "Observation",
                        "status": "final",
                        "code": { "coding": [{ "system": "http://loinc.org", "code": "8310-5" }] },
                        "valueQuantity": { "value": 37.5, "unit": "C" }
                    }
                },
                {
                    "resource": {
                        "resourceType": "Observation",
                        "status": "final",
                        "code": { "coding": [{ "system": "http://loinc.org", "code": "8867-4" }] },
                        "valueQuantity": { "value": 90, "unit": "/min" }
                    }
                },
                {
                    "resource": {
                        "resourceType": "Observation",
                        "status": "final",
                        "code": { "coding": [{ "system": "http://loinc.org", "code": "6690-2" }] },
                        "valueQuantity": { "value": 11.0, "unit": "10*3/uL" }
                    }
                }
            ]
        }
    }
    
    response = await client.post("/v1/diagnose", json=payload)
    job_id = response.json()["job_id"]
    
    # 2. Verify Initial State
    result = await db_session.execute(select(Job).where(Job.id == job_id))
    job = result.scalars().first()
    assert job.status == "QUEUED"
    
    # 3. Simulate Worker
    # (The patching in conftest.py ensures this uses our db_session)
    await process_job(job_id)
    
    # 4. Verify Final State
    # We explicitly expire the object so SQLAlchemy re-reads the rows
    # (even though it's the same session, the object might be stale in memory)
    await db_session.refresh(job)
    
    assert job.status == "COMPLETED"
    assert job.result_payload["diagnosis"] in ["POSITIVE", "NEGATIVE"]