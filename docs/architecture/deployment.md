# Deployment Architecture

Define deployment strategy dựa trên VPS platform choice với Docker containerization.

## Deployment Overview

**Current Phase: Local Development**
- **Platform:** Docker Compose trên local machine
- **Build Command:** `docker-compose build`  
- **Deployment Method:** Direct container execution

**Production Phase: VPS Deployment**
- **Platform:** VPS (DigitalOcean Droplet/AWS EC2) với Docker + Supervisor
- **Build Command:** `docker build -t news-scraper .`
- **Deployment Method:** Docker containers với Nginx reverse proxy
- **Process Management:** Supervisor cho service monitoring

## CI/CD Pipeline

### GitHub Actions Workflow

```yaml
# .github/workflows/deploy.yml
name: Deploy to VPS

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: password
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
    - uses: actions/checkout@v3
    
    - name: Set up Python 3.11
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Run tests
      env:
        DATABASE_URL: postgresql+asyncpg://postgres:password@localhost:5432/test_db
        REDIS_URL: redis://localhost:6379/0
      run: |
        pytest tests/ --cov=src --cov-report=xml
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup SSH
      uses: webfactory/ssh-agent@v0.7.0
      with:
        ssh-private-key: ${{ secrets.VPS_SSH_KEY }}
    
    - name: Deploy to VPS
      run: |
        ssh -o StrictHostKeyChecking=no ${{ secrets.VPS_USER }}@${{ secrets.VPS_HOST }} << 'EOF'
          cd /opt/google-news-scraper
          git pull origin main
          
          # Stop services
          sudo supervisorctl stop all
          
          # Build new images
          docker-compose -f docker-compose.prod.yml build
          
          # Run migrations
          docker-compose -f docker-compose.prod.yml run --rm app alembic upgrade head
          
          # Restart services
          sudo supervisorctl start all
          
          # Health check
          sleep 10
          curl -f http://localhost:8000/api/v1/health || exit 1
        EOF
```

## Production Environment Configuration

### Docker Compose Production

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_prod_data:/var/lib/postgresql/data
    restart: unless-stopped
    networks:
      - internal

  redis:
    image: redis:7-alpine
    volumes:
      - redis_prod_data:/data
    restart: unless-stopped
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    networks:
      - internal

  app:
    build:
      context: .
      dockerfile: docker/Dockerfile.prod
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/0
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
    networks:
      - internal
      - web

  celery-worker:
    build:
      context: .
      dockerfile: docker/Dockerfile.prod
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/0
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
    command: celery -A src.core.scheduler.celery_app worker --loglevel=info --concurrency=4
    networks:
      - internal

  celery-beat:
    build:
      context: .
      dockerfile: docker/Dockerfile.prod
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/0
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
    command: celery -A src.core.scheduler.celery_app beat --loglevel=info
    volumes:
      - celery_beat_prod:/app/celerybeat-schedule
    networks:
      - internal

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./docker/nginx.prod.conf:/etc/nginx/nginx.conf
      - ./docker/ssl:/etc/nginx/ssl  # SSL certificates
    depends_on:
      - app
    restart: unless-stopped
    networks:
      - web

volumes:
  postgres_prod_data:
  redis_prod_data:
  celery_beat_prod:

networks:
  web:
    external: false
  internal:
    external: false
```

## VPS Setup Script

```bash
#!/bin/bash
# scripts/setup_vps.sh - VPS initialization script

set -e

echo "Setting up Google News Scraper VPS..."

# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Install Supervisor
sudo apt install supervisor -y

# Create application directory
sudo mkdir -p /opt/google-news-scraper
sudo chown $USER:$USER /opt/google-news-scraper

# Clone repository
cd /opt
git clone <repository-url> google-news-scraper
cd google-news-scraper

# Setup environment
cp .env.production .env
# Edit .env with production values

# Setup SSL (Let's Encrypt)
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d your-domain.com -d api.your-domain.com

# Setup Supervisor configuration
sudo cp docker/supervisor.prod.conf /etc/supervisor/conf.d/news-scraper.conf

# Setup log rotation
sudo cp docker/logrotate.conf /etc/logrotate.d/news-scraper

# Setup firewall
sudo ufw allow ssh
sudo ufw allow 80
sudo ufw allow 443
sudo ufw --force enable

# Setup monitoring (optional)
sudo apt install htop iotop net-tools -y

# Initial deployment
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml run --rm app alembic upgrade head

# Start services
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start all

echo "VPS setup complete!"
echo "Check status: sudo supervisorctl status"
echo "View logs: sudo supervisorctl tail -f news-scraper"
```

## Nginx Configuration

```nginx
# docker/nginx.prod.conf
events {
    worker_connections 1024;
}

http {
    upstream backend {
        server app:8000;
    }
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    
    # Logging
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';
    
    server {
        listen 80;
        server_name api.your-domain.com;
        return 301 https://$server_name$request_uri;
    }
    
    server {
        listen 443 ssl http2;
        server_name api.your-domain.com;
        
        ssl_certificate /etc/nginx/ssl/fullchain.pem;
        ssl_certificate_key /etc/nginx/ssl/privkey.pem;
        
        # Security headers
        add_header X-Frame-Options DENY;
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1; mode=block";
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";
        
        # Gzip compression
        gzip on;
        gzip_vary on;
        gzip_min_length 1000;
        gzip_types text/plain application/json application/javascript text/css;
        
        location /api/ {
            limit_req zone=api burst=20 nodelay;
            
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # Timeouts
            proxy_connect_timeout 60s;
            proxy_send_timeout 60s;
            proxy_read_timeout 60s;
        }
        
        location /health {
            proxy_pass http://backend/api/v1/health;
            access_log off;
        }
        
        # Static file serving (future frontend)
        location / {
            root /var/www/html;
            index index.html;
            try_files $uri $uri/ /index.html;
        }
    }
}
```

## Supervisor Configuration

```ini
# docker/supervisor.prod.conf
[program:news-scraper]
command=docker-compose -f /opt/google-news-scraper/docker-compose.prod.yml up
directory=/opt/google-news-scraper
autostart=true
autorestart=true
stderr_logfile=/var/log/news-scraper.err.log
stdout_logfile=/var/log/news-scraper.out.log
user=ubuntu
environment=HOME="/home/ubuntu",USER="ubuntu"

