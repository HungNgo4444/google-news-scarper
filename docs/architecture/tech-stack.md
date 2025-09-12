# Tech Stack

Đây là bảng tech stack CHÍNH THỨC cho toàn bộ project. Tất cả development phải sử dụng chính xác các versions này.

## Technology Stack Table

| Category | Technology | Version | Purpose | Rationale |
|----------|------------|---------|---------|-----------|
| Backend Language | Python | 3.11+ | Core application logic | Tương thích với newspaper4k-master, mature ecosystem |
| Backend Framework | FastAPI | 0.104+ | Optional API endpoints | Modern, fast, type hints support |
| Database | PostgreSQL | 15+ | Primary data storage | Robust, excellent JSON support, scalable |
| Cache/Queue | Redis | 7.2+ | Job queue & caching | Fast, reliable for Celery backend |
| Job Scheduler | Celery | 5.3+ | Background job processing | Mature, scalable, good monitoring |
| Web Crawling | newspaper4k-master | existing | Article extraction & Google News | Already available, proven functionality |
| HTTP Client | requests | 2.31+ | Additional HTTP calls | Standard Python library |
| Database ORM | SQLAlchemy | 2.0+ | Database operations | Type-safe, mature, async support |
| Migration Tool | Alembic | 1.12+ | Database migrations | Integrated với SQLAlchemy |
| Configuration | Pydantic Settings | 2.0+ | Config management | Type validation, environment support |
| Logging | structlog | 23.1+ | Structured logging | Better than standard logging |
| Testing Framework | pytest | 7.4+ | Unit & integration tests | Most popular Python testing |
| HTTP Testing | httpx | 0.25+ | API testing | Async support, modern |
| Containerization | Docker | 24+ | Development environment | Consistent environments |
| Container Orchestration | Docker Compose | 2.21+ | Multi-container setup | Local development orchestration |
| Process Manager | Supervisor | 4.2+ | Production process management | Reliable process monitoring |
| Reverse Proxy | Nginx | 1.25+ | Production deployment | Standard web server |

## Key Technology Decisions

### Python 3.11+
- **Rationale:** Tương thích newspaper4k-master, performance improvements, modern async features
- **Purpose:** Core application language for all business logic

### PostgreSQL 15+  
- **Rationale:** JSON support tốt cho flexible article storage, proven scalability, ACID compliance
- **Purpose:** Primary data storage for articles, categories, và crawl jobs

### Celery + Redis
- **Rationale:** Battle-tested combo cho background processing, mature monitoring tools
- **Purpose:** Asynchronous job queue for scheduled crawling tasks

### FastAPI (Optional)
- **Rationale:** Modern framework với automatic OpenAPI docs, type safety
- **Purpose:** Optional admin interface cho category management

### Docker
- **Rationale:** Consistent development environment, easy VPS deployment, service isolation
- **Purpose:** Containerization cho all services và dependencies