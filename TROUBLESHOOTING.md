# Google News Scraper - Container Troubleshooting Guide

This guide provides solutions for common Docker container issues in the Google News Scraper application.

## Table of Contents

- [Quick Diagnostic Commands](#quick-diagnostic-commands)
- [Container Startup Issues](#container-startup-issues)
- [Database Problems](#database-problems)
- [Redis Connection Issues](#redis-connection-issues)
- [Celery Worker Problems](#celery-worker-problems)
- [API Service Issues](#api-service-issues)
- [Performance Problems](#performance-problems)
- [Network Issues](#network-issues)
- [Volume and Data Issues](#volume-and-data-issues)
- [SSL/TLS Problems](#ssltls-problems)
- [Resource Exhaustion](#resource-exhaustion)

## Quick Diagnostic Commands

### System Overview

```bash
# Check all containers status
docker-compose ps

# View resource usage
docker stats --no-stream

# Check container health
docker-compose ps | grep -E "(healthy|unhealthy)"

# View recent logs from all services
docker-compose logs --tail=50
```

### Service-Specific Checks

```bash
# Check web service
curl -f http://localhost:8000/health

# Check database connectivity
docker-compose exec postgres pg_isready -U postgres

# Check Redis connectivity
docker-compose exec redis redis-cli ping

# Check Celery workers
docker-compose exec worker celery -A src.core.scheduler.celery_app inspect ping
```

## Container Startup Issues

### Symptom: Container Exits Immediately

**Check exit codes:**
```bash
docker-compose ps
docker-compose logs service_name
```

**Common causes and solutions:**

1. **Permission Issues:**
   ```bash
   # Fix data directory permissions
   sudo chown -R 1000:1000 data/ logs/
   chmod -R 755 data/
   chmod -R 755 logs/
   ```

2. **Missing Environment Variables:**
   ```bash
   # Verify .env file exists and is complete
   ls -la .env
   docker-compose config  # Validates compose file
   ```

3. **Port Conflicts:**
   ```bash
   # Check for port conflicts
   netstat -tlnp | grep -E ":(8000|5432|6379)"
   
   # Change ports in docker-compose.yml if needed
   ports:
     - "8001:8000"  # Use different host port
   ```

4. **Image Build Failures:**
   ```bash
   # Rebuild images
   docker-compose build --no-cache
   docker-compose up -d
   ```

### Symptom: Service Stuck in Starting State

**Diagnosis:**
```bash
# Check logs for startup issues
docker-compose logs -f service_name

# Check health check configuration
docker inspect $(docker-compose ps -q service_name) | grep -A 10 Health
```

**Solutions:**
```bash
# Increase health check timeout
# In docker-compose.yml:
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 5
  start_period: 60s  # Increase this
```

## Database Problems

### Symptom: "Connection Refused" Errors

**Quick fixes:**
```bash
# Restart PostgreSQL
docker-compose restart postgres

# Check if PostgreSQL is ready
docker-compose exec postgres pg_isready -U postgres -d google_news

# Wait for database startup
timeout 60 bash -c 'until docker-compose exec postgres pg_isready; do sleep 2; done'
```

### Symptom: Database Authentication Failures

**Check credentials:**
```bash
# Verify environment variables
docker-compose exec postgres env | grep POSTGRES

# Test connection manually
docker-compose exec postgres psql -U postgres -d google_news -c "\dt"
```

**Reset credentials:**
```bash
# Stop containers
docker-compose down

# Remove database volume (WARNING: Data loss)
docker volume rm google-news-scraper_postgres_data

# Restart with fresh database
docker-compose up -d postgres
```

### Symptom: Database Migration Failures

**Check migration status:**
```bash
# View current migration version
docker-compose exec web alembic current

# Check migration history
docker-compose exec web alembic history

# Show pending migrations
docker-compose exec web alembic show head
```

**Fix migration issues:**
```bash
# Retry migrations
docker-compose exec web alembic upgrade head

# If migrations are stuck, reset to base
docker-compose exec web alembic downgrade base
docker-compose exec web alembic upgrade head

# Manual database reset (DESTRUCTIVE)
docker-compose exec postgres psql -U postgres -c "DROP DATABASE IF EXISTS google_news;"
docker-compose exec postgres psql -U postgres -c "CREATE DATABASE google_news;"
docker-compose exec web alembic upgrade head
```

## Redis Connection Issues

### Symptom: Redis Connection Errors

**Quick diagnostics:**
```bash
# Check Redis status
docker-compose exec redis redis-cli ping

# Check Redis info
docker-compose exec redis redis-cli info server

# Monitor Redis logs
docker-compose logs -f redis
```

**Fix connection issues:**
```bash
# Restart Redis
docker-compose restart redis

# Clear Redis data if corrupted
docker-compose exec redis redis-cli FLUSHALL

# Check network connectivity
docker-compose exec web ping redis
```

### Symptom: Redis Memory Issues

**Check memory usage:**
```bash
# Check Redis memory info
docker-compose exec redis redis-cli info memory

# Check container memory limits
docker stats $(docker-compose ps -q redis)
```

**Solutions:**
```bash
# Increase Redis memory limit in docker-compose.yml
redis:
  deploy:
    resources:
      limits:
        memory: 512M  # Increase as needed
        
# Configure Redis memory policy
redis:
  command: >
    redis-server
    --maxmemory 400mb
    --maxmemory-policy allkeys-lru
```

## Celery Worker Problems

### Symptom: Workers Not Processing Tasks

**Check worker status:**
```bash
# Inspect Celery workers
docker-compose exec worker celery -A src.core.scheduler.celery_app inspect active
docker-compose exec worker celery -A src.core.scheduler.celery_app inspect stats

# Check task queues
docker-compose exec worker celery -A src.core.scheduler.celery_app inspect active_queues
```

**Restart workers:**
```bash
# Graceful worker restart
docker-compose restart worker

# Scale workers if needed
docker-compose up -d --scale worker=3

# Check worker logs
docker-compose logs -f worker
```

### Symptom: Celery Beat Scheduler Issues

**Check beat status:**
```bash
# View beat logs
docker-compose logs -f beat

# Check scheduled tasks
docker-compose exec beat celery -A src.core.scheduler.celery_app inspect scheduled
```

**Fix beat issues:**
```bash
# Restart beat scheduler
docker-compose restart beat

# Remove beat schedule file if corrupted
docker-compose exec beat rm -f /app/data/beat/celerybeat-schedule
docker-compose restart beat
```

### Symptom: Task Failures and Retries

**Monitor task execution:**
```bash
# View failed tasks in Flower (if enabled)
# Access http://localhost:5555

# Check worker error logs
docker-compose logs worker | grep -i error

# Monitor task execution
docker-compose exec worker celery -A src.core.scheduler.celery_app events
```

## API Service Issues

### Symptom: API Not Responding

**Check API health:**
```bash
# Basic health check
curl -f http://localhost:8000/health

# Detailed health status
curl http://localhost:8000/health/detailed | jq

# Check if process is running
docker-compose exec web ps aux | grep uvicorn
```

**Restart API service:**
```bash
# Restart web service
docker-compose restart web

# Check web service logs
docker-compose logs -f web

# Scale web service if needed
docker-compose up -d --scale web=2
```

### Symptom: Slow API Responses

**Performance diagnostics:**
```bash
# Check response times
time curl http://localhost:8000/health

# Monitor container resources
docker stats $(docker-compose ps -q web)

# Check database query performance
docker-compose logs web | grep -i "slow\|timeout"
```

**Performance tuning:**
```bash
# Increase worker processes
# In docker-compose.yml:
web:
  command: uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --workers 4

# Increase database pool size
# In .env:
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30
```

## Performance Problems

### Symptom: High Memory Usage

**Memory diagnostics:**
```bash
# Check container memory usage
docker stats --no-stream

# Check system memory
free -h

# Find memory-hungry processes
docker-compose exec web top
```

**Memory optimization:**
```bash
# Reduce worker concurrency
# In docker-compose.yml:
worker:
  command: celery -A src.core.scheduler.celery_app worker --concurrency=2

# Set memory limits
web:
  deploy:
    resources:
      limits:
        memory: 512M

# Restart containers to free memory
docker-compose restart
```

### Symptom: High CPU Usage

**CPU diagnostics:**
```bash
# Monitor CPU usage
docker stats $(docker-compose ps -q)

# Check CPU-intensive processes
docker-compose exec web htop  # If htop is installed
```

**CPU optimization:**
```bash
# Limit CPU usage
web:
  deploy:
    resources:
      limits:
        cpus: '1.0'

# Reduce concurrent operations
# Adjust worker concurrency and task rates
```

### Symptom: Slow Database Queries

**Database performance:**
```bash
# Check database connections
docker-compose exec postgres psql -U postgres -d google_news -c "SELECT * FROM pg_stat_activity;"

# Monitor slow queries
docker-compose exec postgres psql -U postgres -d google_news -c "SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"
```

**Database tuning:**
```bash
# Adjust PostgreSQL configuration in docker-compose.yml
postgres:
  command: >
    postgres
    -c shared_buffers=256MB
    -c effective_cache_size=1GB
    -c work_mem=8MB
    -c max_connections=100
```

## Network Issues

### Symptom: Service Discovery Problems

**Network diagnostics:**
```bash
# Check docker network
docker network ls
docker network inspect google-news-scraper_app-network

# Test service connectivity
docker-compose exec web ping postgres
docker-compose exec web ping redis
```

**Fix network issues:**
```bash
# Recreate network
docker-compose down
docker network prune
docker-compose up -d

# Check DNS resolution
docker-compose exec web nslookup postgres
docker-compose exec web nslookup redis
```

### Symptom: External Network Access Issues

**Check external connectivity:**
```bash
# Test internet access from containers
docker-compose exec web ping 8.8.8.8
docker-compose exec web curl -I https://www.google.com

# Check proxy settings if behind corporate firewall
docker-compose exec web env | grep -i proxy
```

## Volume and Data Issues

### Symptom: Data Not Persisting

**Check volume mounts:**
```bash
# List volumes
docker volume ls | grep google-news

# Inspect volume details
docker volume inspect google-news-scraper_postgres_data

# Check mount points
docker-compose exec postgres mount | grep /var/lib/postgresql
```

**Fix persistence issues:**
```bash
# Verify volume configuration in docker-compose.yml
volumes:
  postgres_data:
    driver: local

# Check directory permissions
ls -la data/
sudo chown -R 1000:1000 data/
```

### Symptom: Disk Space Issues

**Check disk usage:**
```bash
# Container disk usage
docker system df

# Volume disk usage
du -sh data/*

# Clean up unused resources
docker system prune -f
docker volume prune -f
```

## SSL/TLS Problems

### Symptom: SSL Certificate Errors

**Check certificates:**
```bash
# Verify certificate files exist
ls -la data/ssl/

# Check certificate validity
openssl x509 -in data/ssl/cert.pem -text -noout | grep -A2 Validity

# Test SSL connection
openssl s_client -connect localhost:443 -servername your-domain.com
```

**Fix SSL issues:**
```bash
# Generate self-signed certificate for testing
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout data/ssl/key.pem \
  -out data/ssl/cert.pem \
  -subj "/CN=localhost"

# Fix certificate permissions
chmod 600 data/ssl/key.pem
chmod 644 data/ssl/cert.pem
```

## Resource Exhaustion

### Emergency Recovery Procedures

**When system is overloaded:**
```bash
# Stop non-critical services
docker-compose stop flower
docker-compose stop beat

# Scale down workers
docker-compose up -d --scale worker=1

# Restart essential services
docker-compose restart postgres redis web

# Monitor recovery
watch docker stats
```

**Resource cleanup:**
```bash
# Clean up Docker resources
docker system prune -a -f
docker volume prune -f

# Remove old log files
find logs/ -name "*.log" -mtime +7 -delete

# Clear Redis cache
docker-compose exec redis redis-cli FLUSHALL
```

### Prevention Strategies

**Resource monitoring:**
```bash
# Set up monitoring script
#!/bin/bash
# save as scripts/monitor.sh
while true; do
  echo "=== $(date) ==="
  docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"
  echo ""
  sleep 30
done
```

**Resource limits:**
```yaml
# In docker-compose.yml
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
```

## Getting Help

### Log Collection for Support

```bash
#!/bin/bash
# Collect diagnostic information
mkdir -p debug-info
cd debug-info

# System info
docker --version > system-info.txt
docker-compose --version >> system-info.txt
uname -a >> system-info.txt
df -h >> system-info.txt
free -h >> system-info.txt

# Container status
docker-compose ps > container-status.txt
docker stats --no-stream > resource-usage.txt

# Logs
docker-compose logs --tail=500 > all-services.log
docker-compose logs web --tail=200 > web-service.log
docker-compose logs postgres --tail=200 > postgres-service.log
docker-compose logs redis --tail=200 > redis-service.log
docker-compose logs worker --tail=200 > worker-service.log

# Health checks
curl -s http://localhost:8000/health > health-check.json
curl -s http://localhost:8000/health/detailed > detailed-health.json

# Configuration
cp ../.env env-config.txt  # Remove sensitive data first
cp ../docker-compose.yml compose-config.yml

echo "Debug information collected in debug-info/ directory"
echo "Review files before sharing to remove sensitive information"
```

### Emergency Contacts

For critical production issues:

1. **Check application health**: `/health/detailed` endpoint
2. **Review recent logs**: `docker-compose logs --tail=100`
3. **Create backup**: `./scripts/deployment/backup-containers.sh`
4. **Document issue**: Include error messages, timestamps, and steps to reproduce
5. **Attempt standard recovery**: Restart affected services
6. **Escalate if necessary**: Contact system administrator or on-call engineer

### Useful Debug Commands

```bash
# Get into container for debugging
docker-compose exec web bash
docker-compose exec postgres psql -U postgres -d google_news
docker-compose exec redis redis-cli

# Check environment variables
docker-compose exec web env

# Check process tree
docker-compose exec web ps auxf

# Check network connectivity
docker-compose exec web netstat -tlnp

# Check file permissions
docker-compose exec web ls -la /app/
docker-compose exec web ls -la /app/logs/
docker-compose exec web ls -la /app/data/
```

---

**Remember**: Always test solutions in a development environment first. For production issues, create a backup before making changes and have a rollback plan ready.