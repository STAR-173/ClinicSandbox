# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

# Install system build deps (needed for some python packages)
RUN apt-get update && apt-get install -y gcc libpq-dev

# Install python deps
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Install runtime libs (libpq is needed for Postgres)
RUN apt-get update && apt-get install -y libpq5 curl && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy Application Code
COPY . .

# Environment Variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# We don't define CMD here because docker-compose will override it 
# (one for API, one for Worker)