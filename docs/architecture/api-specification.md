# API Specification

## Overview

This document provides the complete REST API specification for the Google News Scraper job-centric enhancement. The API follows OpenAPI 3.0 standards and supports job management, article viewing with export, and integrated category scheduling.

## Base Configuration

```yaml
openapi: 3.0.0
info:
  title: Google News Scraper API
  version: 1.0.0
  description: REST API for job-centric article management and crawling automation
  contact:
    name: API Support
    email: support@yourapp.com
servers:
  - url: http://localhost:8000/api/v1
    description: Development server
  - url: https://api.yourapp.com/api/v1
    description: Production server
```

## Authentication

All API endpoints require authentication using JWT tokens:

```yaml
security:
  - BearerAuth: []

components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
```

## Enhanced Jobs Management API

### List Jobs

**GET** `/jobs`

Query parameters for filtering and pagination:

```yaml
parameters:
  - name: status
    in: query
    schema:
      type: string
      enum: [pending, running, completed, failed]
    description: Filter by job status
  - name: category_id
    in: query
    schema:
      type: string
      format: uuid
    description: Filter by category
  - name: priority_min
    in: query
    schema:
      type: integer
      minimum: 0
    description: Filter by minimum priority
  - name: page
    in: query
    schema:
      type: integer
      default: 1
      minimum: 1
    description: Page number for pagination
  - name: size
    in: query
    schema:
      type: integer
      default: 20
      minimum: 1
      maximum: 100
    description: Number of items per page
  - name: sort_by
    in: query
    schema:
      type: string
      enum: [created_at, priority, status, articles_found]
      default: priority
    description: Sort field
  - name: sort_order
    in: query
    schema:
      type: string
      enum: [asc, desc]
      default: desc
    description: Sort order
```

Response example:
```json
{
  "items": [
    {
      "id": "job-uuid-123",
      "category_id": "cat-uuid-456",
      "category_name": "Technology",
      "status": "completed",
      "started_at": "2025-09-15T10:00:00Z",
      "completed_at": "2025-09-15T10:05:00Z",
      "articles_found": 25,
      "articles_saved": 23,
      "priority": 5,
      "duration_seconds": 300,
      "queue_position": null,
      "created_at": "2025-09-15T09:55:00Z"
    }
  ],
  "total": 150,
  "page": 1,
  "pages": 8,
  "size": 20
}
```

### Create Job

**POST** `/jobs`

Request body:
```json
{
  "category_id": "cat-uuid-456",
  "priority": 0,
  "job_metadata": {
    "source": "manual",
    "user_id": "user-123"
  }
}
```

### Update Job Priority (Run Now)

**PATCH** `/jobs/{job_id}/priority`

This endpoint implements the "Run Now" functionality by setting high priority:

Request body:
```json
{
  "priority": 10
}
```

Response:
```json
{
  "id": "job-uuid-123",
  "priority": 10,
  "queue_position": 1,
  "estimated_start_time": "2025-09-15T10:00:30Z",
  "message": "Job priority updated successfully"
}
```

### Update Job Configuration

**PUT** `/jobs/{job_id}`

Request body:
```json
{
  "priority": 5,
  "retry_count": 3,
  "job_metadata": {
    "updated_by": "user-123",
    "reason": "Configuration adjustment"
  }
}
```

### Delete Job

**DELETE** `/jobs/{job_id}`

Query parameters:
```yaml
parameters:
  - name: force
    in: query
    schema:
      type: boolean
      default: false
    description: Force delete running job (admin only)
```

Response:
```json
{
  "message": "Job deleted successfully",
  "impact": {
    "articles_affected": 0,
    "dependent_schedules": []
  }
}
```

## Articles API (New)

### List Articles with Job Filtering

**GET** `/articles`

Key features:
- Job-specific filtering for article viewing
- Full-text search across title and content
- Export preparation with field selection

