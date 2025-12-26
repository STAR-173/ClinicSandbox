import pytest
from src.services.decision_engine import DecisionEngine
from src.schemas.manifest import ModelManifest, LOINCRequirement

# --- Test Data Fixtures ---

@pytest.fixture
def sepsis_manifest():
    return ModelManifest(
        target_diagnosis="sepsis",
        minimum_accuracy=0.95,
        required_observations=[
            LOINCRequirement(code="8867-4", display="Heart Rate", mandatory=True),
            LOINCRequirement(code="8310-5", display="Body Temp", mandatory=True)
        ]
    )

@pytest.fixture
def valid_bundle():
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Observation",
                    "status": "final",
                    "code": {"coding": [{"system": "http://loinc.org", "code": "8867-4"}]},
                    "valueQuantity": {"value": 100}
                }
            },
            {
                "resource": {
                    "resourceType": "Observation",
                    "status": "final",
                    "code": {"coding": [{"system": "http://loinc.org", "code": "8310-5"}]},
                    "valueQuantity": {"value": 37.5}
                }
            }
        ]
    }

@pytest.fixture
def incomplete_bundle():
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {
                "resource": {
                    "resourceType": "Observation",
                    "status": "final",
                    "code": {"coding": [{"system": "http://loinc.org", "code": "8867-4"}]},
                    "valueQuantity": {"value": 100}
                }
            }
            # Missing Body Temp (8310-5)
        ]
    }

# --- Tests ---

def test_gap_analysis_success(valid_bundle, sepsis_manifest):
    is_ready, missing = DecisionEngine.analyze_gap(valid_bundle, sepsis_manifest)
    assert is_ready is True
    assert len(missing) == 0

def test_gap_analysis_failure(incomplete_bundle, sepsis_manifest):
    is_ready, missing = DecisionEngine.analyze_gap(incomplete_bundle, sepsis_manifest)
    assert is_ready is False
    assert len(missing) == 1
    assert missing[0].code == "8310-5"

def test_malformed_fhir_rejection(sepsis_manifest):
    malformed_json = {"resourceType": "Bundle", "type": "collection", "entry": "INVALID_TYPE"}
    
    with pytest.raises(Exception):
        DecisionEngine.analyze_gap(malformed_json, sepsis_manifest)