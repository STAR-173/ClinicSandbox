import asyncio
import json
import signal
import structlog
from sqlalchemy import select
from src.core.logging import setup_logging
from src.db.session import AsyncSessionLocal
from src.db.models import Job
from src.services.queue import redis_client, QUEUE_NAME
from src.core.vm_factory import get_vm_backend
from src.services.webhook import WebhookService

setup_logging()
logger = structlog.get_logger()
SHUTDOWN_FLAG = False

def handle_sigterm(signum, frame):
    global SHUTDOWN_FLAG
    logger.info("worker_shutdown_signal_received")
    SHUTDOWN_FLAG = True

async def process_job(job_id: str):
    logger.info("processing_job_start", job_id=job_id)
    vm_runner = get_vm_backend()
    
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(Job).where(Job.id == job_id))
            job = result.scalars().first()
            if not job: return

            job.status = "PROCESSING"
            await db.commit()
            
            # --- VIRTUALIZATION START ---
            resource = await vm_runner.prepare_resources(str(job.id), "model.pt", job.fhir_bundle_input)
            try:
                output = await vm_runner.run_inference(str(job.id), resource)
                job.status = "COMPLETED"
                job.result_payload = output
            except Exception as e:
                job.status = "FAILED"
                job.result_payload = {"error": str(e)}
            finally:
                await vm_runner.cleanup(str(job.id), resource)
            # --- VIRTUALIZATION END ---

            await db.commit()

            # --- WEBHOOK DISPATCH START ---
            if job.webhook_url:
                try:
                    await WebhookService.send_webhook(
                        url=job.webhook_url, 
                        job_id=str(job.id), 
                        result=job.result_payload
                    )
                except Exception as wh_err:
                    logger.error("webhook_failed_all_retries", job_id=job_id, error=str(wh_err))
            
            logger.info("processing_job_done", status=job.status)

        except Exception as e:
            logger.error("processing_job_error", error=str(e))

async def worker_loop():
    logger.info("worker_startup", queue=QUEUE_NAME)
    while not SHUTDOWN_FLAG:
        try:
            val = await redis_client.brpop(QUEUE_NAME, timeout=1)
            if val:
                await process_job(json.loads(val[1]).get("job_id"))
        except Exception as e:
            logger.error("worker_loop_error", error=str(e))
            await asyncio.sleep(1)

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigterm)
    asyncio.run(worker_loop())