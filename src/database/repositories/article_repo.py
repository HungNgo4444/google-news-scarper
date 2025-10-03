"""Article repository for database operations on Article models.

This module provides the ArticleRepository class that handles all database
operations related to articles, including deduplication, category associations,
and specialized queries for the crawling process.

Key Features:
- URL hash-based deduplication
- Category association management
- Batch operations for efficiency
- Last seen timestamp updates
- Comprehensive error handling and logging

The repository supports the crawler engine with methods for:
- Checking existing articles by URL hash
- Creating articles with category associations
- Updating last seen timestamps for duplicate detection
- Managing many-to-many relationships with categories

Example:
    Basic usage with dependency injection:
    
    ```python
    from src.database.repositories.article_repo import ArticleRepository
    from src.database.models.article import Article
    
    async def create_article_example():
        repo = ArticleRepository()
        
        article_data = {
            "title": "Breaking News",
            "content": "Article content...",
            "source_url": "https://example.com/article",
            "url_hash": "abc123...",
            "author": "John Doe"
        }
        
        category_id = "550e8400-e29b-41d4-a716-446655440000"
        
        # Create article with category association
        article = await repo.create_with_category(article_data, category_id)
        print(f"Created article: {article.title}")
        
        return article
    ```
"""

import logging
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.repositories.base import BaseRepository
from src.database.models.article import Article
from src.database.models.article_category import ArticleCategory
from src.database.models.category import Category
from src.database.connection import get_db_session

logger = logging.getLogger(__name__)


