# API Specification

## REST API Specification

Based on actual implementation analysis of the Google News Scraper codebase.

```yaml
openapi: 3.0.0
info:
  title: Google News Scraper API
  version: 1.0.0
  description: REST API for managing news categories, crawling operations, and system monitoring
  contact:
    name: Google News Scraper Team
    url: https://github.com/your-org/google-news-scraper
servers:
  - url: http://localhost:8000
    description: Local development server
  - url: https://api.news-scraper.com
    description: Production server

# =====================================
# HEALTH & SYSTEM ENDPOINTS (✅ IMPLEMENTED)
# =====================================
paths:
  /health:
    get:
      summary: Basic health check
      description: Used by Docker health checks and load balancers
      tags: [Health]
      responses:
        200:
          description: Service is healthy
          content:
            application/json:
              schema:
                type: object
                properties:
                  status:
                    type: string
                    example: "healthy"
                  service:
                    type: string
                    example: "google-news-scraper"
                  version:
                    type: string
                    example: "1.0.0"
                  environment:
                    type: string
                    example: "development"
                  database:
                    type: string
                    example: "connected"
                  timestamp:
                    type: string
                    format: date-time
        503:
          description: Service unhealthy
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  /health/detailed:
    get:
      summary: Detailed health check with component status
      tags: [Health]
      responses:
        200:
          description: Detailed health status
        503:
          description: Service degraded or unhealthy

  /ready:
    get:
      summary: Readiness probe for Kubernetes
      tags: [Health]
      responses:
        200:
          description: Service ready to accept traffic
        503:
          description: Service not ready

  /live:
    get:
      summary: Liveness probe for Kubernetes
      tags: [Health]
      responses:
        200:
          description: Service is alive

  /:
    get:
      summary: Root endpoint with API information
      tags: [Root]
      responses:
        200:
          description: API information
          content:
            application/json:
              schema:
                type: object
                properties:
                  service:
                    type: string
                    example: "Google News Scraper API"
                  version:
                    type: string
                    example: "1.0.0"
                  docs:
                    type: string
                    example: "/api/v1/docs"
                  health:
                    type: string
                    example: "/health"

# =====================================
# CATEGORY MANAGEMENT (✅ IMPLEMENTED)
# =====================================
  /api/v1/categories:
    get:
      summary: List all categories
      description: Get categories with optional filtering and statistics
      tags: [Categories]
      parameters:
        - name: active_only
          in: query
          description: Filter to show only active categories
          schema:
            type: boolean
            default: true
        - name: include_stats
          in: query
          description: Include article count statistics (slower)
          schema:
            type: boolean
            default: false
      responses:
        200:
          description: List of categories
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CategoryListResponse'
        500:
          description: Failed to retrieve categories
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

    post:
      summary: Create new category
      description: Create a new category with name, keywords, and optional exclude keywords
      tags: [Categories]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CreateCategoryRequest'
      responses:
        201:
          description: Category created successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CategoryResponse'
        400:
          description: Validation error
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ValidationErrorResponse'
        409:
          description: Category name already exists
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        500:
          description: Failed to create category
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  /api/v1/categories/{category_id}:
    get:
      summary: Get category by ID
      description: Retrieve a specific category by its UUID
      tags: [Categories]
      parameters:
        - name: category_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      responses:
        200:
          description: Category found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CategoryResponse'
        404:
          description: Category not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        500:
          description: Failed to retrieve category
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

    put:
      summary: Update category by ID
      description: Update an existing category's name, keywords, exclude keywords, or active status
      tags: [Categories]
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
              $ref: '#/components/schemas/UpdateCategoryRequest'
      responses:
        200:
          description: Category updated successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CategoryResponse'
        400:
          description: Validation error or no fields provided for update
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ValidationErrorResponse'
        404:
          description: Category not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        409:
          description: Category name already exists
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        500:
          description: Failed to update category
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

    delete:
      summary: Delete category by ID
      description: Delete a category and all its associations (hard delete)
      tags: [Categories]
      parameters:
        - name: category_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      responses:
        204:
          description: Category deleted successfully
        404:
          description: Category not found
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        500:
          description: Failed to delete category
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  /api/v1/categories/search/{search_term}:
    get:
      summary: Search categories by name
      description: Search for categories by name using case-insensitive partial matching
      tags: [Categories]
      parameters:
        - name: search_term
          in: path
          required: true
          schema:
            type: string
      responses:
        200:
          description: Search results (may be empty list)
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/CategoryResponse'
        500:
          description: Failed to search categories
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

# =====================================
# JOB MANAGEMENT (🔧 BACKEND READY, FRONTEND PENDING)
# =====================================
  /api/v1/jobs:
    get:
      summary: List crawl jobs
      description: Get list of crawl jobs with filtering and pagination
      tags: [Jobs]
      parameters:
        - name: status
          in: query
          description: Filter by job status
          schema:
            type: string
            enum: [pending, running, completed, failed]
        - name: category_id
          in: query
          description: Filter by category UUID
          schema:
            type: string
            format: uuid
        - name: limit
          in: query
          description: Number of results to return
          schema:
            type: integer
            default: 50
            minimum: 1
            maximum: 100
        - name: offset
          in: query
          description: Number of results to skip
          schema:
            type: integer
            default: 0
            minimum: 0
      responses:
        200:
          description: List of crawl jobs
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/JobListResponse'
        400:
          description: Invalid parameters
        500:
          description: Failed to retrieve jobs

    post:
      summary: Trigger manual crawl job
      description: Create and schedule a new crawl job for a specific category
      tags: [Jobs]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/TriggerJobRequest'
      responses:
        201:
          description: Job scheduled successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/JobResponse'
        400:
          description: Invalid request or category not active
        404:
          description: Category not found
        500:
          description: Failed to schedule job

  /api/v1/jobs/{job_id}:
    get:
      summary: Get job details
      description: Retrieve detailed information about a specific job
      tags: [Jobs]
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
                $ref: '#/components/schemas/JobDetailResponse'
        404:
          description: Job not found
        500:
          description: Failed to retrieve job details

  /api/v1/jobs/{job_id}/status:
    get:
      summary: Get job status
      description: Get current status of a specific job (for polling)
      tags: [Jobs]
      parameters:
        - name: job_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      responses:
        200:
          description: Job status
          content:
            application/json:
              schema:
                type: object
                properties:
                  job_id:
                    type: string
                    format: uuid
                  status:
                    type: string
                    enum: [pending, running, completed, failed]
                  progress:
                    type: object
                    properties:
                      articles_found:
                        type: integer
                      articles_saved:
                        type: integer
                  error_message:
                    type: string
                    nullable: true
                  started_at:
                    type: string
                    format: date-time
                    nullable: true
                  completed_at:
                    type: string
                    format: date-time
                    nullable: true
        404:
          description: Job not found

# =====================================
# ARTICLE MANAGEMENT (❌ NOT IMPLEMENTED - NEEDS BACKEND)
# =====================================
  /api/v1/articles:
    get:
      summary: List articles
      description: Get paginated list of crawled articles with filtering
      tags: [Articles]
      parameters:
        - name: category_id
          in: query
          description: Filter by category UUID
          schema:
            type: string
            format: uuid
        - name: status
          in: query
          description: Filter by article status
          schema:
            type: string
            enum: [active, archived]
        - name: date_from
          in: query
          description: Filter articles from this date
          schema:
            type: string
            format: date
        - name: date_to
          in: query
          description: Filter articles to this date
          schema:
            type: string
            format: date
        - name: search
          in: query
          description: Search in article titles and content
          schema:
            type: string
        - name: limit
          in: query
          description: Number of results to return
          schema:
            type: integer
            default: 20
            minimum: 1
            maximum: 100
        - name: offset
          in: query
          description: Number of results to skip
          schema:
            type: integer
            default: 0
            minimum: 0
        - name: sort_by
          in: query
          description: Sort field
          schema:
            type: string
            enum: [created_at, published_at, title]
            default: created_at
        - name: sort_order
          in: query
          description: Sort order
          schema:
            type: string
            enum: [asc, desc]
            default: desc
      responses:
        200:
          description: List of articles
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ArticleListResponse'
        400:
          description: Invalid parameters
        500:
          description: Failed to retrieve articles

  /api/v1/articles/{article_id}:
    get:
      summary: Get article details
      description: Retrieve detailed information about a specific article
      tags: [Articles]
      parameters:
        - name: article_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      responses:
        200:
          description: Article details
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ArticleDetailResponse'
        404:
          description: Article not found
        500:
          description: Failed to retrieve article

# =====================================
# SCHEDULING MANAGEMENT (❌ NOT IMPLEMENTED - NEEDS BACKEND)
# =====================================
  /api/v1/schedules:
    get:
      summary: List schedules
      description: Get list of configured crawl schedules
      tags: [Schedules]
      parameters:
        - name: active_only
          in: query
          schema:
            type: boolean
            default: true
      responses:
        200:
          description: List of schedules
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ScheduleListResponse'
        500:
          description: Failed to retrieve schedules

    post:
      summary: Create schedule
      description: Create a new recurring crawl schedule for a category
      tags: [Schedules]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CreateScheduleRequest'
      responses:
        201:
          description: Schedule created successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ScheduleResponse'
        400:
          description: Invalid schedule configuration
        404:
          description: Category not found
        500:
          description: Failed to create schedule

  /api/v1/schedules/{schedule_id}:
    get:
      summary: Get schedule details
      description: Retrieve detailed information about a specific schedule
      tags: [Schedules]
      parameters:
        - name: schedule_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      responses:
        200:
          description: Schedule details
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ScheduleDetailResponse'
        404:
          description: Schedule not found
        500:
          description: Failed to retrieve schedule

    put:
      summary: Update schedule
      description: Update an existing schedule configuration
      tags: [Schedules]
      parameters:
        - name: schedule_id
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
              $ref: '#/components/schemas/UpdateScheduleRequest'
      responses:
        200:
          description: Schedule updated successfully
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ScheduleResponse'
        400:
          description: Invalid schedule configuration
        404:
          description: Schedule not found
        500:
          description: Failed to update schedule

    delete:
      summary: Delete schedule
      description: Delete a recurring crawl schedule
      tags: [Schedules]
      parameters:
        - name: schedule_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      responses:
        204:
          description: Schedule deleted successfully
        404:
          description: Schedule not found
        500:
          description: Failed to delete schedule

  /api/v1/schedules/{schedule_id}/toggle:
    post:
      summary: Toggle schedule active status
      description: Enable or disable a schedule
      tags: [Schedules]
      parameters:
        - name: schedule_id
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
                is_active:
                  type: boolean
              required:
                - is_active
      responses:
        200:
          description: Schedule status updated
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ScheduleResponse'
        404:
          description: Schedule not found
        500:
          description: Failed to update schedule status

# =====================================
# COMPONENTS SCHEMAS
# =====================================
components:
  schemas:
    # Category Schemas (✅ IMPLEMENTED)
    CategoryResponse:
      type: object
      properties:
        id:
          type: string
          format: uuid
          description: Unique identifier for the category
        name:
          type: string
          description: Category name (must be unique)
        keywords:
          type: array
          items:
            type: string
          description: Keywords to include in search
        exclude_keywords:
          type: array
          items:
            type: string
          description: Keywords to exclude from search
        is_active:
          type: boolean
          description: Whether the category is active for crawling
        created_at:
          type: string
          format: date-time
          description: When the category was created
        updated_at:
          type: string
          format: date-time
          description: When the category was last updated
      required:
        - id
        - name
        - keywords
        - exclude_keywords
        - is_active
        - created_at
        - updated_at
      example:
        id: "123e4567-e89b-12d3-a456-426614174000"
        name: "Technology"
        keywords: ["python", "javascript", "artificial intelligence"]
        exclude_keywords: ["deprecated", "obsolete"]
        is_active: true
        created_at: "2025-09-14T10:30:00Z"
        updated_at: "2025-09-14T10:30:00Z"

    CategoryWithStatsResponse:
      allOf:
        - $ref: '#/components/schemas/CategoryResponse'
        - type: object
          properties:
            article_count:
              type: integer
              description: Number of articles associated with this category

    CategoryListResponse:
      type: object
      properties:
        categories:
          type: array
          items:
            oneOf:
              - $ref: '#/components/schemas/CategoryResponse'
              - $ref: '#/components/schemas/CategoryWithStatsResponse'
        total:
          type: integer
          description: Total number of categories returned
        active_count:
          type: integer
          description: Number of active categories
      required:
        - categories
        - total
        - active_count

    CreateCategoryRequest:
      type: object
      properties:
        name:
          type: string
          description: Category name (must be unique)
          minLength: 1
          maxLength: 255
        keywords:
          type: array
          items:
            type: string
          description: Keywords to include in search
          minItems: 1
        exclude_keywords:
          type: array
          items:
            type: string
          description: Keywords to exclude from search (optional)
          default: []
        is_active:
          type: boolean
          description: Whether the category should be active
          default: true
      required:
        - name
        - keywords
      example:
        name: "Technology News"
        keywords: ["python", "javascript", "AI"]
        exclude_keywords: ["deprecated"]
        is_active: true

    UpdateCategoryRequest:
      type: object
      properties:
        name:
          type: string
          description: Category name (must be unique)
          minLength: 1
          maxLength: 255
        keywords:
          type: array
          items:
            type: string
          description: Keywords to include in search
        exclude_keywords:
          type: array
          items:
            type: string
          description: Keywords to exclude from search
        is_active:
          type: boolean
          description: Whether the category should be active
      # All fields optional for partial updates

    # Job Schemas (🔧 BACKEND READY, FRONTEND PENDING)
    JobResponse:
      type: object
      properties:
        job_id:
          type: string
          format: uuid
          description: Unique identifier for the job
        category_id:
          type: string
          format: uuid
          description: Category being crawled
        category_name:
          type: string
          description: Name of the category being crawled
        status:
          type: string
          enum: [pending, running, completed, failed]
          description: Current job status
        celery_task_id:
          type: string
          description: Celery task ID for tracking
        priority:
          type: integer
          description: Job priority (higher = more important)
        correlation_id:
          type: string
          description: Correlation ID for log tracking
        created_at:
          type: string
          format: date-time
        started_at:
          type: string
          format: date-time
          nullable: true
        completed_at:
          type: string
          format: date-time
          nullable: true
      required:
        - job_id
        - category_id
        - category_name
        - status
        - created_at

    JobDetailResponse:
      allOf:
        - $ref: '#/components/schemas/JobResponse'
        - type: object
          properties:
            articles_found:
              type: integer
              nullable: true
              description: Number of articles found during crawling
            articles_saved:
              type: integer
              nullable: true
              description: Number of articles successfully saved
            error_message:
              type: string
              nullable: true
              description: Error message if job failed
            error_details:
              type: object
              nullable: true
              description: Detailed error information
            metadata:
              type: object
              description: Additional job metadata

    JobListResponse:
      type: object
      properties:
        jobs:
          type: array
          items:
            $ref: '#/components/schemas/JobResponse'
        total:
          type: integer
          description: Total number of jobs matching filters
        limit:
          type: integer
          description: Number of results returned
        offset:
          type: integer
          description: Number of results skipped
      required:
        - jobs
        - total
        - limit
        - offset

    TriggerJobRequest:
      type: object
      properties:
        category_id:
          type: string
          format: uuid
          description: Category to crawl
        priority:
          type: integer
          description: Job priority
          default: 0
          minimum: 0
          maximum: 10
        metadata:
          type: object
          description: Optional metadata for the job
          additionalProperties: true
      required:
        - category_id
      example:
        category_id: "123e4567-e89b-12d3-a456-426614174000"
        priority: 5
        metadata:
          triggered_by: "manual"
          source: "admin_ui"

    # Article Schemas (❌ NOT IMPLEMENTED - NEEDS BACKEND)
    ArticleResponse:
      type: object
      properties:
        id:
          type: string
          format: uuid
          description: Unique identifier for the article
        title:
          type: string
          description: Article title
        url:
          type: string
          format: uri
          description: Original article URL
        content:
          type: string
          description: Article content (may be truncated)
        summary:
          type: string
          nullable: true
          description: Article summary/excerpt
        author:
          type: string
          nullable: true
          description: Article author
        published_at:
          type: string
          format: date-time
          nullable: true
          description: When the article was originally published
        source:
          type: string
          description: News source (e.g., "BBC", "CNN")
        category_id:
          type: string
          format: uuid
          description: Associated category
        category_name:
          type: string
          description: Name of associated category
        status:
          type: string
          enum: [active, archived]
          description: Article status
        crawl_job_id:
          type: string
          format: uuid
          description: Job that crawled this article
        created_at:
          type: string
          format: date-time
          description: When article was crawled and saved
        updated_at:
          type: string
          format: date-time
          description: When article was last updated
      required:
        - id
        - title
        - url
        - content
        - source
        - category_id
        - category_name
        - status
        - created_at
        - updated_at

    ArticleDetailResponse:
      allOf:
        - $ref: '#/components/schemas/ArticleResponse'
        - type: object
          properties:
            full_content:
              type: string
              description: Complete article content
            metadata:
              type: object
              description: Additional article metadata
              properties:
                word_count:
                  type: integer
                language:
                  type: string
                keywords:
                  type: array
                  items:
                    type: string

    ArticleListResponse:
      type: object
      properties:
        articles:
          type: array
          items:
            $ref: '#/components/schemas/ArticleResponse'
        total:
          type: integer
          description: Total number of articles matching filters
        limit:
          type: integer
          description: Number of results returned
        offset:
          type: integer
          description: Number of results skipped
        filters:
          type: object
          description: Applied filters
          properties:
            category_id:
              type: string
              format: uuid
              nullable: true
            status:
              type: string
              nullable: true
            date_from:
              type: string
              format: date
              nullable: true
            date_to:
              type: string
              format: date
              nullable: true
            search:
              type: string
              nullable: true
      required:
        - articles
        - total
        - limit
        - offset

    # Schedule Schemas (❌ NOT IMPLEMENTED - NEEDS BACKEND)
    ScheduleResponse:
      type: object
      properties:
        id:
          type: string
          format: uuid
          description: Unique identifier for the schedule
        name:
          type: string
          description: Human-readable schedule name
        category_id:
          type: string
          format: uuid
          description: Category to crawl
        category_name:
          type: string
          description: Name of the category
        interval_minutes:
          type: integer
          description: Interval between crawls in minutes
          enum: [1, 5, 15, 30, 60, 120, 360, 720, 1440]
        is_active:
          type: boolean
          description: Whether the schedule is currently active
        next_run:
          type: string
          format: date-time
          nullable: true
          description: When the next crawl is scheduled
        last_run:
          type: string
          format: date-time
          nullable: true
          description: When the last crawl was executed
        created_at:
          type: string
          format: date-time
        updated_at:
          type: string
          format: date-time
      required:
        - id
        - name
        - category_id
        - category_name
        - interval_minutes
        - is_active
        - created_at
        - updated_at

    ScheduleDetailResponse:
      allOf:
        - $ref: '#/components/schemas/ScheduleResponse'
        - type: object
          properties:
            total_runs:
              type: integer
              description: Total number of times this schedule has run
            successful_runs:
              type: integer
              description: Number of successful runs
            failed_runs:
              type: integer
              description: Number of failed runs
            last_job_id:
              type: string
              format: uuid
              nullable: true
              description: ID of the most recent job created by this schedule

    ScheduleListResponse:
      type: object
      properties:
        schedules:
          type: array
          items:
            $ref: '#/components/schemas/ScheduleResponse'
        total:
          type: integer
          description: Total number of schedules
        active_count:
          type: integer
          description: Number of active schedules
      required:
        - schedules
        - total
        - active_count

    CreateScheduleRequest:
      type: object
      properties:
        name:
          type: string
          description: Human-readable schedule name
          minLength: 1
          maxLength: 255
        category_id:
          type: string
          format: uuid
          description: Category to crawl
        interval_minutes:
          type: integer
          description: Interval between crawls in minutes
          enum: [1, 5, 15, 30, 60, 120, 360, 720, 1440]
        is_active:
          type: boolean
          description: Whether the schedule should be active immediately
          default: true
      required:
        - name
        - category_id
        - interval_minutes
      example:
        name: "Technology News - Hourly"
        category_id: "123e4567-e89b-12d3-a456-426614174000"
        interval_minutes: 60
        is_active: true

    UpdateScheduleRequest:
      type: object
      properties:
        name:
          type: string
          description: Human-readable schedule name
          minLength: 1
          maxLength: 255
        interval_minutes:
          type: integer
          description: Interval between crawls in minutes
          enum: [1, 5, 15, 30, 60, 120, 360, 720, 1440]
        is_active:
          type: boolean
          description: Whether the schedule should be active
      # All fields optional for partial updates

    # Error Response Schemas
    ErrorResponse:
      type: object
      properties:
        error:
          type: string
          description: Error category or type
        detail:
          type: string
          description: Detailed error message
        status_code:
          type: integer
          description: HTTP status code
        correlation_id:
          type: string
          description: Request correlation ID for tracking
      required:
        - error
        - detail
        - status_code
      example:
        error: "Validation Error"
        detail: "Category name already exists"
        status_code: 409
        correlation_id: "req_123e4567-e89b-12d3-a456-426614174000"

    ValidationErrorResponse:
      type: object
      properties:
        error:
          type: string
          description: Error type
          example: "Validation Error"
        detail:
          type: string
          description: General validation error message
          example: "Request validation failed"
        validation_errors:
          type: array
          items:
            type: object
            properties:
              loc:
                type: array
                items:
                  oneOf:
                    - type: string
                    - type: integer
                description: Location of the validation error
              msg:
                type: string
                description: Validation error message
              type:
                type: string
                description: Type of validation error
        correlation_id:
          type: string
          description: Request correlation ID for tracking
      required:
        - error
        - detail
        - validation_errors

# =====================================
# SECURITY SCHEMES
# =====================================
  securitySchemes:
    # Note: Currently no authentication implemented
    # Future consideration for API key or JWT authentication
    ApiKeyAuth:
      type: apiKey
      in: header
      name: X-API-Key
      description: "Future: API key authentication (not currently implemented)"

    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: JWT
      description: "Future: JWT token authentication (not currently implemented)"

# =====================================
# TAGS
# =====================================
tags:
  - name: Health
    description: System health and monitoring endpoints
  - name: Root
    description: Root API information
  - name: Categories
    description: Category management operations (✅ Fully Implemented)
  - name: Jobs
    description: Crawl job management (🔧 Backend Ready, Frontend Pending)
  - name: Articles
    description: Article management (❌ Not Implemented - Needs Backend)
  - name: Schedules
    description: Schedule management (❌ Not Implemented - Needs Backend)
```

