# REST API Specification

Dựa trên tech stack đã chọn (FastAPI), đây là REST API specification cho management interface (optional) của hệ thống.

## OpenAPI 3.0 Specification

```yaml
openapi: 3.0.0
info:
  title: Google News Scraper API
  version: 1.0.0
  description: Management API cho Google News Scraper system
servers:
  - url: http://localhost:8000/api/v1
    description: Local development server
  - url: https://your-domain.com/api/v1
    description: Production server

paths:
  /categories:
    get:
      summary: List all categories
      parameters:
        - name: active_only
          in: query
          schema:
            type: boolean
            default: true
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/Category'
    post:
      summary: Create new category
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CreateCategoryRequest'
      responses:
        '201':
          description: Category created
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Category'

  /categories/{category_id}:
    get:
      summary: Get category by ID
      parameters:
        - name: category_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Category'
    put:
      summary: Update category
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
        '200':
          description: Category updated
    delete:
      summary: Delete category
      parameters:
        - name: category_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      responses:
        '204':
          description: Category deleted

  /categories/{category_id}/trigger-crawl:
    post:
      summary: Manually trigger crawl for category
      parameters:
        - name: category_id
          in: path
          required: true
          schema:
            type: string
            format: uuid
      responses:
        '202':
          description: Crawl job queued
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/CrawlJob'

  /articles:
    get:
      summary: List articles with filtering
      parameters:
        - name: category_id
          in: query
          schema:
            type: string
            format: uuid
        - name: limit
          in: query
          schema:
            type: integer
            default: 50
            maximum: 100
        - name: offset
          in: query
          schema:
            type: integer
            default: 0
        - name: from_date
          in: query
          schema:
            type: string
            format: date-time
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ArticleListResponse'

  /crawl-jobs:
    get:
      summary: List crawl jobs with status
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
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/CrawlJob'

  /health:
    get:
      summary: Health check endpoint
      responses:
        '200':
          description: System healthy
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/HealthResponse'

components:
  schemas:
    Category:
      type: object
      properties:
        id:
          type: string
          format: uuid
        name:
          type: string
        keywords:
          type: array
          items:
            type: string
        exclude_keywords:
          type: array
          items:
            type: string
        is_active:
          type: boolean
        created_at:
          type: string
          format: date-time
        updated_at:
          type: string
          format: date-time

    CreateCategoryRequest:
      type: object
      required:
        - name
        - keywords
      properties:
        name:
          type: string
        keywords:
          type: array
          items:
            type: string
        exclude_keywords:
          type: array
          items:
            type: string
        is_active:
          type: boolean
          default: true

    UpdateCategoryRequest:
      type: object
      properties:
        name:
          type: string
        keywords:
          type: array
          items:
            type: string
        exclude_keywords:
          type: array
          items:
            type: string
        is_active:
          type: boolean

    Article:
      type: object
      properties:
        id:
          type: string
          format: uuid
        title:
          type: string
        content:
          type: string
        author:
          type: string
          nullable: true
        publish_date:
          type: string
          format: date-time
        source_url:
          type: string
          format: uri
        image_url:
          type: string
          format: uri
          nullable: true
        created_at:
          type: string
          format: date-time
        categories:
          type: array
          items:
            $ref: '#/components/schemas/Category'

    ArticleListResponse:
      type: object
      properties:
        articles:
          type: array
          items:
            $ref: '#/components/schemas/Article'
        total:
          type: integer
        limit:
          type: integer
        offset:
          type: integer

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
        started_at:
          type: string
          format: date-time
          nullable: true
        completed_at:
          type: string
          format: date-time
          nullable: true
        articles_found:
          type: integer
        error_message:
          type: string
          nullable: true
        retry_count:
          type: integer
        created_at:
          type: string
          format: date-time

    HealthResponse:
      type: object
      properties:
        status:
          type: string
          enum: [healthy, degraded]
        database:
          type: string
          enum: [connected, disconnected]
        redis:
          type: string
          enum: [connected, disconnected]
        celery_workers:
          type: integer
        last_successful_crawl:
          type: string
          format: date-time
          nullable: true
```

## Design Decisions

- **REST over GraphQL:** Đơn giản hơn cho management interface, không cần complex queries
- **UUID trong paths:** Consistent với data model design
- **Pagination support:** Essential cho large datasets
- **Manual trigger endpoint:** Hữu ích cho testing và debugging
- **Health check comprehensive:** Monitor tất cả dependencies (DB, Redis, Celery)
- **Error responses standard:** Consistent error handling across endpoints