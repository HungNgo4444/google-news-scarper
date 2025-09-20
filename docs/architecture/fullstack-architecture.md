# Google News Scraper Fullstack Architecture Document

## Introduction

This document outlines the complete fullstack architecture for the Google News Scraper job-centric article management enhancement, including backend systems, frontend implementation, and their integration. It serves as the single source of truth for AI-driven development, ensuring consistency across the entire technology stack.

This unified approach combines what would traditionally be separate backend and frontend architecture documents, streamlining the development process for modern fullstack applications where these concerns are increasingly intertwined.

### Starter Template or Existing Project

**Status:** Brownfield Enhancement - Existing Production System

**Current Infrastructure Assessment:**
- ✅ **FastAPI Backend**: Production-ready REST APIs with comprehensive endpoints
- ✅ **PostgreSQL Database**: Full article/category/job models with optimized schema
- ✅ **Redis + Celery**: Task queue system with priority queue support
- ✅ **Docker Architecture**: Containerized deployment with health checks
- ✅ **React + TypeScript Frontend**: Foundation with Categories CRUD completed
- ✅ **Component Library**: Shadcn UI with TailwindCSS integration

**Enhancement Scope:**
Transform from basic category management to a comprehensive job-centric article management system with integrated scheduling capabilities. 90% of backend infrastructure exists; frontend components need enhancement to leverage existing powerful backend capabilities.

### Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2025-09-15 | v1.0 | Initial fullstack architecture for job-centric enhancement | Winston (Architect) |

## High Level Architecture

### Technical Summary

The Google News Scraper employs a containerized microservices architecture with FastAPI backend services, React frontend, and PostgreSQL persistence layer, orchestrated through Docker Compose. The system utilizes Redis-backed Celery for distributed task processing with priority queues, enabling real-time job management and article crawling workflows. Frontend-backend integration occurs through RESTful APIs with TypeScript interfaces ensuring type safety across the stack. The architecture supports horizontal scaling through container orchestration and leverages existing infrastructure while adding job-centric article viewing and integrated scheduling capabilities. This brownfield enhancement maintains backward compatibility while introducing advanced priority-based job queue management and seamless category-to-schedule workflow integration.

### Platform and Infrastructure Choice

**Platform:** Docker-based Containerized Architecture with Local/Cloud Flexibility
**Key Services:**
- PostgreSQL 15 (Primary Database)
- Redis 7 (Cache & Message Broker)
- FastAPI (REST API Layer)
- React 19 + Vite (Frontend)
- Celery + Beat (Task Queue & Scheduler)
- Nginx (Reverse Proxy)

**Deployment Host and Regions:** Flexible deployment supporting local development, VPS, or cloud providers (AWS/Azure/GCP)

### Repository Structure

**Structure:** Monorepo with Frontend/Backend Separation
**Monorepo Tool:** Native npm workspaces (simple, effective for this project size)
**Package Organization:** Frontend (React app), Backend (FastAPI), Shared (TypeScript interfaces)

### High Level Architecture Diagram

```mermaid
graph TB
    subgraph "Client Layer"
        WEB[Web Browser]
        MOBILE[Mobile Browser]
    end

    subgraph "CDN/Proxy Layer"
        NGINX[Nginx Reverse Proxy]
    end

    subgraph "Frontend Layer"
        REACT[React Frontend<br/>Vite + TypeScript]
    end

    subgraph "API Layer"
        FASTAPI[FastAPI Backend<br/>REST API + Swagger]
    end

    subgraph "Task Processing Layer"
        CELERY[Celery Workers]
        BEAT[Celery Beat Scheduler]
    end

    subgraph "Data Layer"
        POSTGRES[(PostgreSQL<br/>Articles, Jobs, Categories)]
        REDIS[(Redis<br/>Cache + Message Broker)]
    end

    subgraph "External Services"
        GNEWS[Google News API]
        NEWS4K[Newspaper4k Library]
    end

    WEB --> NGINX
    MOBILE --> NGINX
    NGINX --> REACT
    REACT --> FASTAPI
    FASTAPI --> POSTGRES
    FASTAPI --> REDIS
    FASTAPI --> CELERY
    BEAT --> REDIS
    CELERY --> POSTGRES
    CELERY --> GNEWS
    CELERY --> NEWS4K
    CELERY --> REDIS
```

### Architectural Patterns

- **Container-Based Microservices:** Loosely coupled services with clear boundaries - _Rationale:_ Enables independent scaling and deployment of components
- **Job-Centric Architecture:** UI and data flow organized around crawl jobs - _Rationale:_ Aligns with PRD requirements for job-specific article viewing and management
- **Queue-Based Task Processing:** Asynchronous job processing with priority queues - _Rationale:_ Supports "Run Now" functionality and scalable crawling operations
- **Repository Pattern:** Abstract data access logic for articles, jobs, categories - _Rationale:_ Enables testing and maintains clean separation of concerns
- **Component-Based UI:** Reusable React components with TypeScript - _Rationale:_ Maintainability and type safety across large codebases
- **RESTful API Design:** Standard HTTP methods with clear resource endpoints - _Rationale:_ Simplicity, caching capabilities, and frontend integration ease

## Tech Stack

### Technology Stack Table

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

## Data Models

### CrawlJob

**Purpose:** Tracks individual crawling operations with status, metrics, and job configuration

**Key Attributes:**
- id: UUID - Unique job identifier
- category_id: UUID - Reference to crawled category
- status: Enum - Current job state (pending/running/completed/failed)
- celery_task_id: String - Celery task tracking ID
- started_at/completed_at: DateTime - Job execution timing
- articles_found/articles_saved: Integer - Job success metrics
- priority: Integer - Queue priority for "Run Now" functionality
- correlation_id: String - Request tracing across services

#### TypeScript Interface

```typescript
export interface CrawlJob {
  id: string;
  category_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  celery_task_id?: string;
  started_at?: string;
  completed_at?: string;
  articles_found: number;
  articles_saved: number;
  error_message?: string;
  retry_count: number;
  priority: number;
  job_metadata?: Record<string, any>;
  correlation_id?: string;
  created_at: string;
  updated_at: string;
}
```

#### Relationships
- Belongs to one Category
- Associated with multiple Articles through job execution
- Tracked by Celery task system

### Category

**Purpose:** Defines news categories with keywords and scheduling configuration

**Key Attributes:**
- id: UUID - Unique category identifier
- name: String - Category display name
- keywords: String[] - Search terms for crawling
- is_active: Boolean - Category activation status
- exclude_keywords: String[] - Terms to filter out
- schedule_config: Object - Auto-crawl scheduling settings

#### TypeScript Interface

```typescript
export interface Category {
  id: string;
  name: string;
  keywords: string[];
  is_active: boolean;
  exclude_keywords?: string[];
  created_at: string;
  updated_at: string;
}

export interface CategorySchedule {
  id: string;
  category_id: string;
  interval_minutes: number;
  is_active: boolean;
  next_run_at?: string;
  last_run_at?: string;
  run_history: ScheduleRun[];
}
```

#### Relationships
- Has many CrawlJobs
- Has one CategorySchedule (optional)
- Associated with Articles through crawl jobs

### Article

**Purpose:** Stores crawled news articles with metadata and content

**Key Attributes:**
- id: UUID - Unique article identifier
- url: String - Original article URL
- title: String - Article headline
- content: Text - Full article content
- publish_date: DateTime - Article publication date
- crawl_job_id: UUID - Job that found this article

#### TypeScript Interface

```typescript
export interface Article {
  id: string;
  url: string;
  title: string;
  content: string;
  summary?: string;
  publish_date: string;
  author?: string;
  image_url?: string;
  keywords_matched: string[];
  relevance_score: number;
  crawl_job_id?: string;
  created_at: string;
  updated_at: string;
}
```

#### Relationships
- Belongs to one or more Categories (many-to-many)
- Associated with CrawlJob that discovered it
- Can have multiple keyword matches

## API Specification

### REST API Specification

