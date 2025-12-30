from src.services.virtualization.base import VMBackend
from src.services.virtualization.mock import MockVMBackend
from src.services.virtualization.firecracker import FirecrackerVMBackend
from src.core.config import settings

def get_vm_backend() -> VMBackend:
    """
    Factory to return the appropriate VM engine based on Config.
    """
    if settings.USE_REAL_VM:
        return FirecrackerVMBackend()
    
    return MockVMBackend()