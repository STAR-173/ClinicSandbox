import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
import structlog

from src.core.config import settings
from src.core.logging import setup_logging
from src.api.router import api_router # We will create this next

# 1. Initialize Logging
setup_logging()
logger = structlog.get_logger()

# 2. Lifecycle (Startup/Shutdown)
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("system_startup", env=settings.ENVIRONMENT)
    # Could initialize Redis pool here if not lazy-loaded
    yield
    logger.info("system_shutdown")

# 3. Create App
app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# 4. Middleware: CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Tighten this in Prod
    allow_methods=["*"],
    allow_headers=["*"],
)

# 5. Middleware: Observability & Tracing
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    # Generate correlation ID
    request_id = request.headers.get("X-Request-ID") or "req_" + str(time.time())
    
    # Bind to logger context
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        method=request.method,
        path=request.url.path
    )
    
    start_time = time.perf_counter()
    try:
        response = await call_next(request)
        process_time = time.perf_counter() - start_time
        
        # Log success
        logger.info(
            "http_request_completed",
            status_code=response.status_code,
            duration=process_time
        )
        return response
    except Exception as e:
        # Log crash
        process_time = time.perf_counter() - start_time
        logger.error(
            "http_request_failed",
            error=str(e),
            duration=process_time
        )
        raise e

# 6. Mount Routes
app.include_router(api_router, prefix=settings.API_V1_STR)

# 7. Mount Metrics Endpoint (Prometheus)
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Health Check
@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.PROJECT_VERSION}