class ArticleRepository(BaseRepository[Article]):
    """Repository for Article model database operations.
    
    This repository provides specialized methods for article management including
    deduplication logic, category associations, and crawler-specific operations.
    """
    
    model_class = Article
    
    async def get_by_url_hash(self, url_hash: str) -> Optional[Article]:
        """Retrieve an article by its URL hash.
        
        This is the primary method for deduplication - articles are considered
        duplicates if they have the same URL hash (SHA-256 of source_url).
        
        Args:
            url_hash: SHA-256 hash of the article's source URL
            
        Returns:
            Article instance if found, None otherwise
        """
        return await self.get_by_field("url_hash", url_hash)
    
    async def get_by_content_hash(self, content_hash: str) -> Optional[Article]:
        """Retrieve an article by its content hash.
        
        This method can be used for content-based deduplication to find articles
        with identical content but different URLs.
        
        Args:
            content_hash: SHA-256 hash of the article's content
            
        Returns:
            Article instance if found, None otherwise
        """
        return await self.get_by_field("content_hash", content_hash)
    
    async def create_with_category(self, article_data: Dict[str, Any], category_id: UUID) -> Article:
        """Create a new article with an associated category.
        
        This method creates both the article record and the category association
        in a single transaction to ensure data consistency.
        
        Args:
            article_data: Dictionary containing article field values
            category_id: UUID of the category to associate with the article
            
        Returns:
            Created Article instance with category association
            
        Raises:
            Exception: If article creation or category association fails
        """
        async with get_db_session() as session:
            async with session.begin():
                try:
                    # Create the article
                    article = Article(**article_data)
                    session.add(article)
                    await session.flush()  # Get the article ID
                    
                    # Create category association
                    association = ArticleCategory(
                        article_id=article.id,
                        category_id=category_id,
                        relevance_score=1.0,  # Default relevance score
                        created_at=datetime.now(timezone.utc)
                    )
                    session.add(association)
                    
                    await session.flush()
                    await session.refresh(article)
                    
                    logger.info(
                        f"Created article with category association",
                        extra={
                            "article_id": str(article.id),
                            "category_id": str(category_id),
                            "title": article.title[:50],
                            "url_hash": article.url_hash
                        }
                    )
                    
                    return article
                    
                except Exception as e:
                    logger.error(
                        f"Failed to create article with category: {e}",
                        extra={
                            "category_id": str(category_id),
                            "article_url": article_data.get("source_url", "unknown")
                        }
                    )
                    raise
    
    async def update_last_seen(self, article_id: UUID) -> bool:
        """Update the last_seen timestamp for an existing article.
        
        This method is used when we encounter an article URL that already exists
        in the database, indicating it's still active/available.
        
        Args:
            article_id: UUID of the article to update
            
        Returns:
            True if update was successful, False if article not found
        """
        update_data = {
            "last_seen": datetime.now(timezone.utc)
        }
        
        updated_article = await self.update_by_id(article_id, update_data)
        
        if updated_article:
            logger.debug(
                f"Updated last_seen for article",
                extra={
                    "article_id": str(article_id),
                    "last_seen": updated_article.last_seen.isoformat()
                }
            )
            return True
        else:
            logger.warning(
                f"Failed to update last_seen - article not found",
                extra={"article_id": str(article_id)}
            )
            return False
    
    async def ensure_category_association(self, article_id: UUID, category_id: UUID) -> bool:
        """Ensure a category association exists for an article.
        
        This method creates a category association if it doesn't already exist,
        useful when processing existing articles that may not be associated
        with all relevant categories.
        
        Args:
            article_id: UUID of the article
            category_id: UUID of the category to associate
            
        Returns:
            True if association exists or was created, False on error
        """
        async with get_db_session() as session:
            try:
                # Check if association already exists
                query = select(ArticleCategory).where(
                    and_(
                        ArticleCategory.article_id == article_id,
                        ArticleCategory.category_id == category_id
                    )
                )
                result = await session.execute(query)
                existing = result.scalar_one_or_none()
                
                if existing:
                    logger.debug(
                        f"Category association already exists",
                        extra={
                            "article_id": str(article_id),
                            "category_id": str(category_id)
                        }
                    )
                    return True
                
                # Create new association
                async with session.begin():
                    association = ArticleCategory(
                        article_id=article_id,
                        category_id=category_id,
                        relevance_score=1.0,
                        created_at=datetime.now(timezone.utc)
                    )
                    session.add(association)
                    await session.flush()
                    
                    logger.info(
                        f"Created new category association",
                        extra={
                            "article_id": str(article_id),
                            "category_id": str(category_id)
                        }
                    )
                    return True
                    
            except Exception as e:
                logger.error(
                    f"Failed to ensure category association: {e}",
                    extra={
                        "article_id": str(article_id),
                        "category_id": str(category_id)
                    }
                )
                return False
    
    async def get_articles_by_category(self, category_id: UUID, limit: Optional[int] = None) -> List[Article]:
        """Retrieve all articles associated with a specific category.
        
        Args:
            category_id: UUID of the category
            limit: Maximum number of articles to return
            
        Returns:
            List of Article instances associated with the category
        """
        async with get_db_session() as session:
            query = (
                select(Article)
                .join(ArticleCategory, Article.id == ArticleCategory.article_id)
                .where(ArticleCategory.category_id == category_id)
                .order_by(Article.created_at.desc())
            )
            
            if limit:
                query = query.limit(limit)
            
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def get_recent_articles(self, limit: int = 50) -> List[Article]:
        """Retrieve the most recently created articles.
        
        Args:
            limit: Maximum number of articles to return
            
        Returns:
            List of Article instances ordered by creation date (newest first)
        """
        async with get_db_session() as session:
            query = (
                select(Article)
                .order_by(Article.created_at.desc())
                .limit(limit)
            )
            
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def get_articles_with_categories(
        self, 
        category_id: Optional[UUID] = None,
        category_ids: Optional[List[UUID]] = None,
        limit: int = 50,
        offset: int = 0,
        from_date: Optional[datetime] = None,
        include_category_names: bool = True
    ) -> Tuple[List[Article], int]:
        """Get articles with their categories, advanced filtering and pagination.
        
        Args:
            category_id: Optional single category to filter by
            category_ids: Optional list of category IDs to filter by  
            limit: Maximum number of articles to return
            offset: Number of articles to skip
            from_date: Optional date filter (articles created after this date)
            include_category_names: Whether to eager load category relationships
            
        Returns:
            Tuple of (articles_list, total_count)
        """
        async with get_db_session() as session:
            # Base query
            query = select(Article)
            count_query = select(func.count()).select_from(Article)
            
            # Apply category filtering
            if category_id:
                query = query.join(ArticleCategory).where(ArticleCategory.category_id == category_id)
                count_query = count_query.join(ArticleCategory).where(ArticleCategory.category_id == category_id)
            elif category_ids:
                query = query.join(ArticleCategory).where(ArticleCategory.category_id.in_(category_ids))
                count_query = count_query.join(ArticleCategory).where(ArticleCategory.category_id.in_(category_ids))
            
            # Apply date filtering
            if from_date:
                query = query.where(Article.created_at >= from_date)
                count_query = count_query.where(Article.created_at >= from_date)
            
            # Add eager loading if requested
            if include_category_names:
                query = query.options(selectinload(Article.categories))
            
            # Add ordering and pagination
            query = query.order_by(Article.created_at.desc()).offset(offset).limit(limit)
            
            # Execute both queries
            result = await session.execute(query)
            articles = list(result.scalars().all())
            
            count_result = await session.execute(count_query)
            total_count = count_result.scalar() or 0
            
            return articles, total_count
    
    async def get_articles_with_category_filtering_optimized(
        self,
        category_filters: Optional[Dict[str, Any]] = None,
        relevance_threshold: float = 0.0,
        limit: int = 50,
        offset: int = 0,
        order_by: str = "created_at",
        order_direction: str = "desc"
    ) -> Tuple[List[Article], int]:
        """Optimized article retrieval with advanced category filtering.
        
        Args:
            category_filters: Dictionary with filtering options:
                - category_ids: List[UUID] - Filter by specific categories
                - any_category: bool - Match articles with any category vs all
                - exclude_category_ids: List[UUID] - Exclude specific categories
            relevance_threshold: Minimum relevance score for category associations
            limit: Maximum number of articles to return
            offset: Number of articles to skip
            order_by: Field to order by (created_at, publish_date, relevance_score)
            order_direction: "asc" or "desc"
            
        Returns:
            Tuple of (articles_list, total_count)
        """
        async with get_db_session() as session:
            # Build base query with optimized joins
            query = select(Article).options(selectinload(Article.categories))
            count_query = select(func.count(Article.id.distinct()))
            
            # Apply category filtering with optimized joins
            if category_filters:
                category_ids = category_filters.get('category_ids', [])
                exclude_category_ids = category_filters.get('exclude_category_ids', [])
                any_category = category_filters.get('any_category', True)
                
                if category_ids:
                    # Join with ArticleCategory for filtering
                    ac_alias = ArticleCategory.__table__.alias('ac_filter')
                    
                    if any_category:
                        # Article matches ANY of the specified categories
                        query = query.join(ac_alias, Article.id == ac_alias.c.article_id)
                        query = query.where(ac_alias.c.category_id.in_(category_ids))
                        count_query = count_query.join(ac_alias, Article.id == ac_alias.c.article_id)
                        count_query = count_query.where(ac_alias.c.category_id.in_(category_ids))
                    else:
                        # Article matches ALL of the specified categories
                        for category_id in category_ids:
                            ac_subquery = select(ArticleCategory.article_id).where(
                                ArticleCategory.category_id == category_id
                            )
                            query = query.where(Article.id.in_(ac_subquery))
                            count_query = count_query.where(Article.id.in_(ac_subquery))
                
                # Apply relevance threshold
                if relevance_threshold > 0.0:
                    query = query.where(ac_alias.c.relevance_score >= relevance_threshold)
                    count_query = count_query.where(ac_alias.c.relevance_score >= relevance_threshold)
                
                # Exclude specific categories
                if exclude_category_ids:
                    exclude_subquery = select(ArticleCategory.article_id).where(
                        ArticleCategory.category_id.in_(exclude_category_ids)
                    )
                    query = query.where(~Article.id.in_(exclude_subquery))
                    count_query = count_query.where(~Article.id.in_(exclude_subquery))
            
            # Apply ordering
            if order_by == "relevance_score" and category_filters and category_filters.get('category_ids'):
                # Order by relevance score (requires join)
                if order_direction.lower() == "desc":
                    query = query.order_by(ac_alias.c.relevance_score.desc(), Article.created_at.desc())
                else:
                    query = query.order_by(ac_alias.c.relevance_score.asc(), Article.created_at.desc())
            elif order_by == "publish_date":
                order_field = Article.publish_date.desc() if order_direction.lower() == "desc" else Article.publish_date.asc()
                query = query.order_by(order_field, Article.created_at.desc())
            else:
                # Default to created_at
                order_field = Article.created_at.desc() if order_direction.lower() == "desc" else Article.created_at.asc()
                query = query.order_by(order_field)
            
            # Apply pagination
            query = query.offset(offset).limit(limit)
            
            # Execute queries
            result = await session.execute(query)
            articles = list(result.scalars().unique())  # unique() removes duplicates from joins
            
            count_result = await session.execute(count_query)
            total_count = count_result.scalar() or 0
            
            logger.debug(
                f"Optimized category filtering query executed",
                extra={
                    "category_filters": category_filters,
                    "relevance_threshold": relevance_threshold,
                    "results_count": len(articles),
                    "total_count": total_count,
                    "limit": limit,
                    "offset": offset
                }
            )
            
            return articles, total_count
    
    async def find_articles_by_category(
        self,
        category_id: UUID,
        relevance_threshold: float = 0.0,
        limit: int = 100
    ) -> List[Article]:
        """Find articles associated with specific category above relevance threshold.
        
        Args:
            category_id: UUID of the category to search for
            relevance_threshold: Minimum relevance score (0.0-1.0)
            limit: Maximum number of articles to return
            
        Returns:
            List of Article instances with relevance above threshold
        """
        async with get_db_session() as session:
            query = (
                select(Article)
                .join(ArticleCategory, Article.id == ArticleCategory.article_id)
                .where(
                    and_(
                        ArticleCategory.category_id == category_id,
                        ArticleCategory.relevance_score >= relevance_threshold
                    )
                )
                .order_by(
                    ArticleCategory.relevance_score.desc(),
                    Article.created_at.desc()
                )
                .limit(limit)
            )
            
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def get_articles_with_detailed_categories(
        self,
        article_ids: Optional[List[UUID]] = None,
        category_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0,
        include_category_metadata: bool = True
    ) -> List[Dict[str, Any]]:
        """Get articles with detailed category information and metadata.
        
        Args:
            article_ids: Optional list of specific article IDs to fetch
            category_id: Optional category filter
            limit: Maximum number of articles to return
            offset: Number of articles to skip
            include_category_metadata: Whether to include detailed category info
            
        Returns:
            List of article dictionaries with category details
        """
        async with get_db_session() as session:
            # Build base query with category join
            query = (
                select(
                    Article,
                    ArticleCategory.relevance_score,
                    ArticleCategory.created_at.label('association_created_at')
                )
                .outerjoin(ArticleCategory, Article.id == ArticleCategory.article_id)
            )
            
            # Apply filters
            if article_ids:
                query = query.where(Article.id.in_(article_ids))
            
            if category_id:
                query = query.where(ArticleCategory.category_id == category_id)
            
            # Order by creation date and relevance
            query = query.order_by(
                Article.created_at.desc(),
                ArticleCategory.relevance_score.desc()
            ).offset(offset).limit(limit * 10)  # Get more to handle grouping
            
            result = await session.execute(query)
            rows = result.all()
            
            # Group results by article
            articles_dict = {}
            for row in rows:
                article, relevance_score, association_created_at = row
                article_id = str(article.id)
                
                if article_id not in articles_dict:
                    articles_dict[article_id] = {
                        "id": article_id,
                        "title": article.title,
                        "content": article.content,
                        "author": article.author,
                        "publish_date": article.publish_date.isoformat() if article.publish_date else None,
                        "source_url": article.source_url,
                        "image_url": article.image_url,
                        "url_hash": article.url_hash,
                        "content_hash": article.content_hash,
                        "created_at": article.created_at.isoformat(),
                        "updated_at": article.updated_at.isoformat(),
                        "last_seen": article.last_seen.isoformat(),
                        "categories": []
                    }
                
                # Add category association if exists
                if relevance_score is not None:
                    if include_category_metadata:
                        # Get category details
                        category_query = select(Category).where(Category.id == category_id)
                        category_result = await session.execute(category_query)
                        category = category_result.scalar_one_or_none()
                        
                        category_info = {
                            "category_id": str(category_id),
                            "relevance_score": float(relevance_score) if relevance_score else 1.0,
                            "association_created_at": association_created_at.isoformat() if association_created_at else None
                        }
                        
                        if category:
                            category_info.update({
                                "category_name": category.name,
                                "category_keywords": category.keywords,
                                "category_is_active": category.is_active
                            })
                    else:
                        category_info = {
                            "category_id": str(category_id),
                            "relevance_score": float(relevance_score) if relevance_score else 1.0
                        }
                    
                    articles_dict[article_id]["categories"].append(category_info)
            
            # Convert to list and apply limit
            articles_list = list(articles_dict.values())[:limit]
            
            logger.debug(
                f"Retrieved {len(articles_list)} articles with detailed category information",
                extra={
                    "category_id": str(category_id) if category_id else None,
                    "include_metadata": include_category_metadata,
                    "limit": limit,
                    "offset": offset
                }
            )
            
            return articles_list
    
    async def get_article_with_category_names_and_scores(
        self,
        article_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Get single article with category names and relevance scores.
        
        Args:
            article_id: UUID of the article to retrieve
            
        Returns:
            Article dictionary with category details or None if not found
        """
        async with get_db_session() as session:
            # Get article with category associations
            query = (
                select(Article)
                .options(selectinload(Article.categories))
                .where(Article.id == article_id)
            )
            
            result = await session.execute(query)
            article = result.scalar_one_or_none()
            
            if not article:
                return None
            
            # Build article dict with category details
            article_dict = {
                "id": str(article.id),
                "title": article.title,
                "content": article.content,
                "author": article.author,
                "publish_date": article.publish_date.isoformat() if article.publish_date else None,
                "source_url": article.source_url,
                "image_url": article.image_url,
                "url_hash": article.url_hash,
                "content_hash": article.content_hash,
                "created_at": article.created_at.isoformat(),
                "updated_at": article.updated_at.isoformat(),
                "last_seen": article.last_seen.isoformat(),
                "categories": []
            }
            
            # Get category names and details
            if article.categories:
                category_ids = [assoc.category_id for assoc in article.categories]
                
                # Fetch category details
                category_query = select(Category).where(Category.id.in_(category_ids))
                category_result = await session.execute(category_query)
                categories = {cat.id: cat for cat in category_result.scalars().all()}
                
                # Build category info
                for association in article.categories:
                    category = categories.get(association.category_id)
                    category_info = {
                        "category_id": str(association.category_id),
                        "relevance_score": float(association.relevance_score) if association.relevance_score else 1.0,
                        "association_created_at": association.created_at.isoformat() if association.created_at else None
                    }
                    
                    if category:
                        category_info.update({
                            "category_name": category.name,
                            "category_keywords": category.keywords,
                            "category_is_active": category.is_active
                        })
                    
                    article_dict["categories"].append(category_info)
                
                # Sort categories by relevance score
                article_dict["categories"].sort(
                    key=lambda x: x.get("relevance_score", 0),
                    reverse=True
                )
            
            return article_dict
    
    async def update_article_categories(
        self,
        article_id: UUID,
        category_associations: List[Dict[str, Any]]
    ) -> bool:
        """Update category associations for existing article.
        
        Args:
            article_id: UUID of the article to update
            category_associations: List of category association dicts
            
        Returns:
            True if update successful, False otherwise
        """
        async with get_db_session() as session:
            async with session.begin():
                try:
                    # Remove existing associations
                    delete_query = select(ArticleCategory).where(
                        ArticleCategory.article_id == article_id
                    )
                    existing_associations = await session.execute(delete_query)
                    
                    for association in existing_associations.scalars():
                        await session.delete(association)
                    
                    # Create new associations
                    associations_created = await self._create_category_associations(
                        session, article_id, category_associations
                    )
                    
                    logger.info(
                        f"Updated article categories",
                        extra={
                            "article_id": str(article_id),
                            "associations_created": associations_created
                        }
                    )
                    
                    return True
                    
                except Exception as e:
                    logger.error(
                        f"Failed to update article categories: {e}",
                        extra={"article_id": str(article_id)}
                    )
                    return False
    
    async def count_articles_by_category(self, category_id: UUID) -> int:
        """Count the number of articles associated with a specific category.
        
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
    
    async def search_articles_by_title(self, search_term: str, limit: int = 50) -> List[Article]:
        """Search articles by title using case-insensitive partial matching.
        
        Args:
            search_term: Text to search for in article titles
            limit: Maximum number of articles to return
            
        Returns:
            List of Article instances with matching titles
        """
        async with get_db_session() as session:
            query = (
                select(Article)
                .where(Article.title.ilike(f"%{search_term}%"))
                .order_by(Article.created_at.desc())
                .limit(limit)
            )
            
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def get_duplicate_articles_by_content_hash(self, content_hash: str) -> List[Article]:
        """Find all articles with the same content hash (potential duplicates).
        
        This method is useful for identifying articles with identical content
        but different URLs, which might indicate content syndication or copying.
        
        Args:
            content_hash: SHA-256 hash of article content
            
        Returns:
            List of Article instances with matching content hash
        """
        async with get_db_session() as session:
            query = (
                select(Article)
                .where(Article.content_hash == content_hash)
                .order_by(Article.created_at.asc())
            )
            
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def get_articles_without_content(self, limit: int = 100) -> List[Article]:
        """Find articles that failed content extraction (content is None).
        
        This method is useful for identifying articles that need re-processing
        or have extraction issues.
        
        Args:
            limit: Maximum number of articles to return
            
        Returns:
            List of Article instances without content
        """
        async with get_db_session() as session:
            query = (
                select(Article)
                .where(Article.content.is_(None))
                .order_by(Article.created_at.desc())
                .limit(limit)
            )
            
            result = await session.execute(query)
            return list(result.scalars().all())
    
    async def bulk_create_with_category_associations(
        self,
        articles_data: List[dict],
        category_associations: List[Dict[str, Any]]
    ) -> Tuple[int, int, int]:
        """Enhanced bulk insert with category associations and detailed deduplication tracking.
        
        This method provides comprehensive deduplication with multiple category associations
        per article and enhanced metadata tracking.
        
        Args:
            articles_data: List of article dictionaries to create
            category_associations: List of category association lists, where each inner list
                                 contains associations for the corresponding article:
                                 [[{category_id: UUID, relevance_score: float}, ...], ...]
            
        Returns:
            Tuple of (new_articles, updated_articles, duplicates_skipped)
        """
        if not articles_data:
            return (0, 0, 0)
        
        if len(articles_data) != len(category_associations):
            raise ValueError("articles_data and category_associations must have same length")
        
        new_articles = 0
        updated_articles = 0
        duplicates_skipped = 0
        
        async with get_db_session() as session:
            async with session.begin():
                try:
                    for i, article_data in enumerate(articles_data):
                        article_category_associations = category_associations[i]
                        
                        # Validate category associations
                        if not isinstance(article_category_associations, list):
                            logger.warning(
                                f"Invalid category associations format for article {i}",
                                extra={"article_url": article_data.get('source_url', 'unknown')}
                            )
                            duplicates_skipped += 1
                            continue
                        
                        # Check for existing article by URL hash
                        url_hash = article_data.get('url_hash')
                        if not url_hash:
                            # Generate URL hash if missing
                            source_url = article_data.get('source_url')
                            if source_url:
                                url_hash = Article.generate_url_hash(source_url)
                                article_data['url_hash'] = url_hash
                            else:
                                duplicates_skipped += 1
                                continue
                        
                        # Check for existing article
                        existing_article = await self._get_existing_article_by_hash(
                            session, url_hash
                        )
                        
                        if existing_article:
                            # Update existing article and handle category associations
                            updated = await self._handle_duplicate_article(
                                session, existing_article, article_data, article_category_associations
                            )
                            if updated == "updated":
                                updated_articles += 1
                            else:
                                duplicates_skipped += 1
                        else:
                            # Create new article with category associations
                            article = Article(**article_data)
                            session.add(article)
                            await session.flush()  # Get article ID
                            
                            # Create category associations
                            associations_created = await self._create_category_associations(
                                session, article.id, article_category_associations
                            )
                            
                            if associations_created > 0:
                                new_articles += 1
                            else:
                                duplicates_skipped += 1
                    
                    await session.flush()
                    
                    logger.info(
                        f"Enhanced bulk creation with category associations completed",
                        extra={
                            "new_articles": new_articles,
                            "updated_articles": updated_articles,
                            "duplicates_skipped": duplicates_skipped,
                            "total_articles_processed": len(articles_data)
                        }
                    )
                    
                    return (new_articles, updated_articles, duplicates_skipped)
                    
                except Exception as e:
                    logger.error(
                        f"Enhanced bulk creation with category associations failed: {e}",
                        extra={"articles_count": len(articles_data)}
                    )
                    raise
    
    async def find_similar_articles_by_content(
        self,
        content_hash: str,
        similarity_threshold: float = 0.8,
        include_categories: bool = False
    ) -> List[Article]:
        """Find articles with similar content using content hashes.
        
        This method identifies articles with identical content that might be duplicates
        from different sources or slightly modified versions.
        
        Args:
            content_hash: SHA-256 hash of the article's content
            similarity_threshold: Similarity threshold (currently only supports 1.0 for exact matches)
            include_categories: Whether to eagerly load category relationships
            
        Returns:
            List of Article instances with similar content
        """
        async with get_db_session() as session:
            # Build query for exact content hash matches
            query = select(Article).where(Article.content_hash == content_hash)
            
            if include_categories:
                query = query.options(selectinload(Article.categories))
            
            query = query.order_by(Article.created_at.asc())
            
            result = await session.execute(query)
            exact_matches = list(result.scalars().all())
            
            if exact_matches:
                logger.debug(
                    f"Found {len(exact_matches)} articles with identical content hash",
                    extra={
                        "content_hash": content_hash,
                        "similarity_threshold": similarity_threshold,
                        "matches_found": len(exact_matches)
                    }
                )
            
            return exact_matches
    
    async def detect_and_merge_duplicates(
        self,
        articles_data: List[dict],
        maintain_category_associations: bool = True
    ) -> Dict[str, Any]:
        """Enhanced duplicate detection with category association preservation.
        
        This method identifies duplicates by URL and content hash, then merges
        category associations while preserving the best available content.
        
        Args:
            articles_data: List of article dictionaries to process
            maintain_category_associations: Whether to preserve all category associations
            
        Returns:
            Dictionary with deduplication statistics and results
        """
        if not articles_data:
            return {
                "processed": 0,
                "duplicates_found": 0,
                "associations_merged": 0,
                "content_updates": 0
            }
        
        stats = {
            "processed": 0,
            "duplicates_found": 0,
            "associations_merged": 0,
            "content_updates": 0,
            "unique_articles": [],
            "duplicate_groups": []
        }
        
        async with get_db_session() as session:
            try:
                # Group articles by URL hash for deduplication
                url_hash_groups = {}
                for article_data in articles_data:
                    url_hash = article_data.get('url_hash')
                    if not url_hash and article_data.get('source_url'):
                        url_hash = Article.generate_url_hash(article_data['source_url'])
                        article_data['url_hash'] = url_hash
                    
                    if url_hash:
                        if url_hash not in url_hash_groups:
                            url_hash_groups[url_hash] = []
                        url_hash_groups[url_hash].append(article_data)
                
                # Process each group
                for url_hash, articles_group in url_hash_groups.items():
                    stats["processed"] += len(articles_group)
                    
                    if len(articles_group) == 1:
                        # No duplicates for this URL
                        stats["unique_articles"].append(articles_group[0])
                    else:
                        # Found duplicates
                        stats["duplicates_found"] += len(articles_group) - 1
                        
                        # Merge duplicates
                        merged_article, associations_merged = await self._merge_duplicate_articles(
                            session, articles_group, maintain_category_associations
                        )
                        
                        stats["associations_merged"] += associations_merged
                        stats["duplicate_groups"].append({
                            "url_hash": url_hash,
                            "duplicates_count": len(articles_group),
                            "merged_article": merged_article
                        })
                        
                        if merged_article:
                            stats["unique_articles"].append(merged_article)
                
                logger.info(
                    f"Duplicate detection completed",
                    extra={
                        "articles_processed": stats["processed"],
                        "duplicates_found": stats["duplicates_found"],
                        "associations_merged": stats["associations_merged"],
                        "unique_articles": len(stats["unique_articles"])
                    }
                )
                
                return stats
                
            except Exception as e:
                logger.error(
                    f"Duplicate detection failed: {e}",
                    extra={"articles_count": len(articles_data)}
                )
                raise
    
    async def bulk_create_with_enhanced_deduplication(
        self,
        articles_data: List[dict],
        category_id: UUID,
        keyword_matched: str = None,
        search_query_used: str = None
    ) -> Tuple[int, int, int]:
        """Legacy method - Enhanced bulk insert with single category per article.
        
        This method maintains backward compatibility while using the new
        bulk_create_with_category_associations method internally.
        
        Args:
            articles_data: List of article dictionaries to create
            category_id: UUID of the category to associate articles with
            keyword_matched: Specific keyword that led to article discovery
            search_query_used: The actual OR search query that found this article
            
        Returns:
            Tuple of (new_articles, updated_articles, duplicates_skipped)
        """
        if not articles_data:
            return (0, 0, 0)
        
        # Convert single category to new format
        category_associations = [
            [{"category_id": category_id, "relevance_score": 1.0}]
            for _ in articles_data
        ]
        
        # Use the new method internally
        return await self.bulk_create_with_category_associations(
            articles_data, category_associations
        )
    
    async def _merge_duplicate_articles(
        self,
        session: AsyncSession,
        articles_group: List[dict],
        maintain_associations: bool
    ) -> Tuple[Optional[dict], int]:
        """Merge duplicate articles and combine their category associations.
        
        Args:
            session: Database session
            articles_group: List of duplicate articles to merge
            maintain_associations: Whether to preserve all associations
            
        Returns:
            Tuple of (merged_article_data, associations_merged_count)
        """
        if not articles_group:
            return None, 0
        
        # Select the best article (most complete content)
        best_article = max(
            articles_group,
            key=lambda a: len(str(a.get('content', '') or '').strip())
        )
        
        # Collect all category associations
        all_associations = []
        associations_merged = 0
        
        for article_data in articles_group:
            article_associations = article_data.get('category_associations', [])
            if isinstance(article_associations, list):
                for assoc in article_associations:
                    # Avoid duplicate category associations
                    category_id = assoc.get('category_id')
                    existing = next(
                        (a for a in all_associations if a.get('category_id') == category_id),
                        None
                    )
                    
                    if existing:
                        # Use higher relevance score
                        if assoc.get('relevance_score', 0) > existing.get('relevance_score', 0):
                            existing['relevance_score'] = assoc.get('relevance_score')
                            associations_merged += 1
                    else:
                        all_associations.append(assoc.copy())
                        associations_merged += 1
        
        # Update best article with merged associations
        merged_article = best_article.copy()
        merged_article['category_associations'] = all_associations
        
        logger.debug(
            f"Merged {len(articles_group)} duplicate articles",
            extra={
                "url_hash": best_article.get('url_hash'),
                "associations_merged": associations_merged,
                "best_content_length": len(str(best_article.get('content', '') or '').strip())
            }
        )
        
        return merged_article, associations_merged
    
    async def get_deduplication_statistics(
        self,
        category_id: Optional[UUID] = None,
        days_back: int = 30
    ) -> Dict[str, Any]:
        """Get comprehensive deduplication statistics.
        
        Args:
            category_id: Optional category to filter statistics
            days_back: Number of days to look back for statistics
            
        Returns:
            Dictionary with detailed deduplication metrics
        """
        async with get_db_session() as session:
            from datetime import datetime, timezone, timedelta
            
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
            
            # Base query
            base_query = select(Article).where(Article.created_at >= cutoff_date)
            
            if category_id:
                base_query = base_query.join(
                    ArticleCategory, Article.id == ArticleCategory.article_id
                ).where(ArticleCategory.category_id == category_id)
            
            # Total articles
            total_query = select(func.count()).select_from(base_query.subquery())
            total_result = await session.execute(total_query)
            total_articles = total_result.scalar() or 0
            
            # Articles with content hashes (potential for content deduplication)
            content_hash_query = base_query.where(Article.content_hash.isnot(None))
            content_hash_result = await session.execute(
                select(func.count()).select_from(content_hash_query.subquery())
            )
            articles_with_content_hash = content_hash_result.scalar() or 0
            
            # Duplicate content hashes
            duplicate_content_query = (
                select(Article.content_hash, func.count(Article.content_hash).label('count'))
                .where(
                    and_(
                        Article.created_at >= cutoff_date,
                        Article.content_hash.isnot(None)
                    )
                )
                .group_by(Article.content_hash)
                .having(func.count(Article.content_hash) > 1)
            )
            
            if category_id:
                duplicate_content_query = duplicate_content_query.join(
                    ArticleCategory, Article.id == ArticleCategory.article_id
                ).where(ArticleCategory.category_id == category_id)
            
            duplicate_content_result = await session.execute(duplicate_content_query)
            duplicate_groups = list(duplicate_content_result.all())
            
            # Calculate statistics
            duplicate_content_count = sum(row.count - 1 for row in duplicate_groups)  # Excess duplicates
            unique_content_groups = len(duplicate_groups)
            
            stats = {
                "total_articles": total_articles,
                "articles_with_content_hash": articles_with_content_hash,
                "duplicate_content_groups": unique_content_groups,
                "duplicate_content_articles": duplicate_content_count,
                "content_deduplication_rate": (
                    duplicate_content_count / total_articles * 100 
                    if total_articles > 0 else 0.0
                ),
                "content_hash_coverage": (
                    articles_with_content_hash / total_articles * 100 
                    if total_articles > 0 else 0.0
                ),
                "analysis_period_days": days_back,
                "category_id": str(category_id) if category_id else None,
                "generated_at": datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(
                f"Deduplication statistics generated",
                extra={
                    "category_id": str(category_id) if category_id else "all",
                    "days_back": days_back,
                    **stats
                }
            )
            
            return stats
    
    async def _get_existing_article_by_hash(self, session: AsyncSession, url_hash: str) -> Optional[Article]:
        """Get existing article by URL hash within the session."""
        query = select(Article).where(Article.url_hash == url_hash)
        result = await session.execute(query)
        return result.scalar_one_or_none()
    
    async def _handle_duplicate_article(
        self,
        session: AsyncSession,
        existing_article: Article,
        new_article_data: dict,
        category_associations: List[Dict[str, Any]]
    ) -> str:
        """Handle duplicate article updates with category management.
        
        Args:
            session: Database session
            existing_article: The existing article record
            new_article_data: New article data dict
            category_associations: List of category associations to ensure
            
        Returns:
            "updated", "skipped", or "error"
        """
        try:
            # Update last_seen timestamp
            existing_article.last_seen = datetime.now(timezone.utc)
            
            # Update content hash if provided and missing
            if not existing_article.content_hash and new_article_data.get('content'):
                existing_article.content_hash = Article.generate_content_hash(new_article_data['content'])
            
            # Update content if new content is better (has content when existing doesn't)
            if new_article_data.get('content') and not existing_article.content:
                existing_article.content = new_article_data['content']
                existing_article.description = new_article_data.get('description')
                
            # Merge category associations (avoid duplicates)
            associations_created = await self._create_category_associations(
                session, existing_article.id, category_associations
            )
            
            logger.debug(
                f"Updated existing article with {associations_created} new category associations",
                extra={
                    "article_id": str(existing_article.id),
                    "url_hash": existing_article.url_hash,
                    "associations_created": associations_created
                }
            )
            
            return "updated"
            
        except Exception as e:
            logger.warning(
                f"Failed to update existing article: {e}",
                extra={
                    "article_id": str(existing_article.id),
                    "url_hash": existing_article.url_hash
                }
            )
            return "error"
    
    async def _create_category_associations(
        self,
        session: AsyncSession,
        article_id: UUID,
        category_associations: List[Dict[str, Any]]
    ) -> int:
        """Create category associations with validation.
        
        Args:
            session: Database session
            article_id: UUID of the article
            category_associations: List of category association dicts
            
        Returns:
            Number of associations created
        """
        if not category_associations:
            return 0
        
        associations_created = 0
        
        try:
            for association_data in category_associations:
                if not isinstance(association_data, dict):
                    logger.warning(
                        f"Invalid association data format",
                        extra={"article_id": str(article_id), "data": str(association_data)}
                    )
                    continue
                
                category_id = association_data.get('category_id')
                if not category_id:
                    logger.warning(
                        f"Missing category_id in association",
                        extra={"article_id": str(article_id), "association": association_data}
                    )
                    continue
                
                # Check if association already exists
                existing_query = select(ArticleCategory).where(
                    and_(
                        ArticleCategory.article_id == article_id,
                        ArticleCategory.category_id == category_id
                    )
                )
                existing_result = await session.execute(existing_query)
                existing_association = existing_result.scalar_one_or_none()
                
                if existing_association:
                    # Update relevance score if new one is higher
                    new_relevance = association_data.get('relevance_score', 1.0)
                    if new_relevance > (existing_association.relevance_score or 0.0):
                        existing_association.relevance_score = new_relevance
                        logger.debug(
                            f"Updated existing association relevance score",
                            extra={
                                "article_id": str(article_id),
                                "category_id": str(category_id),
                                "new_relevance": new_relevance
                            }
                        )
                else:
                    # Create new association
                    association = ArticleCategory(
                        article_id=article_id,
                        category_id=category_id,
                        relevance_score=association_data.get('relevance_score', 1.0),
                        created_at=datetime.now(timezone.utc)
                    )
                    session.add(association)
                    associations_created += 1
                    
                    logger.debug(
                        f"Created new category association",
                        extra={
                            "article_id": str(article_id),
                            "category_id": str(category_id),
                            "relevance_score": association_data.get('relevance_score', 1.0)
                        }
                    )
            
            return associations_created

        except Exception as e:
            logger.error(
                f"Failed to create category associations: {e}",
                extra={
                    "article_id": str(article_id),
                    "associations_count": len(category_associations)
                }
            )
            raise

    async def get_articles_paginated(
        self,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        size: int = 20
    ) -> Tuple[List[Article], int]:
        """Get paginated articles with filtering support.

        Args:
            filters: Dictionary of filters to apply
            page: Page number (1-based)
            size: Number of articles per page

        Returns:
            Tuple of (articles_list, total_count)
        """
        async with get_db_session() as session:
            # Build base query with category relationships loaded
            query = select(Article).options(selectinload(Article.categories))
            count_query = select(func.count(Article.id))

            # Apply filters if provided
            if filters:
                conditions = []

                # Job ID filter
                if 'job_id' in filters:
                    conditions.append(Article.crawl_job_id == filters['job_id'])

                # Category ID filter (requires join)
                if 'category_id' in filters:
                    query = query.join(ArticleCategory).join(Category)
                    count_query = count_query.join(ArticleCategory).join(Category)
                    conditions.append(Category.id == filters['category_id'])

                # Search query (full-text search)
                if 'search_query' in filters:
                    search_term = f"%{filters['search_query']}%"
                    conditions.append(
                        func.or_(
                            Article.title.ilike(search_term),
                            Article.content.ilike(search_term)
                        )
                    )

                # Keywords filter
                if 'keywords' in filters and filters['keywords']:
                    conditions.append(
                        Article.keywords_matched.op('&&')(filters['keywords'])
                    )

                # Relevance score filter
                if 'min_relevance_score' in filters:
                    conditions.append(
                        Article.relevance_score >= filters['min_relevance_score']
                    )

                # Date filters
                if 'from_date' in filters:
                    conditions.append(Article.publish_date >= filters['from_date'])
                if 'to_date' in filters:
                    conditions.append(Article.publish_date <= filters['to_date'])

                # Apply all conditions
                if conditions:
                    filter_condition = and_(*conditions)
                    query = query.where(filter_condition)
                    count_query = count_query.where(filter_condition)

            # Get total count
            count_result = await session.execute(count_query)
            total = count_result.scalar()

            # Apply pagination and ordering
            query = query.order_by(
                Article.publish_date.desc().nullslast(),
                Article.created_at.desc()
            ).offset((page - 1) * size).limit(size)

            # Execute query
            result = await session.execute(query)
            articles = result.scalars().all()

            return list(articles), total

    async def get_article_statistics(self) -> Dict[str, Any]:
        """Get article statistics for analytics.

        Returns:
            Dictionary containing various article statistics
        """
        async with get_db_session() as session:
            # Total articles count
            total_result = await session.execute(
                select(func.count(Article.id))
            )
            total_articles = total_result.scalar()

            # Articles by job
            job_stats_result = await session.execute(
                select(
                    Article.crawl_job_id,
                    func.count(Article.id)
                ).where(
                    Article.crawl_job_id.is_not(None)
                ).group_by(Article.crawl_job_id)
            )
            articles_by_job = {
                str(job_id): count for job_id, count in job_stats_result
            }

            # Articles by category (through category associations)
            category_stats_result = await session.execute(
                select(
                    Category.id,
                    Category.name,
                    func.count(ArticleCategory.article_id)
                ).select_from(
                    Category
                ).join(ArticleCategory).group_by(Category.id, Category.name)
            )
            articles_by_category = {
                f"{name} ({str(cat_id)})": count
                for cat_id, name, count in category_stats_result
            }

            # Recent articles (last 24 hours)
            recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
            recent_result = await session.execute(
                select(func.count(Article.id)).where(
                    Article.created_at >= recent_cutoff
                )
            )
            recent_articles_count = recent_result.scalar()

            # Average relevance score
            avg_relevance_result = await session.execute(
                select(func.avg(Article.relevance_score))
            )
            avg_relevance = avg_relevance_result.scalar() or 0.0

            return {
                'total_articles': total_articles,
                'articles_by_job': articles_by_job,
                'articles_by_category': articles_by_category,
                'recent_articles_count': recent_articles_count,
                'average_relevance_score': float(avg_relevance)
            }