# Coding Standards

Define MINIMAL but CRITICAL standards cho AI agents - chỉ focus vào project-specific rules ngăn common mistakes.

## Critical Development Rules

- **Database Transactions:** Always use async context managers cho database operations - `async with db_session.begin()`
- **Error Handling:** All Celery tasks must use try/except với proper logging và job status updates
- **Rate Limiting:** Never make direct external API calls - always go through RateLimiter class
- **Configuration Access:** Use dependency injection cho settings, never import config directly trong business logic
- **newspaper4k Integration:** Always wrap newspaper4k calls trong timeout context và error handling
- **UUID Usage:** Use UUID4 cho all primary keys, convert to string cho JSON responses
- **Async/Await Consistency:** All database operations must be async, repository methods must return awaitable
- **Logging Format:** Use structured logging với correlation IDs cho tracing requests
- **Environment Variables:** Access chỉ through Pydantic Settings classes, validate at startup
- **Docker Health Checks:** All services must implement health check endpoints với proper dependency checking

## Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Classes | PascalCase | `CategoryManager`, `CrawlerEngine` |
| Functions/Methods | snake_case | `crawl_category()`, `save_articles()` |
| Variables | snake_case | `article_count`, `category_id` |
| Constants | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT`, `DEFAULT_TIMEOUT` |
| Files/Modules | snake_case | `category_manager.py`, `article_repo.py` |
| API Endpoints | kebab-case | `/api/v1/crawl-jobs`, `/categories/{id}/trigger-crawl` |
| Database Tables | snake_case | `articles`, `article_categories` |
| Database Columns | snake_case | `created_at`, `source_url` |
| Environment Variables | UPPER_SNAKE_CASE | `DATABASE_URL`, `CELERY_BROKER_URL` |
| Docker Services | kebab-case | `celery-worker`, `celery-beat` |

## Code Quality Examples

### ✅ GOOD: Proper Async Database Operation

```python
async def create_article(self, article_data: dict, category_id: UUID) -> Article:
    async with self.db_session.begin():
        try:
            article = Article(**article_data)
            self.db_session.add(article)
            await self.db_session.flush()
            
            # Add category association
            association = ArticleCategory(
                article_id=article.id,
                category_id=category_id
            )
            self.db_session.add(association)
            
            return article
        except Exception as e:
            logger.error(f"Failed to create article: {e}", extra={
                "article_url": article_data.get("source_url"),
                "category_id": str(category_id)
            })
            raise
```

### ❌ BAD: Missing Error Handling và Logging

```python
def create_article(self, article_data: dict, category_id: UUID):
    article = Article(**article_data)
    self.db_session.add(article)
    self.db_session.commit()
    return article
```

### ✅ GOOD: Proper Celery Task Structure

```python
@celery_app.task(bind=True, max_retries=3)
def crawl_category_task(self, category_id: str):
    logger.info(f"Starting crawl for category {category_id}")
    
    try:
        from src.core.crawler.engine import CrawlerEngine
        from src.database.repositories.category_repo import CategoryRepository
        
        # Update job status
        job_repo = CrawlJobRepository()
        job = job_repo.update_status(self.request.id, "running")
        
        # Execute crawl
        crawler = CrawlerEngine()
        article_count = crawler.crawl_category(UUID(category_id))
        
        # Update completion status
        job_repo.update_status(
            self.request.id, 
            "completed",
            articles_found=article_count
        )
        
        logger.info(f"Crawl completed: {article_count} articles found")
        return {"status": "completed", "articles": article_count}
        
    except Exception as e:
        logger.error(f"Crawl failed for category {category_id}: {e}")
        
        # Update failed status
        job_repo.update_status(
            self.request.id,
            "failed", 
            error_message=str(e)
        )
        
        # Retry with exponential backoff
        raise self.retry(countdown=60 * (2 ** self.request.retries))
```

### ❌ BAD: No Error Handling, Status Updates, or Retry Logic

```python
@celery_app.task
def crawl_category_task(category_id: str):
    crawler = CrawlerEngine()
    return crawler.crawl_category(category_id)
```

### ✅ GOOD: Rate Limiting Wrapper

```python
class RateLimiter:
    def __init__(self, redis_client):
        self.redis = redis_client
    
    async def check_rate_limit(self, key: str, limit: int, window: int) -> bool:
        current_count = await self.redis.get(key)
        
        if current_count is None:
            await self.redis.setex(key, window, 1)
            return True
        
        if int(current_count) >= limit:
            return False
        
        await self.redis.incr(key)
        return True

# Usage trong crawler
async def crawl_with_rate_limiting(self, url: str):
    if not await self.rate_limiter.check_rate_limit(
        f"crawler:{domain}", 
        limit=2, 
        window=60
    ):
        logger.warning(f"Rate limit exceeded for {domain}")
        raise RateLimitExceededError(f"Too many requests to {domain}")
    
    return await self.fetch_article(url)
```

### ❌ BAD: Direct External Calls Without Rate Limiting

```python
async def crawl_article(self, url: str):
    return requests.get(url)  # No rate limiting!
```

## Import Organization

```python
# Standard library imports
import asyncio
import logging
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4

# Third-party imports  
import redis
from celery import Celery
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

