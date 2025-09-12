# Unified Project Structure

Tạo monorepo structure accommodates both backend và optional frontend, được optimize cho Docker development environment.

## Complete Project Structure

```plaintext
google-news-scraper/
├── .github/                     # CI/CD workflows (future)
│   └── workflows/
│       ├── ci.yml              # Test & lint workflow
│       └── deploy.yml          # VPS deployment workflow
├── newspaper4k-master/          # Existing codebase (submodule or copy)
│   ├── newspaper/              # Core newspaper4k functionality
│   ├── tests/                  # Existing tests
│   └── requirements.txt        # newspaper4k dependencies
├── src/                        # Main application source
│   ├── __init__.py
│   ├── main.py                 # Application entry point
│   ├── api/                    # FastAPI application (optional)
│   │   ├── __init__.py
│   │   ├── app.py              # FastAPI app setup
│   │   ├── dependencies.py     # Shared dependencies
│   │   ├── middleware.py       # Auth, CORS, logging middleware
│   │   ├── schemas/            # Pydantic request/response models
│   │   │   ├── __init__.py
│   │   │   ├── category.py
│   │   │   ├── article.py
│   │   │   └── crawl_job.py
│   │   └── routes/             # API endpoints
│   │       ├── __init__.py
│   │       ├── categories.py
│   │       ├── articles.py
│   │       ├── crawl_jobs.py
│   │       └── health.py
│   ├── core/                   # Core business logic
│   │   ├── __init__.py
│   │   ├── crawler/            # Crawler engine
│   │   │   ├── __init__.py
│   │   │   ├── engine.py       # Main crawler orchestration
│   │   │   ├── extractor.py    # newspaper4k wrapper
│   │   │   ├── rate_limiter.py # Rate limiting logic
│   │   │   └── deduplicator.py # Deduplication logic
│   │   ├── scheduler/          # Background job management
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py   # Celery configuration
│   │   │   ├── tasks.py        # Celery tasks
│   │   │   └── cron_scheduler.py # Periodic job setup
│   │   └── category/           # Category management
│   │       ├── __init__.py
│   │       ├── manager.py      # Category business logic
│   │       ├── validator.py    # Keywords validation
│   │       └── search_builder.py # OR logic query builder
│   ├── database/               # Database layer
│   │   ├── __init__.py
│   │   ├── connection.py       # Database connection setup
│   │   ├── models/             # SQLAlchemy models
│   │   │   ├── __init__.py
│   │   │   ├── base.py         # Base model class
│   │   │   ├── article.py      # Article model
│   │   │   ├── category.py     # Category model
│   │   │   └── crawl_job.py    # CrawlJob model
│   │   ├── repositories/       # Data access layer
│   │   │   ├── __init__.py
│   │   │   ├── base.py         # Base repository
│   │   │   ├── article_repo.py
│   │   │   ├── category_repo.py
│   │   │   └── job_repo.py
│   │   └── migrations/         # Alembic migrations
│   │       ├── alembic.ini
│   │       ├── env.py
│   │       └── versions/
│   └── shared/                 # Shared utilities
│       ├── __init__.py
│       ├── config.py           # Pydantic settings
│       ├── logging.py          # Structured logging setup
│       ├── exceptions.py       # Custom exceptions
│       ├── constants.py        # Application constants
│       └── utils.py            # General utilities
├── web/                        # Optional frontend (future)
│   ├── public/                 # Static assets
│   ├── src/
│   │   ├── components/         # React components
│   │   ├── pages/              # Page components
│   │   ├── services/           # API client
│   │   └── types/              # TypeScript types
│   ├── package.json
│   └── vite.config.ts
├── tests/                      # Test suites
│   ├── __init__.py
│   ├── conftest.py            # Pytest configuration
│   ├── unit/                  # Unit tests
│   │   ├── test_crawler.py
│   │   ├── test_category_manager.py
│   │   └── test_repositories.py
│   ├── integration/           # Integration tests
│   │   ├── test_api_endpoints.py
│   │   ├── test_database_ops.py
│   │   └── test_celery_tasks.py
│   └── fixtures/              # Test data
│       ├── categories.json
│       └── articles.json
├── scripts/                   # Utility scripts
│   ├── setup_database.py     # Database initialization
│   ├── seed_categories.py     # Seed initial categories
│   ├── run_crawler.py         # Manual crawl script
│   └── backup_database.py     # Database backup
├── docker/                    # Docker configurations
│   ├── Dockerfile             # Application container
│   ├── Dockerfile.worker      # Celery worker container
│   ├── nginx.conf             # Nginx configuration
│   └── supervisor.conf        # Supervisor process management
├── docs/                      # Documentation
│   ├── prd.md                 # Product requirements
│   ├── architecture/          # Architecture documents
│   │   ├── index.md           # Architecture overview
│   │   ├── tech-stack.md      # Technology decisions
│   │   ├── data-models.md     # Data structure definitions
│   │   └── [other-docs].md    # Additional architecture docs
│   └── api_docs.md            # API documentation
├── .env.example               # Environment variables template
├── .gitignore                 # Git ignore patterns
├── .dockerignore              # Docker ignore patterns
├── docker-compose.yml         # Local development environment
├── docker-compose.prod.yml    # Production environment
├── requirements.txt           # Python dependencies
├── requirements-dev.txt       # Development dependencies
├── pyproject.toml             # Python project configuration
├── pytest.ini                # Pytest configuration
├── alembic.ini                # Alembic configuration
├── celery_beat_schedule.py    # Celery beat schedule
├── supervisord.conf           # Production process management
└── README.md                  # Project documentation
```

