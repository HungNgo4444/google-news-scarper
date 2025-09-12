# Backend Architecture

Define backend-specific architecture details dựa trên monolith approach với modular components.

## Service Architecture

### Traditional Server Architecture

The system follows a traditional server architecture pattern with clear separation of concerns:

**Service Layer Organization:**
```
src/
├── api/                    # API routes layer
│   ├── __init__.py
│   ├── main.py            # FastAPI app setup
│   ├── dependencies.py    # Shared dependencies  
│   └── routes/
│       ├── __init__.py
│       ├── categories.py  # Category CRUD endpoints
│       ├── articles.py    # Article browsing endpoints
│       ├── crawl_jobs.py  # Job monitoring endpoints
│       └── health.py      # Health check endpoint
├── core/                  # Core business logic
│   ├── __init__.py
│   ├── crawler/           # Crawler engine
│   │   ├── __init__.py
│   │   ├── engine.py      # Main crawler orchestration
│   │   ├── extractor.py   # newspaper4k wrapper
│   │   └── rate_limiter.py # Rate limiting logic
│   ├── scheduler/         # Job scheduling
│   │   ├── __init__.py
│   │   ├── celery_app.py  # Celery configuration
│   │   ├── tasks.py       # Celery tasks
│   │   └── cron_jobs.py   # Scheduled job definitions
│   └── category/          # Category management
│       ├── __init__.py
│       ├── manager.py     # Category business logic
│       └── validator.py   # Category validation
├── database/              # Database layer
│   ├── __init__.py
│   ├── models/            # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── article.py
│   │   ├── category.py
│   │   └── crawl_job.py
│   ├── repositories/      # Data access layer
│   │   ├── __init__.py
│   │   ├── base.py        # Base repository
│   │   ├── article_repo.py
│   │   ├── category_repo.py
│   │   └── job_repo.py
│   └── migrations/        # Alembic migrations
│       └── versions/
└── shared/                # Shared utilities
    ├── __init__.py
    ├── config.py          # Configuration management
    ├── logging.py         # Logging setup
    ├── exceptions.py      # Custom exceptions
    └── utils.py           # General utilities
```

## Controller Layer Implementation

### FastAPI Route Controllers

```python
# api/routes/categories.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID

from ..dependencies import get_db_session
from ..schemas import CategoryResponse, CreateCategoryRequest, UpdateCategoryRequest
from ...core.category.manager import CategoryManager
from ...database.repositories.category_repo import CategoryRepository
from ...shared.exceptions import CategoryValidationError

router = APIRouter(prefix="/categories", tags=["categories"])

@router.get("/", response_model=List[CategoryResponse])
async def get_categories(
    active_only: bool = Query(True, description="Filter for active categories only"),
    db: AsyncSession = Depends(get_db_session)
):
    """Get all categories with optional filtering"""
    repo = CategoryRepository(db)
    manager = CategoryManager(repo)
    
    try:
        categories = await manager.get_categories(active_only=active_only)
        return categories
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch categories"
        )

@router.post("/", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    request: CreateCategoryRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """Create new category with keywords"""
    repo = CategoryRepository(db)
    manager = CategoryManager(repo)
    
    try:
        category = await manager.create_category(
            name=request.name,
            keywords=request.keywords,
            exclude_keywords=request.exclude_keywords
        )
        return category
    except CategoryValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create category"
        )

@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """Get category by ID"""
    repo = CategoryRepository(db)
    category = await repo.get_by_id(category_id)
    
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    return category

@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: UUID,
    request: UpdateCategoryRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """Update existing category"""
    repo = CategoryRepository(db)
    manager = CategoryManager(repo)
    
    try:
        category = await manager.update_category(
            category_id=category_id,
            **request.dict(exclude_unset=True)
        )
        
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Category not found"
            )
            
        return category
    except CategoryValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """Delete category and all associated data"""
    repo = CategoryRepository(db)
    manager = CategoryManager(repo)
    
    success = await manager.delete_category(category_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )

@router.post("/{category_id}/trigger-crawl", response_model=CrawlJobResponse)
async def trigger_crawl(
    category_id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """Manually trigger crawl for category"""
    from ...core.scheduler.tasks import crawl_category_task
    from ...database.repositories.job_repo import CrawlJobRepository
    
    # Validate category exists
    repo = CategoryRepository(db)
    category = await repo.get_by_id(category_id)
    
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    if not category.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot crawl inactive category"
        )
    
    # Queue Celery task
    task = crawl_category_task.delay(str(category_id))
    
    # Create job record
    job_repo = CrawlJobRepository(db)
    crawl_job = await job_repo.create(
        category_id=category_id,
        celery_task_id=task.id,
        status="pending",
        priority=1  # Manual triggers get higher priority
    )
    
    return crawl_job
```

