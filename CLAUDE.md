# Google News Scraper - Developer Guide

## 📋 Tổng quan Project

**Google News Scraper** là một hệ thống thu thập và phân tích tin tức từ Google News với kiến trúc microservices sử dụng Docker.

### Công nghệ sử dụng

#### Backend
- **Python 3.13+** - Ngôn ngữ chính
- **FastAPI** - Web framework hiện đại, async
- **PostgreSQL 15** - Database chính
- **Redis 7** - Cache & message broker
- **Celery** - Task queue & scheduling
- **Celery Beat** - Periodic task scheduler
- **SQLAlchemy** - ORM với async support
- **Alembic** - Database migration
- **Playwright** - JavaScript rendering cho scraping
- **Newspaper4k** - Article parsing & extraction

#### Frontend
- **React** - UI framework
- **Vite** - Build tool
- **TypeScript** - Type safety

#### Infrastructure
- **Docker & Docker Compose** - Containerization
- **Nginx** - Reverse proxy
- **Flower** - Celery monitoring (optional)

### Kiến trúc hệ thống

```
┌─────────────┐     ┌──────────────┐
│   Frontend  │────▶│  Nginx       │
│  (React)    │     │  (Port 80)   │
└─────────────┘     └──────┬───────┘
                           │
┌──────────────────────────┼────────────────────────┐
│                          ▼                        │
│  ┌─────────────────────────────────────────────┐ │
│  │        FastAPI Web (Port 8000)              │ │
│  └────────────────┬────────────────────────────┘ │
│                   │                               │
│  ┌────────────────┼────────────────────────────┐ │
│  │                ▼                            │ │
│  │  ┌──────────────────┐  ┌─────────────────┐ │ │
│  │  │   PostgreSQL     │  │     Redis       │ │ │
│  │  │  (Port 5432)     │  │   (Port 6379)   │ │ │
│  │  └──────────────────┘  └─────────────────┘ │ │
│  │           ▲                      ▲          │ │
│  │           │                      │          │ │
│  │  ┌────────┴──────────┬───────────┴────────┐│ │
│  │  │                   │                    ││ │
│  │  │  Celery Worker    │  Celery Beat       ││ │
│  │  │  (Task Queue)     │  (Scheduler)       ││ │
│  │  └───────────────────┴────────────────────┘│ │
│  └──────────────────────────────────────────────┘│
└───────────────────────────────────────────────────┘
```

### Cấu trúc thư mục

```
Google News Scraper/
├── src/                        # Source code chính
│   ├── api/                   # FastAPI routes & endpoints
│   ├── core/                  # Core components (scheduler, celery)
│   ├── crawler/               # Scraping logic
│   ├── database/              # Database models & migrations
│   ├── processors/            # Data processing
│   └── services/              # Business logic
├── frontend/                  # React frontend
├── docker/                    # Docker configurations
│   ├── Dockerfile            # Main Python app
│   ├── Dockerfile.frontend   # React app
│   ├── Dockerfile.worker     # Celery worker
│   ├── nginx.conf            # Nginx dev config
│   └── nginx.prod.conf       # Nginx prod config
├── docs/                      # Documentation
├── tests/                     # Test files
├── scripts/                   # Utility scripts
├── docker-compose.yml        # Dev environment
├── docker-compose.prod.yml   # Production environment
├── alembic.ini               # Database migration config
└── requirements.txt          # Python dependencies
```

## 🚀 Quick Start

### Khởi động hệ thống

```bash
# Clone và di chuyển vào project
cd "f:\Google News Scarper"

# Khởi động tất cả services
docker-compose up -d

# Xem logs
docker-compose logs -f

# Khởi động với monitoring (Flower)
docker-compose --profile monitoring up -d

# Khởi động với Nginx
docker-compose --profile with-nginx up -d
```

### Truy cập ứng dụng

- **Frontend**: http://localhost:3000
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Flower (monitoring)**: http://localhost:5555
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

## 🔄 Cập nhật Code lên Docker (QUAN TRỌNG)

### Phương pháp 1: Rebuild Image (Khuyến nghị cho thay đổi lớn)

```bash
# Dừng services
docker-compose down

# Rebuild images và khởi động lại
docker-compose up -d --build

# Hoặc rebuild specific service
docker-compose up -d --build web
docker-compose up -d --build worker
docker-compose up -d --build frontend
```

### Phương pháp 2: Hot Reload (NHANH NHẤT - cho dev)

Do đã mount volumes trong docker-compose.yml, code thay đổi sẽ tự động sync:

```yaml
volumes:
  - ./src:/app/src:ro  # Code sync tự động
```

**Để áp dụng thay đổi:**

```bash
# Restart service cụ thể (NHANH)
docker-compose restart web         # Restart API
docker-compose restart worker      # Restart Celery worker
docker-compose restart frontend    # Restart React app

# Hoặc restart tất cả
docker-compose restart
```

### Phương pháp 3: Copy file vào container (Cho fix nhanh)

```bash
# Copy file cụ thể vào container
docker cp src/api/routes.py <container_id>:/app/src/api/routes.py

# Restart container
docker-compose restart web
```

### Phương pháp 4: Exec vào container để debug

```bash
# Vào container web
docker exec -it <web_container_id> /bin/bash

# Vào container worker
docker exec -it <worker_container_id> /bin/bash

# Trong container có thể:
# - Chạy lệnh Python trực tiếp
# - Debug code
# - Xem logs
# - Test modules
```

## 📝 Workflow Cập nhật Code Thông thường

### 1. Thay đổi code Python (Backend)

