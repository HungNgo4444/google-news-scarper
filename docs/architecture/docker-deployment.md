# Google News Scraper - Docker Deployment Architecture

## Overview

This document provides comprehensive Docker containerization strategy for the Google News Scraper system, a production-ready Python application built with FastAPI, Celery, PostgreSQL, and Redis.

## 🚨 CRITICAL FIXES APPLIED

**This document has been updated to address critical production issues:**

1. **✅ Database Migration Timing Fixed** - Added migration service to run before web/worker services start
2. **✅ Celery Beat Persistence Fixed** - Added volume mounting for schedule state persistence  
3. **✅ Security Hardened** - Replaced hardcoded passwords with Docker secrets
4. **✅ Resource Limits Added** - Proper CPU and memory constraints for production
5. **✅ Health Checks Enhanced** - Application-specific health validation

**Implementation Priority: Address all fixes before production deployment!**

## System Architecture

### Current Application Stack
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI Web   │    │  Celery Worker  │    │  Celery Beat    │
│   (Port 8000)   │    │  (Background)   │    │  (Scheduler)    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │     Redis       │    │    Volume       │
│   (Port 5432)   │    │   (Port 6379)   │    │   (Storage)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Application Components Analysis

#### 1. Web API Service (FastAPI)
- **Entry Point:** `src/api/main.py` (MISSING - needs creation)
- **Routes:** Complete CRUD operations for categories
- **Dependencies:** FastAPI, Pydantic, SQLAlchemy async
- **Health Checks:** Built-in health endpoint capability
- **Port:** 8000

#### 2. Background Worker Service (Celery)
- **Entry Point:** `src/core/scheduler/celery_app.py`
- **Tasks:** Category crawling, maintenance, monitoring
- **Queues:** default, crawl_queue, maintenance_queue  
- **Dependencies:** Celery, Redis, newspaper4k
- **Scaling:** Horizontal scaling ready

#### 3. Scheduler Service (Celery Beat)
- **Entry Point:** Same as worker with beat mode
- **Schedule:** Cleanup (hourly), monitoring (5min)
- **Persistence:** Redis backend for schedule state
- **High Availability:** Single instance required

#### 4. Database (PostgreSQL)
- **Current Schema:** Articles, Categories, CrawlJobs, ArticleCategories
- **Migration System:** Alembic configured in `src/database/migrations/`
- **Connection:** Async with connection pooling
- **Persistence:** Required for all data

#### 5. Message Broker (Redis)
- **Usage:** Celery broker + result backend
- **Persistence:** Memory + optional disk persistence
- **Configuration:** Clustering support available
- **Monitoring:** Built-in health checks

## Docker Architecture Design

### Multi-Stage Build Strategy

```dockerfile
FROM python:3.11-slim as base
# Base image with common dependencies

FROM base as dependencies
# Install and cache Python dependencies

FROM base as production
# Final production image with minimal footprint
```

### Service Architecture

#### 0. Migration Service (`migration`) - **CRITICAL FIX**
```yaml
migration:
  build: 
    context: .
    target: production
  command: alembic upgrade head
  environment:
    - DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/google_news
  depends_on:
    postgres:
      condition: service_healthy
  restart: "no"  # Run once and exit
```

#### 1. Web Service (`web`)
```yaml
web:
  build: 
    context: .
    target: production
  command: uvicorn src.api.main:app --host 0.0.0.0 --port 8000
  ports:
    - "8000:8000"
  environment:
    - DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/google_news
    - CELERY_BROKER_URL=redis://redis:6379/0
    - CELERY_RESULT_BACKEND=redis://redis:6379/0
  depends_on:
    migration:
      condition: service_completed_successfully
    redis:
      condition: service_healthy
  healthcheck:
    test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8000/health').raise_for_status()"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 40s
```

#### 2. Worker Service (`worker`)
```yaml
worker:
  build:
    context: .
    target: production  
  command: celery -A src.core.scheduler.celery_app worker --loglevel=info --concurrency=4
  environment:
    - DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/google_news
    - CELERY_BROKER_URL=redis://redis:6379/0
    - CELERY_RESULT_BACKEND=redis://redis:6379/0
  depends_on:
    migration:
      condition: service_completed_successfully
    redis:
      condition: service_healthy
  healthcheck:
    test: ["CMD", "celery", "-A", "src.core.scheduler.celery_app", "inspect", "ping", "-d", "celery@$$(hostname)"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 40s
  deploy:
    resources:
      limits:
        cpus: '1.0'
        memory: 1G
      reservations:
        cpus: '0.5'
        memory: 512M
    replicas: 2  # Horizontal scaling
```

#### 3. Scheduler Service (`beat`) - **CRITICAL FIX**
```yaml
beat:
  build:
    context: .
    target: production
  command: celery -A src.core.scheduler.celery_app beat --loglevel=info --schedule=/app/celerybeat-schedule
  environment:
    - DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/google_news
    - CELERY_BROKER_URL=redis://redis:6379/0
    - CELERY_RESULT_BACKEND=redis://redis:6379/0
    - CELERY_BEAT_SCHEDULE_FILENAME=/app/celerybeat-schedule
  volumes:
    - beat_data:/app  # Persist schedule state
  depends_on:
    migration:
      condition: service_completed_successfully
    redis:
      condition: service_healthy
  deploy:
    resources:
      limits:
        cpus: '0.5'
        memory: 256M
    replicas: 1  # Single instance only
```

#### 4. Database Service (`postgres`)
```yaml
postgres:
  image: postgres:15-alpine
  environment:
    POSTGRES_DB: google_news
    POSTGRES_USER: postgres
    POSTGRES_PASSWORD: password
  ports:
    - "5432:5432"
  volumes:
    - postgres_data:/var/lib/postgresql/data
    - ./scripts/init-db.sql:/docker-entrypoint-initdb.d/init-db.sql
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U postgres"]
    interval: 10s
    timeout: 5s
    retries: 5
```

#### 5. Redis Service (`redis`)
```yaml
redis:
  image: redis:7-alpine
  ports:
    - "6379:6379"
  volumes:
    - redis_data:/data
  command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 10s
    timeout: 3s
    retries: 3
```

### Volume Strategy - **UPDATED WITH CRITICAL FIXES**

```yaml
volumes:
  postgres_data:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: ./data/postgres  # Production: use dedicated storage
  redis_data:
    driver: local
    driver_opts:
      type: none  
      o: bind
      device: ./data/redis
  beat_data:  # CRITICAL FIX: Beat scheduler persistence
    driver: local
    driver_opts:
      type: none
      o: bind 
      device: ./data/beat
  logs:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: ./logs
```

### Network Architecture

```yaml
networks:
  default:
    driver: bridge
    name: google_news_network
```

## Environment Configuration

### Development Environment (`.env.development`)
```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/google_news
DATABASE_POOL_SIZE=10
DATABASE_ECHO=true

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Application
ENVIRONMENT=development
LOG_LEVEL=DEBUG
```

### Production Environment (`.env.production`)
```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:${POSTGRES_PASSWORD}@postgres:5432/google_news
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30
DATABASE_ECHO=false

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
CELERY_WORKER_PREFETCH_MULTIPLIER=1

# Application  
ENVIRONMENT=production
LOG_LEVEL=INFO

# Security
SECRET_KEY=${SECRET_KEY}
```

## Missing Components Analysis

### Critical Missing Files

#### 1. FastAPI Main Application (`src/api/main.py`)
**Status:** MISSING - Must create
**Requirements:**
- FastAPI app initialization
- Router registration for categories
- CORS configuration
- Health check endpoint
- Exception handlers
- Startup/shutdown events

#### 2. Application Entry Points
**Status:** MISSING - Must create
- `src/api/main.py` - FastAPI application
- `docker-compose.yml` - Service orchestration
- `Dockerfile` - Container definition
- Environment files for different stages

#### 3. Database Initialization
**Status:** PARTIAL - Needs enhancement
- Alembic is configured but needs production optimizations
- Need database initialization scripts
- Health check integration required

### Optional Enhancements

#### 1. Monitoring Stack
```yaml
prometheus:
  image: prom/prometheus
  ports:
    - "9090:9090"
    
grafana:
  image: grafana/grafana
  ports:
    - "3000:3000"
```

#### 2. Nginx Reverse Proxy
```yaml
nginx:
  image: nginx:alpine
  ports:
    - "80:80"
  volumes:
    - ./nginx.conf:/etc/nginx/nginx.conf
  depends_on:
    - web
```

## Deployment Strategies

### 1. Development Deployment
```bash
# Quick start for development
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build

# With database initialization
docker-compose up postgres redis
sleep 10
docker-compose exec web alembic upgrade head
docker-compose up
```

### 2. Production Deployment  
```bash
# Production with proper sequencing
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d postgres redis
docker-compose exec postgres pg_isready
docker-compose up -d web worker beat

# Health check validation
docker-compose exec web curl -f http://localhost:8000/health
```

### 3. Scaling Strategy
```bash
# Scale workers horizontally
docker-compose up --scale worker=4

# Scale with resource limits
docker-compose --compatibility up --scale worker=4
```

## Performance Optimization

### Container Resource Limits
```yaml
services:
  web:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
        reservations:
          cpus: '0.5'  
          memory: 256M
          
  worker:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
```

### Database Optimization
```yaml
postgres:
  command: |
    postgres -c max_connections=100
             -c shared_buffers=256MB
             -c effective_cache_size=1GB
             -c work_mem=4MB
```

