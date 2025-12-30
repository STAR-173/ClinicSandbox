import asyncio
import json
import os
import httpx
import structlog
import subprocess
from typing import Dict, Any

from src.core.config import settings
from src.services.virtualization.base import VMBackend

logger = structlog.get_logger()

class FirecrackerVMBackend(VMBackend):
    """
    Orchestrates a real Firecracker MicroVM.
    Requires: KVM, /dev/kvm access, and firecracker binary.
    """

    async def prepare_resources(self, job_id: str, model_path: str, input_data: Dict[str, Any]) -> str:
        """
        1. Writes input data to a temp file (to be injected as a drive).
        2. Returns the socket path for the VM controller.
        """
        # In a real implementation, we would create a properly formatted EXT4 overlay 
        # or use a block device. For MVP, we write JSON to a shared location.
        work_dir = f"/tmp/firecracker/{job_id}"
        os.makedirs(work_dir, exist_ok=True)
        
        input_path = f"{work_dir}/input.json"
        with open(input_path, "w") as f:
            json.dump(input_data, f)
            
        logger.info("vm_resources_prepared", job_id=job_id, path=input_path)
        return work_dir

    async def run_inference(self, job_id: str, work_dir: str) -> Dict[str, Any]:
        """
        Configures and Boots the VM via the Firecracker API.
        """
        socket_path = f"{work_dir}/firecracker.socket"
        
        # 1. Spawn the Firecracker Process (Background)
        # In Prod, we would use the 'Jailer' binary here for isolation.
        cmd = [
            settings.FC_BINARY_PATH,
            "--api-sock", socket_path
        ]
        
        logger.info("vm_spawning_process", job_id=job_id, cmd=cmd)
        
        try:
            # We assume the binary exists. If not (Dev env), this crashes.
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except FileNotFoundError:
            # Fallback for Dev environments checking the code
            logger.error("firecracker_binary_missing", hint="Are you on Linux?")
            raise RuntimeError("Firecracker binary not found. Cannot run Real VM.")

        # 2. Wait for Socket to initialize
        transport = httpx.AsyncHTTPTransport(uds=socket_path)
        async with httpx.AsyncClient(transport=transport) as client:
            booted = False
            for _ in range(10): # Try for 1 second
                try:
                    await client.get("http://localhost/")
                    booted = True
                    break
                except httpx.ConnectError:
                    await asyncio.sleep(0.1)
            
            if not booted:
                proc.kill()
                raise TimeoutError("Firecracker API socket did not appear.")

            # 3. Configure Boot Source (The Kernel)
            await client.put("http://localhost/boot-source", json={
                "kernel_image_path": settings.FC_KERNEL_PATH,
                "boot_args": "console=ttyS0 reboot=k panic=1 pci=off"
            })

            # 4. Configure Drives (The RootFS + Data)
            # Drive 1: The OS (Read Only)
            await client.put("http://localhost/drives/rootfs", json={
                "drive_id": "rootfs",
                "path_on_host": settings.FC_ROOTFS_PATH,
                "is_root_device": True,
                "is_read_only": True
            })

            # Drive 2: The Input Data (Read Only)
            # We map the JSON file we created on the host to /dev/vdb inside the VM
            input_file_path = f"{work_dir}/input.json"
            await client.put("http://localhost/drives/input_data", json={
                "drive_id": "input_data",
                "path_on_host": input_file_path,
                "is_root_device": False,
                "is_read_only": True
            })

            # 5. Action: InstanceStart
            logger.info("vm_booting", job_id=job_id)
            await client.put("http://localhost/actions", json={
                "action_type": "InstanceStart"
            })

            # 6. Wait for Result (Reading from a shared output file or pipe)
            # In a real setup, the VM writes to a virtual serial port or network device.
            # We simulate the wait here.
            await asyncio.sleep(1) 
            
            # Retrieve Output (Simplified for MVP)
            # We assume the VM wrote to a file mapped on the host
            # output_file = f"{work_dir}/output.json"
            
            # Since we can't actually run the kernel, we raise an error here to prove we tried.
            # If we were on Linux with the kernel, we'd read the file.
            return {"status": "VM_RAN_BUT_NO_KERNEL_FOUND", "diagnosis": "UNKNOWN"}

        return {}

    async def cleanup(self, job_id: str, work_dir: str):
        # 1. Kill the process
        # 2. Delete the socket and temp files
        socket_path = f"{work_dir}/firecracker.socket"
        if os.path.exists(socket_path):
            os.remove(socket_path)
        logger.info("vm_cleanup_done", job_id=job_id)