## Data Access Layer

### Repository Pattern Implementation

```python
# database/repositories/base.py
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.exc import IntegrityError

T = TypeVar('T')

class BaseRepository(Generic[T], ABC):
    """Base repository with common CRUD operations"""
    
    def __init__(self, db: AsyncSession, model_class):
        self.db = db
        self.model_class = model_class
    
    async def get_by_id(self, id: UUID) -> Optional[T]:
        """Get single record by ID"""
        result = await self.db.execute(
            select(self.model_class).where(self.model_class.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_all(
        self, 
        limit: int = 100, 
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[T]:
        """Get multiple records with optional filtering"""
        query = select(self.model_class)
        
        # Apply filters
        if filters:
            for key, value in filters.items():
                if hasattr(self.model_class, key):
                    query = query.where(getattr(self.model_class, key) == value)
        
        query = query.limit(limit).offset(offset)
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count records with optional filtering"""
        query = select(func.count(self.model_class.id))
        
        if filters:
            for key, value in filters.items():
                if hasattr(self.model_class, key):
                    query = query.where(getattr(self.model_class, key) == value)
        
        result = await self.db.execute(query)
        return result.scalar()
    
    async def create(self, **kwargs) -> T:
        """Create new record"""
        instance = self.model_class(**kwargs)
        self.db.add(instance)
        
        try:
            await self.db.commit()
            await self.db.refresh(instance)
            return instance
        except IntegrityError as e:
            await self.db.rollback()
            raise ValueError(f"Database integrity error: {str(e.orig)}")
    
    async def update_by_id(self, id: UUID, **kwargs) -> Optional[T]:
        """Update record by ID"""
        # Remove None values và empty strings
        update_data = {k: v for k, v in kwargs.items() if v is not None and v != ""}
        
        if not update_data:
            return await self.get_by_id(id)
        
        await self.db.execute(
            update(self.model_class)
            .where(self.model_class.id == id)
            .values(**update_data)
        )
        
        await self.db.commit()
        return await self.get_by_id(id)
    
    async def delete_by_id(self, id: UUID) -> bool:
        """Delete record by ID"""
        result = await self.db.execute(
            delete(self.model_class).where(self.model_class.id == id)
        )
        
        await self.db.commit()
        return result.rowcount > 0
    
    async def exists(self, **kwargs) -> bool:
        """Check if record exists with given conditions"""
        query = select(self.model_class.id)
        
        for key, value in kwargs.items():
            if hasattr(self.model_class, key):
                query = query.where(getattr(self.model_class, key) == value)
        
        result = await self.db.execute(query.limit(1))
        return result.scalar() is not None
```

### Specialized Repository Implementation

```python
# database/repositories/article_repo.py
from typing import List, Optional, Tuple
from sqlalchemy import select, insert, func, and_
from sqlalchemy.orm import selectinload
from uuid import UUID
from datetime import datetime, timedelta

from .base import BaseRepository
from ..models.article import Article
from ..models.category import Category, article_categories

class ArticleRepository(BaseRepository[Article]):
    def __init__(self, db_session):
        super().__init__(db_session, Article)
    
    async def find_by_url_hash(self, url_hash: str) -> Optional[Article]:
        """Find article by URL hash for deduplication"""
        result = await self.db.execute(
            select(Article).where(Article.url_hash == url_hash)
        )
        return result.scalar_one_or_none()
    
    async def get_articles_with_categories(
        self, 
        category_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0,
        from_date: Optional[datetime] = None
    ) -> Tuple[List[Article], int]:
        """Get articles with their categories, with filtering and pagination"""
        
        # Base query with eager loading
        query = select(Article).options(
            selectinload(Article.categories)
        ).order_by(Article.created_at.desc())
        
        # Count query
        count_query = select(func.count(Article.id))
        
        # Apply category filter
        if category_id:
            query = query.join(article_categories).where(
                article_categories.c.category_id == category_id
            )
            count_query = count_query.join(article_categories).where(
                article_categories.c.category_id == category_id
            )
        
        # Apply date filter
        if from_date:
            query = query.where(Article.created_at >= from_date)
            count_query = count_query.where(Article.created_at >= from_date)
        
        # Execute queries
        articles_result = await self.db.execute(
            query.limit(limit).offset(offset)
        )
        count_result = await self.db.execute(count_query)
        
        articles = articles_result.scalars().all()
        total = count_result.scalar()
        
        return articles, total
    
    async def bulk_create_with_deduplication(
        self, 
        articles_data: List[dict], 
        category_id: UUID
    ) -> int:
        """Bulk insert articles với deduplication logic"""
        saved_count = 0
        
        for article_data in articles_data:
            # Generate URL hash
            url_hash = self._generate_url_hash(article_data['source_url'])
            existing = await self.find_by_url_hash(url_hash)
            
            if existing:
                # Check if content changed
                content_hash = self._generate_content_hash(
                    article_data.get('content', '')
                )
                
                if existing.content_hash != content_hash:
                    # Update existing article
                    await self.update_by_id(
                        existing.id,
                        content=article_data['content'],
                        content_hash=content_hash,
                        updated_at=datetime.utcnow(),
                        last_seen=datetime.utcnow()
                    )
                else:
                    # Just update last_seen
                    await self.update_by_id(
                        existing.id,
                        last_seen=datetime.utcnow()
                    )
            else:
                # Create new article
                article = await self.create(
                    **article_data,
                    url_hash=url_hash,
                    content_hash=self._generate_content_hash(
                        article_data.get('content', '')
                    )
                )
                
                # Add category association
                await self.db.execute(
                    insert(article_categories).values(
                        article_id=article.id,
                        category_id=category_id,
                        relevance_score=1.0
                    )
                )
                saved_count += 1
        
        await self.db.commit()
        return saved_count
    
    async def cleanup_old_articles(self, days_old: int = 30) -> int:
        """Remove articles older than specified days"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        result = await self.db.execute(
            delete(Article).where(Article.created_at < cutoff_date)
        )
        
        await self.db.commit()
        return result.rowcount
    
    async def get_articles_by_search(
        self, 
        search_term: str,
        limit: int = 20
    ) -> List[Article]:
        """Full-text search trong article titles và content"""
        query = select(Article).where(
            func.to_tsvector('english', Article.title + ' ' + Article.content)
            .match(search_term)
        ).order_by(
            Article.created_at.desc()
        ).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    def _generate_url_hash(self, url: str) -> str:
        """Generate URL hash for deduplication"""
        import hashlib
        return hashlib.sha256(url.lower().strip().encode()).hexdigest()
    
    def _generate_content_hash(self, content: str) -> str:
        """Generate content hash for change detection"""
        import hashlib
        if not content or not content.strip():
            return ""
        return hashlib.sha256(content.encode()).hexdigest()
```