```yaml
openapi: 3.0.0
info:
  title: Google News Scraper API
  version: 1.0.0
  description: REST API for job-centric article management and crawling automation
servers:
  - url: http://localhost:8000/api/v1
    description: Development server
  - url: https://api.yourapp.com/api/v1
    description: Production server

paths:
  # Jobs Management (Enhanced)
  /jobs:
    get:
      summary: List crawl jobs with filtering
      parameters:
        - name: status
          in: query
          schema:
            type: string
            enum: [pending, running, completed, failed]
        - name: category_id
          in: query
          schema:
            type: string
            format: uuid
        - name: page
          in: query
          schema:
            type: integer
            default: 1
        - name: size
          in: query
          schema:
            type: integer
            default: 20
      responses:
        200:
          description: Paginated list of jobs
          content:
            application/json:
              schema:
                type: object
                properties:
                  items:
                    type: array
                    items:
                      $ref: '#/components/schemas/CrawlJob'
                  total:
                    type: integer
                  page:
                    type: integer
                  pages:
                    type: integer

    post:
      summary: Create new crawl job
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                category_id:
                  type: string
                  format: uuid
                priority:
                  type: integer
                  default: 0
              required:
                - category_id
      responses:
        201:
          description: Job created successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CrawlJob'

  /jobs/{job_id}:
    get:
      summary: Get job details
      parameters:
        - name: job_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      responses:
        200:
          description: Job details
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CrawlJob'

    put:
      summary: Update job configuration
      parameters:
        - name: job_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                priority:
                  type: integer
                retry_count:
                  type: integer
                job_metadata:
                  type: object
      responses:
        200:
          description: Job updated successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CrawlJob'

    delete:
      summary: Delete job
      parameters:
        - name: job_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      responses:
        204:
          description: Job deleted successfully

  /jobs/{job_id}/priority:
    patch:
      summary: Update job priority (Run Now functionality)
      parameters:
        - name: job_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                priority:
                  type: integer
                  description: Higher values = higher priority
              required:
                - priority
      responses:
        200:
          description: Priority updated successfully

  # Articles API (New)
  /articles:
    get:
      summary: List articles with job filtering
      parameters:
        - name: job_id
          in: query
          schema:
            type: string
            format: uuid
          description: Filter by specific crawl job
        - name: category_id
          in: query
          schema:
            type: string
            format: uuid
        - name: search
          in: query
          schema:
            type: string
          description: Search in title and content
        - name: page
          in: query
          schema:
            type: integer
            default: 1
        - name: size
          in: query
          schema:
            type: integer
            default: 20
      responses:
        200:
          description: Paginated list of articles
          content:
            application/json:
              schema:
                type: object
                properties:
                  items:
                    type: array
                    items:
                      $ref: '#/components/schemas/Article'
                  total:
                    type: integer
                  page:
                    type: integer
                  pages:
                    type: integer

  /articles/export:
    post:
      summary: Export articles in various formats
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                job_id:
                  type: string
                  format: uuid
                format:
                  type: string
                  enum: [json, csv, xlsx]
                fields:
                  type: array
                  items:
                    type: string
              required:
                - format
      responses:
        200:
          description: Exported file
          content:
            application/json:
              schema:
                type: object
            text/csv:
              schema:
                type: string
            application/vnd.openxmlformats-officedocument.spreadsheetml.sheet:
              schema:
                type: string
                format: binary

  # Categories with Scheduling (Enhanced)
  /categories/{category_id}/schedules:
    get:
      summary: Get category schedule configuration
      parameters:
        - name: category_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      responses:
        200:
          description: Schedule configuration
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CategorySchedule'

    post:
      summary: Create or update category schedule
      parameters:
        - name: category_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                interval_minutes:
                  type: integer
                  description: Schedule interval in minutes
                is_active:
                  type: boolean
              required:
                - interval_minutes
                - is_active
      responses:
        201:
          description: Schedule created/updated
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CategorySchedule'

components:
  schemas:
    CrawlJob:
      type: object
      properties:
        id:
          type: string
          format: uuid
        category_id:
          type: string
          format: uuid
        status:
          type: string
          enum: [pending, running, completed, failed]
        celery_task_id:
          type: string
        started_at:
          type: string
          format: date-time
        completed_at:
          type: string
          format: date-time
        articles_found:
          type: integer
        articles_saved:
          type: integer
        error_message:
          type: string
        retry_count:
          type: integer
        priority:
          type: integer
        job_metadata:
          type: object
        correlation_id:
          type: string
        created_at:
          type: string
          format: date-time
        updated_at:
          type: string
          format: date-time

    Article:
      type: object
      properties:
        id:
          type: string
          format: uuid
        url:
          type: string
          format: uri
        title:
          type: string
        content:
          type: string
        summary:
          type: string
        publish_date:
          type: string
          format: date-time
        author:
          type: string
        image_url:
          type: string
          format: uri
        keywords_matched:
          type: array
          items:
            type: string
        relevance_score:
          type: number
          format: float
        crawl_job_id:
          type: string
          format: uuid
        created_at:
          type: string
          format: date-time
        updated_at:
          type: string
          format: date-time

    CategorySchedule:
      type: object
      properties:
        id:
          type: string
          format: uuid
        category_id:
          type: string
          format: uuid
        interval_minutes:
          type: integer
        is_active:
          type: boolean
        next_run_at:
          type: string
          format: date-time
        last_run_at:
          type: string
          format: date-time
        created_at:
          type: string
          format: date-time
        updated_at:
          type: string
          format: date-time

  securitySchemes:
    ApiKeyAuth:
      type: apiKey
      in: header
      name: X-API-Key
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT

security:
  - ApiKeyAuth: []
  - BearerAuth: []
```

## Components

### FastAPI Backend Service

**Responsibility:** Core API service providing REST endpoints for job management, article retrieval, and category scheduling

**Key Interfaces:**
- `/api/v1/jobs` - Complete CRUD operations with priority management
- `/api/v1/articles` - Article listing with job-based filtering and export
- `/api/v1/categories/{id}/schedules` - Integrated scheduling configuration
- Health check endpoints for container orchestration

**Dependencies:** PostgreSQL database, Redis cache, Celery task queue

**Technology Stack:** Python 3.11+, FastAPI, SQLAlchemy, Alembic, Pydantic schemas

### React Frontend Application

**Responsibility:** User interface for job-centric article management and category scheduling

**Key Interfaces:**
- JobsList component with action buttons (Run Now, Edit, Delete, View Articles)
- JobArticlesModal for article viewing with export functionality
- Enhanced CategoryForm with integrated Schedules tab
- Real-time job status monitoring with WebSocket consideration

**Dependencies:** FastAPI backend API, Authentication service

**Technology Stack:** React 19, TypeScript, Vite, TailwindCSS, Shadcn UI components

### Celery Task Processing Service

**Responsibility:** Asynchronous crawling operations with priority queue management and scheduling

**Key Interfaces:**
- Priority-based job execution queue
- Celery Beat integration for scheduled crawling
- Real-time status updates via Redis
- Error handling and retry mechanisms

**Dependencies:** Redis message broker, Google News API, Newspaper4k library

**Technology Stack:** Celery 5.3+, Redis 7, Python asyncio, Celery Beat scheduler

### PostgreSQL Database Service

**Responsibility:** Primary data persistence for articles, jobs, categories, and scheduling configuration

**Key Interfaces:**
- Optimized queries for job-article associations
- JSONB support for flexible job metadata
- Full-text search capabilities for articles
- Efficient indexing for real-time job status queries

**Dependencies:** None (base infrastructure)

**Technology Stack:** PostgreSQL 15, optimized with performance tuning parameters

### Component Diagrams

