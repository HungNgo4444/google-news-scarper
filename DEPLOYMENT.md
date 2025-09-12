# Google News Scraper - Deployment Guide

This guide provides comprehensive instructions for deploying the Google News Scraper application using Docker containerization across different environments.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Environment Setup](#environment-setup)
- [Development Deployment](#development-deployment)
- [Production Deployment](#production-deployment)
- [Container Management](#container-management)
- [Backup and Recovery](#backup-and-recovery)
- [Monitoring and Health Checks](#monitoring-and-health-checks)
- [Troubleshooting](#troubleshooting)
- [Security Considerations](#security-considerations)

## Prerequisites

### System Requirements

- **Docker**: Version 24.0+
- **Docker Compose**: Version 2.21+
- **System Memory**: Minimum 4GB, Recommended 8GB
- **Disk Space**: Minimum 10GB free space
- **Network**: Outbound internet access for crawling

### Verification Commands

```bash
# Check Docker installation
docker --version
docker-compose --version

# Verify Docker daemon is running
docker info

# Check available resources
docker system df
```

## Environment Setup

### 1. Clone and Prepare Repository

```bash
git clone <repository-url> google-news-scraper
cd google-news-scraper

# Create environment file from template
cp .env.example .env

# Edit configuration as needed
nano .env
```

### 2. Directory Structure Setup

The deployment creates the following directory structure:

```
google-news-scraper/
├── docker/                     # Docker configuration files
│   ├── Dockerfile              # Main application container
│   ├── Dockerfile.worker       # Celery worker container
│   ├── nginx.conf              # Development reverse proxy
│   ├── nginx.prod.conf         # Production SSL configuration
│   └── supervisor.conf         # Production process management
├── data/                       # Persistent data storage
│   ├── postgres/               # PostgreSQL data
│   ├── redis/                  # Redis data
│   ├── beat/                   # Celery Beat schedule
│   └── ssl/                    # SSL certificates (production)
├── logs/                       # Application logs
├── backups/                    # Backup storage
└── secrets/                    # Production secrets (gitignored)
```

## Development Deployment

### Quick Start

```bash
# One-command deployment
./scripts/deployment/deploy-dev.sh

# Or step by step:
./scripts/deployment/deploy-dev.sh deploy
```

### Manual Development Setup

1. **Build containers:**
   ```bash
   docker build -f docker/Dockerfile -t google-news-scraper:latest .
   docker build -f docker/Dockerfile.worker -t google-news-scraper-worker:latest .
   ```

2. **Start services:**
   ```bash
   docker-compose up -d
   ```

3. **Run migrations:**
   ```bash
   docker-compose exec web alembic upgrade head
   ```

4. **Verify deployment:**
   ```bash
   curl http://localhost:8000/health
   ```

### Development Services

| Service | URL | Purpose |
|---------|-----|---------|
| Web API | http://localhost:8000 | Main application API |
| API Docs | http://localhost:8000/api/v1/docs | Interactive API documentation |
| Health Check | http://localhost:8000/health | Container health monitoring |
| PostgreSQL | localhost:5432 | Database (postgres/postgres) |
| Redis | localhost:6379 | Cache and message broker |
| Flower | http://localhost:5555 | Celery monitoring (optional) |

### Development Commands

```bash
# View logs
docker-compose logs -f

# Access container shell
docker-compose exec web bash

# Scale workers
docker-compose up -d --scale worker=3

# Stop services
docker-compose down

# Clean reset
docker-compose down -v
docker system prune -f
```

## Production Deployment

### Security Prerequisites

1. **Create secrets directory:**
   ```bash
   mkdir secrets
   echo "your_postgres_password" > secrets/postgres_password.txt
   echo "your_redis_password" > secrets/redis_password.txt
   chmod 600 secrets/*.txt
   ```

2. **SSL certificates (optional):**
   ```bash
   mkdir -p data/ssl
   # Copy your SSL certificates:
   # - cert.pem (certificate)
   # - key.pem (private key)
   # - ca-cert.pem (CA bundle)
   # - dhparam.pem (DH parameters)
   ```

3. **Production environment file:**
   ```bash
   cp .env.example .env.production
   # Edit with production values
   nano .env.production
   ```

### Production Deployment

```bash
# Full production deployment
./scripts/deployment/deploy-prod.sh

# Or specific operations:
./scripts/deployment/deploy-prod.sh deploy    # Full deployment
./scripts/deployment/deploy-prod.sh update    # Update services
./scripts/deployment/deploy-prod.sh scale worker 5  # Scale workers
```

### Production Configuration

Key production environment variables:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:password@postgres:5432/google_news_prod

# Security
ENVIRONMENT=production
LOG_LEVEL=INFO
DATABASE_ECHO=false

# Performance
WEB_WORKERS=4
CELERY_WORKER_CONCURRENCY=4
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30

# Monitoring
FLOWER_USERNAME=admin
FLOWER_PASSWORD=secure_password
```

### Production Services

| Service | URL | Purpose |
|---------|-----|---------|
| Web API | https://your-domain.com | Main application (SSL) |
| Health Check | https://your-domain.com/health | Basic health monitoring |
| Detailed Health | https://your-domain.com/health/detailed | Comprehensive health status |
| Flower | https://your-domain.com/flower | Celery monitoring (authenticated) |

## Container Management

### Service Scaling

```bash
# Scale web services
docker-compose -f docker-compose.prod.yml up -d --scale web=3

# Scale workers
docker-compose -f docker-compose.prod.yml up -d --scale worker=5

# Note: Beat scheduler must always have exactly 1 replica
```

### Rolling Updates

```bash
# Zero-downtime update
./scripts/deployment/deploy-prod.sh update

# Manual rolling update
docker-compose -f docker-compose.prod.yml up -d --scale web=1 web
# Wait for health check
docker-compose -f docker-compose.prod.yml up -d --scale web=2 web
```

### Container Health Monitoring

The application provides multiple health check endpoints:

- `/health` - Basic health check for load balancers
- `/health/detailed` - Comprehensive component status
- `/ready` - Kubernetes readiness probe
- `/live` - Kubernetes liveness probe

### Log Management

```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f web
docker-compose logs -f worker

# Log rotation (automatic in production)
docker-compose logs --tail=1000 web
```

## Backup and Recovery

### Automated Backups

```bash
# Create full backup
./scripts/deployment/backup-containers.sh

# List available backups
./scripts/deployment/backup-containers.sh list

# Restore from backup
./scripts/deployment/backup-containers.sh restore 20241201_143022
```

### Manual Backup Operations

```bash
# Database backup
docker-compose exec postgres pg_dump -U postgres google_news > backup.sql

# Redis backup
docker-compose exec redis redis-cli BGSAVE
docker cp $(docker-compose ps -q redis):/data/dump.rdb redis_backup.rdb

# Volume backup
docker run --rm -v google-news-scraper_postgres_data:/data -v $PWD:/backup alpine tar czf /backup/postgres_volume.tar.gz -C /data .
```

### Backup Schedule

For production environments, set up automated backups:

```bash
# Add to crontab for daily backups at 2 AM
0 2 * * * /path/to/google-news-scraper/scripts/deployment/backup-containers.sh
```

## Monitoring and Health Checks

### Container Health Checks

All containers include built-in health checks:

```bash
# Check container health
docker-compose ps

# View health check logs
docker inspect $(docker-compose ps -q web) | grep Health -A 10
```

### Application Monitoring

1. **Health Endpoints:**
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8000/health/detailed
   ```

2. **Celery Monitoring:**
   - Access Flower at http://localhost:5555
   - Monitor task queues, workers, and execution times

3. **Database Monitoring:**
   ```bash
   # Connection status
   docker-compose exec postgres pg_isready

   # Performance stats
   docker-compose exec postgres psql -U postgres -c "SELECT * FROM pg_stat_activity;"
   ```

### Performance Monitoring

Key metrics to monitor:

- **Response times**: Check `/health/detailed` response times
- **Database connections**: Monitor pool usage
- **Memory usage**: Container memory consumption
- **Queue lengths**: Celery task backlogs
- **Error rates**: Application error logs

## Troubleshooting

### Common Issues

#### 1. Container Startup Failures

```bash
# Check logs
docker-compose logs service_name

# Check container status
docker-compose ps

# Restart specific service
docker-compose restart service_name
```

#### 2. Database Connection Issues

```bash
# Check database status
docker-compose exec postgres pg_isready

# Check connection from app
docker-compose exec web python -c "from src.database.connection import get_database_connection; import asyncio; print(asyncio.run(get_database_connection().health_check()))"

# Reset database connection
docker-compose restart postgres web
```

#### 3. Memory Issues

```bash
# Check container memory usage
docker stats

# Restart memory-heavy services
docker-compose restart worker

# Scale down if necessary
docker-compose up -d --scale worker=2
```

#### 4. SSL/TLS Issues (Production)

```bash
# Check certificate validity
openssl x509 -in data/ssl/cert.pem -text -noout

# Test SSL configuration
openssl s_client -connect your-domain.com:443 -servername your-domain.com

# Check nginx configuration
docker-compose exec nginx nginx -t
```

### Debug Mode

Enable debug mode for development:

```bash
# Set in .env
LOG_LEVEL=DEBUG
DATABASE_ECHO=true

# Restart services
docker-compose restart web worker
```

### Performance Tuning

#### Database Optimization

```bash
# Adjust PostgreSQL settings in docker-compose.yml
postgres:
  command: >
    postgres
    -c max_connections=100
    -c shared_buffers=256MB
    -c effective_cache_size=1GB
    -c work_mem=4MB
```

#### Application Scaling

```bash
# Scale based on load
docker-compose up -d --scale web=4 --scale worker=6

# Monitor performance impact
watch docker stats
```

## Security Considerations

### Production Security Checklist

- [ ] Use secrets management (Docker secrets)
- [ ] Enable SSL/TLS termination
- [ ] Configure firewall rules
- [ ] Use non-root containers
- [ ] Secure environment variable handling
- [ ] Enable container security scanning
- [ ] Configure log rotation
- [ ] Set up monitoring and alerting
- [ ] Regular security updates
- [ ] Backup encryption

### Network Security

```yaml
# In docker-compose.prod.yml
networks:
  app-network:
    driver: bridge
    driver_opts:
      com.docker.network.bridge.name: google-news-net
```

### Container Security

- All containers run as non-root users
- Read-only filesystems where possible
- Minimal base images (alpine/slim)
- Security headers in Nginx
- Rate limiting enabled

### Regular Maintenance

```bash
# Update base images
docker-compose pull
docker-compose up -d

# Clean unused resources
docker system prune -f

# Update application
git pull
./scripts/deployment/deploy-prod.sh update
```

## Support and Maintenance

### Log Locations

- **Application logs**: `./logs/`
- **Container logs**: `docker-compose logs`
- **System logs**: `/var/log/` (host system)

### Maintenance Commands

```bash
# Health check all services
curl -s http://localhost:8000/health/detailed | jq

# Update all services
./scripts/deployment/deploy-prod.sh update

# Create maintenance backup
./scripts/deployment/backup-containers.sh

# Monitor resource usage
docker stats --no-stream
```

### Emergency Procedures

1. **Service Degradation:**
   ```bash
   # Scale up quickly
   docker-compose up -d --scale worker=10
   
   # Check health status
   curl http://localhost:8000/health/detailed
   ```

2. **Database Issues:**
   ```bash
   # Restore from latest backup
   ./scripts/deployment/backup-containers.sh restore LATEST_BACKUP_ID
   ```

3. **Complete System Recovery:**
   ```bash
   # Stop everything
   docker-compose down
   
   # Restore from backup
   ./scripts/deployment/backup-containers.sh restore BACKUP_ID
   
   # Restart services
   ./scripts/deployment/deploy-prod.sh
   ```

---

**Note**: Always test deployment procedures in a development environment before applying to production. Keep backups and have a rollback plan ready for production deployments.