```bash
# Sửa code trong src/
# Code đã được mount, tự động sync

# Restart service để áp dụng
docker-compose restart web
docker-compose restart worker

# Xem logs để check
docker-compose logs -f web
```

### 2. Thay đổi dependencies (requirements.txt)

```bash
# Sửa requirements.txt

# Rebuild image
docker-compose up -d --build web worker

# Hoặc
docker-compose down
docker-compose up -d --build
```

### 3. Database migration

```bash
# Tạo migration mới
docker-compose exec web alembic revision --autogenerate -m "Description"

# Apply migration
docker-compose exec web alembic upgrade head

# Hoặc restart migration service
docker-compose up -d migration
```

### 4. Thay đổi frontend

```bash
# Sửa code trong frontend/
# Code được mount, tự động hot reload qua Vite

# Nếu thêm dependencies:
cd frontend
npm install
docker-compose restart frontend
```

### 5. Thay đổi cấu hình Docker

```bash
# Sửa docker-compose.yml hoặc Dockerfile

# Rebuild và khởi động lại
docker-compose down
docker-compose up -d --build
```

## 🔍 Debug & Troubleshooting

### Xem logs

```bash
# Tất cả services
docker-compose logs -f

# Service cụ thể
docker-compose logs -f web
docker-compose logs -f worker
docker-compose logs -f postgres

# Tail 100 dòng cuối
docker-compose logs --tail=100 web
```

### Check status

```bash
# Xem services đang chạy
docker-compose ps

# Xem resource usage
docker stats

# Xem networks
docker network ls
```

### Celery monitoring

```bash
# Qua Flower UI
http://localhost:5555

# Hoặc CLI
docker-compose exec worker celery -A src.core.scheduler.celery_app inspect active
docker-compose exec worker celery -A src.core.scheduler.celery_app inspect stats
```

### Database access

```bash
# Connect tới PostgreSQL
docker-compose exec postgres psql -U postgres -d google_news

# Backup database
docker-compose exec postgres pg_dump -U postgres google_news > backup.sql

# Restore database
docker-compose exec -T postgres psql -U postgres google_news < backup.sql
```

### Redis monitoring

```bash
# Redis CLI
docker-compose exec redis redis-cli

# Monitor commands
docker-compose exec redis redis-cli MONITOR

# Check memory
docker-compose exec redis redis-cli INFO memory
```

## 🛠 Các lệnh Docker hữu ích

```bash
# Dọn dẹp containers cũ
docker-compose down -v  # Xóa cả volumes
docker system prune -a  # Dọn dẹp toàn bộ

# Rebuild from scratch
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d

# Xem logs real-time nhiều services
docker-compose logs -f web worker beat

# Scale worker
docker-compose up -d --scale worker=3

# Export/Import images
docker save -o google-news-web.tar google-news-scraper-web
docker load -i google-news-web.tar
```

## 🎯 Best Practices

### Development

1. **Luôn dùng volumes mount** cho code để hot reload
2. **Restart thay vì rebuild** khi chỉ đổi code
3. **Xem logs thường xuyên** để catch errors sớm
4. **Dùng Flower** để monitor Celery tasks
5. **Commit code trước khi rebuild** để tránh mất code

### Production

1. **Dùng docker-compose.prod.yml** cho production
2. **Set environment variables** qua .env file
3. **Backup database thường xuyên**
4. **Monitor resources** (CPU, Memory, Disk)
5. **Use specific image tags** thay vì latest

### Docker Performance

1. **Limit container resources** trong docker-compose.yml
2. **Use multi-stage builds** trong Dockerfile
3. **Clean up old images/containers** định kỳ
4. **Use .dockerignore** để giảm build context
5. **Cache layers hiệu quả** bằng cách sắp xếp Dockerfile đúng

## 📊 Environment Variables

Xem file [.env.example](.env.example) cho full list. Key variables:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/google_news

# Redis/Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# App
ENVIRONMENT=development
LOG_LEVEL=INFO
ENABLE_JAVASCRIPT_RENDERING=true

# Frontend
VITE_API_BASE_URL=http://localhost:8000
```

## 🔐 Security Notes

1. **Đổi default passwords** trong production
2. **Không commit .env** file
3. **Use secrets management** cho sensitive data
4. **Restrict network exposure** trong production
5. **Regular security updates** cho base images

## 📚 Tài liệu thêm

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Celery Docs](https://docs.celeryq.dev/)
- [Docker Compose Docs](https://docs.docker.com/compose/)
- [PostgreSQL Docs](https://www.postgresql.org/docs/)
- [Redis Docs](https://redis.io/docs/)

## 🎓 Tips & Tricks

### Speed up development

```bash
# Alias hữu ích (thêm vào .bashrc hoặc .zshrc)
alias dc='docker-compose'
alias dcup='docker-compose up -d'
alias dcdown='docker-compose down'
alias dclogs='docker-compose logs -f'
alias dcrestart='docker-compose restart'
alias dcrebuild='docker-compose up -d --build'

# Sử dụng
dcup            # Thay vì docker-compose up -d
dclogs web      # Thay vì docker-compose logs -f web
dcrestart web   # Thay vì docker-compose restart web
```

### Xem thay đổi code real-time

```bash
# Terminal 1: Logs
docker-compose logs -f web worker

# Terminal 2: Code changes
# (sửa code)

# Terminal 3: Quick restart
docker-compose restart web worker
```

### Quick database reset

```bash
# Reset database và chạy lại migrations
docker-compose down -v
docker-compose up -d postgres redis
sleep 5
docker-compose up -d migration
docker-compose up -d web worker beat
```

---

**Version**: 1.1
**Last Updated**: 2025-10-02
**Python**: 3.13+
**Docker Compose**: 3.8+