```mermaid
graph TB
    subgraph "Frontend Layer"
        UI[React UI Components]
        STATE[State Management]
        API_CLIENT[API Client Services]
    end

    subgraph "API Gateway Layer"
        ROUTER[FastAPI Router]
        AUTH[Auth Middleware]
        CORS[CORS Middleware]
    end

    subgraph "Business Logic Layer"
        JOB_SVC[Job Service]
        ARTICLE_SVC[Article Service]
        CATEGORY_SVC[Category Service]
        SCHEDULE_SVC[Schedule Service]
    end

    subgraph "Data Access Layer"
        JOB_REPO[Job Repository]
        ARTICLE_REPO[Article Repository]
        CATEGORY_REPO[Category Repository]
    end

    subgraph "Task Processing Layer"
        CELERY_WORKER[Celery Workers]
        CELERY_BEAT[Celery Beat]
        TASK_QUEUE[Redis Task Queue]
    end

    subgraph "Data Storage Layer"
        POSTGRES[(PostgreSQL)]
        REDIS[(Redis Cache)]
    end

    UI --> STATE
    STATE --> API_CLIENT
    API_CLIENT --> ROUTER
    ROUTER --> AUTH
    AUTH --> CORS
    CORS --> JOB_SVC
    CORS --> ARTICLE_SVC
    CORS --> CATEGORY_SVC
    CORS --> SCHEDULE_SVC

    JOB_SVC --> JOB_REPO
    ARTICLE_SVC --> ARTICLE_REPO
    CATEGORY_SVC --> CATEGORY_REPO
    SCHEDULE_SVC --> CELERY_BEAT

    JOB_REPO --> POSTGRES
    ARTICLE_REPO --> POSTGRES
    CATEGORY_REPO --> POSTGRES

    JOB_SVC --> TASK_QUEUE
    TASK_QUEUE --> CELERY_WORKER
    CELERY_BEAT --> TASK_QUEUE
    CELERY_WORKER --> POSTGRES
    CELERY_WORKER --> REDIS
```

## External APIs

### Google News API

- **Purpose:** Primary news source for article discovery and crawling
- **Documentation:** https://newsapi.org/docs (assuming NewsAPI or similar service)
- **Base URL(s):** https://newsapi.org/v2
- **Authentication:** API Key in request headers
- **Rate Limits:** 1000 requests/day (free tier), upgrade for production

**Key Endpoints Used:**
- `GET /everything` - Search articles by keywords and date range
- `GET /top-headlines` - Get breaking news by category/country

**Integration Notes:** Newspaper4k library handles article content extraction after URL discovery via Google News RSS feeds

### Newspaper4k Library Integration

- **Purpose:** Article content extraction, parsing, and metadata extraction
- **Documentation:** https://newspaper.readthedocs.io/
- **Base URL(s):** N/A (Python library)
- **Authentication:** None required
- **Rate Limits:** Dependent on target website rate limiting

**Key Endpoints Used:**
- Article.download() - Fetch article content
- Article.parse() - Extract title, content, metadata
- Article.nlp() - Generate summaries and extract keywords

**Integration Notes:** Handles Vietnamese character encoding (UTF-8), supports multiple content formats, includes built-in caching mechanisms

## Core Workflows

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant FastAPI
    participant Celery
    participant Database
    participant GoogleNews

    Note over User,GoogleNews: Job-Centric Article Management Workflow

    User->>Frontend: Click "View Articles" on job
    Frontend->>FastAPI: GET /api/v1/articles?job_id={id}
    FastAPI->>Database: Query articles by job_id
    Database-->>FastAPI: Return article list with metadata
    FastAPI-->>Frontend: Return paginated articles
    Frontend-->>User: Display articles with export option

    User->>Frontend: Click "Run Now" on pending job
    Frontend->>FastAPI: PATCH /api/v1/jobs/{id}/priority
    FastAPI->>Database: Update job priority to high
    FastAPI->>Celery: Send high-priority task
    Celery->>GoogleNews: Search for articles
    GoogleNews-->>Celery: Return article URLs
    Celery->>Database: Save articles with job_id
    Celery-->>FastAPI: Update job status to completed
    FastAPI-->>Frontend: Real-time status update
    Frontend-->>User: Show job completion

    User->>Frontend: Configure category schedule
    Frontend->>FastAPI: POST /api/v1/categories/{id}/schedules
    FastAPI->>Database: Save schedule configuration
    FastAPI->>Celery: Update Beat scheduler
    Celery-->>FastAPI: Confirm schedule activation
    FastAPI-->>Frontend: Schedule created successfully
    Frontend-->>User: Show next run time

    Note over Celery,Database: Automated Scheduled Crawling
    Celery->>Database: Create new scheduled job
    Celery->>GoogleNews: Execute scheduled crawl
    GoogleNews-->>Celery: Return articles
    Celery->>Database: Save articles and update job
```

## Database Schema

Based on the existing PostgreSQL implementation, here's the enhanced schema for job-centric functionality:

```sql
-- Enhanced CrawlJob table (existing, optimized)
CREATE TABLE crawl_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id UUID NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    status crawljobstatus NOT NULL DEFAULT 'pending',
    celery_task_id VARCHAR(255) UNIQUE,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    articles_found INTEGER NOT NULL DEFAULT 0,
    articles_saved INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    priority INTEGER NOT NULL DEFAULT 0,
    job_metadata JSONB DEFAULT '{}',
    correlation_id VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Constraints
    CONSTRAINT articles_found_non_negative CHECK (articles_found >= 0),
    CONSTRAINT articles_saved_non_negative CHECK (articles_saved >= 0),
    CONSTRAINT articles_saved_not_exceed_found CHECK (articles_saved <= articles_found),
    CONSTRAINT retry_count_non_negative CHECK (retry_count >= 0),
    CONSTRAINT retry_count_max_limit CHECK (retry_count <= 10),
    CONSTRAINT started_at_status_consistency CHECK (
        (started_at IS NULL AND status = 'pending') OR
        (started_at IS NOT NULL AND status != 'pending')
    ),
    CONSTRAINT completed_at_status_consistency CHECK (
        (completed_at IS NULL AND status IN ('pending', 'running')) OR
        (completed_at IS NOT NULL AND status IN ('completed', 'failed'))
    ),
    CONSTRAINT completion_after_start CHECK (
        started_at IS NULL OR completed_at IS NULL OR completed_at >= started_at
    )
);

-- New CategorySchedule table for integrated scheduling
CREATE TABLE category_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id UUID NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    interval_minutes INTEGER NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    next_run_at TIMESTAMPTZ,
    last_run_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Constraints
    CONSTRAINT interval_positive CHECK (interval_minutes > 0),
    CONSTRAINT interval_reasonable CHECK (interval_minutes >= 15), -- Minimum 15 minutes
    CONSTRAINT unique_category_schedule UNIQUE (category_id)
);

-- Enhanced Articles table with job tracking
ALTER TABLE articles ADD COLUMN IF NOT EXISTS crawl_job_id UUID REFERENCES crawl_jobs(id);
ALTER TABLE articles ADD COLUMN IF NOT EXISTS keywords_matched TEXT[];
ALTER TABLE articles ADD COLUMN IF NOT EXISTS relevance_score REAL DEFAULT 0.0;

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_articles_crawl_job_id ON articles(crawl_job_id);
CREATE INDEX IF NOT EXISTS idx_articles_keywords_matched_gin ON articles USING gin(keywords_matched);
CREATE INDEX IF NOT EXISTS idx_articles_relevance_score ON articles(relevance_score DESC);
CREATE INDEX IF NOT EXISTS idx_crawl_jobs_priority_status ON crawl_jobs(priority DESC, status, created_at);
CREATE INDEX IF NOT EXISTS idx_category_schedules_next_run ON category_schedules(next_run_at) WHERE is_active = true;

-- Full-text search for articles
CREATE INDEX IF NOT EXISTS idx_articles_fulltext ON articles USING gin(to_tsvector('english', title || ' ' || COALESCE(content, '')));

-- Trigger for automatic updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_crawl_jobs_updated_at BEFORE UPDATE ON crawl_jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_category_schedules_updated_at BEFORE UPDATE ON category_schedules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

## Frontend Architecture

### Component Architecture

#### Component Organization

