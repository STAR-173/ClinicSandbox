import asyncio
import json
import os
import tempfile
import structlog
from typing import Dict, Any
from src.services.virtualization.base import VMBackend

logger = structlog.get_logger()

class MockVMBackend(VMBackend):
    """
    Runs inside the Docker container and simulates a VM.
    """
    async def prepare_resources(self, job_id: str, model_path: str, input_data: Dict[str, Any]) -> str:
        # Create a temp file inside the container
        fd, path = tempfile.mkstemp(suffix=f"_{job_id}.json", text=True)
        with os.fdopen(fd, 'w') as tmp:
            json.dump(input_data, tmp)
        return path

    async def run_inference(self, job_id: str, resource_path: str) -> Dict[str, Any]:
        logger.info("vm_mock_processing_start", job_id=job_id)
        # Simulate computation time
        await asyncio.sleep(2.0)
        
        # Mock Result
        return {
            "diagnosis": "POSITIVE",
            "confidence": 0.98,
            "backend": "DOCKER_MOCK"
        }

    async def cleanup(self, job_id: str, resource_path: str):
        if os.path.exists(resource_path):
            os.remove(resource_path)