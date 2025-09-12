"""Base repository class providing common database operations.

This module defines the BaseRepository class that provides standard CRUD operations
and common database patterns for all repository implementations.

The base repository follows these principles:
- Async/await compatibility throughout
- Proper transaction management with rollback handling
- Type hints for better IDE support and code clarity
- Structured logging with correlation IDs
- Generic type support for model operations

Example:
    Creating a specific repository:
    
    ```python
    from typing import Optional
    from src.database.repositories.base import BaseRepository
    from src.database.models.article import Article
    
    class ArticleRepository(BaseRepository[Article]):
        model_class = Article
        
        async def get_by_url_hash(self, url_hash: str) -> Optional[Article]:
            return await self.get_by_field("url_hash", url_hash)
    ```
"""

import logging
from typing import TypeVar, Generic, Optional, List, Dict, Any, Type
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone

from src.database.models.base import BaseModel
from src.database.connection import get_db_session

T = TypeVar('T', bound=BaseModel)

logger = logging.getLogger(__name__)


class BaseRepository(Generic[T]):
    """Base repository class providing common database operations.
    
    This class provides standard CRUD operations and common database patterns
    that can be inherited by specific repository implementations.
    
    Attributes:
        model_class: The SQLAlchemy model class this repository operates on
    """
    
    model_class: Type[T] = None
    
    def __init__(self):
        """Initialize the base repository.
        
        Raises:
            ValueError: If model_class is not defined in the subclass
        """
        if self.model_class is None:
            raise ValueError("model_class must be defined in repository subclass")
    
    async def get_by_id(self, id: UUID) -> Optional[T]:
        """Retrieve a model instance by its ID.
        
        Args:
            id: The UUID of the record to retrieve
            
        Returns:
            Model instance if found, None otherwise
        """
        async with get_db_session() as session:
            query = select(self.model_class).where(self.model_class.id == id)
            result = await session.execute(query)
            return result.scalar_one_or_none()
    
    async def get_by_field(self, field_name: str, value: Any) -> Optional[T]:
        """Retrieve a model instance by a specific field value.
        
        Args:
            field_name: Name of the field to filter by
            value: Value to match
            
        Returns:
            Model instance if found, None otherwise
        """
        async with get_db_session() as session:
            field = getattr(self.model_class, field_name)
            query = select(self.model_class).where(field == value)
            result = await session.execute(query)
            return result.scalar_one_or_none()
    
    async def get_all(self, limit: Optional[int] = None, offset: Optional[int] = None) -> List[T]:
        """Retrieve all model instances with optional pagination.
        
        Args:
            limit: Maximum number of records to return
            offset: Number of records to skip
            
        Returns:
            List of model instances
        """
        async with get_db_session() as session:
            query = select(self.model_class)
            
            if offset:
                query = query.offset(offset)
            if limit:
                query = query.limit(limit)
            
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def create(self, data: Dict[str, Any]) -> T:
        """Create a new model instance.
        
        Args:
            data: Dictionary of field values for the new instance
            
        Returns:
            Created model instance
            
        Raises:
            Exception: If creation fails
        """
        async with get_db_session() as session:
            async with session.begin():
                try:
                    instance = self.model_class(**data)
                    session.add(instance)
                    await session.flush()
                    await session.refresh(instance)
                    return instance
                except Exception as e:
                    logger.error(f"Failed to create {self.model_class.__name__}: {e}")
                    raise
    
    async def update_by_id(self, id: UUID, data: Dict[str, Any]) -> Optional[T]:
        """Update a model instance by its ID.
        
        Args:
            id: The UUID of the record to update
            data: Dictionary of field values to update
            
        Returns:
            Updated model instance if found, None otherwise
        """
        async with get_db_session() as session:
            async with session.begin():
                try:
                    # Add updated_at timestamp
                    data['updated_at'] = datetime.now(timezone.utc)
                    
                    query = (
                        update(self.model_class)
                        .where(self.model_class.id == id)
                        .values(**data)
                        .execution_options(synchronize_session="fetch")
                    )
                    
                    result = await session.execute(query)
                    
                    if result.rowcount == 0:
                        return None
                    
                    # Fetch and return updated instance
                    updated_instance = await self.get_by_id(id)
                    return updated_instance
                    
                except Exception as e:
                    logger.error(f"Failed to update {self.model_class.__name__} {id}: {e}")
                    raise
    
    async def delete_by_id(self, id: UUID) -> bool:
        """Delete a model instance by its ID.
        
        Args:
            id: The UUID of the record to delete
            
        Returns:
            True if deleted, False if not found
        """
        async with get_db_session() as session:
            async with session.begin():
                try:
                    query = delete(self.model_class).where(self.model_class.id == id)
                    result = await session.execute(query)
                    return result.rowcount > 0
                except Exception as e:
                    logger.error(f"Failed to delete {self.model_class.__name__} {id}: {e}")
                    raise
    
    async def count(self) -> int:
        """Count the total number of model instances.
        
        Returns:
            Total count of records
        """
        async with get_db_session() as session:
            query = select(func.count()).select_from(self.model_class)
            result = await session.execute(query)
            return result.scalar() or 0
    
    async def exists_by_id(self, id: UUID) -> bool:
        """Check if a model instance exists by its ID.
        
        Args:
            id: The UUID to check
            
        Returns:
            True if exists, False otherwise
        """
        async with get_db_session() as session:
            query = select(func.count()).select_from(self.model_class).where(self.model_class.id == id)
            result = await session.execute(query)
            count = result.scalar() or 0
            return count > 0
    
    async def exists_by_field(self, field_name: str, value: Any) -> bool:
        """Check if a model instance exists by a specific field value.
        
        Args:
            field_name: Name of the field to check
            value: Value to match
            
        Returns:
            True if exists, False otherwise
        """
        async with get_db_session() as session:
            field = getattr(self.model_class, field_name)
            query = select(func.count()).select_from(self.model_class).where(field == value)
            result = await session.execute(query)
            count = result.scalar() or 0
            return count > 0