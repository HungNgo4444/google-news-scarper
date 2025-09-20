"""Sync category repository for Celery tasks."""

import logging
from typing import Optional
from uuid import UUID

from src.database.repositories.sync_base import SyncBaseRepository
from src.database.models.category import Category

logger = logging.getLogger(__name__)


class SyncCategoryRepository(SyncBaseRepository[Category]):
    """Sync category repository for Celery workers."""

    model_class = Category

    def get_by_name(self, name: str) -> Optional[Category]:
        """Get category by name."""
        return self.get_by_field("name", name)

    def get_active_categories(self):
        """Get all active categories."""
        with self.get_session() as session:
            from sqlalchemy import select
            stmt = select(Category).where(Category.is_active == True)
            result = session.execute(stmt)
            return result.scalars().all()