```
src/
├── components/           # Reusable UI components
│   ├── ui/              # Shadcn UI base components
│   ├── jobs/            # Job-related components
│   │   ├── JobsList.tsx
│   │   ├── JobArticlesModal.tsx
│   │   ├── JobEditModal.tsx
│   │   ├── JobStatusBadge.tsx
│   │   └── PriorityControls.tsx
│   ├── articles/        # Article components
│   │   ├── ArticleList.tsx
│   │   ├── ArticleExport.tsx
│   │   └── ArticlePreview.tsx
│   ├── categories/      # Enhanced category components
│   │   ├── CategoryForm.tsx
│   │   ├── ScheduleTab.tsx
│   │   └── ScheduleHistory.tsx
│   └── common/          # Shared components
│       ├── LoadingSpinner.tsx
│       ├── ErrorBoundary.tsx
│       └── ConfirmDialog.tsx
├── hooks/               # Custom React hooks
│   ├── useJobs.ts
│   ├── useArticles.ts
│   ├── useSchedules.ts
│   └── useRealTimeUpdates.ts
├── services/            # API client services
├── types/               # TypeScript type definitions
├── utils/               # Helper functions
└── pages/               # Page components
```

#### Component Template

```typescript
import React from 'react';
import { cn } from '@/lib/utils';

interface JobArticlesModalProps {
  jobId: string;
  isOpen: boolean;
  onClose: () => void;
  className?: string;
}

export const JobArticlesModal: React.FC<JobArticlesModalProps> = ({
  jobId,
  isOpen,
  onClose,
  className
}) => {
  const { articles, loading, error } = useArticles({ jobId });

  if (!isOpen) return null;

  return (
    <div className={cn("fixed inset-0 z-50 bg-black/50", className)}>
      <div className="flex items-center justify-center min-h-screen p-4">
        <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[80vh] overflow-hidden">
          <div className="p-6 border-b border-gray-200">
            <h2 className="text-xl font-semibold">Articles from Job</h2>
            <button
              onClick={onClose}
              className="absolute top-4 right-4 text-gray-500 hover:text-gray-700"
            >
              ✕
            </button>
          </div>

          <div className="p-6 overflow-y-auto">
            {loading && <LoadingSpinner />}
            {error && <ErrorMessage error={error} />}
            {articles && (
              <ArticleList
                articles={articles}
                showExport={true}
                jobId={jobId}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
```

### State Management Architecture

#### State Structure

```typescript
// Global Application State
interface AppState {
  user: UserState;
  jobs: JobsState;
  articles: ArticlesState;
  categories: CategoriesState;
  schedules: SchedulesState;
  ui: UIState;
}

interface JobsState {
  jobs: CrawlJob[];
  currentJob: CrawlJob | null;
  loading: boolean;
  error: string | null;
  filters: JobFilters;
  pagination: PaginationState;
}

interface ArticlesState {
  articles: Article[];
  loading: boolean;
  error: string | null;
  filters: ArticleFilters;
  exportStatus: ExportStatus;
}

interface SchedulesState {
  schedules: Map<string, CategorySchedule>; // Keyed by category_id
  loading: boolean;
  error: string | null;
}

interface UIState {
  modals: {
    jobArticles: { isOpen: boolean; jobId: string | null };
    jobEdit: { isOpen: boolean; jobId: string | null };
    scheduleConfig: { isOpen: boolean; categoryId: string | null };
  };
  notifications: Notification[];
  theme: 'light' | 'dark';
}
```

#### State Management Patterns

- **Context Providers:** Separate contexts for Jobs, Articles, Categories, and UI state
- **Custom Hooks:** Encapsulate state logic and API calls (useJobs, useArticles, useSchedules)
- **Optimistic Updates:** Immediate UI updates for priority changes with rollback on failure
- **Real-time Sync:** WebSocket connection for job status updates across components
- **Local Storage:** Persist user preferences, filters, and UI state

### Routing Architecture

#### Route Organization

```
/                           # Dashboard overview
├── /jobs                   # Jobs management page
│   ├── /jobs/:id           # Job detail view
│   └── /jobs/:id/articles  # Job articles view
├── /categories             # Categories management
│   ├── /categories/:id     # Category detail/edit
│   └── /categories/:id/schedule # Category scheduling
├── /articles               # Global articles view
└── /settings              # Application settings
```

#### Protected Route Pattern

```typescript
import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRole?: string;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  requiredRole
}) => {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return <LoadingSpinner />;
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (requiredRole && user.role !== requiredRole) {
    return <Navigate to="/unauthorized" replace />;
  }

  return <>{children}</>;
};
```

### Frontend Services Layer

#### API Client Setup

```typescript
import axios, { AxiosInstance, AxiosRequestConfig } from 'axios';

class ApiClient {
  private client: AxiosInstance;

  constructor(baseURL: string) {
    this.client = axios.create({
      baseURL,
      timeout: 10000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
  }

  private setupInterceptors() {
    // Request interceptor for auth token
    this.client.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('auth_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          localStorage.removeItem('auth_token');
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }
    );
  }

  async get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.get<T>(url, config);
    return response.data;
  }

  async post<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.post<T>(url, data, config);
    return response.data;
  }

  async patch<T>(url: string, data?: any, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.patch<T>(url, data, config);
    return response.data;
  }

  async delete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await this.client.delete<T>(url, config);
    return response.data;
  }
}

export const apiClient = new ApiClient(import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1');
```

#### Service Example

```typescript
import { apiClient } from './apiClient';
import { CrawlJob, Article, PaginatedResponse } from '@/types';

export class JobsService {
  static async getJobs(params?: {
    status?: string;
    category_id?: string;
    page?: number;
    size?: number;
  }): Promise<PaginatedResponse<CrawlJob>> {
    return apiClient.get<PaginatedResponse<CrawlJob>>('/jobs', { params });
  }

  static async updateJobPriority(jobId: string, priority: number): Promise<CrawlJob> {
    return apiClient.patch<CrawlJob>(`/jobs/${jobId}/priority`, { priority });
  }

  static async getJobArticles(jobId: string, params?: {
    page?: number;
    size?: number;
    search?: string;
  }): Promise<PaginatedResponse<Article>> {
    return apiClient.get<PaginatedResponse<Article>>(`/articles`, {
      params: { job_id: jobId, ...params }
    });
  }

  static async exportJobArticles(jobId: string, format: 'json' | 'csv' | 'xlsx'): Promise<Blob> {
    const response = await apiClient.post<Blob>('/articles/export',
      { job_id: jobId, format },
      { responseType: 'blob' }
    );
    return response;
  }

  static async deleteJob(jobId: string): Promise<void> {
    return apiClient.delete(`/jobs/${jobId}`);
  }
}
```

## Backend Architecture

### Service Architecture

#### Traditional Server Architecture

The Google News Scraper uses a traditional FastAPI server architecture with clear separation of concerns:

#### Controller/Route Organization

```
src/api/
├── main.py                 # FastAPI app configuration
├── routes/                 # API route handlers
│   ├── __init__.py
│   ├── jobs.py            # Enhanced job management routes
│   ├── articles.py        # New article API routes
│   ├── categories.py      # Enhanced category routes
│   └── schedules.py       # New scheduling routes
├── schemas/               # Pydantic request/response models
│   ├── job.py
│   ├── article.py
│   ├── category.py
│   └── schedule.py
├── dependencies/          # FastAPI dependencies
│   ├── auth.py
│   ├── database.py
│   └── pagination.py
└── middleware/           # Custom middleware
    ├── cors.py
    ├── logging.py
    └── error_handling.py
```

