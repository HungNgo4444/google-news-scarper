# Security and Performance

Define security và performance considerations cho fullstack application trên VPS environment.

## Security Requirements

### Application Security

**Input Validation:**
- Pydantic schemas validate tất cả request data
- SQLAlchemy prevents SQL injection với parameterized queries
- URL validation cho external requests
- File upload validation (if implemented)

**API Security:**
- Optional API key authentication cho admin endpoints
- Request rate limiting (10 req/s per IP via Nginx)
- CORS policy restrictive cho production
- Request size limits để prevent DoS attacks

**Data Security:**
- Database connection encryption (SSL/TLS)
- Sensitive data không stored trong logs
- Environment variables cho all secrets
- Regular backup encryption

### Infrastructure Security

**Server Hardening:**
- UFW firewall allow only ports 22 (SSH), 80 (HTTP), 443 (HTTPS)
- SSH key-based authentication only, disable password login
- Fail2ban cho brute force protection
- Automatic security updates enabled

**Container Security:**
- Non-root user trong Docker containers
- Minimal base images (python:3.11-slim)
- Regular container image updates
- Read-only filesystems where possible

**Network Security:**
- Internal Docker networks cho service isolation
- Nginx reverse proxy cho SSL termination
- No direct database access từ external
- VPN access cho administrative tasks

**SSL/TLS Configuration:**
```nginx
# Strong SSL configuration
ssl_protocols TLSv1.2 TLSv1.3;
ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384;
ssl_prefer_server_ciphers off;
ssl_session_timeout 10m;
ssl_session_cache shared:SSL:10m;

# Security headers
add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload";
add_header X-Content-Type-Options nosniff;
add_header X-Frame-Options DENY;
add_header X-XSS-Protection "1; mode=block";
add_header Referrer-Policy "strict-origin-when-cross-origin";
```

### Application-Level Security

**Rate Limiting Implementation:**
```python
class RateLimiter:
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def check_rate_limit(
        self, 
        key: str, 
        limit: int, 
        window: int,
        identifier: str = None
    ) -> bool:
        """Check if request is within rate limits"""
        
        # Create unique key
        rate_key = f"rate_limit:{key}:{identifier or 'anonymous'}"
        
        current_count = await self.redis.get(rate_key)
        
        if current_count is None:
            # First request trong window
            await self.redis.setex(rate_key, window, 1)
            return True
        
        if int(current_count) >= limit:
            return False
        
        await self.redis.incr(rate_key)
        return True

# Usage trong API endpoints
@app.middleware("http")
async def rate_limiting_middleware(request: Request, call_next):
    client_ip = request.client.host
    rate_limiter = RateLimiter(redis_client)
    
    # Different limits cho different endpoints
    if request.url.path.startswith("/api/"):
        allowed = await rate_limiter.check_rate_limit(
            "api", 60, 60, client_ip  # 60 requests per minute
        )
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded"}
            )
    
    response = await call_next(request)
    return response
```

**Input Sanitization:**
```python
import html
import re
from urllib.parse import urlparse

class InputSanitizer:
    @staticmethod
    def sanitize_html(text: str) -> str:
        """Remove HTML tags và escape special characters"""
        if not text:
            return ""
        
        # Remove HTML tags
        clean_text = re.sub('<.*?>', '', text)
        # Escape HTML entities
        return html.escape(clean_text)
    
    @staticmethod
    def validate_url(url: str) -> bool:
        """Validate URL format và allowed schemes"""
        try:
            parsed = urlparse(url)
            return parsed.scheme in ['http', 'https'] and bool(parsed.netloc)
        except Exception:
            return False
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Remove dangerous characters từ filenames"""
        # Remove path traversal attempts
        filename = os.path.basename(filename)
        # Remove dangerous characters
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        return filename[:255]  # Limit length
```

## Performance Optimization

### Database Performance

**Connection Pooling:**
```python
from sqlalchemy.pool import QueuePool

engine = create_async_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,          # Number of connections to maintain
    max_overflow=20,       # Additional connections when needed
    pool_timeout=30,       # Timeout when getting connection
    pool_recycle=3600,     # Recycle connections every hour
    pool_pre_ping=True,    # Validate connections before use
    echo=False             # Disable SQL logging in production
)
```