## Implementation Status Summary

### ✅ **FULLY IMPLEMENTED**
- **Health Endpoints**: `/health`, `/health/detailed`, `/ready`, `/live`
- **Categories API**: Complete CRUD operations with search functionality
- **Error Handling**: Comprehensive error responses with correlation IDs
- **CORS Configuration**: Development and production environments supported

### 🔧 **BACKEND READY, FRONTEND PENDING**
- **Job Management Infrastructure**: Celery tasks and job tracking implemented
- **Manual Job Triggering**: `trigger_category_crawl_task` Celery task exists
- **Job Status Tracking**: CrawlJobRepository with comprehensive status management

### ❌ **NOT IMPLEMENTED - REQUIRES DEVELOPMENT**
- **Jobs API Endpoints**: REST endpoints for job management and status polling
- **Articles API**: Complete `/api/v1/articles` endpoints with filtering and search
- **ArticleRepository Methods**: Backend data access layer for articles
- **Schedules API**: Dynamic Celery Beat schedule management
- **Frontend UI Components**: Manual job triggering, articles viewing, scheduling interfaces

## Backend-Frontend Integration Notes

### **Current Integration Patterns**
- **API Client**: TypeScript ApiClient class in `frontend/src/services/api.ts`
- **Error Handling**: Consistent ApiError class with status codes and correlation IDs
- **CORS**: Backend configured for `http://localhost:3000` development origin
- **Type Safety**: TypeScript interfaces match API schemas

### **Missing Integration Requirements**
1. **Job Status Polling**: Frontend needs real-time job status updates
2. **Articles Pagination**: Backend pagination implementation with frontend pagination component
3. **Schedule Management**: Dynamic Celery Beat integration with persistent storage
4. **WebSocket Support**: Optional for real-time job progress updates (alternative to polling)
