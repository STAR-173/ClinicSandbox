import pytest
from httpx import AsyncClient
from sqlalchemy import select
from src.db.models import AuditLog

@pytest.mark.asyncio
async def test_negotiation_triggers_audit_log(client: AsyncClient, db_session):
    # 1. Payload missing required Sepsis codes (LOINC 8310-5 etc)
    payload = {
        "client_id": "audit_integration_test",
        "target_diagnosis": "sepsis",
        "fhir_bundle": {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": [
                 { "resource": { "resourceType": "Patient", "id": "pat-1" } }
            ]
        }
    }

    # 2. Send Request
    response = await client.post("/v1/diagnose", json=payload)
    
    # 3. Assert HTTP Contract
    assert response.status_code == 409
    assert response.json()["detail"]["status"] == "NEGOTIATION_REQUIRED"

    # 4. Assert Database Side Effect
    # Query the audit log table
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.event_type == "DECISION_NEGOTIATION_REQUIRED")
    )
    logs = result.scalars().all()
    
    # Find our specific log (since the DB might have rows from other runs)
    target_log = None
    for log in logs:
        if log.details.get("client_id") == "audit_integration_test":
            target_log = log
            break
            
    assert target_log is not None
    assert "missing_codes" in target_log.details