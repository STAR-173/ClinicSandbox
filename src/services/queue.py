import json
import structlog
from redis.asyncio import Redis
from src.core.config import settings

logger = structlog.get_logger()

# Connection Pool
redis_client = Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    decode_responses=True # Returns strings instead of bytes
)

QUEUE_NAME = "clinisandbox_jobs"

async def enqueue_job(job_id: str, job_data: dict):
    """
    Pushes the job ID to the Redis List.
    We don't need to push the whole FHIR bundle to Redis (it's big).
    We just push the ID. The worker will fetch the data from Postgres.
    
    However, for the 'Walking Skeleton', passing data might be easier.
    Let's stick to the 'Clean Arch' way: Pass ID only.
    """
    
    # Payload for the worker
    message = {
        "job_id": job_id,
        "attempt": 1
    }
    
    # LPUSH (Left Push) to the list
    await redis_client.lpush(QUEUE_NAME, json.dumps(message))
    
    logger.info("job_enqueued", queue=QUEUE_NAME, job_id=job_id)