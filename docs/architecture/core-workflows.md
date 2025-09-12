# Core Workflows

Minh họa các key system workflows bằng sequence diagrams cho critical user journeys từ PRD.

## Workflow 1: Scheduled Category Crawling

```mermaid
sequenceDiagram
    participant CRON as Cron/Scheduler
    participant SCH as Scheduler Service
    participant CELERY as Celery Queue
    participant WORKER as Crawler Worker
    participant N4K as newspaper4k-master
    participant GN as Google News
    participant NS as News Sites
    participant DB as Database Service
    participant REDIS as Redis Cache
    
    CRON->>SCH: trigger scheduled crawl
    SCH->>DB: get active categories
    DB-->>SCH: categories list
    
    loop For each category
        SCH->>CELERY: queue_crawl_job(category_id)
        SCH->>DB: create CrawlJob(pending)
    end
    
    CELERY->>WORKER: assign crawl task
    WORKER->>DB: update CrawlJob(running)
    
    WORKER->>REDIS: check rate limit
    alt Rate limit OK
        WORKER->>N4K: GoogleNewsSource.search(category.keywords OR logic)
        N4K->>GN: search request with OR keywords
        GN-->>N4K: news URLs + metadata
        
        loop For each article URL
            WORKER->>REDIS: check rate limit for domain
            alt Rate limit OK
                N4K->>NS: fetch article HTML
                NS-->>N4K: article content
                N4K->>N4K: extract(title, content, author, date, image)
            else Rate limited
                WORKER->>WORKER: sleep with exponential backoff
            end
        end
        
        N4K-->>WORKER: extracted articles list
        WORKER->>DB: save_articles_with_deduplication(articles, category_id)
        DB->>DB: check duplicates by URL hash
        DB-->>WORKER: saved count
        
        WORKER->>DB: update CrawlJob(completed, articles_found=count)
    else Rate limited
        WORKER->>DB: update CrawlJob(failed, error="rate_limited")
        WORKER->>CELERY: schedule retry with delay
    end
```

## Workflow 2: Manual Category Management

```mermaid
sequenceDiagram
    participant USER as Admin User
    participant API as API Service
    participant CM as Category Manager
    participant DB as Database Service
    participant SCH as Scheduler Service
    participant CELERY as Celery Queue
    
    USER->>API: POST /categories {name, keywords}
    API->>CM: create_category(name, keywords)
    CM->>CM: validate keywords OR logic
    CM->>DB: save new category
    DB-->>CM: category created
    CM-->>API: category object
    API-->>USER: 201 Created + category
    
    Note over USER,CELERY: Manual crawl trigger
    USER->>API: POST /categories/{id}/trigger-crawl
    API->>SCH: trigger_immediate_crawl(category_id)
    SCH->>CELERY: queue high priority crawl job
    SCH->>DB: create CrawlJob(pending, priority=high)
    SCH-->>API: job queued
    API-->>USER: 202 Accepted + job_id
    
    Note over USER,DB: Update category keywords
    USER->>API: PUT /categories/{id} {new_keywords}
    API->>CM: update_category(id, new_keywords)
    CM->>CM: validate new keywords
    CM->>DB: update category
    CM->>SCH: reschedule_category_jobs(category_id)
    SCH->>CELERY: cancel old jobs, queue new ones
    CM-->>API: updated category
    API-->>USER: 200 OK + updated category
```

## Workflow 3: Article Deduplication Flow

```mermaid
sequenceDiagram
    participant WORKER as Crawler Worker
    participant DB as Database Service
    participant HASH as Hash Generator
    
    WORKER->>WORKER: extracted articles from crawl
    
    loop For each article
        WORKER->>HASH: generate URL hash + content hash
        HASH-->>WORKER: article hashes
        
        WORKER->>DB: check_duplicate_by_url_hash(url_hash)
        
        alt Article exists
            DB-->>WORKER: existing article found
            WORKER->>DB: check if content changed (content_hash)
            alt Content different
                DB->>DB: update article content + updated_at
                DB->>DB: keep existing category associations
            else Content same
                DB->>DB: only update last_seen timestamp
            end
        else New article
            DB-->>WORKER: no duplicate found
            WORKER->>DB: insert new article
            WORKER->>DB: create article_category associations
        end
    end
    
    WORKER->>DB: cleanup orphaned articles (optional)
    Note over DB: Remove articles older than retention period
```

## Workflow 4: Error Handling & Retry Flow

```mermaid
sequenceDiagram
    participant WORKER as Crawler Worker
    participant N4K as newspaper4k-master
    participant EXT as External Service
    participant DB as Database Service
    participant CELERY as Celery Queue
    
    WORKER->>N4K: crawl request
    N4K->>EXT: HTTP request
    
    alt Network Error
        EXT-->>N4K: ConnectionError/Timeout
        N4K-->>WORKER: Exception raised
        WORKER->>WORKER: increment retry_count
        
        alt retry_count < MAX_RETRIES
            WORKER->>CELERY: schedule retry with exponential backoff
            WORKER->>DB: update CrawlJob(status=pending, retry_count++)
        else Max retries exceeded
            WORKER->>DB: update CrawlJob(status=failed, error_message)
            WORKER->>WORKER: log critical error for monitoring
        end
        
    else Rate Limited (429/403)
        EXT-->>N4K: HTTP 429/403 response
        N4K-->>WORKER: Rate limit detected
        WORKER->>REDIS: increase backoff time for domain
        WORKER->>CELERY: schedule retry after longer delay
        WORKER->>DB: update CrawlJob(status=pending, error="rate_limited")
        
    else Extraction Error
        EXT-->>N4K: Invalid HTML/parsing error
        N4K-->>WORKER: Partial extraction or empty result
        WORKER->>WORKER: log extraction error
        WORKER->>DB: save partial article if title exists
        Note over WORKER: Continue with next article, don't fail entire job
        
    else Success
        EXT-->>N4K: Valid response
        N4K-->>WORKER: Extracted article data
        WORKER->>DB: save article successfully
    end
```

## Workflow 5: System Startup & Initialization

```mermaid
sequenceDiagram
    participant DOCKER as Docker Compose
    participant PG as PostgreSQL
    participant REDIS as Redis
    participant APP as Application
    participant CELERY_W as Celery Worker
    participant CELERY_B as Celery Beat
    
    DOCKER->>PG: start database container
    DOCKER->>REDIS: start cache container
    
    PG->>PG: initialize database
    REDIS->>REDIS: initialize cache
    
    DOCKER->>APP: start application container
    APP->>PG: check database connection
    APP->>REDIS: check cache connection
    APP->>APP: run database migrations
    APP->>APP: load configuration
    APP->>APP: start FastAPI server
    
    DOCKER->>CELERY_W: start worker containers
    CELERY_W->>REDIS: connect to broker
    CELERY_W->>PG: connect to database
    CELERY_W->>CELERY_W: register task handlers
    
    DOCKER->>CELERY_B: start beat scheduler
    CELERY_B->>REDIS: connect to broker
    CELERY_B->>CELERY_B: load scheduled tasks
    CELERY_B->>REDIS: start scheduling periodic jobs
    
    Note over DOCKER: All services running and healthy
```

## Key Workflow Principles

1. **Asynchronous Processing:** Scheduler không block chờ crawl completion
2. **Graceful Error Handling:** Different strategies cho different error types
3. **Rate Limiting Respect:** Multiple checkpoints để avoid getting blocked
4. **Deduplication Efficiency:** Hash-based checking before expensive database operations
5. **Retry Logic:** Exponential backoff với max attempts để avoid infinite loops
6. **Status Tracking:** Comprehensive job status updates for monitoring
7. **Resource Management:** Cleanup và memory management trong long-running processes