Query parameters:
```yaml
parameters:
  - name: job_id
    in: query
    schema:
      type: string
      format: uuid
    description: Filter by specific crawl job (primary use case)
  - name: category_id
    in: query
    schema:
      type: string
      format: uuid
    description: Filter by category
  - name: search
    in: query
    schema:
      type: string
    description: Search in title and content
  - name: keywords
    in: query
    schema:
      type: array
      items:
        type: string
    description: Filter by matched keywords
  - name: relevance_min
    in: query
    schema:
      type: number
      format: float
      minimum: 0.0
      maximum: 1.0
    description: Minimum relevance score
  - name: date_from
    in: query
    schema:
      type: string
      format: date
    description: Filter by publish date (from)
  - name: date_to
    in: query
    schema:
      type: string
      format: date
    description: Filter by publish date (to)
  - name: fields
    in: query
    schema:
      type: array
      items:
        type: string
        enum: [id, url, title, content, summary, publish_date, author, keywords_matched, relevance_score]
    description: Select specific fields to return
```

Response example:
```json
{
  "items": [
    {
      "id": "article-uuid-789",
      "url": "https://example.com/tech-news-1",
      "title": "Latest AI Developments in 2025",
      "summary": "Article summary...",
      "publish_date": "2025-09-15T08:00:00Z",
      "author": "John Smith",
      "keywords_matched": ["AI", "technology", "2025"],
      "relevance_score": 0.85,
      "crawl_job_id": "job-uuid-123",
      "content_preview": "First 200 characters of content..."
    }
  ],
  "total": 23,
  "page": 1,
  "pages": 2,
  "size": 20,
  "filters_applied": {
    "job_id": "job-uuid-123",
    "relevance_min": 0.7
  }
}
```

### Get Article Details

**GET** `/articles/{article_id}`

Response includes full content and metadata:
```json
{
  "id": "article-uuid-789",
  "url": "https://example.com/tech-news-1",
  "title": "Latest AI Developments in 2025",
  "content": "Full article content...",
  "summary": "Article summary...",
  "publish_date": "2025-09-15T08:00:00Z",
  "author": "John Smith",
  "image_url": "https://example.com/image.jpg",
  "keywords_matched": ["AI", "technology", "2025"],
  "relevance_score": 0.85,
  "crawl_job_id": "job-uuid-123",
  "job_info": {
    "category_name": "Technology",
    "crawl_date": "2025-09-15T10:00:00Z"
  },
  "created_at": "2025-09-15T10:02:00Z",
  "updated_at": "2025-09-15T10:02:00Z"
}
```

### Export Articles

**POST** `/articles/export`

Supports multiple formats with UTF-8 encoding for Vietnamese characters:

Request body:
```json
{
  "job_id": "job-uuid-123",
  "format": "xlsx",
  "fields": ["title", "url", "publish_date", "content", "keywords_matched"],
  "filters": {
    "relevance_min": 0.5,
    "date_from": "2025-09-01"
  },
  "include_metadata": true
}
```

Response headers:
```
Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
Content-Disposition: attachment; filename="articles_job-uuid-123_20250915.xlsx"
X-Export-Stats: {"total_articles": 23, "filtered_articles": 18}
```

## Enhanced Categories API

### List Categories with Schedule Information

**GET** `/categories`

Response includes schedule status:
```json
{
  "items": [
    {
      "id": "cat-uuid-456",
      "name": "Technology",
      "keywords": ["AI", "technology", "programming"],
      "is_active": true,
      "exclude_keywords": ["advertisement", "sponsored"],
      "schedule": {
        "id": "schedule-uuid-789",
        "interval_minutes": 60,
        "is_active": true,
        "next_run_at": "2025-09-15T11:00:00Z",
        "last_run_at": "2025-09-15T10:00:00Z"
      },
      "last_crawl": {
        "job_id": "job-uuid-123",
        "completed_at": "2025-09-15T10:05:00Z",
        "articles_found": 25
      },
      "next_run_display": "in 13 minutes"
    }
  ]
}
```

## Category Scheduling API (New)

### Get Category Schedule

**GET** `/categories/{category_id}/schedules`

