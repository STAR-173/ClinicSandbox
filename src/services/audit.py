import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.models import AuditLog

logger = structlog.get_logger()

async def record_audit_event(
    db: AsyncSession, 
    event_type: str, 
    details: dict, 
    job_id: str = None
):
    """
    Persists an event to the audit log table.
    """
    try:
        log_entry = AuditLog(
            job_id=job_id,
            event_type=event_type,
            details=details
        )
        db.add(log_entry)
        
        # We assume the caller manages the transaction commit for atomicity.
        # If the main operation fails, the audit log might roll back too 
        # (which is correct for "Decision made" events within a transaction).
        
        logger.info("audit_event_recorded", audit_type=event_type, job_id=job_id)
    except Exception as e:
        # standard logging fallback if DB audit fails
        logger.error("audit_logging_failed", error=str(e), audit_type=event_type)