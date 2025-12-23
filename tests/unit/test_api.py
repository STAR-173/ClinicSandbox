import pytest
from httpx import AsyncClient
from sqlalchemy import select
from src.db.models import Job

# This marker tells pytest this is an async test
@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "version" in response.json()

@pytest.mark.asyncio
async def test_create_diagnosis_job(client: AsyncClient, db_session):
    payload = {
        "client_id": "pytest_bot",
        "target_diagnosis": "sepsis",
        "webhook_url": "http://pytest.local/hook",
        "fhir_bundle": {"resourceType": "Bundle", "entry": []}
    }
    
    # 1. Send Request
    response = await client.post("/v1/diagnose", json=payload)
    
    # 2. Verify Response
    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "QUEUED"
    
    # 3. Verify DB (using the shared session)
    job_id = data["job_id"]
    result = await db_session.execute(select(Job).where(Job.id == job_id))
    job = result.scalars().first()
    
    assert job is not None
    assert job.client_id == "pytest_bot"
    assert job.status == "QUEUED"

@pytest.mark.asyncio
async def test_invalid_diagnosis_model(client: AsyncClient):
    payload = {
        "client_id": "pytest_bot",
        "target_diagnosis": "cancer_v1", # This model doesn't exist in our hardcoded list
        "fhir_bundle": {}
    }
    response = await client.post("/v1/diagnose", json=payload)
    assert response.status_code == 400