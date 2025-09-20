"""Sync base repository class for use in Celery tasks.

This module provides synchronous database operations to avoid
event loop conflicts in Celery workers.
"""

import logging
from typing import TypeVar, Generic, Optional, List, Dict, Any, Type
from uuid import UUID
from sqlalchemy import create_engine, select, update, delete, func
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime, timezone

from src.database.models.base import BaseModel
from src.shared.config import get_settings

T = TypeVar('T', bound=BaseModel)

logger = logging.getLogger(__name__)


class SyncBaseRepository(Generic[T]):
    """Sync base repository class for Celery tasks.

    Uses synchronous SQLAlchemy operations to avoid event loop conflicts.
    """

    model_class: Type[T] = None

    def __init__(self):
        self.settings = get_settings()
        # Create sync engine
        database_url = self.settings.DATABASE_URL
        if database_url.startswith("postgresql+asyncpg://"):
            # Convert to sync psycopg2 URL
            database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

        self.engine = create_engine(
            database_url,
            pool_size=5,
            max_overflow=10,
            pool_timeout=30,
            pool_pre_ping=True,
            echo=self.settings.DATABASE_ECHO
        )

        self.Session = sessionmaker(bind=self.engine)

    def get_session(self) -> Session:
        """Get database session."""
        return self.Session()

    def get_by_id(self, id: UUID) -> Optional[T]:
        """Get model by ID."""
        with self.get_session() as session:
            return session.get(self.model_class, id)

    def get_by_field(self, field_name: str, value: Any) -> Optional[T]:
        """Get model by specific field."""
        with self.get_session() as session:
            field = getattr(self.model_class, field_name)
            stmt = select(self.model_class).where(field == value)
            result = session.execute(stmt)
            return result.scalar_one_or_none()

    def create(self, **kwargs) -> T:
        """Create new model instance."""
        with self.get_session() as session:
            instance = self.model_class(**kwargs)
            session.add(instance)
            session.commit()
            session.refresh(instance)
            return instance

    def update_by_id(self, id: UUID, **kwargs) -> Optional[T]:
        """Update model by ID."""
        with self.get_session() as session:
            instance = session.get(self.model_class, id)
            if instance:
                for key, value in kwargs.items():
                    setattr(instance, key, value)
                instance.updated_at = datetime.now(timezone.utc)
                session.commit()
                session.refresh(instance)
            return instance

    def delete_by_id(self, id: UUID) -> bool:
        """Delete model by ID."""
        with self.get_session() as session:
            instance = session.get(self.model_class, id)
            if instance:
                session.delete(instance)
                session.commit()
                return True
            return False

    def list_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """List all models with pagination."""
        with self.get_session() as session:
            stmt = select(self.model_class).limit(limit).offset(offset)
            result = session.execute(stmt)
            return result.scalars().all()

    def count(self) -> int:
        """Count total models."""
        with self.get_session() as session:
            stmt = select(func.count(self.model_class.id))
            result = session.execute(stmt)
            return result.scalar()