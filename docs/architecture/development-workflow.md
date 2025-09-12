# Development Workflow

Define development setup và workflow cho fullstack application với Docker-based local environment.

## Local Development Setup

### Prerequisites

```bash
# Required software installations
# Docker & Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Docker Compose (if not included)
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Python 3.11+ (for local development)
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip

# Git (for version control)
sudo apt install git

# Optional: VS Code with extensions
# - Python extension
# - Docker extension  
# - PostgreSQL extension
```

### Initial Setup

```bash
# Clone repository
git clone <repository-url>
cd google-news-scraper

# Copy environment template
cp .env.example .env

# Edit environment variables
nano .env

# Build and start all services
docker-compose up --build -d

# Wait for services to be ready (check logs)
docker-compose logs -f

# Run database migrations
docker-compose exec app python -m alembic upgrade head

# Seed initial categories (optional)
docker-compose exec app python scripts/seed_categories.py

# Verify setup
curl http://localhost:8000/api/v1/health
```

### Development Commands

```bash
# Start all services
docker-compose up -d

# Start with logs visible
docker-compose up

# Start specific services
docker-compose up -d postgres redis

# Start backend only
docker-compose up -d app celery-worker celery-beat

# Start frontend only (when implemented)
docker-compose up -d web

# View logs
docker-compose logs -f app
docker-compose logs -f celery-worker

# Run tests
docker-compose exec app pytest

# Run tests with coverage
docker-compose exec app pytest --cov=src --cov-report=html

# Run specific test file
docker-compose exec app pytest tests/unit/test_crawler.py -v

# Access database
docker-compose exec postgres psql -U postgres -d news_scraper

# Access Redis CLI
docker-compose exec redis redis-cli

# Run migrations
docker-compose exec app alembic upgrade head

# Create new migration
docker-compose exec app alembic revision --autogenerate -m "description"

# Manual crawl test
docker-compose exec app python scripts/run_crawler.py --category-id <uuid>

# Check Celery workers
docker-compose exec celery-worker celery -A src.core.scheduler.celery_app inspect active

# Stop all services
docker-compose down

# Stop with volume cleanup
docker-compose down -v
```

## Environment Configuration

### Required Environment Variables

```bash
# Backend (.env)
DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/news_scraper
REDIS_URL=redis://redis:6379/0

# Celery configuration
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# API configuration (optional)
API_HOST=0.0.0.0
API_PORT=8000
API_KEY=your-secret-api-key

# Crawler settings
CRAWLER_RATE_LIMIT_PER_SECOND=2
CRAWLER_REQUEST_TIMEOUT=30
CRAWLER_MAX_RETRIES=3
CRAWLER_USER_AGENT="Google News Scraper Bot 1.0"

# newspaper4k settings
NEWSPAPER_BROWSER_USER_AGENT="Mozilla/5.0 (compatible; NewsBot/1.0)"
NEWSPAPER_REQUEST_TIMEOUT=10
NEWSPAPER_THREAD_TIMEOUT_SECONDS=15
NEWSPAPER_NUMBER_THREADS=10

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Shared
ENVIRONMENT=development
SECRET_KEY=your-super-secret-key-change-in-production
DEBUG=true
```

## Docker Compose Configuration

### Development Environment

```yaml
# docker-compose.yml - Development environment
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: news_scraper
      POSTGRES_USER: postgres  
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./docker/init-db.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379" 
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  app:
    build:
      context: .
      dockerfile: docker/Dockerfile
    ports:
      - "8000:8000"
    volumes:
      - .:/app
      - /app/.venv  # Exclude venv from bind mount
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/news_scraper
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/0
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload
    develop:
      watch:
        - action: sync
          path: ./src
          target: /app/src
        - action: rebuild
          path: requirements.txt

  celery-worker:
    build:
      context: .
      dockerfile: docker/Dockerfile
    volumes:
      - .:/app
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/news_scraper
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/0
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: celery -A src.core.scheduler.celery_app worker --loglevel=info --concurrency=2

  celery-beat:
    build:
      context: .
      dockerfile: docker/Dockerfile
    volumes:
      - .:/app
      - celery_beat_data:/app/celerybeat-schedule
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/news_scraper
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/0
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: celery -A src.core.scheduler.celery_app beat --loglevel=info

volumes:
  postgres_data:
  redis_data:
  celery_beat_data:
```