Response:
```json
{
  "id": "schedule-uuid-789",
  "category_id": "cat-uuid-456",
  "interval_minutes": 60,
  "is_active": true,
  "next_run_at": "2025-09-15T11:00:00Z",
  "last_run_at": "2025-09-15T10:00:00Z",
  "run_history": [
    {
      "executed_at": "2025-09-15T10:00:00Z",
      "status": "success",
      "job_id": "job-uuid-123",
      "articles_found": 25
    },
    {
      "executed_at": "2025-09-15T09:00:00Z",
      "status": "success",
      "job_id": "job-uuid-122",
      "articles_found": 18
    }
  ],
  "created_at": "2025-09-14T10:00:00Z",
  "updated_at": "2025-09-15T10:00:00Z"
}
```

### Create/Update Category Schedule

**POST** `/categories/{category_id}/schedules`

Request body:
```json
{
  "interval_minutes": 60,
  "is_active": true,
  "start_immediately": false
}
```

Response:
```json
{
  "id": "schedule-uuid-789",
  "category_id": "cat-uuid-456",
  "interval_minutes": 60,
  "is_active": true,
  "next_run_at": "2025-09-15T11:00:00Z",
  "celery_task_id": "beat-task-456",
  "message": "Schedule created successfully"
}
```

### Update Schedule Status

**PATCH** `/categories/{category_id}/schedules`

Request body:
```json
{
  "is_active": false,
  "reason": "Temporary disable for maintenance"
}
```

### Manual Trigger from Category

**POST** `/categories/{category_id}/crawl`

Immediately trigger crawl job for category:

Request body:
```json
{
  "priority": 10,
  "bypass_schedule": true
}
```

Response:
```json
{
  "job_id": "job-uuid-124",
  "status": "pending",
  "priority": 10,
  "estimated_start_time": "2025-09-15T10:00:30Z",
  "message": "Manual crawl job created successfully"
}
```

## Error Response Format

All API endpoints use consistent error response format:

```json
{
  "error": {
    "code": "JOB_NOT_FOUND",
    "message": "Job with ID job-uuid-123 not found",
    "details": {
      "job_id": "job-uuid-123",
      "resource": "crawl_job"
    },
    "timestamp": "2025-09-15T10:00:00Z",
    "requestId": "req-uuid-456"
  }
}
```

### Standard Error Codes

| Code | Description | HTTP Status |
|------|-------------|-------------|
| `VALIDATION_ERROR` | Request validation failed | 422 |
| `JOB_NOT_FOUND` | Job not found | 404 |
| `JOB_ALREADY_RUNNING` | Cannot modify running job | 400 |
| `PRIORITY_UPDATE_FAILED` | Failed to update job priority | 400 |
| `EXPORT_GENERATION_FAILED` | Export process failed | 500 |
| `SCHEDULE_CONFLICT` | Scheduling conflict detected | 409 |
| `DATABASE_CONNECTION_ERROR` | Database unavailable | 503 |
| `RATE_LIMIT_EXCEEDED` | Too many requests | 429 |
| `INSUFFICIENT_PERMISSIONS` | Access denied | 403 |
| `CATEGORY_INACTIVE` | Category is not active | 400 |

## Rate Limiting

API endpoints have different rate limits based on operation type:

- **Read operations** (GET): 1000 requests/hour per user
- **Write operations** (POST, PUT, PATCH): 500 requests/hour per user
- **Export operations**: 50 requests/hour per user
- **Priority updates**: 100 requests/hour per user

Rate limit headers:
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1694781600
```

## Pagination

All list endpoints support cursor-based pagination:

```json
{
  "items": [...],
  "pagination": {
    "total": 150,
    "page": 1,
    "pages": 8,
    "size": 20,
    "has_next": true,
    "has_prev": false,
    "next_cursor": "eyJpZCI6ImpvYi11dWlkLTEyMyJ9",
    "prev_cursor": null
  }
}
```

## API Versioning

- Current version: `v1`
- Version specified in URL path: `/api/v1/`
- Breaking changes will increment major version
- Backward compatibility maintained for 12 months
- Deprecation notices provided 6 months in advance

## OpenAPI Schema

The complete OpenAPI 3.0 schema is available at:
- Development: `http://localhost:8000/api/v1/openapi.json`
- Production: `https://api.yourapp.com/api/v1/openapi.json`

Interactive API documentation:
- Swagger UI: `/api/v1/docs`
- ReDoc: `/api/v1/redoc`