from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime

# 1. Input Schema (Client -> API)
class JobCreateRequest(BaseModel):
    client_id: str = Field(..., min_length=1, description="ID of the calling bot")
    target_diagnosis: str = Field(..., description="e.g. sepsis, pneumonia")
    webhook_url: Optional[str] = Field(None, description="Callback URL for results")
    fhir_bundle: Dict[str, Any] = Field(..., description="Valid FHIR R4 Bundle")

    # Strict config
    model_config = ConfigDict(extra="forbid")

# 2. Output Schema (API -> Client)
class JobResponse(BaseModel):
    job_id: UUID
    status: str
    created_at: datetime
    eta_seconds: int = 5

# 3. Detail Schema (GET /jobs/{id})
class JobStatusResponse(BaseModel):
    job_id: UUID
    status: str
    result: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime