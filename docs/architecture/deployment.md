# Deployment Architecture

## Overview

The Google News Scraper deployment architecture is designed for flexibility, supporting local development, staging, and production environments using Docker containers. The architecture emphasizes reliability, scalability, and maintainability while supporting the job-centric enhancement requirements.

## Deployment Strategy

### Multi-Environment Approach

#### Development Environment
- **Platform:** Docker Compose on local machine
- **Frontend:** Vite dev server with hot reload
- **Backend:** FastAPI with auto-reload
- **Database:** PostgreSQL in container with volume persistence
- **Task Queue:** Redis + Celery with Flower monitoring

#### Staging Environment
- **Platform:** Cloud VPS or Container Service
- **Frontend:** Static build served by Nginx
- **Backend:** FastAPI with Gunicorn/Uvicorn workers
- **Database:** Managed PostgreSQL or containerized with backups
- **Task Queue:** Redis cluster with Celery workers

#### Production Environment
- **Platform:** Cloud infrastructure (AWS/Azure/GCP) or dedicated servers
- **Frontend:** CDN-served static assets with edge caching
- **Backend:** Load-balanced FastAPI instances
- **Database:** Managed database service with read replicas
- **Task Queue:** Redis cluster with auto-scaling worker nodes

## Container Architecture

### Docker Compose Configuration

#### Development (docker-compose.yml)

```yaml
version: '3.8'

services:
  # Database Services
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: google_news
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_INITDB_ARGS: --encoding=UTF-8 --lc-collate=en_US.UTF-8 --lc-ctype=en_US.UTF-8
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./data/postgres:/var/lib/postgresql/data_backup
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d google_news"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    restart: unless-stopped
    command: >
      postgres
      -c max_connections=100
      -c shared_buffers=128MB
      -c effective_cache_size=512MB
      -c maintenance_work_mem=64MB
      -c checkpoint_completion_target=0.9
      -c wal_buffers=16MB
      -c default_statistics_target=100
      -c random_page_cost=1.1
      -c effective_io_concurrency=200
      -c work_mem=4MB

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5
    restart: unless-stopped
    command: >
      redis-server
      --maxmemory 200mb
      --maxmemory-policy allkeys-lru
      --save 900 1
      --save 300 10
      --save 60 10000
      --appendonly yes

  # Application Services
  backend:
    build:
      context: .
      dockerfile: docker/Dockerfile.backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/google_news
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
      - ENVIRONMENT=development
      - LOG_LEVEL=DEBUG
      - CORS_ORIGINS=http://localhost:3000,http://frontend:3000
    volumes:
      - ./src:/app/src:ro
      - ./logs:/app/logs
      - ./data/uploads:/app/data/uploads
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    restart: unless-stopped

  frontend:
    build:
      context: .
      dockerfile: docker/Dockerfile.frontend
    ports:
      - "3000:3000"
    environment:
      - VITE_API_BASE_URL=http://backend:8000/api/v1
      - VITE_WS_URL=ws://backend:8000/ws
      - VITE_ENVIRONMENT=development
    volumes:
      - ./frontend/src:/app/src:ro
      - ./frontend/public:/app/public:ro
    depends_on:
      backend:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  # Task Processing
  celery-worker:
    build:
      context: .
      dockerfile: docker/Dockerfile.backend
    command: >
      celery -A src.core.scheduler.celery_app worker
      --loglevel=info
      --concurrency=2
      --queues=priority,default,scheduled
      --max-tasks-per-child=50
      --prefetch-multiplier=1
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/google_news
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
      - ENVIRONMENT=development
      - LOG_LEVEL=DEBUG
      - C_FORCE_ROOT=1
    volumes:
      - ./src:/app/src:ro
      - ./logs:/app/logs
      - ./data/crawler:/app/data/crawler
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      backend:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "celery", "-A", "src.core.scheduler.celery_app", "inspect", "ping"]
      interval: 60s
      timeout: 15s
      retries: 3
      start_period: 60s
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 512M
        reservations:
          memory: 256M

  celery-beat:
    build:
      context: .
      dockerfile: docker/Dockerfile.backend
    command: >
      celery -A src.core.scheduler.celery_app beat
      --loglevel=info
      --schedule=/app/data/beat/celerybeat-schedule
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/google_news
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
      - ENVIRONMENT=development
      - LOG_LEVEL=DEBUG
      - C_FORCE_ROOT=1
    volumes:
      - ./src:/app/src:ro
      - ./logs:/app/logs
      - beat_data:/app/data/beat
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    deploy:
      resources:
        limits:
          memory: 256M

  # Monitoring (Optional)
  flower:
    build:
      context: .
      dockerfile: docker/Dockerfile.backend
    command: >
      celery -A src.core.scheduler.celery_app flower
      --port=5555
      --address=0.0.0.0
      --basic_auth=admin:password
    ports:
      - "5555:5555"
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - CELERY_RESULT_BACKEND=redis://redis:6379/1
    depends_on:
      - redis
      - celery-worker
    restart: unless-stopped
    profiles:
      - monitoring

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./docker/nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./docker/nginx/ssl:/etc/nginx/ssl:ro
      - ./logs/nginx:/var/log/nginx
    depends_on:
      - backend
      - frontend
    restart: unless-stopped
    profiles:
      - with-proxy

volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local
  beat_data:
    driver: local

networks:
  default:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

#### Production (docker-compose.prod.yml)

```yaml
version: '3.8'

