import uuid
import datetime
from sqlalchemy import String, DateTime, ForeignKey, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func

class Base(DeclarativeBase):
    pass

class DiagnosticModel(Base):
    """
    Registry of available ML models (e.g., Sepsis-v1).
    """
    __tablename__ = "diagnostic_models"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, index=True)
    key: Mapped[str] = mapped_column(String, unique=True, index=True) # e.g. "sepsis", "pneumonia"
    version: Mapped[str] = mapped_column(String)
    required_fhir_resources: Mapped[dict] = mapped_column(JSONB, default={}) # For Negotiation
    
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Job(Base):
    """
    A single diagnostic execution request.
    """
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[str] = mapped_column(String, index=True)
    
    # Status: QUEUED, PROCESSING, COMPLETED, FAILED, NEGOTIATION_REQUIRED
    status: Mapped[str] = mapped_column(String, default="QUEUED", index=True)
    
    target_model_key: Mapped[str] = mapped_column(String) # e.g. "sepsis"
    
    # Input/Output
    fhir_bundle_input: Mapped[dict] = mapped_column(JSONB) # The patient data
    result_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True) # The diagnosis
    
    webhook_url: Mapped[str | None] = mapped_column(String, nullable=True)
    
    # Timestamps for Observability
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

class AuditLog(Base):
    """
    Immutable record of system decisions.
    """
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Nullable because some events might not be tied to a job (e.g., system startup, login)
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=True)
    
    event_type: Mapped[str] = mapped_column(String, index=True) # e.g. "DECISION_NEGOTIATION_REQUIRED"
    details: Mapped[dict] = mapped_column(JSONB) # The context (missing codes, client id)
    
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())