"""Sync category repository for Celery tasks."""

import logging
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timezone, timedelta

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

    def get_due_scheduled_categories(self, current_time: datetime) -> List[Category]:
        """Get categories with enabled schedules that are due for execution.

        Args:
            current_time: Current UTC datetime to compare against

        Returns:
            List of categories where schedule_enabled=true and next_scheduled_run_at <= current_time
        """
        with self.get_session() as session:
            from sqlalchemy import select, and_

            stmt = (
                select(Category)
                .where(
                    and_(
                        Category.schedule_enabled == True,
                        Category.is_active == True,
                        Category.next_scheduled_run_at != None,
                        Category.next_scheduled_run_at <= current_time
                    )
                )
                .order_by(Category.next_scheduled_run_at.asc())
            )

            result = session.execute(stmt)
            categories = list(result.scalars().all())

            logger.info(
                f"Found {len(categories)} due scheduled categories",
                extra={
                    "count": len(categories),
                    "current_time": current_time.isoformat(),
                    "category_ids": [str(c.id) for c in categories]
                }
            )

            return categories

    def update_schedule_timing(
        self,
        category_id: UUID,
        last_run: datetime,
        next_run: datetime
    ) -> Optional[Category]:
        """Update category schedule timing after job execution.

        Args:
            category_id: Category UUID
            last_run: Timestamp of last execution
            next_run: Calculated timestamp for next execution

        Returns:
            Updated Category object if found, None otherwise
        """
        with self.get_session() as session:
            from sqlalchemy import update

            stmt = (
                update(Category)
                .where(Category.id == category_id)
                .values(
                    last_scheduled_run_at=last_run,
                    next_scheduled_run_at=next_run,
                    updated_at=datetime.now(timezone.utc)
                )
                .returning(Category)
            )

            result = session.execute(stmt)
            session.commit()

            updated_category = result.scalar_one_or_none()

            if updated_category:
                logger.info(
                    f"Updated schedule timing for category",
                    extra={
                        "category_id": str(category_id),
                        "category_name": updated_category.name,
                        "last_run": last_run.isoformat(),
                        "next_run": next_run.isoformat()
                    }
                )

            return updated_category