**Query Optimization:**
```python
# ✅ GOOD: Use specific selects với joins
async def get_articles_with_categories(self, limit: int = 50):
    query = select(
        Article.id,
        Article.title, 
        Article.created_at,
        func.array_agg(Category.name).label('category_names')
    ).select_from(
        Article.__table__.join(article_categories)
        .join(Category.__table__)
    ).group_by(
        Article.id
    ).order_by(
        Article.created_at.desc()
    ).limit(limit)
    
    result = await self.db.execute(query)
    return result.all()

# ✅ GOOD: Use pagination
async def get_articles_paginated(
    self, 
    page: int = 1, 
    size: int = 20
) -> Tuple[List[Article], int]:
    offset = (page - 1) * size
    
    # Get total count
    count_query = select(func.count(Article.id))
    total = await self.db.scalar(count_query)
    
    # Get paginated results
    query = select(Article).order_by(
        Article.created_at.desc()
    ).offset(offset).limit(size)
    
    result = await self.db.execute(query)
    articles = result.scalars().all()
    
    return articles, total
```

**Database Indexes Strategy:**
```sql
-- Performance-critical indexes
CREATE INDEX CONCURRENTLY idx_articles_created_at_desc ON articles(created_at DESC);
CREATE INDEX CONCURRENTLY idx_articles_category_lookup ON article_categories(category_id, created_at DESC);
CREATE INDEX CONCURRENTLY idx_crawl_jobs_status_priority ON crawl_jobs(status, priority DESC) WHERE status = 'pending';

-- Partial indexes cho common filters
CREATE INDEX CONCURRENTLY idx_active_categories ON categories(name) WHERE is_active = true;
CREATE INDEX CONCURRENTLY idx_recent_articles ON articles(created_at) WHERE created_at > CURRENT_DATE - INTERVAL '30 days';

-- Full-text search indexes
CREATE INDEX CONCURRENTLY idx_articles_title_search ON articles USING gin(to_tsvector('english', title));
```

### Application Performance

**Async Processing:**
```python
import asyncio
from typing import List, Coroutine

class AsyncBatchProcessor:
    def __init__(self, max_concurrent: int = 10):
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_batch(
        self, 
        items: List[str], 
        processor_func: Coroutine
    ) -> List[any]:
        """Process items concurrently với rate limiting"""
        
        async def process_with_semaphore(item):
            async with self.semaphore:
                return await processor_func(item)
        
        tasks = [process_with_semaphore(item) for item in items]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        successful_results = [
            result for result in results 
            if not isinstance(result, Exception)
        ]
        
        return successful_results

# Usage trong crawler
async def crawl_articles_batch(self, urls: List[str]) -> List[Article]:
    processor = AsyncBatchProcessor(max_concurrent=5)
    
    return await processor.process_batch(
        urls, 
        self.extract_single_article
    )
```

**Memory Management:**
```python
import gc
import psutil
from typing import Generator, List

class MemoryOptimizedProcessor:
    def __init__(self, memory_threshold_mb: int = 512):
        self.memory_threshold = memory_threshold_mb * 1024 * 1024
    
    def process_large_dataset(
        self, 
        dataset: List[any], 
        batch_size: int = 100
    ) -> Generator[List[any], None, None]:
        """Process large datasets trong memory-efficient chunks"""
        
        for i in range(0, len(dataset), batch_size):
            batch = dataset[i:i + batch_size]
            
            yield batch
            
            # Memory management
            memory_usage = psutil.Process().memory_info().rss
            if memory_usage > self.memory_threshold:
                gc.collect()
    
    async def crawl_with_memory_management(
        self, 
        article_urls: List[str]
    ) -> int:
        """Crawl articles với memory management"""
        total_processed = 0
        
        for batch in self.process_large_dataset(article_urls, batch_size=50):
            # Process batch
            articles = await self.extract_articles_batch(batch)
            
            # Save to database immediately
            saved_count = await self.save_articles_batch(articles)
            total_processed += saved_count
            
            # Clear batch from memory
            del articles, batch
            gc.collect()
        
        return total_processed
```

### External Service Performance

**Circuit Breaker Pattern:**
```python
import time
from typing import Callable, Any
from enum import Enum

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open" 
    HALF_OPEN = "half_open"

class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: Exception = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function với circuit breaker protection"""
        
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        return (
            time.time() - self.last_failure_time >= self.recovery_timeout
        )
    
    def _on_success(self):
        self.failure_count = 0
        self.state = CircuitState.CLOSED
    
    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN

# Usage
google_news_breaker = CircuitBreaker(
    failure_threshold=3,
    recovery_timeout=120  # 2 minutes
)

async def safe_google_news_call(query: str):
    return await google_news_breaker.call(
        self.google_news_client.search,
        query
    )
```

