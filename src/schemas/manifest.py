from pydantic import BaseModel, Field
from typing import List, Optional

class LOINCRequirement(BaseModel):
    code: str = Field(..., description="The LOINC code (e.g., '8867-4')")
    display: str = Field(..., description="Human readable name (e.g., 'Heart Rate')")
    mandatory: bool = Field(True, description="If False, the model can run without it but accuracy drops")

class ModelManifest(BaseModel):
    """
    Defines what a Diagnostic Model needs to run.
    Stored in the 'required_fhir_resources' JSONB column of the DB.
    """
    target_diagnosis: str
    minimum_accuracy: float
    required_observations: List[LOINCRequirement] = []
    
    # TODO: Add 'required_conditions', 'required_medications' later