## Key Structure Decisions

### 1. Monorepo Approach
- **Rationale:** Tất cả code trong single repository để dễ management và deployment
- **Benefits:** Shared code, unified versioning, simple CI/CD
- **Trade-offs:** Larger repo size, but easier coordination

### 2. newspaper4k-master Integration  
- **Location:** Root level directory `newspaper4k-master/`
- **Approach:** Separate directory, có thể submodule hoặc copy
- **Integration:** Import as dependency trong src/core/crawler/

### 3. src/ Organization
- **Pattern:** Clear separation theo layers (api, core, database, shared)
- **Benefits:** Clean architecture, easy navigation
- **Modules:**
  - `api/` - FastAPI REST interface (optional)
  - `core/` - Business logic và domain services  
  - `database/` - Data persistence layer
  - `shared/` - Common utilities và configuration

### 4. Testing Hierarchy
- **Structure:** Separate unit, integration tests
- **Location:** Top-level `tests/` directory
- **Benefits:** Clear test organization, parallel development

### 5. Docker-First Structure
- **Configuration:** Multiple Dockerfiles cho different services
- **Environment:** Separate compose files cho dev/prod
- **Benefits:** Consistent environments, easy deployment

## Module Import Guidelines

### Python Import Structure
```python
# Standard library imports
import asyncio
import logging
from typing import List, Optional
from uuid import UUID

# Third-party imports
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import newspaper

# Local application imports
from src.shared.config import get_settings
from src.database.models import Article, Category
from src.core.crawler.engine import CrawlerEngine

# newspaper4k-master imports
from newspaper4k_master.newspaper import Config
from newspaper4k_master.newspaper.google_news import GoogleNewsSource
```

### Module Dependencies
```python
# Core dependency flow
src/shared/              # No dependencies
src/database/            # Depends on: shared
src/core/               # Depends on: shared, database
src/api/                # Depends on: shared, database, core
```

## File Naming Conventions

### Python Files
- **Modules:** `snake_case.py` (e.g., `category_manager.py`)
- **Classes:** `PascalCase` (e.g., `CategoryManager`)
- **Functions:** `snake_case` (e.g., `create_category`)
- **Constants:** `UPPER_SNAKE_CASE` (e.g., `MAX_RETRY_COUNT`)

### Configuration Files
- **Docker:** `kebab-case.yml` (e.g., `docker-compose.yml`)
- **Config:** `snake_case.ini` (e.g., `alembic.ini`)
- **Scripts:** `snake_case.py` (e.g., `setup_database.py`)

## Directory Benefits

### Development Benefits
- **Clear boundaries:** Mỗi component có directory riêng
- **Scalable:** Easy to add new modules hoặc split services later
- **Test-friendly:** Tests có thể access tất cả modules
- **IDE support:** Good IntelliSense và navigation

### Production Benefits  
- **Docker-ready:** Containerization built into structure
- **CI/CD ready:** GitHub Actions workflows included
- **Configuration management:** Environment-specific configs
- **Monitoring ready:** Structured logging và health checks

### Maintenance Benefits
- **Documentation co-location:** Docs gần code để easy maintenance
- **Version control:** Single repo cho all components
- **Dependency management:** Centralized requirements
- **Backup simplicity:** Single repo backup

## Growth Path

### Phase 1: MVP (Current)
```
google-news-scraper/
├── src/core/crawler/    # Basic crawling
├── src/database/        # Data persistence
├── src/shared/         # Configuration
└── scripts/            # Manual operations
```

### Phase 2: API Layer
```
+ src/api/              # REST API addition
+ tests/integration/    # API testing
+ docker/nginx.conf     # Reverse proxy
```

### Phase 3: Frontend
```
+ web/                  # React management interface
+ docker/nginx.conf     # Static file serving
+ .github/workflows/    # Frontend CI/CD
```

### Phase 4: Advanced Features
```
+ src/core/analytics/   # Usage analytics
+ src/core/ml/          # Content classification
+ monitoring/           # Advanced monitoring
```

This structure supports organic growth while maintaining clean organization principles.