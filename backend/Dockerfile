FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir . && pip install --no-cache-dir httpx

# Copy application code
COPY alembic.ini .
COPY alembic/ alembic/
COPY app/ app/
COPY worker.py .
COPY entrypoint.sh .

RUN chmod +x entrypoint.sh

# Run as non-root user
RUN adduser --disabled-password --gecos "" appuser
USER appuser

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Use entrypoint for auto-migration and seeding
ENTRYPOINT ["./entrypoint.sh"]