## Business Logic Layer

### Service Layer Implementation

```python
# core/category/manager.py
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from ...database.repositories.category_repo import CategoryRepository
from ...database.models.category import Category
from ...shared.exceptions import CategoryValidationError, CategoryNotFoundError
from ...shared.logging import get_logger

logger = get_logger(__name__)

class CategoryManager:
    """Business logic for category management"""
    
    def __init__(self, repository: CategoryRepository):
        self.repository = repository
        self.max_keywords = 20
        self.min_keywords = 1
        self.max_keyword_length = 100
    
    async def get_categories(
        self, 
        active_only: bool = True
    ) -> List[Category]:
        """Get all categories với optional filtering"""
        filters = {"is_active": True} if active_only else {}
        return await self.repository.get_all(filters=filters)
    
    async def get_category_by_id(self, category_id: UUID) -> Category:
        """Get category by ID với error handling"""
        category = await self.repository.get_by_id(category_id)
        if not category:
            raise CategoryNotFoundError(f"Category {category_id} not found")
        return category
    
    async def create_category(
        self,
        name: str,
        keywords: List[str],
        exclude_keywords: Optional[List[str]] = None,
        is_active: bool = True
    ) -> Category:
        """Create new category với validation"""
        
        # Validate inputs
        self._validate_name(name)
        self._validate_keywords(keywords)
        
        if exclude_keywords:
            self._validate_keywords(exclude_keywords, field_name="exclude_keywords")
        
        # Check for duplicate name
        if await self.repository.exists(name=name):
            raise CategoryValidationError(
                f"Category with name '{name}' already exists",
                field="name"
            )
        
        # Create category
        try:
            category = await self.repository.create(
                name=name.strip(),
                keywords=keywords,
                exclude_keywords=exclude_keywords or [],
                is_active=is_active
            )
            
            logger.info(f"Category created successfully: {name}", extra={
                "category_id": str(category.id),
                "keywords_count": len(keywords)
            })
            
            return category
            
        except Exception as e:
            logger.error(f"Failed to create category: {e}", extra={
                "category_name": name,
                "error": str(e)
            })
            raise
    
    async def update_category(
        self,
        category_id: UUID,
        name: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        exclude_keywords: Optional[List[str]] = None,
        is_active: Optional[bool] = None
    ) -> Optional[Category]:
        """Update existing category"""
        
        # Validate category exists
        await self.get_category_by_id(category_id)
        
        # Validate inputs
        update_data = {}
        
        if name is not None:
            self._validate_name(name)
            # Check for duplicate name (excluding current category)
            existing = await self.repository.get_by_name(name)
            if existing and existing.id != category_id:
                raise CategoryValidationError(
                    f"Category with name '{name}' already exists",
                    field="name"
                )
            update_data["name"] = name.strip()
        
        if keywords is not None:
            self._validate_keywords(keywords)
            update_data["keywords"] = keywords
        
        if exclude_keywords is not None:
            self._validate_keywords(exclude_keywords, field_name="exclude_keywords")
            update_data["exclude_keywords"] = exclude_keywords
        
        if is_active is not None:
            update_data["is_active"] = is_active
        
        # Update category
        try:
            category = await self.repository.update_by_id(category_id, **update_data)
            
            logger.info(f"Category updated successfully", extra={
                "category_id": str(category_id),
                "fields_updated": list(update_data.keys())
            })
            
            return category
            
        except Exception as e:
            logger.error(f"Failed to update category: {e}", extra={
                "category_id": str(category_id),
                "error": str(e)
            })
            raise
    
    async def delete_category(self, category_id: UUID) -> bool:
        """Delete category and all associated data"""
        # Validate category exists
        await self.get_category_by_id(category_id)
        
        try:
            success = await self.repository.delete_by_id(category_id)
            
            if success:
                logger.info(f"Category deleted successfully", extra={
                    "category_id": str(category_id)
                })
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to delete category: {e}", extra={
                "category_id": str(category_id),
                "error": str(e)
            })
            raise
    
    def build_search_query(self, keywords: List[str]) -> str:
        """Build OR search query từ keywords"""
        if not keywords:
            return ""
        
        # Clean và escape keywords
        cleaned_keywords = []
        for keyword in keywords:
            cleaned = keyword.strip().lower()
            if cleaned:
                # Escape special characters for search
                cleaned = cleaned.replace('"', '\\"')
                cleaned_keywords.append(f'"{cleaned}"')
        
        return " OR ".join(cleaned_keywords)
    
    def _validate_name(self, name: str) -> None:
        """Validate category name"""
        if not name or not name.strip():
            raise CategoryValidationError(
                "Category name cannot be empty",
                field="name"
            )
        
        if len(name.strip()) > 255:
            raise CategoryValidationError(
                "Category name cannot exceed 255 characters",
                field="name"
            )
    
    def _validate_keywords(
        self, 
        keywords: List[str], 
        field_name: str = "keywords"
    ) -> None:
        """Validate keywords list"""
        if not keywords:
            if field_name == "keywords":  # Required for main keywords
                raise CategoryValidationError(
                    "Keywords list cannot be empty",
                    field=field_name
                )
            return  # Optional for exclude_keywords
        
        if len(keywords) > self.max_keywords:
            raise CategoryValidationError(
                f"Too many keywords (max {self.max_keywords})",
                field=field_name
            )
        
        # Check individual keywords
        for i, keyword in enumerate(keywords):
            if not keyword or not keyword.strip():
                raise CategoryValidationError(
                    f"Empty keyword at position {i+1}",
                    field=field_name
                )
            
            if len(keyword.strip()) > self.max_keyword_length:
                raise CategoryValidationError(
                    f"Keyword too long at position {i+1} (max {self.max_keyword_length} chars)",
                    field=field_name
                )
        
        # Check for duplicates
        cleaned_keywords = [kw.strip().lower() for kw in keywords if kw.strip()]
        if len(cleaned_keywords) != len(set(cleaned_keywords)):
            raise CategoryValidationError(
                "Duplicate keywords found",
                field=field_name
            )
```