# Local application imports
from src.shared.config import get_settings
from src.shared.exceptions import CrawlerError
from src.database.models import Article, Category
from src.database.repositories.base import BaseRepository
```

## Configuration Pattern

### ✅ GOOD: Dependency Injection Pattern

```python
class CategoryManager:
    def __init__(
        self,
        repository: CategoryRepository,
        settings: Settings = Depends(get_settings),
        logger: Logger = Depends(get_logger)
    ):
        self.repository = repository
        self.settings = settings
        self.logger = logger
        self.max_keywords = settings.MAX_KEYWORDS_PER_CATEGORY
```

### ❌ BAD: Direct Import and Access

```python
from src.shared.config import settings  # Don't do this!

class CategoryManager:
    def __init__(self, repository: CategoryRepository):
        self.repository = repository
        self.max_keywords = settings.MAX_KEYWORDS_PER_CATEGORY  # Bad!
```

## Error Handling Pattern

### ✅ GOOD: Structured Error Handling với Context

```python
async def extract_article_content(self, url: str) -> Optional[Dict]:
    correlation_id = str(uuid4())
    
    try:
        logger.info(f"Extracting article: {url}", extra={
            "correlation_id": correlation_id,
            "url": url
        })
        
        # newspaper4k extraction với timeout
        async with asyncio.timeout(self.settings.EXTRACTION_TIMEOUT):
            article_data = await self.newspaper_extractor.extract(url)
        
        if not article_data or not article_data.get('title'):
            logger.warning(f"No content extracted from {url}", extra={
                "correlation_id": correlation_id
            })
            return None
        
        return article_data
        
    except asyncio.TimeoutError:
        logger.error(f"Extraction timeout for {url}", extra={
            "correlation_id": correlation_id,
            "timeout": self.settings.EXTRACTION_TIMEOUT
        })
        return None
        
    except Exception as e:
        logger.error(f"Extraction failed for {url}: {e}", extra={
            "correlation_id": correlation_id,
            "error_type": type(e).__name__
        })
        return None
```

### ❌ BAD: Generic Exception Handling

```python
def extract_article_content(self, url: str):
    try:
        return self.newspaper_extractor.extract(url)
    except:  # Too broad!
        return None  # No logging!
```

## Testing Standards

### ✅ GOOD: Descriptive Test Names và Proper Setup

```python
class TestCategoryManager:
    @pytest.fixture
    async def category_manager(self, mock_repository, test_settings):
        return CategoryManager(
            repository=mock_repository,
            settings=test_settings
        )
    
    @pytest.mark.asyncio
    async def test_create_category_with_valid_keywords_succeeds(
        self, category_manager, mock_repository
    ):
        # Arrange
        category_data = {
            "name": "Technology", 
            "keywords": ["python", "javascript"]
        }
        mock_repository.create.return_value = Category(**category_data)
        
        # Act
        result = await category_manager.create_category(
            name="Technology",
            keywords=["python", "javascript"]
        )
        
        # Assert
        assert result.name == "Technology"
        assert len(result.keywords) == 2
        mock_repository.create.assert_called_once()
```

### ❌ BAD: Vague Test Names và No Setup

```python
def test_category(self):
    manager = CategoryManager()  # No proper setup
    result = manager.create_category("test", ["keyword"])
    assert result  # Weak assertion
```

## Documentation Standards

### Docstring Format

```python
async def crawl_category(self, category: Category) -> List[Article]:
    """Crawl articles for a specific category using newspaper4k.
    
    Args:
        category: Category object with keywords for search
        
    Returns:
        List of extracted Article objects
        
    Raises:
        RateLimitExceededError: When external API rate limit hit
        ExtractionError: When article extraction fails
        
    Example:
        >>> articles = await crawler.crawl_category(tech_category)
        >>> len(articles)
        15
    """
```

## Performance Guidelines

### Database Query Optimization

```python
# ✅ GOOD: Use specific queries với limits
async def get_recent_articles(self, limit: int = 50) -> List[Article]:
    query = select(Article).order_by(
        Article.created_at.desc()
    ).limit(limit)
    result = await self.db.execute(query)
    return result.scalars().all()

# ❌ BAD: Load all data
async def get_recent_articles(self) -> List[Article]:
    query = select(Article).order_by(Article.created_at.desc())
    result = await self.db.execute(query)
    return result.scalars().all()  # Could be thousands!
```

### Memory Management

```python
# ✅ GOOD: Process trong batches
async def process_articles_batch(self, articles: List[str]) -> int:
    processed = 0
    batch_size = 50
    
    for i in range(0, len(articles), batch_size):
        batch = articles[i:i + batch_size]
        
        # Process batch
        for article_url in batch:
            await self.process_single_article(article_url)
            processed += 1
        
        # Clear memory periodically
        if processed % 200 == 0:
            gc.collect()
    
    return processed
```

## Security Guidelines

### Input Validation

```python
# ✅ GOOD: Validate all inputs
class CreateCategoryRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    keywords: List[str] = Field(..., min_items=1, max_items=20)
    
    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('Category name cannot be empty')
        return v.strip()
    
    @validator('keywords')
    def validate_keywords(cls, v):
        cleaned = [kw.strip() for kw in v if kw.strip()]
        if not cleaned:
            raise ValueError('At least one valid keyword required')
        return cleaned
```

### SQL Injection Prevention

```python
# ✅ GOOD: Use parameterized queries
async def search_articles_by_title(self, search_term: str):
    query = select(Article).where(
        Article.title.ilike(f"%{search_term}%")
    )
    return await self.db.execute(query)

# ❌ BAD: String concatenation
async def search_articles_by_title(self, search_term: str):
    sql = f"SELECT * FROM articles WHERE title ILIKE '%{search_term}%'"
    return await self.db.execute(text(sql))
```