## Development Workflow Patterns

### Feature Development Workflow

```bash
# Create feature branch
git checkout -b feature/category-search-improvements

# Start development environment
docker-compose up -d

# Make changes, test locally
docker-compose exec app pytest tests/unit/test_categories.py

# Run integration tests
docker-compose exec app pytest tests/integration/

# Commit changes
git add .
git commit -m "feat: improve category OR search logic"

# Push and create PR
git push origin feature/category-search-improvements
```

### Database Changes Workflow

```bash
# Create migration after model changes
docker-compose exec app alembic revision --autogenerate -m "add category exclude_keywords"

# Review generated migration
# Edit if needed

# Apply migration
docker-compose exec app alembic upgrade head

# Test with fresh database
docker-compose down -v
docker-compose up -d postgres redis
docker-compose exec app alembic upgrade head
```

### Testing Workflow

```bash
# Run all tests
docker-compose exec app pytest

# Run with coverage
docker-compose exec app pytest --cov=src --cov-report=term-missing

# Run specific test categories
docker-compose exec app pytest tests/unit/ -v
docker-compose exec app pytest tests/integration/ -v

# Test crawler manually
docker-compose exec app python scripts/run_crawler.py --test

# Performance testing
docker-compose exec app python scripts/performance_test.py
```

## Development Tools Integration

### VS Code Configuration

```json
// .vscode/settings.json
{
    "python.defaultInterpreterPath": "./venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": false,
    "python.linting.flake8Enabled": true,
    "python.formatting.provider": "black",
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": ["tests/"],
    "docker.defaultRegistryPath": "localhost:5000",
    "files.exclude": {
        "**/__pycache__": true,
        "**/.pytest_cache": true,
        "**/celerybeat-schedule*": true
    }
}
```

### Git Hooks

```bash
#!/bin/sh
# .git/hooks/pre-commit
# Run tests before commit

echo "Running pre-commit checks..."

# Run linting
docker-compose exec app flake8 src/
if [ $? -ne 0 ]; then
    echo "Linting failed. Please fix issues before committing."
    exit 1
fi

# Run unit tests
docker-compose exec app pytest tests/unit/
if [ $? -ne 0 ]; then
    echo "Unit tests failed. Please fix issues before committing."
    exit 1
fi

echo "Pre-commit checks passed!"
```

## Debugging Setup

### Python Debugging

```python
# For debugging trong Docker containers
import debugpy

# Enable attach debugger
debugpy.listen(("0.0.0.0", 5678))
print("Waiting for debugger attach...")
debugpy.wait_for_client()
debugpy.breakpoint()
```

### Docker Debug Configuration

```yaml
# docker-compose.debug.yml
version: '3.8'
services:
  app:
    extends:
      file: docker-compose.yml
      service: app
    ports:
      - "8000:8000"
      - "5678:5678"  # Debug port
    command: python -m debugpy --listen 0.0.0.0:5678 --wait-for-client -m uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload
```

## Performance Monitoring

### Local Monitoring Commands

```bash
# Monitor resource usage
docker stats

# Monitor specific container
docker stats google-news-scraper-app-1

# Check container logs
docker-compose logs -f --tail=100 app

# Database query monitoring
docker-compose exec postgres psql -U postgres -d news_scraper -c "SELECT * FROM pg_stat_activity;"

# Redis monitoring
docker-compose exec redis redis-cli monitor
```

## Best Practices

### Development Guidelines

1. **Always use Docker:** Consistent environment across team
2. **Test before commit:** Pre-commit hooks prevent broken code
3. **Follow naming conventions:** Consistent với project standards
4. **Document changes:** Update relevant docs when making changes
5. **Use feature branches:** Never commit directly to main
6. **Clean up:** Remove unused code và imports regularly

### Docker Best Practices

1. **Use specific tags:** Avoid `latest` tags trong production
2. **Multi-stage builds:** Optimize image size
3. **Health checks:** Ensure services are ready before use
4. **Volume management:** Understand data persistence
5. **Resource limits:** Set appropriate CPU/memory limits
6. **Security:** Don't run containers as root