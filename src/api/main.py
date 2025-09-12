"""FastAPI application entry point for Google News Scraper.

This module creates and configures the FastAPI application with proper middleware,
routing, and lifecycle event handlers for containerized deployment.

Features:
- Health check endpoint for container health monitoring
- CORS middleware for development
- Database connection lifecycle management  
- Structured logging integration
- Error handling middleware
- API versioning with /api/v1 prefix

Usage:
    Development: uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
    Production: uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4
    
Container Usage:
    docker run -p 8000:8000 -e DATABASE_URL=... app
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import structlog

from src.shared.config import get_settings
from src.database.connection import get_database_connection, close_database_connection
from src.shared.health import get_health_checker
from src.api.routes.categories import router as categories_router

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager for startup and shutdown events."""
    # Startup
    settings = get_settings()
    logger.info("Starting Google News Scraper API", 
                environment=settings.ENVIRONMENT,
                log_level=settings.LOG_LEVEL)
    
    # Initialize database connection
    try:
        db_connection = get_database_connection(settings)
        logger.info("Database connection initialized")
        
        # Verify database health
        is_healthy = await db_connection.health_check()
        if not is_healthy:
            logger.error("Database health check failed during startup")
            raise RuntimeError("Database connection failed")
        
        logger.info("Database health check passed")
        
    except Exception as e:
        logger.error("Failed to initialize database connection", error=str(e))
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down Google News Scraper API")
    try:
        await close_database_connection()
        logger.info("Database connection closed")
    except Exception as e:
        logger.error("Error during database cleanup", error=str(e))


# Create FastAPI application with lifecycle management
app = FastAPI(
    title="Google News Scraper API",
    description="REST API for managing Google News crawling categories and articles",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json"
)

# Get settings for middleware configuration
settings = get_settings()

# CORS middleware configuration
if settings.ENVIRONMENT == "development":
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # In production, specify actual origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    # Production CORS - more restrictive
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[],  # Configure specific origins in production
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add request processing time header and structured logging."""
    import time
    import uuid
    
    start_time = time.time()
    correlation_id = str(uuid.uuid4())
    
    # Add correlation ID to request state
    request.state.correlation_id = correlation_id
    
    logger.info(
        "Request started",
        correlation_id=correlation_id,
        method=request.method,
        path=request.url.path,
        client_ip=request.client.host if request.client else None
    )
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    response.headers["X-Correlation-ID"] = correlation_id
    
    logger.info(
        "Request completed",
        correlation_id=correlation_id,
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        process_time=process_time
    )
    
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with structured logging."""
    correlation_id = getattr(request.state, 'correlation_id', 'unknown')
    
    logger.warning(
        "HTTP exception",
        correlation_id=correlation_id,
        status_code=exc.status_code,
        detail=exc.detail,
        method=request.method,
        path=request.url.path
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP Exception",
            "detail": exc.detail,
            "status_code": exc.status_code,
            "correlation_id": correlation_id
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors with detailed information."""
    correlation_id = getattr(request.state, 'correlation_id', 'unknown')
    
    logger.warning(
        "Request validation error",
        correlation_id=correlation_id,
        errors=exc.errors(),
        method=request.method,
        path=request.url.path
    )
    
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation Error",
            "detail": "Request validation failed",
            "validation_errors": exc.errors(),
            "correlation_id": correlation_id
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions with proper logging."""
    correlation_id = getattr(request.state, 'correlation_id', 'unknown')
    
    logger.error(
        "Unhandled exception",
        correlation_id=correlation_id,
        error=str(exc),
        error_type=type(exc).__name__,
        method=request.method,
        path=request.url.path,
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": "An unexpected error occurred",
            "correlation_id": correlation_id
        }
    )


# Health check endpoint for container health monitoring
@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint for container orchestration.
    
    Returns:
        dict: Health status with service info and database connectivity
        
    This endpoint is used by Docker health checks, Kubernetes probes,
    and load balancers to determine service health.
    """
    try:
        # Check database connectivity
        db_connection = get_database_connection()
        db_healthy = await db_connection.health_check()
        
        if not db_healthy:
            logger.error("Health check failed - database connectivity issue")
            raise HTTPException(
                status_code=503,
                detail="Database connectivity failed"
            )
        
        return {
            "status": "healthy",
            "service": "google-news-scraper",
            "version": "1.0.0",
            "environment": settings.ENVIRONMENT,
            "database": "connected",
            "timestamp": "2025-09-12T00:00:00Z"
        }
        
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        raise HTTPException(
            status_code=503,
            detail=f"Service unhealthy: {str(e)}"
        )


# Comprehensive health status endpoint
@app.get("/health/detailed", tags=["health"])
async def detailed_health_check():
    """Detailed health check with all component status.
    
    Returns:
        dict: Comprehensive health status of all components
    """
    try:
        health_checker = get_health_checker()
        system_health = await health_checker.check_system_health(include_detailed=True)
        
        response_data = system_health.to_dict()
        
        # Set appropriate HTTP status based on health
        if system_health.status.value == "unhealthy":
            raise HTTPException(status_code=503, detail=response_data)
        elif system_health.status.value == "degraded":
            # Return 200 but indicate degraded status
            response_data["warning"] = "Some components are degraded"
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Detailed health check failed", error=str(e))
        raise HTTPException(
            status_code=503,
            detail=f"Health check failed: {str(e)}"
        )

# Readiness probe endpoint for Kubernetes
@app.get("/ready", tags=["health"])
async def readiness_check():
    """Readiness probe endpoint for Kubernetes orchestration.
    
    Returns:
        dict: Readiness status indicating service can accept traffic
    """
    try:
        health_checker = get_health_checker()
        
        # Check critical components for readiness
        db_health = await health_checker.check_database_health()
        redis_health = await health_checker.check_redis_health()
        
        critical_components = [db_health, redis_health]
        ready = all(comp.is_healthy for comp in critical_components)
        
        if not ready:
            failed_components = [comp.name for comp in critical_components if not comp.is_healthy]
            raise HTTPException(
                status_code=503,
                detail=f"Critical components not ready: {', '.join(failed_components)}"
            )
        
        return {
            "status": "ready",
            "service": "google-news-scraper",
            "checks": {
                comp.name: "ready" if comp.is_healthy else "not_ready"
                for comp in critical_components
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Readiness check failed", error=str(e))
        raise HTTPException(
            status_code=503,
            detail=f"Service not ready: {str(e)}"
        )


# Liveness probe endpoint for Kubernetes
@app.get("/live", tags=["health"])
async def liveness_check():
    """Liveness probe endpoint for Kubernetes orchestration.
    
    Returns:
        dict: Basic liveness status
    """
    return {
        "status": "alive",
        "service": "google-news-scraper"
    }


# Root endpoint
@app.get("/", tags=["root"])
async def root():
    """Root endpoint with API information."""
    return {
        "service": "Google News Scraper API",
        "version": "1.0.0",
        "docs": "/api/v1/docs",
        "health": "/health"
    }


# Include API routers
app.include_router(categories_router)

# Additional routers would be included here when available
# app.include_router(articles_router)
# app.include_router(crawl_jobs_router)


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True if settings.ENVIRONMENT == "development" else False,
        log_level=settings.LOG_LEVEL.lower()
    )