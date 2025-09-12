# External APIs

Dựa trên newspaper4k-master và PRD requirements, hệ thống sẽ integrate với các external APIs sau:

## Google News API

- **Purpose:** Primary source cho news discovery và search theo keywords với OR logic
- **Documentation:** Integrated trong newspaper4k-master qua GoogleNewsSource class  
- **Base URL(s):** `https://news.google.com/rss/search` (RSS feeds), các internal Google News URLs
- **Authentication:** Không cần API key, sử dụng public RSS feeds
- **Rate Limits:** Không official documentation, cần implement conservative rate limiting (~1-2 requests/second)

**Key Endpoints Used:**
- `GET /rss/search?q={query}&hl={language}&gl={country}&ceid={region}` - Search news với keywords
- Newspaper4k-master GoogleNewsSource handles URL construction và parameters

**Integration Notes:** 
- Newspaper4k-master đã có sẵn GoogleNewsSource class với filtering options
- Có proxy support built-in cho anti-blocking
- URL decoding tự động từ Google News URLs về original URLs
- Cần implement additional rate limiting và retry logic

## Individual News Website APIs

- **Purpose:** Extract full article content từ original news sources sau khi get URLs từ Google News
- **Documentation:** Varies per website, newspaper4k-master handles extraction automatically
- **Base URL(s):** Dynamic based on source URLs from Google News results  
- **Authentication:** None (public articles), một số sites có thể require headers/user agents
- **Rate Limits:** Varies per website, cần implement per-domain rate limiting

**Key Endpoints Used:**
- `GET {article_url}` - Fetch full article HTML content
- Newspaper4k-master extractors handle parsing: TitleExtractor, ContentExtractor, AuthorsExtractor, etc.

**Integration Notes:**
- Newspaper4k-master có CloudScraper support để bypass Cloudflare protection
- Multi-threaded downloads với ThreadPoolExecutor
- Configurable timeout settings
- Cần handle various content types và encoding issues

## Redis API (Internal)

- **Purpose:** Job queue cho Celery và caching layer cho rate limiting
- **Documentation:** Standard Redis commands
- **Base URL(s):** `redis://localhost:6379` (local), configurable cho production
- **Authentication:** Optional password authentication
- **Rate Limits:** Local Redis instance, no external limits

**Key Operations:**
- Job queue operations cho Celery
- SET/GET cho rate limiting counters  
- TTL operations cho cache expiration

## PostgreSQL (Internal)

- **Purpose:** Primary data storage, không phải external API nhưng cần note connection requirements
- **Base URL(s):** `postgresql://user:pass@localhost:5432/dbname`
- **Authentication:** Username/password authentication
- **Rate Limits:** Connection pool limits, query timeout limits

## Integration Architecture

```mermaid
sequenceDiagram
    participant SCH as Scheduler
    participant CE as Crawler Engine  
    participant N4K as newspaper4k-master
    participant GN as Google News
    participant NS as News Sites
    participant DB as PostgreSQL
    
    SCH->>CE: trigger_crawl(category)
    CE->>N4K: GoogleNewsSource.search(keywords)
    N4K->>GN: RSS search request
    GN-->>N4K: news URLs list
    N4K->>NS: fetch article content
    NS-->>N4K: HTML content
    N4K->>N4K: extract title, content, author, etc
    N4K-->>CE: extracted articles
    CE->>DB: save articles with deduplication
    CE-->>SCH: crawl completed
```

## Rate Limiting Strategy

### Google News Rate Limiting
```python
class GoogleNewsRateLimiter:
    def __init__(self, requests_per_second=1.5):
        self.requests_per_second = requests_per_second
        self.last_request_time = 0
    
    async def wait_if_needed(self):
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        min_interval = 1.0 / self.requests_per_second
        
        if time_since_last < min_interval:
            wait_time = min_interval - time_since_last
            await asyncio.sleep(wait_time)
        
        self.last_request_time = time.time()
```

### Per-Domain Rate Limiting
```python
class DomainRateLimiter:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.default_requests_per_minute = 30
    
    async def can_request(self, domain: str) -> bool:
        key = f"rate_limit:{domain}"
        current_requests = await self.redis.get(key) or 0
        
        if int(current_requests) >= self.default_requests_per_minute:
            return False
            
        # Increment counter
        await self.redis.incr(key)
        await self.redis.expire(key, 60)  # 1 minute window
        return True
```

## Error Handling & Resilience

### Circuit Breaker Pattern
```python
class ExternalServiceCircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=300):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
    
    def can_execute(self) -> bool:
        if self.state == "closed":
            return True
        elif self.state == "open":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "half-open"
                return True
            return False
        else:  # half-open
            return True
    
    def record_success(self):
        self.failure_count = 0
        self.state = "closed"
    
    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
```

## Integration Best Practices

1. **Conservative Rate Limiting:** Better safe than blocked
2. **Graceful Degradation:** Continue working even if some sources fail
3. **Comprehensive Logging:** Track all external API interactions
4. **Retry with Backoff:** Exponential backoff for failed requests
5. **Health Monitoring:** Monitor external service availability
6. **Fallback Mechanisms:** Alternative sources when primary fails