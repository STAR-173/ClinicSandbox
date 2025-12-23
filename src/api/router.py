from fastapi import APIRouter
from src.api.endpoints import jobs

api_router = APIRouter()

# Register the endpoints
api_router.include_router(jobs.router, tags=["Diagnosis Jobs"])