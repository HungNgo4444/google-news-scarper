# Multi-stage Dockerfile for Google News Scraper API
# Optimized for production deployment with security and performance considerations

# Stage 1: Base image with common system dependencies
FROM python:3.11-slim as base

# Set environment variables for Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd --gid 1000 app && \
    useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home app

# Stage 2: Dependencies installation with caching optimization
FROM base as dependencies

# Switch to app user for dependency installation
USER app

# Set working directory
WORKDIR /app

# Copy requirements first for better layer caching
COPY --chown=app:app requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 3: Production image with minimal footprint
FROM base as production

# Set working directory
WORKDIR /app

# Copy Python dependencies from dependencies stage
COPY --from=dependencies /home/app/.local /home/app/.local

# Copy application source code
COPY src/ ./src/
COPY newspaper4k-master/ ./newspaper4k-master/

# Copy configuration files
COPY alembic.ini .
COPY pytest.ini .

# Create necessary directories with proper permissions
RUN mkdir -p /app/logs /app/data && \
    chown -R app:app /app

# Switch to non-root user
USER app

# Add user's local bin to PATH for installed packages
ENV PATH=/home/app/.local/bin:$PATH

# Set Python path to include the application source
ENV PYTHONPATH=/app:/app/src:/app/newspaper4k-master

# Expose application port
EXPOSE 8000

# Health check configuration
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command - runs the FastAPI application
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

# Labels for container metadata
LABEL maintainer="Google News Scraper Team" \
      version="1.0.0" \
      description="Google News Scraper API container" \
      org.opencontainers.image.source="https://github.com/company/google-news-scraper" \
      org.opencontainers.image.title="Google News Scraper API" \
      org.opencontainers.image.description="Containerized API for Google News crawling and article management" \
      org.opencontainers.image.version="1.0.0"