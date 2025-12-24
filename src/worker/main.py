import asyncio
import json
import signal
import sys
import structlog
from sqlalchemy import select

# Imports from our core system
from src.core.config import settings
from src.core.logging import setup_logging
from src.db.session import AsyncSessionLocal
from src.db.models import Job
from src.services.queue import redis_client, QUEUE_NAME

# Initialize Logging
setup_logging()
logger = structlog.get_logger()

# Flag for graceful shutdown
SHUTDOWN_FLAG = False

def handle_sigterm(signum, frame):
    global SHUTDOWN_FLAG
    logger.info("worker_shutdown_signal_received")
    SHUTDOWN_FLAG = True

async def process_job(job_id: str):
    """
    The core logic. In M2, this calls Firecracker.
    In M1, this is a mock.
    """
    logger.info("processing_job_start", job_id=job_id)
    
    async with AsyncSessionLocal() as db:
        try:
            # 1. Fetch Job
            result = await db.execute(select(Job).where(Job.id == job_id))
            job = result.scalars().first()
            
            if not job:
                logger.error("job_not_found_in_db", job_id=job_id)
                return

            # 2. Update Status -> PROCESSING
            job.status = "PROCESSING"
            await db.commit()
            
            # 3. Simulate Work (The "Thinking" Phase)
            await asyncio.sleep(5) 
            
            # 4. Generate Mock Result
            mock_result = {
                "diagnosis": "POSITIVE" if "sepsis" in job.target_model_key else "NEGATIVE",
                "confidence_score": 0.98,
                "biomarkers": ["wbc_count_high", "lactate_elevated"]
            }
            
            # 5. Update Status -> COMPLETED
            job.status = "COMPLETED"
            job.result_payload = mock_result
            await db.commit()
            
            logger.info("processing_job_success", job_id=job_id)
            
        except Exception as e:
            logger.error("processing_job_failed", job_id=job_id, error=str(e))
            # Try to update DB to FAILED
            # (In a real app, we need robust error handling here to ensure we don't leave jobs in PROCESSING)
            try:
                job.status = "FAILED"
                await db.commit()
            except:
                pass

async def worker_loop():
    """
    Continuous loop that pulls from Redis.
    """
    logger.info("worker_startup", queue=QUEUE_NAME)
    
    while not SHUTDOWN_FLAG:
        try:
            # BRPOP: Blocking Right Pop. Waits 1 second for data.
            # Returns: (queue_name, data) or None
            # We use BLPOP or BRPOP. Since we used LPUSH, we use RPOP (FIFO) or BRPOP.
            # Wait... standard Queue is LPUSH (Head) -> RPOP (Tail).
            
            val = await redis_client.brpop(QUEUE_NAME, timeout=1)
            
            if val:
                # val is a tuple: ('clinisandbox_jobs', '{"job_id": "..."}')
                queue_name, data_str = val
                data = json.loads(data_str)
                job_id = data.get("job_id")
                
                # Context Propagation (Trace ID would be extracted here in M2)
                structlog.contextvars.bind_contextvars(job_id=job_id)
                    
                await process_job(job_id)
                
                # Clear context after job
                structlog.contextvars.clear_contextvars()
            
        except Exception as e:
            logger.error("worker_loop_error", error=str(e))
            await asyncio.sleep(1) # Don't tight loop on error

    logger.info("worker_shutdown_complete")

if __name__ == "__main__":
    # Register signal handlers for graceful exit
    signal.signal(signal.SIGINT, handle_sigterm)
    signal.signal(signal.SIGTERM, handle_sigterm)
    
    # Run the loop
    asyncio.run(worker_loop())