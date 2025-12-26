import pytest
import json
import httpx
from unittest.mock import AsyncMock, patch
from src.services.webhook import WebhookService
from src.core.config import settings

# Test Payload
JOB_ID = "test-job-123"
RESULT = {"diagnosis": "POSITIVE"}

@pytest.fixture
def mock_httpx_client():
    with patch("httpx.AsyncClient") as mock_client:
        yield mock_client

def test_signature_generation():
    """
    Ensure HMAC-SHA256 generation is correct and consistent.
    """
    payload = {
        "job_id": JOB_ID,
        "status": "COMPLETED",
        "result": RESULT,
        "timestamp": "2025-..."
    }
    
    sig1 = WebhookService.generate_signature(payload)
    sig2 = WebhookService.generate_signature(payload)
    
    assert sig1 == sig2
    assert len(sig1) == 64 # SHA256 hex digest length

@pytest.mark.asyncio
async def test_webhook_successful_delivery():
    """
    Test the happy path: Server returns 200 OK.
    """
    url = "http://webhook.test/callback"
    
    # Mock the response
    mock_post = AsyncMock()
    mock_post.return_value.status_code = 200
    mock_post.return_value.raise_for_status = lambda: None # No exception
    
    # Patch httpx.AsyncClient.post
    with patch("httpx.AsyncClient.post", new=mock_post):
        await WebhookService.send_webhook(url, JOB_ID, RESULT)
        
        # Verify calls
        assert mock_post.called
        args, kwargs = mock_post.call_args
        assert args[0] == url
        assert "X-CliniSandbox-Signature" in kwargs["headers"]

@pytest.mark.asyncio
async def test_webhook_retry_logic():
    """
    Test that the service retries 3 times on 500 errors.
    """
    url = "http://webhook.test/fail"
    
    # Mock a failure response that triggers raise_for_status
    mock_response = AsyncMock()
    mock_response.status_code = 500
    
    # Define a side effect that raises HTTPStatusError
    def side_effect(*args, **kwargs):
        raise httpx.HTTPStatusError("500 Error", request=None, response=mock_response)

    mock_post = AsyncMock(side_effect=side_effect)

    # We patch the retry wait time to be 0 so the test runs fast
    with patch("httpx.AsyncClient.post", new=mock_post):
        # We expect it to eventually fail after retries
        with pytest.raises(httpx.HTTPStatusError):
            await WebhookService.send_webhook(url, JOB_ID, RESULT)
        
        # Check call count. 
        # Tenacity default in our code is stop_after_attempt(3)
        assert mock_post.call_count == 3