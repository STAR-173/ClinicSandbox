#!/bin/bash
set -e

echo "Running DB Migrations..."
alembic upgrade head

echo "Starting Uvicorn Server..."
# host 0.0.0.0 is required for Docker networking
exec uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload