from abc import ABC, abstractmethod
from typing import Dict, Any

class VMBackend(ABC):
    @abstractmethod
    async def prepare_resources(self, job_id: str, model_path: str, input_data: Dict[str, Any]) -> str:
        pass

    @abstractmethod
    async def run_inference(self, job_id: str, resource_id: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def cleanup(self, job_id: str, resource_id: str):
        pass