#### Controller Template

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from src.database.connection import get_database_session
from src.database.repositories.job_repo import CrawlJobRepository
from src.api.schemas.job import JobResponse, JobUpdate, PriorityUpdate
from src.api.dependencies.pagination import PaginationParams
from src.core.scheduler.tasks import update_job_priority_task

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.get("/", response_model=PaginatedResponse[JobResponse])
async def list_jobs(
    status: Optional[str] = Query(None),
    category_id: Optional[str] = Query(None),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_database_session)
):
    """List crawl jobs with filtering and pagination."""
    job_repo = CrawlJobRepository(db)

    jobs, total = await job_repo.get_paginated_jobs(
        status=status,
        category_id=category_id,
        page=pagination.page,
        size=pagination.size
    )

    return PaginatedResponse(
        items=[JobResponse.from_orm(job) for job in jobs],
        total=total,
        page=pagination.page,
        pages=(total + pagination.size - 1) // pagination.size
    )

@router.patch("/{job_id}/priority", response_model=JobResponse)
async def update_job_priority(
    job_id: str,
    priority_update: PriorityUpdate,
    db: AsyncSession = Depends(get_database_session)
):
    """Update job priority for Run Now functionality."""
    job_repo = CrawlJobRepository(db)

    job = await job_repo.get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Update priority in database
    updated_job = await job_repo.update_job_priority(
        job_id,
        priority_update.priority
    )

    # Trigger Celery priority update if job is pending
    if updated_job.status == "pending":
        await update_job_priority_task.delay(job_id, priority_update.priority)

    return JobResponse.from_orm(updated_job)

@router.delete("/{job_id}")
async def delete_job(
    job_id: str,
    db: AsyncSession = Depends(get_database_session)
):
    """Delete crawl job with confirmation."""
    job_repo = CrawlJobRepository(db)

    job = await job_repo.get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status == "running":
        raise HTTPException(
            status_code=400,
            detail="Cannot delete running job"
        )

    await job_repo.delete_job(job_id)
    return {"message": "Job deleted successfully"}
```

### Database Architecture

#### Schema Design

The enhanced schema builds upon the existing PostgreSQL structure:

```sql
-- Job priority and article association enhancements
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_crawl_jobs_priority_queue
ON crawl_jobs(priority DESC, created_at ASC)
WHERE status = 'pending';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_articles_job_metadata
ON articles USING gin((CASE WHEN crawl_job_id IS NOT NULL
THEN jsonb_build_object('job_id', crawl_job_id)
ELSE '{}'::jsonb END));

-- Materialized view for job statistics
CREATE MATERIALIZED VIEW job_statistics AS
SELECT
    j.id as job_id,
    j.category_id,
    j.status,
    j.articles_found,
    j.articles_saved,
    COUNT(a.id) as articles_associated,
    AVG(a.relevance_score) as avg_relevance_score,
    j.duration_seconds
FROM crawl_jobs j
LEFT JOIN articles a ON a.crawl_job_id = j.id
GROUP BY j.id, j.category_id, j.status, j.articles_found, j.articles_saved, j.duration_seconds;

CREATE UNIQUE INDEX ON job_statistics (job_id);
CREATE INDEX ON job_statistics (category_id, status);

-- Refresh schedule for materialized view
CREATE OR REPLACE FUNCTION refresh_job_statistics()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY job_statistics;
END;
$$ LANGUAGE plpgsql;
```

#### Data Access Layer

```python
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.orm import selectinload, joinedload

from src.database.models.crawl_job import CrawlJob, CrawlJobStatus
from src.database.models.article import Article
from src.database.repositories.base import BaseRepository

class CrawlJobRepository(BaseRepository[CrawlJob]):
    def __init__(self, db: AsyncSession):
        super().__init__(CrawlJob, db)

    async def get_paginated_jobs(
        self,
        status: Optional[str] = None,
        category_id: Optional[str] = None,
        page: int = 1,
        size: int = 20
    ) -> Tuple[List[CrawlJob], int]:
        """Get paginated jobs with optional filtering."""
        query = select(CrawlJob).options(
            joinedload(CrawlJob.category)
        )

        # Apply filters
        if status:
            query = query.where(CrawlJob.status == status)
        if category_id:
            query = query.where(CrawlJob.category_id == category_id)

        # Get total count
        count_query = select(func.count(CrawlJob.id))
        if status:
            count_query = count_query.where(CrawlJob.status == status)
        if category_id:
            count_query = count_query.where(CrawlJob.category_id == category_id)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        # Apply pagination and ordering
        query = query.order_by(
            CrawlJob.priority.desc(),
            CrawlJob.created_at.desc()
        ).offset((page - 1) * size).limit(size)

        result = await self.db.execute(query)
        jobs = result.scalars().all()

        return list(jobs), total

    async def update_job_priority(
        self,
        job_id: str,
        priority: int
    ) -> CrawlJob:
        """Update job priority with atomic operation."""
        stmt = (
            update(CrawlJob)
            .where(CrawlJob.id == job_id)
            .values(priority=priority, updated_at=func.now())
            .returning(CrawlJob)
        )

        result = await self.db.execute(stmt)
        await self.db.commit()

        return result.scalar_one()

    async def get_jobs_by_priority(
        self,
        limit: int = 10
    ) -> List[CrawlJob]:
        """Get pending jobs ordered by priority for queue processing."""
        query = (
            select(CrawlJob)
            .where(CrawlJob.status == CrawlJobStatus.PENDING)
            .order_by(
                CrawlJob.priority.desc(),
                CrawlJob.created_at.asc()
            )
            .limit(limit)
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_job_with_articles(
        self,
        job_id: str
    ) -> Optional[CrawlJob]:
        """Get job with associated articles."""
        query = (
            select(CrawlJob)
            .options(selectinload(CrawlJob.articles))
            .where(CrawlJob.id == job_id)
        )

        result = await self.db.execute(query)
        return result.scalar_one_or_none()
```

### Authentication and Authorization

#### Auth Flow

```mermaid
sequenceDiagram
    participant Client
    participant Frontend
    participant FastAPI
    participant Database
    participant JWT

    Client->>Frontend: Login request
    Frontend->>FastAPI: POST /auth/login
    FastAPI->>Database: Validate user credentials
    Database-->>FastAPI: User data
    FastAPI->>JWT: Generate access token
    JWT-->>FastAPI: Token created
    FastAPI-->>Frontend: Return token + user info
    Frontend->>Frontend: Store token in localStorage
    Frontend-->>Client: Login successful

    Note over Client,JWT: Protected API Requests

    Frontend->>FastAPI: API request with Authorization header
    FastAPI->>JWT: Validate token
    JWT-->>FastAPI: Token valid + user claims
    FastAPI->>Database: Execute authorized request
    Database-->>FastAPI: Return data
    FastAPI-->>Frontend: Protected resource data
```

#### Middleware/Guards

```python
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional

from src.shared.config import get_settings
from src.database.repositories.user_repo import UserRepository

security = HTTPBearer()
settings = get_settings()

async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """Verify JWT token and return user claims."""
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )

        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )

        # Check token expiration
        exp = payload.get("exp")
        if exp and datetime.utcnow() > datetime.utcfromtimestamp(exp):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired"
            )

        return payload

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

async def get_current_user(
    token_data: dict = Depends(verify_token),
    db: AsyncSession = Depends(get_database_session)
):
    """Get current authenticated user."""
    user_repo = UserRepository(db)
    user = await user_repo.get_user_by_id(token_data["sub"])

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    return user

def require_role(required_role: str):
    """Decorator for role-based access control."""
    def role_checker(current_user = Depends(get_current_user)):
        if current_user.role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    return role_checker

# Usage in routes
@router.delete("/{job_id}")
async def delete_job(
    job_id: str,
    current_user = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_database_session)
):
    # Protected endpoint implementation
    pass