services:
  backend:
    build:
      context: .
      dockerfile: docker/Dockerfile.backend
      target: production
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - CELERY_BROKER_URL=${CELERY_BROKER_URL}
      - CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND}
      - JWT_SECRET_KEY=${JWT_SECRET_KEY}
      - ENVIRONMENT=production
      - LOG_LEVEL=INFO
      - CORS_ORIGINS=${CORS_ORIGINS}
    command: >
      gunicorn src.api.main:app
      -w 4
      -k uvicorn.workers.UvicornWorker
      --bind 0.0.0.0:8000
      --access-logfile -
      --error-logfile -
      --log-level info
    deploy:
      replicas: 2
      resources:
        limits:
          memory: 1G
          cpus: '1.0'
        reservations:
          memory: 512M
          cpus: '0.5'
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
        window: 120s
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  frontend:
    build:
      context: .
      dockerfile: docker/Dockerfile.frontend
      target: production
    environment:
      - VITE_API_BASE_URL=${FRONTEND_API_URL}
      - VITE_ENVIRONMENT=production
    deploy:
      replicas: 2
      resources:
        limits:
          memory: 256M
          cpus: '0.5'
        reservations:
          memory: 128M
          cpus: '0.25'

  celery-worker:
    build:
      context: .
      dockerfile: docker/Dockerfile.backend
      target: production
    command: >
      celery -A src.core.scheduler.celery_app worker
      --loglevel=info
      --concurrency=4
      --queues=priority,default,scheduled
      --max-tasks-per-child=100
      --prefetch-multiplier=1
      --optimization=fair
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - CELERY_BROKER_URL=${CELERY_BROKER_URL}
      - CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND}
      - ENVIRONMENT=production
      - LOG_LEVEL=INFO
    deploy:
      replicas: 3
      resources:
        limits:
          memory: 1G
          cpus: '1.0'
        reservations:
          memory: 512M
          cpus: '0.5'
      restart_policy:
        condition: on-failure
        delay: 10s
        max_attempts: 3
        window: 300s

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./docker/nginx/prod.conf:/etc/nginx/nginx.conf:ro
      - ./docker/nginx/ssl:/etc/nginx/ssl:ro
      - /var/log/nginx:/var/log/nginx
    depends_on:
      - backend
      - frontend
    deploy:
      resources:
        limits:
          memory: 256M
          cpus: '0.5'
    restart: unless-stopped
```

## Dockerfile Configurations

### Backend Dockerfile

```dockerfile
# docker/Dockerfile.backend
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN groupadd -r app && useradd -r -g app app

# Set work directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Development target
FROM base as development

# Install development dependencies
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

# Copy source code
COPY --chown=app:app . .

# Switch to app user
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Production target
FROM base as production

# Copy source code
COPY --chown=app:app . .

# Install production dependencies only
RUN pip install --no-cache-dir gunicorn[gthread]

# Switch to app user
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Production command
CMD ["gunicorn", "src.api.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
```

### Frontend Dockerfile

```dockerfile
# docker/Dockerfile.frontend
FROM node:18-alpine as base

# Set working directory
WORKDIR /app

# Copy package files
COPY frontend/package*.json ./

# Development target
FROM base as development

# Install dependencies
RUN npm ci

# Copy source code
COPY frontend/ .

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:3000/health || exit 1

# Development command
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# Build target
FROM base as build

# Install dependencies
RUN npm ci

# Copy source code
COPY frontend/ .

# Build application
RUN npm run build

# Production target
FROM nginx:alpine as production

# Copy built files
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY docker/nginx/frontend.conf /etc/nginx/conf.d/default.conf

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost/health || exit 1

# Expose port
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
```

## CI/CD Pipeline

### GitHub Actions Workflow

```yaml
# .github/workflows/ci-cd.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  # Test jobs
  test-backend:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_db
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Run database migrations
        run: alembic upgrade head
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/test_db

      - name: Run backend tests
        run: |
          pytest src/tests/ -v --cov=src --cov-report=xml
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/test_db
          CELERY_BROKER_URL: redis://localhost:6379/0
          CELERY_RESULT_BACKEND: redis://localhost:6379/1

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml

  test-frontend:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '18'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        run: cd frontend && npm ci

      - name: Run linting
        run: cd frontend && npm run lint

      - name: Run type checking
        run: cd frontend && npm run type-check

      - name: Run frontend tests
        run: cd frontend && npm test -- --coverage

      - name: Build frontend
        run: cd frontend && npm run build

      - name: Upload build artifacts
        uses: actions/upload-artifact@v3
        with:
          name: frontend-build
          path: frontend/dist/

  # Build and push Docker images
  build-images:
    needs: [test-backend, test-frontend]
    runs-on: ubuntu-latest
    if: github.event_name == 'push'

    permissions:
      contents: read
      packages: write

    strategy:
      matrix:
        component: [backend, frontend]

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Log in to Container Registry
        uses: docker/login-action@v2
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v4
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}-${{ matrix.component }}
          tags: |
            type=ref,event=branch
            type=ref,event=pr
            type=sha,prefix={{branch}}-
            type=raw,value=latest,enable={{is_default_branch}}

      - name: Build and push Docker image
        uses: docker/build-push-action@v4
        with:
          context: .
          file: docker/Dockerfile.${{ matrix.component }}
          target: production
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  # Deploy to staging
  deploy-staging:
    needs: [build-images]
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/develop'

    environment:
      name: staging
      url: https://staging.yourapp.com

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Deploy to staging
        run: |
          echo "Deploying to staging environment..."
          # Add staging deployment commands here
          # Example: kubectl apply, docker-compose up, etc.

  # Deploy to production
  deploy-production:
    needs: [build-images]
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'

    environment:
      name: production
      url: https://yourapp.com

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Deploy to production
        run: |
          echo "Deploying to production environment..."
          # Add production deployment commands here

  # Security scanning
  security-scan:
    runs-on: ubuntu-latest
    needs: [build-images]

    steps:
      - name: Run Trivy vulnerability scanner
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}-backend:latest
          format: 'sarif'
          output: 'trivy-results.sarif'

      - name: Upload Trivy scan results
        uses: github/codeql-action/upload-sarif@v2
        with:
          sarif_file: 'trivy-results.sarif'
```

## Environment Configuration

### Environment Variables Management

#### Development (.env.example)

```bash
# Database Configuration
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/google_news
POSTGRES_DB=google_news
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# Redis Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
REDIS_URL=redis://localhost:6379

# Application Configuration
ENVIRONMENT=development
LOG_LEVEL=DEBUG
SECRET_KEY=your-secret-key-change-in-production
JWT_SECRET_KEY=your-jwt-secret-key
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

# CORS Configuration
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
DEV_CORS_ORIGINS=["http://localhost:3000","http://localhost:3001"]

# External APIs
GOOGLE_NEWS_API_KEY=your-google-news-api-key
NEWS_API_KEY=your-news-api-key

# File Storage
UPLOAD_DIRECTORY=./data/uploads
MAX_UPLOAD_SIZE=10485760  # 10MB

# Monitoring
SENTRY_DSN=your-sentry-dsn-optional
ENABLE_METRICS=true

# Frontend Configuration
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/ws
VITE_ENVIRONMENT=development
```

#### Production Environment Variables

```bash
# Production configuration with secrets management
DATABASE_URL=${DATABASE_URL_SECRET}
CELERY_BROKER_URL=${REDIS_CLUSTER_URL}
CELERY_RESULT_BACKEND=${REDIS_CLUSTER_URL}/1

ENVIRONMENT=production
LOG_LEVEL=INFO
SECRET_KEY=${SECRET_KEY_SECRET}
JWT_SECRET_KEY=${JWT_SECRET_SECRET}

CORS_ORIGINS=${PRODUCTION_DOMAINS}

# External service URLs
GOOGLE_NEWS_API_KEY=${GOOGLE_NEWS_API_SECRET}

# CDN and Storage
STATIC_URL=${CDN_BASE_URL}
MEDIA_URL=${S3_BUCKET_URL}

# Monitoring
SENTRY_DSN=${SENTRY_DSN_SECRET}
NEW_RELIC_LICENSE_KEY=${NEW_RELIC_SECRET}

# Frontend production URLs
VITE_API_BASE_URL=${PRODUCTION_API_URL}
VITE_WS_URL=${PRODUCTION_WS_URL}
VITE_ENVIRONMENT=production
```

## Infrastructure Scaling

### Horizontal Scaling Configuration

#### Docker Swarm (Simple Scaling)

```yaml
# docker-compose.swarm.yml
version: '3.8'

services:
  backend:
    deploy:
      replicas: 3
      update_config:
        parallelism: 1
        delay: 10s
        failure_action: rollback
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
        window: 120s
      placement:
        constraints:
          - node.role == worker
      resources:
        limits:
          memory: 1G
          cpus: '1.0'
        reservations:
          memory: 512M
          cpus: '0.5'

  celery-worker:
    deploy:
      replicas: 5
      update_config:
        parallelism: 2
        delay: 30s
      restart_policy:
        condition: on-failure
        delay: 10s
        max_attempts: 3
        window: 300s
      placement:
        constraints:
          - node.labels.worker_type == cpu-intensive
      resources:
        limits:
          memory: 2G
          cpus: '2.0'
        reservations:
          memory: 1G
          cpus: '1.0'

  nginx:
    deploy:
      replicas: 2
      placement:
        constraints:
          - node.role == manager
      resources:
        limits:
          memory: 256M
          cpus: '0.5'
```

#### Kubernetes (Advanced Scaling)

```yaml
# k8s/backend-deployment.yml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: google-news-scraper-backend
  labels:
    app: google-news-scraper
    component: backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: google-news-scraper
      component: backend
  template:
    metadata:
      labels:
        app: google-news-scraper
        component: backend
    spec:
      containers:
      - name: backend
        image: ghcr.io/yourorg/google-news-scraper-backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: database-url
        - name: CELERY_BROKER_URL
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: redis-url
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5

---
apiVersion: v1
kind: Service
metadata:
  name: backend-service
spec:
  selector:
    app: google-news-scraper
    component: backend
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP

---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: backend-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: google-news-scraper-backend
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

## Monitoring and Logging

### Logging Configuration

```yaml
# docker/logging/docker-compose.logging.yml
version: '3.8'

services:
  # Centralized logging with ELK stack
  elasticsearch:
    image: elasticsearch:8.8.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
    ports:
      - "9200:9200"
    volumes:
      - elasticsearch_data:/usr/share/elasticsearch/data

  logstash:
    image: logstash:8.8.0
    ports:
      - "5000:5000"
    volumes:
      - ./docker/logstash/pipeline:/usr/share/logstash/pipeline:ro
      - ./logs:/app/logs:ro
    depends_on:
      - elasticsearch

  kibana:
    image: kibana:8.8.0
    ports:
      - "5601:5601"
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
    depends_on:
      - elasticsearch

  # Log shipping
  filebeat:
    image: elastic/filebeat:8.8.0
    user: root
    volumes:
      - ./docker/filebeat/filebeat.yml:/usr/share/filebeat/filebeat.yml:ro
      - ./logs:/app/logs:ro
      - /var/lib/docker/containers:/var/lib/docker/containers:ro
      - /var/run/docker.sock:/var/run/docker.sock:ro
    depends_on:
      - logstash
    command: filebeat -e -strict.perms=false

volumes:
  elasticsearch_data:
    driver: local
```

### Health Checks and Monitoring

```yaml
# Health check endpoints for all services
healthchecks:
  backend:
    test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 60s

  frontend:
    test: ["CMD", "curl", "-f", "http://localhost:3000/health"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 30s

  celery-worker:
    test: ["CMD", "celery", "-A", "src.core.scheduler.celery_app", "inspect", "ping"]
    interval: 60s
    timeout: 15s
    retries: 3
    start_period: 60s

  postgres:
    test: ["CMD-SHELL", "pg_isready -U postgres -d google_news"]
    interval: 10s
    timeout: 5s
    retries: 5
    start_period: 30s

  redis:
    test: ["CMD", "redis-cli", "ping"]
    interval: 10s
    timeout: 3s
    retries: 5
    start_period: 10s
```

This deployment architecture provides a comprehensive, scalable foundation that supports the job-centric enhancement requirements while maintaining operational excellence across all environments.