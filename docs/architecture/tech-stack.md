# Tech Stack

## Technology Stack Table

| Category | Technology | Version | Purpose | Rationale |
|----------|------------|---------|---------|-----------|
| Frontend Language | TypeScript | 5.x | Type-safe frontend development | Better development experience and fewer runtime errors |
| Frontend Framework | React | 18.x | UI component framework | Industry standard with excellent ecosystem |
| UI Component Library | Shadcn UI + TailwindCSS | Latest | Styled component system | Consistent design system with utility-first CSS |
| State Management | React Context + useState | Built-in | Client-side state management | Simple solution adequate for admin interface complexity |
| Backend Language | Python | 3.11 | Server-side development | Existing codebase language, excellent for data processing |
| Backend Framework | FastAPI | 0.104+ | REST API framework | Already implemented, provides automatic documentation |
| API Style | REST | OpenAPI 3.0 | HTTP-based API communication | Existing implementation with comprehensive endpoints |
| Database | PostgreSQL | 15 | Primary data storage | Already configured with proper schema and migrations |
| Cache | Redis | 7 | Caching and message broker | Existing implementation for Celery and performance |
| File Storage | Local filesystem | N/A | Article content storage | Current implementation, no external storage needed yet |
| Authentication | FastAPI Security | Built-in | API authentication (future) | Existing framework capability for future auth implementation |
| Frontend Testing | Vitest + Testing Library | Latest | Component and unit testing | Modern, fast testing framework for React applications |
| Backend Testing | Pytest | 7.x+ | API and service testing | Existing testing framework already in use |
| E2E Testing | Playwright | Latest | End-to-end testing | Modern, reliable E2E testing across browsers |
| Build Tool | Vite | Latest | Frontend build system | Fast development server and optimized production builds |
| Bundler | Vite (built-in) | Latest | Module bundling | Integrated with Vite, modern ES modules support |
| IaC Tool | Docker Compose | 3.8+ | Container orchestration | Already configured and proven for development/production |
| CI/CD | GitHub Actions | Latest | Automated build and deployment | Industry standard with excellent Docker integration |
| Monitoring | Docker logs + Flower | Current | Application monitoring | Leverage existing Celery monitoring, expand as needed |
| Logging | Python logging + Console | Built-in | Application logging | Extend existing backend logging to frontend |
| CSS Framework | TailwindCSS | 3.x | Utility-first styling | Excellent developer experience and design consistency |