```

## Unified Project Structure

```
google-news-scraper/
├── .github/                    # CI/CD workflows
│   └── workflows/
│       ├── ci.yaml
│       ├── deploy.yaml
│       └── test.yaml
├── frontend/                   # React Frontend Application
│   ├── src/
│   │   ├── components/         # UI components
│   │   │   ├── ui/             # Shadcn UI base components
│   │   │   ├── jobs/           # Job management components
│   │   │   ├── articles/       # Article viewing components
│   │   │   ├── categories/     # Enhanced category components
│   │   │   └── common/         # Shared components
│   │   ├── pages/              # Page components/routes
│   │   ├── hooks/              # Custom React hooks
│   │   ├── services/           # API client services
│   │   ├── stores/             # State management (Context)
│   │   ├── types/              # Frontend-specific types
│   │   ├── utils/              # Frontend utilities
│   │   └── styles/             # Global styles/themes
│   ├── public/                 # Static assets
│   ├── tests/                  # Frontend tests
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── tsconfig.json
├── src/                        # Backend FastAPI Application
│   ├── api/                    # API routes and handlers
│   │   ├── routes/             # Route modules
│   │   ├── schemas/            # Pydantic models
│   │   ├── dependencies/       # FastAPI dependencies
│   │   └── main.py             # FastAPI app entry point
│   ├── core/                   # Core business logic
│   │   ├── crawler/            # Crawling engine
│   │   └── scheduler/          # Celery tasks and scheduling
│   ├── database/               # Database layer
│   │   ├── models/             # SQLAlchemy models
│   │   ├── repositories/       # Data access repositories
│   │   ├── migrations/         # Alembic migrations
│   │   └── connection.py       # DB connection management
│   ├── shared/                 # Shared utilities
│   │   ├── config.py           # Configuration management
│   │   ├── exceptions.py       # Custom exceptions
│   │   └── health.py           # Health check utilities
│   └── tests/                  # Backend tests
├── shared/                     # Shared TypeScript types
│   ├── types/                  # Common interfaces
│   │   ├── job.ts
│   │   ├── article.ts
│   │   ├── category.ts
│   │   └── api.ts
│   ├── constants/              # Shared constants
│   └── utils/                  # Cross-platform utilities
├── docker/                     # Docker configurations
│   ├── Dockerfile              # Backend Dockerfile
│   ├── Dockerfile.frontend     # Frontend Dockerfile
│   ├── Dockerfile.worker       # Celery worker Dockerfile
│   └── nginx.conf              # Nginx configuration
├── docs/                       # Documentation
│   ├── prd/                    # Product requirements
│   ├── architecture/           # Architecture documentation
│   ├── api/                    # API documentation
│   └── deployment/             # Deployment guides
├── scripts/                    # Build/deploy scripts
│   ├── setup.sh                # Initial setup script
│   ├── build.sh                # Build script
│   └── deploy.sh               # Deployment script
├── tests/                      # Integration and E2E tests
│   ├── integration/            # API integration tests
│   └── e2e/                    # End-to-end tests
├── .env.example                # Environment template
├── docker-compose.yml          # Development environment
├── docker-compose.prod.yml     # Production environment
├── requirements.txt            # Python dependencies
├── package.json                # Root package.json (if using workspaces)
├── alembic.ini                 # Database migration config
└── README.md                   # Project documentation
```

## Development Workflow

### Local Development Setup

#### Prerequisites

```bash
# Required software
- Docker & Docker Compose
- Node.js 18+ & npm
- Python 3.11+
- Git

# Verify installations
docker --version
docker-compose --version
node --version
python --version
```

#### Initial Setup

```bash
# Clone repository
git clone <repository-url>
cd google-news-scraper

# Copy environment configuration
cp .env.example .env

# Edit environment variables
nano .env  # Configure DATABASE_URL, API keys, etc.

# Build and start all services
docker-compose up --build

# Run database migrations
docker-compose exec web alembic upgrade head

# Install frontend dependencies (if running outside Docker)
cd frontend && npm install

# Create initial admin user (optional)
docker-compose exec web python -m src.scripts.create_admin
```

#### Development Commands

```bash
# Start all services
docker-compose up -d

# Start frontend only (for frontend development)
cd frontend && npm run dev

# Start backend only (for API development)
docker-compose up web postgres redis worker beat

# Run tests
# Backend tests
docker-compose exec web pytest
# Frontend tests
cd frontend && npm test
# E2E tests
cd frontend && npm run test:e2e

# View logs
docker-compose logs -f web
docker-compose logs -f worker
docker-compose logs -f frontend

# Database operations
docker-compose exec postgres psql -U postgres -d google_news
docker-compose exec web alembic revision --autogenerate -m "Migration name"
```

### Environment Configuration

#### Required Environment Variables

```bash
# Frontend (.env.local)
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/ws
VITE_ENVIRONMENT=development

# Backend (.env)
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/google_news
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60

# Shared
ENVIRONMENT=development
LOG_LEVEL=DEBUG
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
POSTGRES_DB=google_news
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
```

## Deployment Architecture

### Deployment Strategy

**Frontend Deployment:**
- **Platform:** Vercel/Netlify for static hosting or Docker container
- **Build Command:** `npm run build`
- **Output Directory:** `dist/`
- **CDN/Edge:** Built-in CDN with edge caching

**Backend Deployment:**
- **Platform:** Docker containers on VPS/Cloud (AWS ECS, Azure Container Instances)
- **Build Command:** `docker build -f docker/Dockerfile .`
- **Deployment Method:** Rolling deployment with health checks

### CI/CD Pipeline

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
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
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio

      - name: Run database migrations
        run: alembic upgrade head
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/test_db

      - name: Run backend tests
        run: pytest src/tests/ -v
        env:
          DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/test_db
          CELERY_BROKER_URL: redis://localhost:6379/0

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '18'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        run: cd frontend && npm ci

      - name: Run frontend tests
        run: cd frontend && npm test -- --coverage

      - name: Run build test
        run: cd frontend && npm run build

  deploy-staging:
    needs: [test-backend, test-frontend]
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/develop'

    steps:
      - uses: actions/checkout@v4

      - name: Build and push Docker images
        run: |
          docker build -t google-news-scraper:staging .
          docker build -f docker/Dockerfile.frontend -t google-news-frontend:staging .

      - name: Deploy to staging
        run: |
          # Deploy commands for staging environment
          echo "Deploying to staging..."

  deploy-production:
    needs: [test-backend, test-frontend]
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'

    steps:
      - uses: actions/checkout@v4

      - name: Build and push Docker images
        run: |
          docker build -t google-news-scraper:latest .
          docker build -f docker/Dockerfile.frontend -t google-news-frontend:latest .

      - name: Deploy to production
        run: |
          # Deploy commands for production environment
          echo "Deploying to production..."
```

### Environments

| Environment | Frontend URL | Backend URL | Purpose |
|-------------|--------------|-------------|---------|
| Development | http://localhost:3000 | http://localhost:8000 | Local development |
| Staging | https://staging.yourapp.com | https://api-staging.yourapp.com | Pre-production testing |
| Production | https://yourapp.com | https://api.yourapp.com | Live environment |

## Security and Performance

### Security Requirements

**Frontend Security:**
- CSP Headers: `default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'`
- XSS Prevention: React's built-in XSS protection + input sanitization
- Secure Storage: JWT tokens in httpOnly cookies, sensitive data encrypted

**Backend Security:**
- Input Validation: Pydantic models with strict validation rules
- Rate Limiting: 100 requests/minute per IP for API endpoints
- CORS Policy: Restricted to frontend domains only

**Authentication Security:**
- Token Storage: JWT in httpOnly cookies with secure flags
- Session Management: Stateless JWT with refresh token rotation
- Password Policy: Minimum 8 characters, complexity requirements

### Performance Optimization

**Frontend Performance:**
- Bundle Size Target: < 500KB gzipped initial load
- Loading Strategy: Code splitting with React.lazy, progressive loading
- Caching Strategy: Browser cache for assets, React Query for API caching

**Backend Performance:**
- Response Time Target: < 200ms for API endpoints, < 2s for complex queries
- Database Optimization: Proper indexing, connection pooling, query optimization
- Caching Strategy: Redis for session data, query result caching

## Testing Strategy

### Testing Pyramid

```
      E2E Tests (Playwright)
        /            \
  Integration Tests   API Tests
    /        \        /      \
Frontend Unit    Backend Unit
   (Vitest)       (pytest)
```

### Test Organization

#### Frontend Tests