## Authentication and Authorization (Future)

### JWT Authentication Implementation

```python
# core/auth/jwt_handler.py (Future implementation)
from datetime import datetime, timedelta
from typing import Optional
import jwt
from passlib.context import CryptContext

from ...shared.config import get_settings

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class JWTHandler:
    def __init__(self):
        self.secret_key = settings.SECRET_KEY
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 30
    
    def create_access_token(self, data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(
            minutes=self.access_token_expire_minutes
        )
        to_encode.update({"exp": expire})
        
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> Optional[dict]:
        try:
            payload = jwt.decode(
                token, 
                self.secret_key, 
                algorithms=[self.algorithm]
            )
            return payload
        except jwt.PyJWTError:
            return None
    
    def hash_password(self, password: str) -> str:
        return pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)
```

## Key Architecture Principles

1. **Separation of Concerns:** Clear boundaries giữa API, business logic, và data access
2. **Dependency Injection:** Loose coupling through constructor injection
3. **Repository Pattern:** Abstract data access layer cho testability
4. **Service Layer:** Encapsulate business logic và validation rules
5. **Error Handling:** Consistent exception handling với proper logging
6. **Async/Await:** Non-blocking I/O operations throughout
7. **Type Safety:** Strong typing với Pydantic và SQLAlchemy
8. **Configuration Management:** Environment-based configuration
9. **Logging:** Structured logging với correlation IDs
10. **Health Monitoring:** Comprehensive health checks cho all dependencies