### Redis Optimization
```yaml
redis:
  command: |
    redis-server --maxmemory 512mb
                 --maxmemory-policy allkeys-lru
                 --save 900 1
                 --appendonly yes
```

## Security Considerations

### Container Security
- Non-root user execution
- Read-only root filesystem where possible
- Minimal base images (alpine)
- Regular security updates

### Network Security
```yaml
networks:
  frontend:
    driver: bridge
    internal: false
  backend:
    driver: bridge  
    internal: true
```

### Secrets Management - **CRITICAL SECURITY FIX**
```yaml
secrets:
  postgres_password:
    file: ./secrets/postgres_password.txt
  secret_key:
    file: ./secrets/secret_key.txt

# Updated Database service with secrets
postgres:
  image: postgres:15-alpine
  environment:
    POSTGRES_DB: google_news
    POSTGRES_USER: postgres
    POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password  # FIXED: No hardcoded password
  secrets:
    - postgres_password
  volumes:
    - postgres_data:/var/lib/postgresql/data
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U postgres"]

# Updated Web service with secrets  
web:
  environment:
    - DATABASE_URL=postgresql+asyncpg://postgres:@postgres:5432/google_news  # Password from secret
    - SECRET_KEY_FILE=/run/secrets/secret_key
  secrets:
    - postgres_password  
    - secret_key
```

**Security Implementation Checklist:**
- [ ] Create `./secrets/postgres_password.txt` with strong password
- [ ] Create `./secrets/secret_key.txt` with random secret key
- [ ] Set proper file permissions: `chmod 600 ./secrets/*`
- [ ] Never commit secrets to version control
- [ ] Use different secrets for each environment

## Monitoring and Logging

### Health Checks
All services include comprehensive health checks with:
- Startup period for initialization
- Appropriate intervals for monitoring
- Retry logic for temporary failures

### Logging Strategy
```yaml
services:
  web:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### Metrics Collection
- Application metrics via FastAPI metrics endpoint
- Celery metrics via flower or custom collectors
- Database metrics via PostgreSQL exporter
- Redis metrics via Redis exporter

## Backup and Recovery

### Database Backup
```bash
# Automated backup script
docker-compose exec postgres pg_dump -U postgres google_news > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Volume Backup
```bash
# Backup persistent volumes
docker run --rm -v google_news_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_backup.tar.gz -C /data .
```

## Troubleshooting

### Common Issues

#### 1. Database Connection Issues
```bash
# Check database connectivity
docker-compose exec web python -c "from src.database.connection import get_engine; import asyncio; asyncio.run(get_engine().connect())"
```

#### 2. Celery Worker Issues
```bash
# Check worker status
docker-compose exec worker celery -A src.core.scheduler.celery_app inspect ping
docker-compose exec worker celery -A src.core.scheduler.celery_app inspect stats
```

#### 3. Redis Connectivity
```bash
# Test Redis connection
docker-compose exec redis redis-cli ping
docker-compose exec web python -c "import redis; r=redis.Redis(host='redis', port=6379); print(r.ping())"
```

### Debug Mode
```yaml
# docker-compose.debug.yml
services:
  web:
    command: uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload --log-level debug
    volumes:
      - .:/app
    environment:
      - LOG_LEVEL=DEBUG
      - DATABASE_ECHO=true
```

## Implementation Checklist

### Phase 1: Core Setup
- [ ] Create `src/api/main.py` FastAPI application
- [ ] Create `Dockerfile` with multi-stage build
- [ ] Create `docker-compose.yml` base configuration
- [ ] Create environment configuration files
- [ ] Test basic service connectivity

### Phase 2: Database Integration
- [ ] Create database initialization scripts
- [ ] Test Alembic migrations in containers
- [ ] Verify connection pooling configuration
- [ ] Test backup/restore procedures

### Phase 3: Application Services
- [ ] Test FastAPI health checks
- [ ] Verify Celery worker functionality
- [ ] Test Celery Beat scheduling
- [ ] Validate cross-service communication

### Phase 4: Production Readiness
- [ ] Configure resource limits
- [ ] Set up monitoring and logging
- [ ] Implement secrets management
- [ ] Test scaling scenarios
- [ ] Create deployment documentation

### Phase 5: Security and Monitoring
- [ ] Security scanning of images
- [ ] Set up monitoring stack
- [ ] Configure alerting
- [ ] Create runbook documentation

## Next Steps

1. **Immediate Actions:**
   - Create missing FastAPI main.py
   - Build Docker configuration files
   - Test local development setup

2. **Short-term Goals:**
   - Production environment configuration
   - Monitoring integration
   - Security hardening

3. **Long-term Enhancements:**
   - Kubernetes deployment option
   - CI/CD pipeline integration
   - Advanced monitoring and alerting

---

*This document provides the foundation for containerizing the Google News Scraper system. The architecture is designed for production use with proper scaling, monitoring, and maintenance capabilities.*