```
frontend/tests/
├── components/              # Component unit tests
│   ├── jobs/
│   │   ├── JobsList.test.tsx
│   │   ├── JobArticlesModal.test.tsx
│   │   └── PriorityControls.test.tsx
│   └── articles/
│       ├── ArticleList.test.tsx
│       └── ArticleExport.test.tsx
├── hooks/                   # Custom hook tests
│   ├── useJobs.test.ts
│   └── useArticles.test.ts
├── services/                # API service tests
│   └── JobsService.test.ts
└── e2e/                     # End-to-end tests
    ├── job-management.spec.ts
    ├── article-viewing.spec.ts
    └── category-scheduling.spec.ts
```

#### Backend Tests

```
src/tests/
├── api/                     # API endpoint tests
│   ├── test_jobs.py
│   ├── test_articles.py
│   └── test_categories.py
├── repositories/            # Repository layer tests
│   ├── test_job_repo.py
│   └── test_article_repo.py
├── services/               # Business logic tests
│   └── test_crawler.py
└── integration/            # Integration tests
    ├── test_job_workflow.py
    └── test_scheduling.py
```

#### E2E Tests

```
tests/e2e/
├── specs/
│   ├── job-article-workflow.spec.ts
│   ├── priority-management.spec.ts
│   └── category-scheduling.spec.ts
├── fixtures/
│   ├── test-data.json
│   └── mock-responses.ts
└── utils/
    ├── test-helpers.ts
    └── page-objects.ts
```

### Test Examples

#### Frontend Component Test

```typescript
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { JobArticlesModal } from '@/components/jobs/JobArticlesModal';
import { JobsService } from '@/services/JobsService';

// Mock the service
vi.mock('@/services/JobsService');

describe('JobArticlesModal', () => {
  const mockArticles = [
    {
      id: '1',
      title: 'Test Article',
      url: 'https://example.com/article1',
      content: 'Article content...',
      publish_date: '2025-09-15T10:00:00Z',
      keywords_matched: ['python', 'ai']
    }
  ];

  beforeEach(() => {
    vi.mocked(JobsService.getJobArticles).mockResolvedValue({
      items: mockArticles,
      total: 1,
      page: 1,
      pages: 1
    });
  });

  it('should display articles for a job', async () => {
    render(
      <JobArticlesModal
        jobId="job-123"
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Test Article')).toBeInTheDocument();
    });

    expect(JobsService.getJobArticles).toHaveBeenCalledWith('job-123', {
      page: 1,
      size: 20
    });
  });

  it('should handle export functionality', async () => {
    const mockBlob = new Blob(['csv data'], { type: 'text/csv' });
    vi.mocked(JobsService.exportJobArticles).mockResolvedValue(mockBlob);

    render(
      <JobArticlesModal
        jobId="job-123"
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Export Data')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Export Data'));
    fireEvent.click(screen.getByText('CSV'));

    await waitFor(() => {
      expect(JobsService.exportJobArticles).toHaveBeenCalledWith('job-123', 'csv');
    });
  });
});
```

#### Backend API Test

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.main import app
from src.database.models.crawl_job import CrawlJob, CrawlJobStatus
from tests.conftest import override_get_db

client = TestClient(app)