[program:news-scraper-cleanup]
command=/opt/google-news-scraper/scripts/cleanup_old_data.sh
directory=/opt/google-news-scraper
autostart=false
autorestart=false
stderr_logfile=/var/log/news-scraper-cleanup.err.log
stdout_logfile=/var/log/news-scraper-cleanup.out.log
user=ubuntu
```

## Production Dockerfile

```dockerfile
# docker/Dockerfile.prod
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8000/api/v1/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Environment Management

### Production Environment Variables

```bash
# .env.production
DATABASE_URL=postgresql+asyncpg://news_user:secure_password@postgres:5432/news_scraper
REDIS_URL=redis://redis:6379/0

CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

API_HOST=0.0.0.0
API_PORT=8000
API_KEY=your-production-api-key

# Crawler settings
CRAWLER_RATE_LIMIT_PER_SECOND=1.5
CRAWLER_REQUEST_TIMEOUT=30
CRAWLER_MAX_RETRIES=3

# Security
SECRET_KEY=your-super-secure-production-key
DEBUG=false
LOG_LEVEL=INFO

# Environment
ENVIRONMENT=production
```

## Deployment Environments

| Environment | Frontend URL | Backend URL | Purpose |
|-------------|-------------|-------------|---------|
| Development | http://localhost:3000 | http://localhost:8000 | Local development |
| Staging | https://staging.your-domain.com | https://staging-api.your-domain.com | Pre-production testing |
| Production | https://your-domain.com | https://api.your-domain.com | Live environment |

## Backup Strategy

### Database Backup Script

```bash
#!/bin/bash
# scripts/backup_database.sh

BACKUP_DIR="/opt/backups/google-news-scraper"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="news_scraper_backup_${DATE}.sql"

# Create backup directory
mkdir -p $BACKUP_DIR

# Create database backup
docker-compose exec -T postgres pg_dump -U news_user news_scraper > "${BACKUP_DIR}/${BACKUP_FILE}"

# Compress backup
gzip "${BACKUP_DIR}/${BACKUP_FILE}"

# Remove old backups (keep last 30 days)
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete

echo "Database backup completed: ${BACKUP_FILE}.gz"
```

### Automated Backup Cron Job

```bash
# Add to crontab with: crontab -e
# Daily backup at 2 AM
0 2 * * * /opt/google-news-scraper/scripts/backup_database.sh

# Weekly cleanup at 3 AM Sunday
0 3 * * 0 /opt/google-news-scraper/scripts/cleanup_old_data.sh
```

## Monitoring và Alerting

### Deployment Health Checks

```bash
#!/bin/bash
# scripts/health_check.sh

echo "Checking service health..."

# Check API health
API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/health)
if [ $API_STATUS -eq 200 ]; then
    echo "✅ API is healthy"
else
    echo "❌ API is unhealthy (status: $API_STATUS)"
    exit 1
fi

# Check database connectivity
docker-compose exec -T postgres pg_isready -U news_user
if [ $? -eq 0 ]; then
    echo "✅ Database is healthy"
else
    echo "❌ Database is unhealthy"
    exit 1
fi

# Check Redis connectivity
docker-compose exec -T redis redis-cli ping
if [ $? -eq 0 ]; then
    echo "✅ Redis is healthy"
else
    echo "❌ Redis is unhealthy"
    exit 1
fi

# Check Celery workers
WORKER_COUNT=$(docker-compose exec -T celery-worker celery -A src.core.scheduler.celery_app inspect active | grep -c "celery@")
if [ $WORKER_COUNT -gt 0 ]; then
    echo "✅ Celery workers are running ($WORKER_COUNT active)"
else
    echo "❌ No Celery workers found"
    exit 1
fi

echo "All services are healthy! 🎉"
```

## Rollback Strategy

```bash
#!/bin/bash
# scripts/rollback.sh

echo "Rolling back to previous version..."

# Stop current services
sudo supervisorctl stop all

# Get last successful commit
PREVIOUS_COMMIT=$(git log --oneline -n 2 | tail -1 | cut -d' ' -f1)
echo "Rolling back to commit: $PREVIOUS_COMMIT"

# Checkout previous version
git checkout $PREVIOUS_COMMIT

# Rebuild containers
docker-compose -f docker-compose.prod.yml build

# Run database migrations down if needed
# docker-compose -f docker-compose.prod.yml run --rm app alembic downgrade -1

# Restart services
sudo supervisorctl start all

# Health check
sleep 10
./scripts/health_check.sh

echo "Rollback completed!"
```

## Security Considerations

1. **SSL/TLS:** Let's Encrypt certificates cho HTTPS
2. **Firewall:** UFW với only necessary ports open
3. **User Permissions:** Non-root containers và limited system access
4. **Secrets Management:** Environment variables, not hardcoded
5. **Regular Updates:** Automated security updates cho OS và dependencies
6. **Access Control:** SSH key authentication, no password login
7. **Network Security:** Internal Docker networks cho service isolation