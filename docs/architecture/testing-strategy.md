# Testing Strategy

Define comprehensive testing approach cho fullstack application với emphasis trên reliability và maintainability.

## Testing Pyramid

```text
        E2E Tests (5-10%)
       /                 \
    Integration Tests (20-30%)
   /                           \
Unit Tests (60-70%)    API Tests (20-30%)
```

## Test Organization

### Unit Tests Structure

```text
tests/unit/
├── test_core/
│   ├── test_crawler/
│   │   ├── test_engine.py          # Crawler engine logic
│   │   ├── test_extractor.py       # newspaper4k wrapper
│   │   ├── test_rate_limiter.py    # Rate limiting logic
│   │   └── test_deduplicator.py    # Deduplication logic
│   ├── test_category/
│   │   ├── test_manager.py         # Category business logic
│   │   ├── test_validator.py       # Keywords validation
│   │   └── test_search_builder.py  # OR query building
│   └── test_scheduler/
│       ├── test_tasks.py           # Celery tasks
│       └── test_cron_scheduler.py  # Scheduled jobs
├── test_database/
│   ├── test_models.py              # SQLAlchemy models
│   ├── test_repositories/
│   │   ├── test_article_repo.py    # Article repository
│   │   ├── test_category_repo.py   # Category repository
│   │   └── test_job_repo.py        # CrawlJob repository
│   └── test_migrations.py          # Database migrations
├── test_api/
│   ├── test_routes/
│   │   ├── test_categories.py      # Category endpoints
│   │   ├── test_articles.py        # Article endpoints
│   │   └── test_health.py          # Health check
│   └── test_schemas.py             # Pydantic schemas
└── test_shared/
    ├── test_config.py              # Configuration
    ├── test_utils.py               # Utilities
    └── test_exceptions.py          # Exception handling
```

### Integration Tests Structure

```text
tests/integration/
├── test_crawler_integration.py    # Full crawl workflow
├── test_database_operations.py    # Database CRUD operations  
├── test_celery_tasks.py           # Background job processing
├── test_api_endpoints.py          # End-to-end API testing
└── test_external_services.py      # newspaper4k + Google News
```

### E2E Tests Structure

```text
tests/e2e/
├── test_complete_workflows.py     # Full system workflows
├── test_scheduled_crawling.py     # Scheduled job execution
└── test_error_recovery.py         # Error handling scenarios
```

## Unit Test Examples

### Category Manager Test

```python
# tests/unit/test_core/test_category/test_manager.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from src.core.category.manager import CategoryManager
from src.database.repositories.category_repo import CategoryRepository
from src.shared.exceptions import CategoryValidationError

class TestCategoryManager:
    @pytest.fixture
    def mock_repository(self):
        """Mock category repository"""
        repo = AsyncMock(spec=CategoryRepository)
        return repo
    
    @pytest.fixture
    def category_manager(self, mock_repository):
        """Category manager with mocked repository"""
        return CategoryManager(mock_repository)
    
    @pytest.mark.asyncio
    async def test_create_category_success(self, category_manager, mock_repository):
        """Test successful category creation"""
        # Arrange
        category_data = {
            "id": uuid4(),
            "name": "Technology",
            "keywords": ["tech", "software", "AI"],
            "is_active": True
        }
        mock_repository.create.return_value = MagicMock(**category_data)
        mock_repository.get_by_name.return_value = None  # No duplicate
        
        # Act
        result = await category_manager.create_category(
            name="Technology",
            keywords=["tech", "software", "AI"]
        )
        
        # Assert
        assert result.name == "Technology"
        assert result.keywords == ["tech", "software", "AI"]
        mock_repository.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_category_duplicate_name(self, category_manager, mock_repository):
        """Test category creation with duplicate name"""
        # Arrange
        existing_category = MagicMock(name="Technology")
        mock_repository.get_by_name.return_value = existing_category
        
        # Act & Assert
        with pytest.raises(CategoryValidationError, match="Category name already exists"):
            await category_manager.create_category(
                name="Technology",
                keywords=["tech"]
            )
    
    @pytest.mark.asyncio
    async def test_validate_or_search_logic(self, category_manager):
        """Test OR logic validation for keywords"""
        # Act
        query = category_manager.build_search_query(
            keywords=["python", "javascript", "golang"]
        )
        
        # Assert
        expected = "python OR javascript OR golang"
        assert query == expected
    
    def test_validate_keywords_empty_list(self, category_manager):
        """Test validation with empty keywords list"""
        # Act & Assert
        with pytest.raises(CategoryValidationError, match="Keywords cannot be empty"):
            category_manager.validate_keywords([])
    
    def test_validate_keywords_too_many(self, category_manager):
        """Test validation with too many keywords"""
        # Arrange
        too_many_keywords = [f"keyword{i}" for i in range(21)]  # Limit is 20
        
        # Act & Assert
        with pytest.raises(CategoryValidationError, match="Too many keywords"):
            category_manager.validate_keywords(too_many_keywords)
```

### Crawler Engine Test

```python
# tests/unit/test_core/test_crawler/test_engine.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.core.crawler.engine import CrawlerEngine
from src.database.models import Category, Article
from src.shared.exceptions import RateLimitExceededError

class TestCrawlerEngine:
    @pytest.fixture
    def mock_rate_limiter(self):
        limiter = AsyncMock()
        limiter.check_rate_limit.return_value = True
        return limiter
    
    @pytest.fixture
    def mock_extractor(self):
        extractor = AsyncMock()
        return extractor
    
    @pytest.fixture
    def crawler_engine(self, mock_rate_limiter, mock_extractor):
        engine = CrawlerEngine()
        engine.rate_limiter = mock_rate_limiter
        engine.extractor = mock_extractor
        return engine
    
    @pytest.mark.asyncio
    async def test_crawl_category_success(self, crawler_engine, mock_extractor):
        """Test successful category crawling"""
        # Arrange
        category = Category(
            id=uuid4(),
            name="Technology",
            keywords=["python", "AI"],
            is_active=True
        )
        
        mock_articles = [
            {
                "title": "Python 3.13 Released",
                "content": "New features in Python...",
                "author": "John Doe",
                "source_url": "https://example.com/python-news"
            }
        ]
        mock_extractor.extract_articles.return_value = mock_articles
        
        # Act
        result = await crawler_engine.crawl_category(category)
        
        # Assert
        assert len(result) == 1
        assert result[0]["title"] == "Python 3.13 Released"
        mock_extractor.extract_articles.assert_called_once()
    
    @pytest.mark.asyncio 
    async def test_crawl_category_rate_limited(self, crawler_engine, mock_rate_limiter):
        """Test crawl with rate limit exceeded"""
        # Arrange
        category = Category(
            id=uuid4(),
            name="Technology", 
            keywords=["python"],
            is_active=True
        )
        mock_rate_limiter.check_rate_limit.return_value = False
        
        # Act & Assert
        with pytest.raises(RateLimitExceededError):
            await crawler_engine.crawl_category(category)
    
    @pytest.mark.asyncio
    async def test_apply_category_filters(self, crawler_engine):
        """Test article filtering logic"""
        # Arrange
        articles = [
            {"title": "Python Tutorial", "content": "Learn Python programming"},
            {"title": "Java News", "content": "Java 21 features"},
            {"title": "AI Revolution", "content": "Artificial intelligence advances"}
        ]
        category = Category(keywords=["python", "AI"])
        
        # Act
        filtered = await crawler_engine.apply_category_filters(articles, category)
        
        # Assert
        assert len(filtered) == 2  # Python and AI articles
        titles = [article["title"] for article in filtered]
        assert "Python Tutorial" in titles
        assert "AI Revolution" in titles
        assert "Java News" not in titles
```

## Integration Test Examples

### Full Crawl Workflow Test

```python
# tests/integration/test_crawler_integration.py
import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock

from src.main import app
from src.database.models import Category, Article
from tests.conftest import TestDatabase

class TestCrawlerIntegration:
    @pytest.fixture
    async def test_category(self, test_db):
        """Create test category"""
        category = Category(
            name="Test Tech News",
            keywords=["python", "AI", "machine learning"],
            is_active=True
        )
        test_db.add(category)
        await test_db.commit()
        await test_db.refresh(category)
        return category
    
    @pytest.mark.asyncio
    async def test_full_crawl_workflow(self, test_category, test_db):
        """Test complete crawl workflow from trigger to database save"""
        
        # Mock newspaper4k responses
        mock_articles = [
            {
                "title": "New Python Features in 2024",
                "content": "Python 3.13 introduces amazing new features...",
                "author": "John Doe", 
                "publish_date": "2024-01-15T10:00:00Z",
                "source_url": "https://example.com/python-features",
                "image_url": "https://example.com/image.jpg"
            },
            {
                "title": "AI Revolution in Healthcare",
                "content": "Artificial intelligence is transforming...",
                "author": "Jane Smith",
                "publish_date": "2024-01-14T15:30:00Z", 
                "source_url": "https://example.com/ai-healthcare",
                "image_url": None
            }
        ]
        
        with patch('src.core.crawler.engine.CrawlerEngine.crawl_category') as mock_crawl:
            mock_crawl.return_value = mock_articles
            
            # Trigger crawl via API
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.post(
                    f"/api/v1/categories/{test_category.id}/trigger-crawl"
                )
                
                assert response.status_code == 202
                job_data = response.json()
                assert job_data["status"] == "pending"
        
        # Verify articles were saved to database
        articles = await test_db.execute(
            select(Article).join(article_categories).where(
                article_categories.c.category_id == test_category.id
            )
        )
        saved_articles = articles.scalars().all()
        
        assert len(saved_articles) == 2
        assert any(article.title == "New Python Features in 2024" for article in saved_articles)
        assert any(article.title == "AI Revolution in Healthcare" for article in saved_articles)
    
    @pytest.mark.asyncio
    async def test_deduplication_workflow(self, test_category, test_db):
        """Test that duplicate articles are not saved twice"""
        
        # Create existing article
        existing_article = Article(
            title="Python News",
            source_url="https://example.com/python-news",
            url_hash=generate_url_hash("https://example.com/python-news"),
            content="Original content"
        )
        test_db.add(existing_article)
        await test_db.commit()
        
        # Mock crawler returning same URL with updated content
        mock_articles = [{
            "title": "Python News", 
            "source_url": "https://example.com/python-news",
            "content": "Updated content"  # Different content
        }]
        
        with patch('src.core.crawler.engine.CrawlerEngine.crawl_category') as mock_crawl:
            mock_crawl.return_value = mock_articles
            
            # Run deduplication logic
            from src.core.crawler.engine import CrawlerEngine
            crawler = CrawlerEngine()
            
            saved_count = await crawler.save_articles_with_deduplication(
                mock_articles, test_category.id
            )
            
            # Should update existing article, not create new one
            assert saved_count == 0  # No new articles saved
            
            # Verify content was updated
            await test_db.refresh(existing_article)
            assert existing_article.content == "Updated content"
```