@pytest.mark.asyncio
async def test_update_job_priority(db_session: AsyncSession, sample_job: CrawlJob):
    """Test updating job priority for Run Now functionality."""

    # Update priority via API
    response = client.patch(
        f"/api/v1/jobs/{sample_job.id}/priority",
        json={"priority": 10},
        headers={"Authorization": "Bearer test_token"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["priority"] == 10
    assert data["id"] == str(sample_job.id)

    # Verify database update
    await db_session.refresh(sample_job)
    assert sample_job.priority == 10

@pytest.mark.asyncio
async def test_get_job_articles(db_session: AsyncSession, sample_job_with_articles):
    """Test retrieving articles for a specific job."""

    response = client.get(
        "/api/v1/articles",
        params={"job_id": str(sample_job_with_articles.id)},
        headers={"Authorization": "Bearer test_token"}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 3  # Based on test fixture
    assert all(article["crawl_job_id"] == str(sample_job_with_articles.id)
              for article in data["items"])

@pytest.mark.asyncio
async def test_job_export_functionality(db_session: AsyncSession, sample_job_with_articles):
    """Test article export functionality."""

    response = client.post(
        "/api/v1/articles/export",
        json={
            "job_id": str(sample_job_with_articles.id),
            "format": "csv"
        },
        headers={"Authorization": "Bearer test_token"}
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv"
    assert "title,url,publish_date" in response.text
```

#### E2E Test

```typescript
import { test, expect } from '@playwright/test';

test.describe('Job-Centric Article Management', () => {
  test.beforeEach(async ({ page }) => {
    // Login and navigate to jobs page
    await page.goto('/login');
    await page.fill('[data-testid="username"]', 'admin');
    await page.fill('[data-testid="password"]', 'password');
    await page.click('[data-testid="login-button"]');
    await page.waitForURL('/jobs');
  });

  test('should complete Run Now workflow', async ({ page }) => {
    // Find a pending job and click Run Now
    await page.click('[data-testid="job-row"]:first-child [data-testid="run-now-button"]');

    // Confirm the priority update
    await page.click('[data-testid="confirm-priority-update"]');

    // Wait for job status to update
    await expect(page.locator('[data-testid="job-status"]:first-child')).toContainText('Running');

    // Wait for job completion (or timeout)
    await expect(page.locator('[data-testid="job-status"]:first-child'))
      .toContainText('Completed', { timeout: 30000 });
  });

  test('should view and export job articles', async ({ page }) => {
    // Click View Articles on a completed job
    await page.click('[data-testid="completed-job"] [data-testid="view-articles-button"]');

    // Verify articles modal opens
    await expect(page.locator('[data-testid="job-articles-modal"]')).toBeVisible();

    // Check articles are displayed
    await expect(page.locator('[data-testid="article-item"]')).toHaveCount.greaterThan(0);

    // Test export functionality
    await page.click('[data-testid="export-data-button"]');
    await page.click('[data-testid="export-csv-option"]');

    // Wait for download
    const downloadPromise = page.waitForEvent('download');
    await page.click('[data-testid="confirm-export"]');
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toMatch(/articles.*\.csv$/);
  });

  test('should configure category scheduling', async ({ page }) => {
    // Navigate to categories
    await page.click('[data-testid="nav-categories"]');

    // Edit a category
    await page.click('[data-testid="category-row"]:first-child [data-testid="edit-button"]');

    // Switch to Schedules tab
    await page.click('[data-testid="schedules-tab"]');

    // Configure schedule
    await page.selectOption('[data-testid="interval-select"]', '60'); // 1 hour
    await page.check('[data-testid="schedule-active-checkbox"]');

    // Save changes
    await page.click('[data-testid="save-category-button"]');

    // Verify schedule is displayed in category list
    await expect(page.locator('[data-testid="next-scheduled"]:first-child'))
      .toContainText('in 60 minutes');
  });
});
```

## Coding Standards

### Critical Fullstack Rules

- **Type Sharing:** Always define types in shared/ directory and import from there - never duplicate interfaces
- **API Calls:** Never make direct HTTP calls - use the service layer with proper error handling
- **Environment Variables:** Access only through config objects, never process.env directly in components
- **Error Handling:** All API routes must use the standard error handler with correlation ID tracking
- **State Updates:** Never mutate state directly - use proper state management patterns with React Context
- **Database Queries:** Always use repository pattern, never raw SQL in route handlers
- **Job Priority Updates:** Use atomic database operations for job priority changes to prevent race conditions
- **Article Export:** All exports must support UTF-8 encoding for Vietnamese characters
- **Real-time Updates:** Use WebSocket connections sparingly, prefer polling for job status updates
- **Container Health:** All containers must implement proper health checks and graceful shutdown

### Naming Conventions

| Element | Frontend | Backend | Example |
|---------|----------|---------|---------|
| Components | PascalCase | - | `JobArticlesModal.tsx` |
| Hooks | camelCase with 'use' | - | `useJobArticles.ts` |
| API Routes | - | kebab-case | `/api/v1/job-articles` |
| Database Tables | - | snake_case | `crawl_jobs` |
| Database Columns | - | snake_case | `articles_found` |
| Environment Variables | UPPER_SNAKE_CASE | UPPER_SNAKE_CASE | `CELERY_BROKER_URL` |
| Service Methods | camelCase | snake_case | `getJobArticles` / `get_job_articles` |
| Event Handlers | camelCase with 'handle' | - | `handleRunNowClick` |

## Error Handling Strategy

### Error Flow

```mermaid
sequenceDiagram
    participant Frontend
    participant FastAPI
    participant Database
    participant Celery

    Frontend->>FastAPI: API Request
    FastAPI->>Database: Database Query
    Database-->>FastAPI: Database Error
    FastAPI->>FastAPI: Log error with correlation ID
    FastAPI-->>Frontend: Structured error response
    Frontend->>Frontend: Display user-friendly error
    Frontend->>Frontend: Log error for debugging

    Note over Frontend,Celery: Async Task Error Handling

    FastAPI->>Celery: Background Task
    Celery->>Database: Task fails
    Celery->>Celery: Log error and retry
    Celery-->>FastAPI: Task failure notification
    FastAPI->>Frontend: WebSocket/polling update
    Frontend->>Frontend: Show task failure notification
```

### Error Response Format

```typescript
interface ApiError {
  error: {
    code: string;
    message: string;
    details?: Record<string, any>;
    timestamp: string;
    requestId: string;
  };
}

// Standard error codes
enum ErrorCodes {
  VALIDATION_ERROR = 'VALIDATION_ERROR',
  JOB_NOT_FOUND = 'JOB_NOT_FOUND',
  JOB_ALREADY_RUNNING = 'JOB_ALREADY_RUNNING',
  PRIORITY_UPDATE_FAILED = 'PRIORITY_UPDATE_FAILED',
  EXPORT_GENERATION_FAILED = 'EXPORT_GENERATION_FAILED',
  SCHEDULE_CONFLICT = 'SCHEDULE_CONFLICT',
  DATABASE_CONNECTION_ERROR = 'DATABASE_CONNECTION_ERROR',
  RATE_LIMIT_EXCEEDED = 'RATE_LIMIT_EXCEEDED'
}
```

### Frontend Error Handling

```typescript
import { toast } from 'sonner';

class ApiErrorHandler {
  static handle(error: any): void {
    const correlation_id = error.response?.headers?.['x-correlation-id'];

    if (error.response?.data?.error) {
      const apiError = error.response.data.error;

      switch (apiError.code) {
        case 'JOB_NOT_FOUND':
          toast.error('Job not found. It may have been deleted.');
          break;
        case 'JOB_ALREADY_RUNNING':
          toast.error('Cannot modify job that is currently running.');
          break;
        case 'PRIORITY_UPDATE_FAILED':
          toast.error('Failed to update job priority. Please try again.');
          break;
        case 'EXPORT_GENERATION_FAILED':
          toast.error('Export failed. Please check your selection and try again.');
          break;
        default:
          toast.error(apiError.message || 'An unexpected error occurred.');
      }

      // Log for debugging
      console.error('API Error:', {
        code: apiError.code,
        message: apiError.message,
        correlation_id,
        timestamp: apiError.timestamp
      });
    } else {
      // Network or other errors
      toast.error('Connection error. Please check your internet connection.');
      console.error('Network Error:', error);
    }
  }
}

// Usage in hooks
export const useJobActions = () => {
  const updateJobPriority = async (jobId: string, priority: number) => {
    try {
      const result = await JobsService.updateJobPriority(jobId, priority);
      toast.success('Job priority updated successfully');
      return result;
    } catch (error) {
      ApiErrorHandler.handle(error);
      throw error;
    }
  };

  return { updateJobPriority };
};
```

### Backend Error Handling

```python
import logging
import traceback
from datetime import datetime
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError
import structlog

logger = structlog.get_logger(__name__)

class AppException(Exception):
    """Base application exception."""
    def __init__(self, message: str, code: str, details: dict = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(self.message)

class JobNotFoundException(AppException):
    def __init__(self, job_id: str):
        super().__init__(
            message=f"Job with ID {job_id} not found",
            code="JOB_NOT_FOUND",
            details={"job_id": job_id}
        )

class JobAlreadyRunningException(AppException):
    def __init__(self, job_id: str):
        super().__init__(
            message="Cannot modify job that is currently running",
            code="JOB_ALREADY_RUNNING",
            details={"job_id": job_id}
        )

async def app_exception_handler(request: Request, exc: AppException):
    """Handle custom application exceptions."""
    correlation_id = getattr(request.state, 'correlation_id', 'unknown')

    logger.warning(
        "Application exception",
        correlation_id=correlation_id,
        error_code=exc.code,
        error_message=exc.message,
        error_details=exc.details,
        path=request.url.path
    )

    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
                "timestamp": datetime.utcnow().isoformat(),
                "requestId": correlation_id
            }
        },
        headers={"X-Correlation-ID": correlation_id}
    )

async def database_exception_handler(request: Request, exc: Exception):
    """Handle database-related exceptions."""
    correlation_id = getattr(request.state, 'correlation_id', 'unknown')

    if isinstance(exc, IntegrityError):
        error_code = "DATABASE_INTEGRITY_ERROR"
        message = "Data integrity constraint violation"
        status_code = 400
    elif isinstance(exc, OperationalError):
        error_code = "DATABASE_CONNECTION_ERROR"
        message = "Database connection failed"
        status_code = 503
    else:
        error_code = "DATABASE_ERROR"
        message = "Database operation failed"
        status_code = 500

    logger.error(
        "Database exception",
        correlation_id=correlation_id,
        error_code=error_code,
        error_type=type(exc).__name__,
        error_message=str(exc),
        path=request.url.path,
        exc_info=True
    )

    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": error_code,
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
                "requestId": correlation_id
            }
        },
        headers={"X-Correlation-ID": correlation_id}
    )

# Usage in route handlers
@router.patch("/{job_id}/priority")
async def update_job_priority(
    job_id: str,
    priority_update: PriorityUpdate,
    db: AsyncSession = Depends(get_database_session)
):
    job_repo = CrawlJobRepository(db)

    job = await job_repo.get_job_by_id(job_id)
    if not job:
        raise JobNotFoundException(job_id)

    if job.status == CrawlJobStatus.RUNNING:
        raise JobAlreadyRunningException(job_id)

    try:
        updated_job = await job_repo.update_job_priority(job_id, priority_update.priority)
        return JobResponse.from_orm(updated_job)
    except IntegrityError as e:
        logger.error("Failed to update job priority", job_id=job_id, error=str(e))
        raise AppException(
            message="Failed to update job priority due to data conflict",
            code="PRIORITY_UPDATE_FAILED",
            details={"job_id": job_id}
        )
```

## Monitoring and Observability

### Monitoring Stack

- **Frontend Monitoring:** Vercel Analytics + Sentry for error tracking
- **Backend Monitoring:** Structured logging with correlation IDs + custom health endpoints
- **Error Tracking:** Sentry integration for both frontend and backend error aggregation
- **Performance Monitoring:** Built-in FastAPI middleware for request timing + React Profiler for component performance

### Key Metrics

**Frontend Metrics:**
- Core Web Vitals (LCP, FID, CLS)
- JavaScript errors and unhandled promise rejections
- API response times from client perspective
- User interactions (job actions, article views, exports)

**Backend Metrics:**
- Request rate and response time per endpoint
- Error rate by endpoint and error type
- Database query performance and connection pool usage
- Celery task queue length and processing time
- Job completion rate and crawling success metrics

---

This comprehensive fullstack architecture document provides the foundation for implementing the job-centric article management enhancement while maintaining the existing system's reliability and performance. The architecture supports the PRD requirements for priority-based job management, integrated article viewing with export capabilities, and seamless category scheduling integration.