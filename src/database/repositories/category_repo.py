"""Category repository for database operations on Category models.

This module provides the CategoryRepository class that handles all database
operations related to categories, including keyword management and article
associations for the crawling process.

Key Features:
- Category lookup by name and status
- Active category filtering for crawling
- Keyword and exclude_keywords management
- Article association counting
- Comprehensive error handling and logging

Example:
    Basic category operations:
    
    ```python
    from src.database.repositories.category_repo import CategoryRepository
    
    async def manage_categories():
        repo = CategoryRepository()
        
        # Get active categories for crawling
        active_categories = await repo.get_active_categories()
        
        for category in active_categories:
            print(f"Category: {category.name}")
            print(f"Keywords: {category.keywords}")
            print(f"Exclude: {category.exclude_keywords}")
            
            # Count associated articles
            count = await repo.count_articles_in_category(category.id)
            print(f"Articles: {count}")
    ```
"""

import logging
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.repositories.base import BaseRepository
from src.database.models.category import Category
from src.database.models.article_category import ArticleCategory
from src.database.connection import get_db_session

logger = logging.getLogger(__name__)


class CategoryRepository(BaseRepository[Category]):
    """Repository for Category model database operations.
    
    This repository provides specialized methods for category management
    including active status filtering, keyword searches, and article associations.
    """
    
    model_class = Category
    
    async def get_by_name(self, name: str) -> Optional[Category]:
        """Retrieve a category by its name.
        
        Args:
            name: The category name to search for
            
        Returns:
            Category instance if found, None otherwise
        """
        return await self.get_by_field("name", name)
    
    async def get_active_categories(self) -> List[Category]:
        """Retrieve all active categories for crawling.
        
        Returns:
            List of Category instances where is_active=True
        """
        async with get_db_session() as session:
            query = (
                select(Category)
                .where(Category.is_active == True)
                .order_by(Category.name)
            )
            
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def get_categories_with_keywords(self, keyword: str) -> List[Category]:
        """Find categories that contain a specific keyword.
        
        This method searches in both keywords and exclude_keywords arrays
        to find categories that reference the given keyword.
        
        Args:
            keyword: The keyword to search for
            
        Returns:
            List of Category instances containing the keyword
        """
        async with get_db_session() as session:
            # PostgreSQL JSON operators for array containment
            query = (
                select(Category)
                .where(
                    Category.keywords.op('@>')([keyword])
                )
                .order_by(Category.name)
            )
            
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def create_category(
        self, 
        name: str, 
        keywords: List[str], 
        exclude_keywords: List[str] = None,
        is_active: bool = True
    ) -> Category:
        """Create a new category with keywords.
        
        Args:
            name: Category name (must be unique)
            keywords: List of keywords for OR search logic
            exclude_keywords: Optional list of keywords to exclude
            is_active: Whether the category is active for crawling
            
        Returns:
            Created Category instance
            
        Raises:
            Exception: If category creation fails
        """
        category_data = {
            "name": name.strip(),
            "keywords": [kw.strip() for kw in keywords if kw.strip()],
            "exclude_keywords": [kw.strip() for kw in (exclude_keywords or []) if kw.strip()],
            "is_active": is_active
        }
        
        category = await self.create(category_data)
        
        logger.info(
            f"Created new category",
            extra={
                "category_id": str(category.id),
                "name": category.name,
                "keywords_count": len(category.keywords),
                "exclude_keywords_count": len(category.exclude_keywords),
                "is_active": category.is_active
            }
        )
        
        return category
    
    async def update_keywords(
        self, 
        category_id: UUID, 
        keywords: List[str], 
        exclude_keywords: List[str] = None
    ) -> Optional[Category]:
        """Update keywords for an existing category.
        
        Args:
            category_id: UUID of the category to update
            keywords: New list of keywords
            exclude_keywords: New list of exclude keywords
            
        Returns:
            Updated Category instance if found, None otherwise
        """
        update_data = {
            "keywords": [kw.strip() for kw in keywords if kw.strip()],
            "exclude_keywords": [kw.strip() for kw in (exclude_keywords or []) if kw.strip()]
        }
        
        updated_category = await self.update_by_id(category_id, update_data)
        
        if updated_category:
            logger.info(
                f"Updated category keywords",
                extra={
                    "category_id": str(category_id),
                    "name": updated_category.name,
                    "keywords_count": len(updated_category.keywords),
                    "exclude_keywords_count": len(updated_category.exclude_keywords)
                }
            )
        
        return updated_category
    
    async def set_active_status(self, category_id: UUID, is_active: bool) -> Optional[Category]:
        """Update the active status of a category.
        
        Args:
            category_id: UUID of the category to update
            is_active: New active status
            
        Returns:
            Updated Category instance if found, None otherwise
        """
        update_data = {"is_active": is_active}
        
        updated_category = await self.update_by_id(category_id, update_data)
        
        if updated_category:
            logger.info(
                f"Updated category active status",
                extra={
                    "category_id": str(category_id),
                    "name": updated_category.name,
                    "is_active": is_active
                }
            )
        
        return updated_category
    
    async def count_articles_in_category(self, category_id: UUID) -> int:
        """Count the number of articles associated with a category.
        
        Args:
            category_id: UUID of the category
            
        Returns:
            Number of articles associated with the category
        """
        async with get_db_session() as session:
            query = (
                select(func.count())
                .select_from(ArticleCategory)
                .where(ArticleCategory.category_id == category_id)
            )
            
            result = await session.execute(query)
            return result.scalar() or 0
    
    async def get_categories_with_article_counts(self) -> List[Dict[str, Any]]:
        """Get all categories with their article counts.
        
        Returns:
            List of dictionaries containing category info and article counts
        """
        async with get_db_session() as session:
            query = (
                select(
                    Category.id,
                    Category.name,
                    Category.keywords,
                    Category.exclude_keywords,
                    Category.is_active,
                    Category.created_at,
                    func.count(ArticleCategory.article_id).label("article_count")
                )
                .outerjoin(ArticleCategory, Category.id == ArticleCategory.category_id)
                .group_by(
                    Category.id,
                    Category.name,
                    Category.keywords,
                    Category.exclude_keywords,
                    Category.is_active,
                    Category.created_at
                )
                .order_by(Category.name)
            )
            
            result = await session.execute(query)
            rows = result.fetchall()
            
            return [
                {
                    "id": str(row.id),
                    "name": row.name,
                    "keywords": row.keywords,
                    "exclude_keywords": row.exclude_keywords,
                    "is_active": row.is_active,
                    "created_at": row.created_at,
                    "article_count": row.article_count
                }
                for row in rows
            ]
    
    async def search_categories_by_name(self, search_term: str) -> List[Category]:
        """Search categories by name using case-insensitive partial matching.
        
        Args:
            search_term: Text to search for in category names
            
        Returns:
            List of Category instances with matching names
        """
        async with get_db_session() as session:
            query = (
                select(Category)
                .where(Category.name.ilike(f"%{search_term}%"))
                .order_by(Category.name)
            )
            
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def get_categories_with_articles(self) -> List[Category]:
        """Retrieve categories with their article associations loaded.

        Uses eager loading to fetch categories along with their associated
        articles in a single query.

        Returns:
            List of Category instances with articles relationship loaded
        """
        async with get_db_session() as session:
            query = (
                select(Category)
                .options(selectinload(Category.articles))
                .order_by(Category.name)
            )

            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_due_scheduled_categories(self, current_time: datetime) -> List[Category]:
        """Get categories with enabled schedules that are due for execution.

        Args:
            current_time: Current UTC datetime to compare against

        Returns:
            List of categories where schedule_enabled=true and next_scheduled_run_at <= current_time
        """
        async with get_db_session() as session:
            query = (
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

            result = await session.execute(query)
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

    async def update_schedule_timing(
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
        async with get_db_session() as session:
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

            result = await session.execute(stmt)
            await session.commit()

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

    async def update_schedule_config(
        self,
        category_id: UUID,
        enabled: bool,
        interval_minutes: Optional[int] = None
    ) -> Optional[Category]:
        """Update category schedule configuration.

        Args:
            category_id: Category UUID
            enabled: Whether schedule is enabled
            interval_minutes: Schedule interval (1, 30, 60, 1440)

        Returns:
            Updated Category object if found, None otherwise
        """
        async with get_db_session() as session:
            values = {
                "schedule_enabled": enabled,
                "updated_at": datetime.now(timezone.utc)
            }

            if interval_minutes is not None:
                values["schedule_interval_minutes"] = interval_minutes

            # Calculate next run if enabling
            if enabled and interval_minutes:
                values["next_scheduled_run_at"] = datetime.now(timezone.utc) + timedelta(minutes=interval_minutes)
            elif not enabled:
                # Clear next run if disabling
                values["next_scheduled_run_at"] = None

            stmt = (
                update(Category)
                .where(Category.id == category_id)
                .values(**values)
                .returning(Category)
            )

            result = await session.execute(stmt)
            await session.commit()

            updated_category = result.scalar_one_or_none()

            if updated_category:
                logger.info(
                    f"Updated schedule config for category",
                    extra={
                        "category_id": str(category_id),
                        "category_name": updated_category.name,
                        "enabled": enabled,
                        "interval_minutes": interval_minutes,
                        "next_run": updated_category.next_scheduled_run_at.isoformat() if updated_category.next_scheduled_run_at else None
                    }
                )

            return updated_category