## E2E Test Example

```python
# tests/e2e/test_complete_workflows.py
import pytest
import asyncio
from httpx import AsyncClient

from src.main import app

class TestCompleteWorkflows:
    @pytest.mark.asyncio
    async def test_end_to_end_news_scraping(self, test_db):
        """Test complete end-to-end workflow"""
        
        async with AsyncClient(app=app, base_url="http://test") as client:
            # 1. Create category
            category_data = {
                "name": "Python Development",
                "keywords": ["python", "django", "fastapi"],
                "is_active": True
            }
            
            response = await client.post("/api/v1/categories", json=category_data)
            assert response.status_code == 201
            category = response.json()
            category_id = category["id"]
            
            # 2. Trigger manual crawl
            response = await client.post(f"/api/v1/categories/{category_id}/trigger-crawl")
            assert response.status_code == 202
            crawl_job = response.json()
            
            # 3. Wait for job completion (simulate background processing)
            job_id = crawl_job["id"]
            max_wait = 60  # seconds
            wait_time = 0
            
            while wait_time < max_wait:
                response = await client.get(f"/api/v1/crawl-jobs/{job_id}")
                job_status = response.json()["status"]
                
                if job_status in ["completed", "failed"]:
                    break
                    
                await asyncio.sleep(2)
                wait_time += 2
            
            assert job_status == "completed"
            
            # 4. Verify articles were crawled and saved
            response = await client.get(f"/api/v1/articles?category_id={category_id}")
            assert response.status_code == 200
            
            articles_data = response.json()
            articles = articles_data["articles"]
            
            assert len(articles) > 0
            assert articles_data["total"] > 0
            
            # 5. Verify article content
            first_article = articles[0]
            assert "title" in first_article
            assert "content" in first_article
            assert "source_url" in first_article
            assert first_article["title"] is not None
            assert len(first_article["title"]) > 0
```

## Test Configuration

```python
# tests/conftest.py
import pytest
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.database.models import Base
from src.main import app
from src.shared.config import get_settings

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def test_engine():
    """Create test database engine"""
    settings = get_settings()
    test_db_url = settings.TEST_DATABASE_URL
    
    engine = create_async_engine(test_db_url, echo=False)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()

@pytest.fixture
async def test_db(test_engine):
    """Create test database session"""
    TestSession = sessionmaker(
        test_engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )
    
    async with TestSession() as session:
        yield session
        await session.rollback()

@pytest.fixture
async def client():
    """Create test HTTP client"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
```

## Test Execution Commands

```bash
# Run all tests
docker-compose exec app pytest

# Run with coverage
docker-compose exec app pytest --cov=src --cov-report=html --cov-report=term-missing

# Run specific test types
docker-compose exec app pytest tests/unit/ -v
docker-compose exec app pytest tests/integration/ -v
docker-compose exec app pytest tests/e2e/ -v

# Run tests with markers
docker-compose exec app pytest -m "not slow"
docker-compose exec app pytest -m "integration"

# Run tests in parallel
docker-compose exec app pytest -n auto

# Run tests with detailed output
docker-compose exec app pytest -vvv --tb=long

# Generate coverage report
docker-compose exec app pytest --cov=src --cov-report=html
# Open htmlcov/index.html to view coverage report
```

## Testing Best Practices

1. **Comprehensive Coverage:** Unit tests cho logic, integration cho workflows, E2E cho user scenarios
2. **Mock External Dependencies:** Isolate tests từ external services
3. **Database Testing:** Separate test database với proper cleanup
4. **Async Testing:** Proper handling của async operations
5. **Performance Testing:** Include timing và resource usage checks
6. **Fixture Organization:** Reusable test setup và teardown
7. **Test Data Management:** Use factories và fixtures cho consistent test data
8. **Descriptive Test Names:** Clear indication của what is being tested
9. **Arrange-Act-Assert:** Structure tests clearly
10. **Test Isolation:** Each test should be independent