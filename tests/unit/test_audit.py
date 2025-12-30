import pytest
from unittest.mock import AsyncMock, MagicMock
from src.services.audit import record_audit_event
from src.db.models import AuditLog

@pytest.mark.asyncio
async def test_record_audit_event_success():
    # Mock the Database Session
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    
    # Call the service
    await record_audit_event(
        db=mock_db,
        event_type="TEST_EVENT",
        details={"foo": "bar"},
        job_id=None
    )
    
    # Assertions
    # 1. Ensure db.add() was called
    assert mock_db.add.called
    
    # 2. Inspect the object passed to db.add()
    args, _ = mock_db.add.call_args
    log_entry = args[0]
    
    assert isinstance(log_entry, AuditLog)
    assert log_entry.event_type == "TEST_EVENT"
    assert log_entry.details == {"foo": "bar"}