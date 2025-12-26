from src.services.virtualization.base import VMBackend
from src.services.virtualization.mock import MockVMBackend

def get_vm_backend() -> VMBackend:
    # For now, always return Mock. In V2, we add logic for Firecracker.
    return MockVMBackend()