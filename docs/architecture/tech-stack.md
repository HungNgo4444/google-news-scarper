# Technology Stack

## Technology Stack Table

| Category | Technology | Version | Purpose | Rationale |
|----------|------------|---------|---------|-----------|
| Frontend Language | TypeScript | 5.8+ | Type-safe frontend development | Existing codebase standard, prevents runtime errors |
| Frontend Framework | React | 19.1+ | Component-based UI development | Already implemented, mature ecosystem |
| UI Component Library | Shadcn UI + TailwindCSS | Latest | Modern, accessible UI components | Already integrated, design system ready |
| State Management | React Context + Hooks | Native | Client state management | Sufficient for current scope, no additional dependencies |
| Backend Language | Python | 3.11+ | Backend API development | Existing FastAPI implementation |
| Backend Framework | FastAPI | Latest | High-performance REST API | Already implemented with comprehensive endpoints |
| API Style | REST | OpenAPI 3.0 | HTTP-based API communication | Existing Swagger integration, familiar patterns |
| Database | PostgreSQL | 15+ | Primary data persistence | Already configured with optimized schema |
| Cache | Redis | 7+ | Caching and message broker | Already integrated with Celery |
| File Storage | Local + Future S3 | N/A | Article content and media storage | Start local, plan for cloud migration |
| Authentication | JWT + FastAPI Security | Native | API authentication and authorization | Standard approach, integrates with existing patterns |
| Frontend Testing | Vitest + Testing Library | Latest | Component and integration testing | Already configured in package.json |
| Backend Testing | pytest + FastAPI TestClient | Latest | API and unit testing | Python standard, FastAPI integration |
| E2E Testing | Playwright | Latest | End-to-end workflow testing | Modern, reliable cross-browser testing |
| Build Tool | npm/pip | Latest | Package management and build | Standard tools for each ecosystem |
| Bundler | Vite | 7+ | Frontend bundling and dev server | Already configured, fast development |
| IaC Tool | Docker Compose | Latest | Container orchestration | Already implemented and working |
| CI/CD | GitHub Actions | Latest | Automated testing and deployment | Integration with existing repository |
| Monitoring | Custom Health Endpoints | Native | Basic service monitoring | Already implemented in main.py |
| Logging | Python structlog | Latest | Structured application logging | Already configured with correlation IDs |
| CSS Framework | TailwindCSS | 3.4+ | Utility-first styling | Already integrated with design system |

## Key Technology Decisions

### Frontend Stack
- **React 19**: Latest stable version with improved performance and concurrent features
- **TypeScript**: Type safety across the entire frontend codebase
- **Vite**: Fast build tool with hot module replacement for development
- **Shadcn UI**: Modern component library built on Radix UI primitives
- **TailwindCSS**: Utility-first CSS framework for rapid UI development

### Backend Stack
- **FastAPI**: High-performance Python web framework with automatic OpenAPI documentation
- **SQLAlchemy**: ORM with async support for database operations
- **Alembic**: Database migration tool for schema evolution
- **Celery**: Distributed task queue for background job processing
- **Redis**: In-memory data store for caching and message brokering

### Database & Infrastructure
- **PostgreSQL 15**: ACID-compliant relational database with JSONB support
- **Docker Compose**: Container orchestration for development and deployment
- **Nginx**: Reverse proxy and load balancer
- **GitHub Actions**: CI/CD pipeline for automated testing and deployment

### Development Tools
- **Playwright**: Cross-browser end-to-end testing
- **pytest**: Python testing framework with async support
- **Vitest**: Fast unit testing framework for JavaScript/TypeScript
- **ESLint + Prettier**: Code formatting and linting standards