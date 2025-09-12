import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from functools import lru_cache
import logging


def _get_env_file() -> str:
    """Determine which environment file to load based on environment and container context."""
    # Check if running in container
    if os.path.exists("/.dockerenv") or os.environ.get("CONTAINER_RUNTIME"):
        logging.info("Running in container environment")
    
    # Environment-specific env file loading
    environment = os.environ.get("ENVIRONMENT", "development")
    
    # Priority order for env files:
    # 1. .env.{environment} (e.g., .env.production)
    # 2. .env.local (local overrides)
    # 3. .env (default)
    
    possible_env_files = [
        f".env.{environment}",
        ".env.local", 
        ".env"
    ]
    
    for env_file in possible_env_files:
        if os.path.exists(env_file):
            logging.info(f"Loading environment from: {env_file}")
            return env_file
    
    logging.warning("No environment file found, using environment variables only")
    return ".env"  # Fallback, won't be loaded if doesn't exist


class Settings(BaseSettings):
    DATABASE_URL: str = Field(
        ...,
        description="PostgreSQL database connection URL",
        env="DATABASE_URL"
    )
    
    DATABASE_POOL_SIZE: int = Field(
        default=10,
        description="Database connection pool size",
        env="DATABASE_POOL_SIZE"
    )
    
    DATABASE_MAX_OVERFLOW: int = Field(
        default=20,
        description="Database connection pool max overflow",
        env="DATABASE_MAX_OVERFLOW"
    )
    
    DATABASE_POOL_TIMEOUT: int = Field(
        default=30,
        description="Database connection pool timeout in seconds",
        env="DATABASE_POOL_TIMEOUT"
    )
    
    DATABASE_ECHO: bool = Field(
        default=False,
        description="Enable SQLAlchemy echo mode for debugging",
        env="DATABASE_ECHO"
    )
    
    ENVIRONMENT: str = Field(
        default="development",
        description="Application environment",
        env="ENVIRONMENT"
    )
    
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level",
        env="LOG_LEVEL"
    )
    
    # newspaper4k extraction settings
    EXTRACTION_TIMEOUT: int = Field(
        default=30,
        description="Timeout for article extraction in seconds",
        env="EXTRACTION_TIMEOUT"
    )
    
    EXTRACTION_MAX_RETRIES: int = Field(
        default=3,
        description="Maximum number of retry attempts for extraction",
        env="EXTRACTION_MAX_RETRIES"
    )
    
    EXTRACTION_RETRY_BASE_DELAY: float = Field(
        default=1.0,
        description="Base delay in seconds for exponential backoff",
        env="EXTRACTION_RETRY_BASE_DELAY"
    )
    
    EXTRACTION_RETRY_MULTIPLIER: float = Field(
        default=2.0,
        description="Multiplier for exponential backoff",
        env="EXTRACTION_RETRY_MULTIPLIER"
    )
    
    NEWSPAPER_LANGUAGE: str = Field(
        default="en",
        description="Language setting for newspaper4k",
        env="NEWSPAPER_LANGUAGE"
    )
    
    NEWSPAPER_KEEP_ARTICLE_HTML: bool = Field(
        default=True,
        description="Keep article HTML in newspaper4k",
        env="NEWSPAPER_KEEP_ARTICLE_HTML"
    )
    
    NEWSPAPER_FETCH_IMAGES: bool = Field(
        default=True,
        description="Enable image fetching in newspaper4k",
        env="NEWSPAPER_FETCH_IMAGES"
    )
    
    NEWSPAPER_HTTP_SUCCESS_ONLY: bool = Field(
        default=True,
        description="Only process successful HTTP responses in newspaper4k",
        env="NEWSPAPER_HTTP_SUCCESS_ONLY"
    )
    
    # Celery configuration
    CELERY_BROKER_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Celery message broker URL",
        env="CELERY_BROKER_URL"
    )
    
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://localhost:6379/0",
        description="Celery result backend URL", 
        env="CELERY_RESULT_BACKEND"
    )
    
    CELERY_TASK_SERIALIZER: str = Field(
        default="json",
        description="Celery task serialization format",
        env="CELERY_TASK_SERIALIZER"
    )
    
    CELERY_RESULT_SERIALIZER: str = Field(
        default="json",
        description="Celery result serialization format",
        env="CELERY_RESULT_SERIALIZER"
    )
    
    CELERY_ACCEPT_CONTENT: list = Field(
        default=["json"],
        description="Celery accepted content types",
        env="CELERY_ACCEPT_CONTENT"
    )
    
    CELERY_TIMEZONE: str = Field(
        default="UTC",
        description="Celery timezone setting",
        env="CELERY_TIMEZONE"
    )
    
    CELERY_ENABLE_UTC: bool = Field(
        default=True,
        description="Enable UTC in Celery",
        env="CELERY_ENABLE_UTC"
    )
    
    CELERY_WORKER_PREFETCH_MULTIPLIER: int = Field(
        default=1,
        description="Celery worker prefetch multiplier",
        env="CELERY_WORKER_PREFETCH_MULTIPLIER"
    )
    
    CELERY_TASK_TRACK_STARTED: bool = Field(
        default=True,
        description="Track when Celery tasks start",
        env="CELERY_TASK_TRACK_STARTED"
    )
    
    CELERY_TASK_REJECT_ON_WORKER_LOST: bool = Field(
        default=True,
        description="Reject tasks when worker is lost",
        env="CELERY_TASK_REJECT_ON_WORKER_LOST"
    )
    
    # Job scheduling settings
    JOB_EXECUTION_TIMEOUT: int = Field(
        default=1800,  # 30 minutes
        description="Maximum job execution time in seconds",
        env="JOB_EXECUTION_TIMEOUT"
    )
    
    MAX_CONCURRENT_JOBS: int = Field(
        default=10,
        description="Maximum number of concurrent crawl jobs",
        env="MAX_CONCURRENT_JOBS"
    )
    
    JOB_CLEANUP_DAYS: int = Field(
        default=30,
        description="Number of days to keep completed jobs",
        env="JOB_CLEANUP_DAYS"
    )
    
    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith(("postgresql://", "postgresql+asyncpg://")):
            raise ValueError("DATABASE_URL must start with postgresql:// or postgresql+asyncpg://")
        return v
    
    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}")
        return v.upper()
    
    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        valid_envs = ["development", "testing", "staging", "production"]
        if v.lower() not in valid_envs:
            raise ValueError(f"ENVIRONMENT must be one of {valid_envs}")
        return v.lower()
    
    @field_validator("EXTRACTION_TIMEOUT")
    @classmethod
    def validate_extraction_timeout(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("EXTRACTION_TIMEOUT must be positive")
        if v > 300:  # 5 minutes max
            raise ValueError("EXTRACTION_TIMEOUT must not exceed 300 seconds")
        return v
    
    @field_validator("EXTRACTION_MAX_RETRIES")
    @classmethod
    def validate_max_retries(cls, v: int) -> int:
        if v < 0:
            raise ValueError("EXTRACTION_MAX_RETRIES must be non-negative")
        if v > 10:
            raise ValueError("EXTRACTION_MAX_RETRIES must not exceed 10")
        return v
    
    @field_validator("EXTRACTION_RETRY_BASE_DELAY")
    @classmethod
    def validate_retry_base_delay(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("EXTRACTION_RETRY_BASE_DELAY must be positive")
        return v
    
    @field_validator("EXTRACTION_RETRY_MULTIPLIER")
    @classmethod
    def validate_retry_multiplier(cls, v: float) -> float:
        if v < 1.0:
            raise ValueError("EXTRACTION_RETRY_MULTIPLIER must be >= 1.0")
        return v
    
    @field_validator("NEWSPAPER_LANGUAGE")
    @classmethod
    def validate_language(cls, v: str) -> str:
        valid_languages = ["en", "es", "fr", "de", "it", "pt", "ru", "ja", "ko", "zh"]
        if v.lower() not in valid_languages:
            raise ValueError(f"NEWSPAPER_LANGUAGE must be one of {valid_languages}")
        return v.lower()
    
    @field_validator("CELERY_BROKER_URL", "CELERY_RESULT_BACKEND")
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        if not v.startswith("redis://"):
            raise ValueError("Celery broker and result backend URLs must start with redis://")
        return v
    
    @field_validator("CELERY_TASK_SERIALIZER", "CELERY_RESULT_SERIALIZER")
    @classmethod
    def validate_celery_serializer(cls, v: str) -> str:
        valid_serializers = ["json", "pickle", "yaml", "msgpack"]
        if v.lower() not in valid_serializers:
            raise ValueError(f"Celery serializer must be one of {valid_serializers}")
        return v.lower()
    
    @field_validator("JOB_EXECUTION_TIMEOUT")
    @classmethod
    def validate_job_timeout(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("JOB_EXECUTION_TIMEOUT must be positive")
        if v > 7200:  # 2 hours max
            raise ValueError("JOB_EXECUTION_TIMEOUT must not exceed 7200 seconds")
        return v
    
    @field_validator("MAX_CONCURRENT_JOBS")
    @classmethod
    def validate_max_concurrent_jobs(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("MAX_CONCURRENT_JOBS must be positive")
        if v > 50:
            raise ValueError("MAX_CONCURRENT_JOBS must not exceed 50")
        return v
    
    @field_validator("JOB_CLEANUP_DAYS")
    @classmethod
    def validate_cleanup_days(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("JOB_CLEANUP_DAYS must be positive")
        if v > 365:
            raise ValueError("JOB_CLEANUP_DAYS must not exceed 365 days")
        return v
    
    # Container-aware API configuration
    API_HOST: str = Field(
        default="0.0.0.0",
        description="API host binding address",
        env="API_HOST"
    )
    
    API_PORT: int = Field(
        default=8000,
        description="API port number",
        env="API_PORT"
    )
    
    # Container health check configuration
    HEALTH_CHECK_INTERVAL: str = Field(
        default="30s",
        description="Container health check interval",
        env="HEALTH_CHECK_INTERVAL"
    )
    
    HEALTH_CHECK_TIMEOUT: str = Field(
        default="10s",
        description="Container health check timeout",
        env="HEALTH_CHECK_TIMEOUT"
    )
    
    HEALTH_CHECK_RETRIES: int = Field(
        default=3,
        description="Container health check retry count",
        env="HEALTH_CHECK_RETRIES"
    )
    
    # Container resource configuration
    WEB_WORKERS: int = Field(
        default=1,
        description="Number of Uvicorn workers for production",
        env="WEB_WORKERS"
    )
    
    @field_validator("WEB_WORKERS")
    @classmethod
    def validate_web_workers(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("WEB_WORKERS must be positive")
        if v > 16:
            raise ValueError("WEB_WORKERS must not exceed 16")
        return v
    
    @field_validator("API_PORT")
    @classmethod
    def validate_api_port(cls, v: int) -> int:
        if v <= 0 or v > 65535:
            raise ValueError("API_PORT must be between 1 and 65535")
        return v

    model_config = {
        "env_file": _get_env_file(),
        "env_file_encoding": "utf-8",
        "case_sensitive": True
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()