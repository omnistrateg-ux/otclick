# Otclick Employer Acquisition Engine - Production Dockerfile
# Multi-stage build for optimized image size

# Stage 1: Builder
FROM python:3.12-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster package management
RUN pip install uv

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies
RUN uv pip install --system --no-cache-dir -e ".[prod]"

# Stage 2: Runtime
FROM python:3.12-slim as runtime

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /var/cache/apt/*

# Create non-root user
RUN groupadd --gid 1000 otclick \
    && useradd --uid 1000 --gid otclick --shell /bin/bash --create-home otclick

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=otclick:otclick app/ ./app/
COPY --chown=otclick:otclick workers/ ./workers/
COPY --chown=otclick:otclick migrations/ ./migrations/
COPY --chown=otclick:otclick alembic.ini ./
COPY --chown=otclick:otclick pyproject.toml ./

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    OTCLICK_ENVIRONMENT=production

# Switch to non-root user
USER otclick

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health/live || exit 1

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Expose port
EXPOSE 8000
