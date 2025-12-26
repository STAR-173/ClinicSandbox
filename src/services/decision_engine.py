import structlog
from typing import List, Dict, Any, Tuple
from fhir.resources.bundle import Bundle
from fhir.resources.observation import Observation
from pydantic import ValidationError

from src.schemas.manifest import ModelManifest, LOINCRequirement

logger = structlog.get_logger()

class DecisionEngine:
    
    @staticmethod
    def validate_fhir_structure(bundle_json: Dict[str, Any]) -> Bundle:
        """
        Strictly parses JSON into a FHIR R4 Bundle object.
        Raises ValidationError if invalid.
        """
        try:
            # fhir.resources does strict validation
            return Bundle(**bundle_json)
        except ValidationError as e:
            logger.warning("fhir_validation_failed", error=str(e))
            raise e
        except Exception as e:
            logger.error("fhir_parsing_crash", error=str(e))
            raise ValueError("Invalid FHIR JSON structure")

    @staticmethod
    def extract_loinc_codes(bundle: Bundle) ->  Dict[str, Observation]:
        """
        Scans the bundle and returns a map of {LOINC_CODE: ObservationResource}.
        """
        found_codes = {}
        
        if not bundle.entry:
            return found_codes

        for entry in bundle.entry:
            resource = entry.resource

            # Fallback to resourceType if resource_type is missing
            r_type = getattr(resource, "resource_type", None)
            if not r_type:
                r_type = getattr(resource, "resourceType", None)
            if not r_type:
                r_type = resource.__class__.__name__
            
            # We are currently interested in Observations (Lab Results, Vitals)
            if r_type == "Observation":
                # FHIR uses 'code.coding[]' list. We verify the system is LOINC.
                if resource.code and resource.code.coding:
                    for coding in resource.code.coding:
                        # Standard LOINC URL: http://loinc.org
                        if "loinc.org" in (coding.system or ""):
                            found_codes[coding.code] = resource
                            
        return found_codes

    @staticmethod
    def analyze_gap(bundle_json: Dict[str, Any], manifest: ModelManifest) -> Tuple[bool, List[LOINCRequirement]]:
        """
        Compares Patient Data vs Model Requirements.
        Returns:
            (True, []) -> Ready to Run
            (False, [missing_reqs]) -> Negotiation Needed
        """
        # 1. Parse & Validate
        try:
            bundle = DecisionEngine.validate_fhir_structure(bundle_json)
        except Exception:
            # If we can't parse it, we can't analyze it. Caller handles the 400.
            raise

        # 2. Extract Patient's Codes
        patient_codes = DecisionEngine.extract_loinc_codes(bundle)
        logger.info("analyzing_gap", found_codes=list(patient_codes.keys()))

        # 3. Check Requirements
        missing_requirements = []
        
        for req in manifest.required_observations:
            if req.mandatory:
                if req.code not in patient_codes:
                    missing_requirements.append(req)
        
        if missing_requirements:
            return False, missing_requirements
        
        return True, []