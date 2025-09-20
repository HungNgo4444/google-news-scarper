import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator, ConfigDict
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

    # JavaScript rendering settings for sync_playwright integration
    ENABLE_JAVASCRIPT_RENDERING: bool = Field(
        default=True,
        description="Enable JavaScript rendering using sync_playwright for articles that fail standard extraction",
        env="ENABLE_JAVASCRIPT_RENDERING"
    )

    PLAYWRIGHT_HEADLESS: bool = Field(
        default=True,
        description="Run Playwright browser in headless mode",
        env="PLAYWRIGHT_HEADLESS"
    )

    PLAYWRIGHT_TIMEOUT: int = Field(
        default=30,
        description="Timeout for Playwright page operations in seconds",
        env="PLAYWRIGHT_TIMEOUT"
    )

    PLAYWRIGHT_WAIT_TIME: float = Field(
        default=2.0,
        description="Time to wait for JavaScript to render in seconds",
        env="PLAYWRIGHT_WAIT_TIME"
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

    # Concurrency settings
    CRAWLER_CONCURRENCY_LIMIT: int = Field(
        default=10,
        description="Maximum concurrent extractions (increased from 5)",
        env="CRAWLER_CONCURRENCY_LIMIT"
    )

    # CloudScraper settings
    CLOUDSCRAPER_ENABLED: bool = Field(
        default=True,
        description="Enable CloudScraper for anti-bot protection",
        env="CLOUDSCRAPER_ENABLED"
    )

    CLOUDSCRAPER_DELAY: float = Field(
        default=1.0,
        description="Delay between CloudScraper requests in seconds",
        env="CLOUDSCRAPER_DELAY"
    )

    # Event loop settings
    CELERY_ASYNC_TIMEOUT: int = Field(
        default=300,
        description="Timeout for async operations in Celery tasks",
        env="CELERY_ASYNC_TIMEOUT"
    )

    ARTICLE_EXTRACTION_BATCH_SIZE: int = Field(
        default=10,
        description="Batch size for article extraction",
        env="ARTICLE_EXTRACTION_BATCH_SIZE"
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

    @field_validator("PLAYWRIGHT_TIMEOUT")
    @classmethod
    def validate_playwright_timeout(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("PLAYWRIGHT_TIMEOUT must be positive")
        if v > 120:  # 2 minutes max
            raise ValueError("PLAYWRIGHT_TIMEOUT must not exceed 120 seconds")
        return v

    @field_validator("PLAYWRIGHT_WAIT_TIME")
    @classmethod
    def validate_playwright_wait_time(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("PLAYWRIGHT_WAIT_TIME must be positive")
        if v > 10.0:  # 10 seconds max
            raise ValueError("PLAYWRIGHT_WAIT_TIME must not exceed 10 seconds")
        return v
    
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

    # PostgreSQL Container Configuration
    POSTGRES_DB: str = Field(
        default="google_news",
        description="PostgreSQL database name",
        env="POSTGRES_DB"
    )

    POSTGRES_USER: str = Field(
        default="postgres",
        description="PostgreSQL username",
        env="POSTGRES_USER"
    )

    POSTGRES_PASSWORD: str = Field(
        default="postgres",
        description="PostgreSQL password",
        env="POSTGRES_PASSWORD"
    )

    # PostgreSQL Performance Tuning
    POSTGRES_MAX_CONNECTIONS: int = Field(
        default=100,
        description="PostgreSQL max connections",
        env="POSTGRES_MAX_CONNECTIONS"
    )

    POSTGRES_SHARED_BUFFERS: str = Field(
        default="256MB",
        description="PostgreSQL shared buffers",
        env="POSTGRES_SHARED_BUFFERS"
    )

    POSTGRES_EFFECTIVE_CACHE_SIZE: str = Field(
        default="1GB",
        description="PostgreSQL effective cache size",
        env="POSTGRES_EFFECTIVE_CACHE_SIZE"
    )

    POSTGRES_MAINTENANCE_WORK_MEM: str = Field(
        default="64MB",
        description="PostgreSQL maintenance work memory",
        env="POSTGRES_MAINTENANCE_WORK_MEM"
    )

    POSTGRES_WORK_MEM: str = Field(
        default="4MB",
        description="PostgreSQL work memory",
        env="POSTGRES_WORK_MEM"
    )

    # Redis Configuration
    REDIS_MAX_MEMORY: str = Field(
        default="400mb",
        description="Redis max memory setting",
        env="REDIS_MAX_MEMORY"
    )

    # Container Data Paths
    POSTGRES_DATA_PATH: str = Field(
        default="./data/postgres",
        description="PostgreSQL data volume path",
        env="POSTGRES_DATA_PATH"
    )

    REDIS_DATA_PATH: str = Field(
        default="./data/redis",
        description="Redis data volume path",
        env="REDIS_DATA_PATH"
    )

    BEAT_DATA_PATH: str = Field(
        default="./data/beat",
        description="Celery beat data volume path",
        env="BEAT_DATA_PATH"
    )

    # SSL/TLS Configuration
    SSL_CERT_PATH: str = Field(
        default="/etc/nginx/ssl/cert.pem",
        description="SSL certificate path",
        env="SSL_CERT_PATH"
    )

    SSL_KEY_PATH: str = Field(
        default="/etc/nginx/ssl/key.pem",
        description="SSL private key path",
        env="SSL_KEY_PATH"
    )

    SSL_CA_CERT_PATH: str = Field(
        default="/etc/nginx/ssl/ca-cert.pem",
        description="SSL CA certificate path",
        env="SSL_CA_CERT_PATH"
    )

    SSL_DHPARAM_PATH: str = Field(
        default="/etc/nginx/ssl/dhparam.pem",
        description="SSL DH parameters path",
        env="SSL_DHPARAM_PATH"
    )

    # Secrets Management
    POSTGRES_PASSWORD_FILE: str = Field(
        default="./secrets/postgres_password.txt",
        description="PostgreSQL password file path",
        env="POSTGRES_PASSWORD_FILE"
    )

    REDIS_PASSWORD_FILE: str = Field(
        default="./secrets/redis_password.txt",
        description="Redis password file path",
        env="REDIS_PASSWORD_FILE"
    )

    # Monitoring
    FLOWER_USERNAME: str = Field(
        default="admin",
        description="Celery Flower admin username",
        env="FLOWER_USERNAME"
    )

    FLOWER_PASSWORD: str = Field(
        default="change_this_password",
        description="Celery Flower admin password",
        env="FLOWER_PASSWORD"
    )

    HEALTH_CHECK_START_PERIOD: str = Field(
        default="40s",
        description="Container health check start period",
        env="HEALTH_CHECK_START_PERIOD"
    )

    # Docker Compose Configuration
    COMPOSE_PROJECT_NAME: str = Field(
        default="google-news-scraper",
        description="Docker Compose project name",
        env="COMPOSE_PROJECT_NAME"
    )

    COMPOSE_FILE: str = Field(
        default="docker-compose.yml",
        description="Docker Compose file path",
        env="COMPOSE_FILE"
    )

    # Container Resource Limits
    WEB_CPU_LIMIT: str = Field(
        default="1.0",
        description="Web container CPU limit",
        env="WEB_CPU_LIMIT"
    )

    WEB_MEMORY_LIMIT: str = Field(
        default="512M",
        description="Web container memory limit",
        env="WEB_MEMORY_LIMIT"
    )

    WEB_CPU_RESERVATION: str = Field(
        default="0.5",
        description="Web container CPU reservation",
        env="WEB_CPU_RESERVATION"
    )

    WEB_MEMORY_RESERVATION: str = Field(
        default="256M",
        description="Web container memory reservation",
        env="WEB_MEMORY_RESERVATION"
    )

    WORKER_CPU_LIMIT: str = Field(
        default="2.0",
        description="Worker container CPU limit",
        env="WORKER_CPU_LIMIT"
    )

    WORKER_MEMORY_LIMIT: str = Field(
        default="1G",
        description="Worker container memory limit",
        env="WORKER_MEMORY_LIMIT"
    )

    WORKER_CPU_RESERVATION: str = Field(
        default="0.5",
        description="Worker container CPU reservation",
        env="WORKER_CPU_RESERVATION"
    )

    WORKER_MEMORY_RESERVATION: str = Field(
        default="512M",
        description="Worker container memory reservation",
        env="WORKER_MEMORY_RESERVATION"
    )

    POSTGRES_CPU_LIMIT: str = Field(
        default="2.0",
        description="PostgreSQL container CPU limit",
        env="POSTGRES_CPU_LIMIT"
    )

    POSTGRES_MEMORY_LIMIT: str = Field(
        default="2G",
        description="PostgreSQL container memory limit",
        env="POSTGRES_MEMORY_LIMIT"
    )

    POSTGRES_CPU_RESERVATION: str = Field(
        default="0.5",
        description="PostgreSQL container CPU reservation",
        env="POSTGRES_CPU_RESERVATION"
    )

    POSTGRES_MEMORY_RESERVATION: str = Field(
        default="1G",
        description="PostgreSQL container memory reservation",
        env="POSTGRES_MEMORY_RESERVATION"
    )

    REDIS_CPU_LIMIT: str = Field(
        default="1.0",
        description="Redis container CPU limit",
        env="REDIS_CPU_LIMIT"
    )

    REDIS_MEMORY_LIMIT: str = Field(
        default="512M",
        description="Redis container memory limit",
        env="REDIS_MEMORY_LIMIT"
    )

    REDIS_CPU_RESERVATION: str = Field(
        default="0.2",
        description="Redis container CPU reservation",
        env="REDIS_CPU_RESERVATION"
    )

    REDIS_MEMORY_RESERVATION: str = Field(
        default="256M",
        description="Redis container memory reservation",
        env="REDIS_MEMORY_RESERVATION"
    )

    # Development Settings
    DEV_RELOAD: bool = Field(
        default=True,
        description="Enable auto-reload in development",
        env="DEV_RELOAD"
    )

    DEV_DEBUG: bool = Field(
        default=True,
        description="Enable debug mode in development",
        env="DEV_DEBUG"
    )

    DEV_CORS_ORIGINS: str = Field(
        default='["http://localhost:3000", "http://localhost:8080"]',
        description="CORS origins for development",
        env="DEV_CORS_ORIGINS"
    )

    # Production Settings
    PROD_ALLOWED_HOSTS: str = Field(
        default='["your-domain.com", "www.your-domain.com"]',
        description="Allowed hosts for production",
        env="PROD_ALLOWED_HOSTS"
    )

    PROD_CORS_ORIGINS: str = Field(
        default='["https://your-domain.com"]',
        description="CORS origins for production",
        env="PROD_CORS_ORIGINS"
    )

    PROD_SECURE_SSL_REDIRECT: bool = Field(
        default=True,
        description="Force SSL redirect in production",
        env="PROD_SECURE_SSL_REDIRECT"
    )

    PROD_SESSION_COOKIE_SECURE: bool = Field(
        default=True,
        description="Secure session cookies in production",
        env="PROD_SESSION_COOKIE_SECURE"
    )

    PROD_CSRF_COOKIE_SECURE: bool = Field(
        default=True,
        description="Secure CSRF cookies in production",
        env="PROD_CSRF_COOKIE_SECURE"
    )

    # Logging Configuration
    LOG_FORMAT: str = Field(
        default="json",
        description="Log format (json/text)",
        env="LOG_FORMAT"
    )

    LOG_FILE_PATH: str = Field(
        default="./logs/app.log",
        description="Log file path",
        env="LOG_FILE_PATH"
    )

    LOG_MAX_FILE_SIZE: str = Field(
        default="50MB",
        description="Maximum log file size",
        env="LOG_MAX_FILE_SIZE"
    )

    LOG_BACKUP_COUNT: int = Field(
        default=10,
        description="Number of log backup files",
        env="LOG_BACKUP_COUNT"
    )

    LOG_ROTATION_INTERVAL: str = Field(
        default="daily",
        description="Log rotation interval",
        env="LOG_ROTATION_INTERVAL"
    )

    DATABASE_LOG_LEVEL: str = Field(
        default="WARNING",
        description="Database component log level",
        env="DATABASE_LOG_LEVEL"
    )

    CELERY_LOG_LEVEL: str = Field(
        default="INFO",
        description="Celery component log level",
        env="CELERY_LOG_LEVEL"
    )

    CRAWLER_LOG_LEVEL: str = Field(
        default="INFO",
        description="Crawler component log level",
        env="CRAWLER_LOG_LEVEL"
    )

    API_LOG_LEVEL: str = Field(
        default="INFO",
        description="API component log level",
        env="API_LOG_LEVEL"
    )

    # Backup Configuration
    BACKUP_ENABLED: bool = Field(
        default=True,
        description="Enable automated backups",
        env="BACKUP_ENABLED"
    )

    BACKUP_SCHEDULE: str = Field(
        default="0 2 * * *",
        description="Backup schedule (cron format)",
        env="BACKUP_SCHEDULE"
    )

    BACKUP_RETENTION_DAYS: int = Field(
        default=30,
        description="Backup retention period in days",
        env="BACKUP_RETENTION_DAYS"
    )

    BACKUP_POSTGRES_PATH: str = Field(
        default="./data/postgres_backup",
        description="PostgreSQL backup directory",
        env="BACKUP_POSTGRES_PATH"
    )

    BACKUP_REDIS_PATH: str = Field(
        default="./data/redis_backup",
        description="Redis backup directory",
        env="BACKUP_REDIS_PATH"
    )

    # Email Alerting
    SMTP_HOST: str = Field(
        default="smtp.gmail.com",
        description="SMTP server hostname",
        env="SMTP_HOST"
    )

    SMTP_PORT: int = Field(
        default=587,
        description="SMTP server port",
        env="SMTP_PORT"
    )

    SMTP_USE_TLS: bool = Field(
        default=True,
        description="Use TLS for SMTP connection",
        env="SMTP_USE_TLS"
    )

    SMTP_USERNAME: str = Field(
        default="alerts@your-domain.com",
        description="SMTP authentication username",
        env="SMTP_USERNAME"
    )

    SMTP_PASSWORD: str = Field(
        default="your_email_password",
        description="SMTP authentication password",
        env="SMTP_PASSWORD"
    )

    ALERT_FROM_EMAIL: str = Field(
        default="alerts@your-domain.com",
        description="Alert sender email address",
        env="ALERT_FROM_EMAIL"
    )

    ALERT_TO_EMAIL: str = Field(
        default="admin@your-domain.com",
        description="Alert recipient email address",
        env="ALERT_TO_EMAIL"
    )

    # Webhook Alerting
    WEBHOOK_URL: str = Field(
        default="https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK",
        description="Webhook URL for alerts",
        env="WEBHOOK_URL"
    )

    WEBHOOK_ENABLED: bool = Field(
        default=False,
        description="Enable webhook alerts",
        env="WEBHOOK_ENABLED"
    )

    # Performance Configuration
    WEB_WORKER_CONNECTIONS: int = Field(
        default=1000,
        description="Maximum worker connections",
        env="WEB_WORKER_CONNECTIONS"
    )

    WEB_WORKER_CLASS: str = Field(
        default="uvicorn.workers.UvicornWorker",
        description="Web worker class",
        env="WEB_WORKER_CLASS"
    )

    CELERY_WORKER_CONCURRENCY: int = Field(
        default=4,
        description="Celery worker concurrency",
        env="CELERY_WORKER_CONCURRENCY"
    )

    CELERY_WORKER_MAX_TASKS_PER_CHILD: int = Field(
        default=1000,
        description="Max tasks per Celery worker child",
        env="CELERY_WORKER_MAX_TASKS_PER_CHILD"
    )

    CELERY_WORKER_DISABLE_RATE_LIMITS: bool = Field(
        default=False,
        description="Disable Celery worker rate limits",
        env="CELERY_WORKER_DISABLE_RATE_LIMITS"
    )

    # Feature Flags
    ENABLE_API_DOCS: bool = Field(
        default=True,
        description="Enable API documentation",
        env="ENABLE_API_DOCS"
    )

    ENABLE_FLOWER_MONITORING: bool = Field(
        default=True,
        description="Enable Celery Flower monitoring",
        env="ENABLE_FLOWER_MONITORING"
    )

    ENABLE_NGINX_PROXY: bool = Field(
        default=True,
        description="Enable Nginx reverse proxy",
        env="ENABLE_NGINX_PROXY"
    )

    ENABLE_SSL_TERMINATION: bool = Field(
        default=False,
        description="Enable SSL termination",
        env="ENABLE_SSL_TERMINATION"
    )

    ENABLE_LOG_AGGREGATION: bool = Field(
        default=False,
        description="Enable log aggregation",
        env="ENABLE_LOG_AGGREGATION"
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

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow"
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()