### Caching Strategy

**Multi-Level Caching:**
```python
from functools import wraps
import json
import hashlib

class CacheManager:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.default_ttl = 3600  # 1 hour
    
    def cache_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key từ function arguments"""
        key_data = f"{prefix}:{args}:{sorted(kwargs.items())}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    async def get(self, key: str) -> any:
        """Get value từ cache"""
        cached = await self.redis.get(key)
        if cached:
            return json.loads(cached)
        return None
    
    async def set(self, key: str, value: any, ttl: int = None) -> None:
        """Set value trong cache"""
        ttl = ttl or self.default_ttl
        serialized = json.dumps(value, default=str)
        await self.redis.setex(key, ttl, serialized)
    
    def cached(self, ttl: int = None, prefix: str = "cache"):
        """Decorator để cache function results"""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Generate cache key
                cache_key = self.cache_key(
                    f"{prefix}:{func.__name__}", 
                    *args, 
                    **kwargs
                )
                
                # Try to get từ cache
                cached_result = await self.get(cache_key)
                if cached_result is not None:
                    return cached_result
                
                # Execute function
                result = await func(*args, **kwargs)
                
                # Cache result
                await self.set(cache_key, result, ttl)
                
                return result
            return wrapper
        return decorator

# Usage
cache_manager = CacheManager(redis_client)

@cache_manager.cached(ttl=1800, prefix="categories")
async def get_active_categories():
    """Cache active categories cho 30 minutes"""
    return await self.category_repo.get_active()

@cache_manager.cached(ttl=300, prefix="articles")
async def get_recent_articles(limit: int = 50):
    """Cache recent articles cho 5 minutes"""
    return await self.article_repo.get_recent(limit)
```

## Performance Targets

### Response Time Targets
- **Health Check:** < 100ms
- **Category CRUD:** < 200ms
- **Article Listing:** < 500ms  
- **Crawl Trigger:** < 100ms (async job queue)

### Throughput Targets
- **API Requests:** 100+ req/s sustained
- **Concurrent Crawling:** 5-10 concurrent article extractions
- **Database Operations:** < 50ms average query time

### Resource Utilization Targets
- **CPU Usage:** < 70% average on VPS
- **Memory Usage:** < 80% of available RAM
- **Database Connections:** < 50% of pool size
- **Disk I/O:** < 80% utilization

### Crawler Performance Targets
- **Articles per minute:** 60-120 (depending on rate limits)
- **Success rate:** > 90% for article extraction
- **External service timeout:** < 30 seconds per request
- **Memory usage:** < 1GB per crawler worker

## Monitoring Implementation

### Performance Metrics Collection
```python
import time
from contextlib import asynccontextmanager

class PerformanceMonitor:
    def __init__(self, metrics_collector):
        self.metrics = metrics_collector
    
    @asynccontextmanager
    async def monitor_operation(self, operation_name: str):
        start_time = time.time()
        success = False
        error_type = None
        
        try:
            yield
            success = True
        except Exception as e:
            error_type = type(e).__name__
            raise
        finally:
            duration = (time.time() - start_time) * 1000  # ms
            
            self.metrics.record_operation(
                operation_name=operation_name,
                duration_ms=duration,
                success=success,
                error_type=error_type
            )

# Usage
monitor = PerformanceMonitor(metrics_collector)

async def crawl_article(self, url: str) -> Article:
    async with monitor.monitor_operation("article_extraction"):
        return await self.extract_article_content(url)
```

## Security Best Practices

1. **Defense in Depth:** Multiple security layers
2. **Principle of Least Privilege:** Minimal necessary permissions
3. **Input Validation:** Validate all external inputs
4. **Output Encoding:** Escape data before output  
5. **Secure Communication:** HTTPS/TLS everywhere
6. **Regular Updates:** Keep dependencies updated
7. **Monitoring:** Log security events và anomalies
8. **Incident Response:** Plan cho security incidents

## Performance Best Practices

1. **Optimize Database Queries:** Use appropriate indexes và query patterns
2. **Implement Caching:** Multi-level caching strategy
3. **Async Processing:** Non-blocking I/O operations
4. **Resource Monitoring:** Track CPU, memory, disk usage
5. **Load Testing:** Regular performance testing
6. **Profiling:** Identify bottlenecks trong code
7. **Scaling Strategy:** Plan cho horizontal scaling
8. **Resource Limits:** Set appropriate container limits