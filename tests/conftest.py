import asyncio
from typing import AsyncGenerator
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

from src.main import app
from src.core.config import settings
from src.db.session import get_db

# Use NullPool for tests to force a new connection per test (avoiding "Event Loop Closed" on cached connections)
# This is slightly slower but much more stable on Windows.
engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
TestingSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates a fresh SQLAlchemy session for each test.
    Starts a transaction -> Yields -> Rolls back.
    """
    connection = await engine.connect()
    transaction = await connection.begin()
    
    # Bind the session to this specific connection/transaction
    session = TestingSessionLocal(bind=connection)
    
    # ----------------------------------------------------------------------
    # CRITICAL FIX: Patch the global 'AsyncSessionLocal' used by the Worker
    # so it uses THIS session instead of creating a new one.
    # This ensures the Worker writes to the same transaction the Test reads.
    # ----------------------------------------------------------------------
    import src.worker.main
    original_session_factory = src.worker.main.AsyncSessionLocal
    src.worker.main.AsyncSessionLocal = lambda: session 
    # Note: Lambda returns the *instance* directly, not a context manager factory, 
    # so we might need a small adapter if the code uses 'async with AsyncSessionLocal() as db:'
    
    # Actually, the worker code is: 'async with AsyncSessionLocal() as db:'
    # So we need to mock the context manager behavior.
    class MockSessionManager:
        async def __aenter__(self):
            return session
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass # Do not close the session here, let the fixture handle it
            
    src.worker.main.AsyncSessionLocal = MockSessionManager

    yield session
    
    # TEARDOWN
    # Restore the original factory
    src.worker.main.AsyncSessionLocal = original_session_factory
    
    await session.close()
    await transaction.rollback()
    await connection.close()

@pytest.fixture(scope="function")
async def client(db_session) -> AsyncGenerator[AsyncClient, None]:
    """
    Creates a FastAPI Test Client that uses the overridden DB session.
    """
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()

from unittest.mock import AsyncMock

@pytest.fixture(autouse=True)
def mock_redis_queue(monkeypatch):
    """
    Automatically mocks the 'enqueue_job' function for ALL tests 
    to prevent 'Event loop is closed' errors on the global Redis client.
    
    If a specific test (like Integration) NEEDS real Redis, 
    it can override this or we can scope it to 'unit' only.
    """
    
    # Create a dummy async function that does nothing
    async def mock_enqueue(job_id, job_data):
        return
    
    # Patch the function where it is IMPORTED (in the endpoint file)
    monkeypatch.setattr("src.api.endpoints.jobs.enqueue_job", mock_enqueue)