import hmac
import hashlib
import json
import structlog
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.core.config import settings

logger = structlog.get_logger()

class WebhookService:
    
    @staticmethod
    def generate_signature(payload: dict) -> str:
        """
        Creates an HMAC-SHA256 signature of the JSON payload.
        """
        # Sort keys ensures deterministic JSON for signing
        payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
        secret_bytes = settings.WEBHOOK_SECRET.encode('utf-8')
        
        signature = hmac.new(secret_bytes, payload_bytes, hashlib.sha256).hexdigest()
        return signature

    @staticmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError)),
        reraise=True
    )
    async def send_webhook(url: str, job_id: str, result: dict):
        """
        Sends the result to the client. Retries 3 times on failure.
        """
        logger.info("webhook_attempt_start", job_id=job_id, url=url)
        
        payload = {
            "job_id": job_id,
            "status": "COMPLETED",
            "result": result,
            # In a real app, add a timestamp here to prevent replay attacks
            # "timestamp": datetime.utcnow().isoformat() 
        }
        
        signature = WebhookService.generate_signature(payload)
        
        headers = {
            "Content-Type": "application/json",
            "X-CliniSandbox-Signature": signature,
            "User-Agent": "CliniSandbox-Webhook/1.0"
        }
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
        logger.info("webhook_delivery_success", job_id=job_id, status_code=response.status_code)