"""Sync article repository for Celery tasks."""

import logging
import hashlib
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import select, and_, or_, exists, func
from sqlalchemy.orm import selectinload

from src.database.repositories.sync_base import SyncBaseRepository
from src.database.models.article import Article
from src.database.models.category import Category
from src.database.models.article_category import ArticleCategory

logger = logging.getLogger(__name__)


class SyncArticleRepository(SyncBaseRepository[Article]):
    """Sync article repository for Celery workers."""

    model_class = Article

    def _generate_url_hash(self, url: str) -> str:
        """Generate URL hash for deduplication."""
        return hashlib.sha256(url.encode('utf-8')).hexdigest()

    def save_articles_with_deduplication(
        self,
        articles_data: List[Dict[str, Any]],
        category_id: UUID
    ) -> int:
        """Save articles with deduplication logic.

        Args:
            articles_data: List of article data dictionaries
            category_id: Category to associate articles with

        Returns:
            Number of articles successfully saved
        """
        if not articles_data:
            return 0

        saved_count = 0

        try:
            with self.get_session() as session:
                for article_data in articles_data:
                    try:
                        # Generate URL hash for deduplication
                        source_url = article_data.get('source_url', '')
                        if not source_url:
                            logger.warning("Article missing source_url, skipping")
                            continue

                        url_hash = self._generate_url_hash(source_url)

                        # Check if article already exists
                        existing_article = session.execute(
                            select(Article).where(Article.url_hash == url_hash)
                        ).scalar_one_or_none()

                        if existing_article:
                            # Update last_seen for existing article
                            existing_article.last_seen = datetime.now(timezone.utc)

                            # Check if this category association already exists
                            existing_association = session.execute(
                                select(ArticleCategory).where(
                                    and_(
                                        ArticleCategory.article_id == existing_article.id,
                                        ArticleCategory.category_id == category_id
                                    )
                                )
                            ).scalar_one_or_none()

                            if not existing_association:
                                # Create new category association
                                article_category = ArticleCategory(
                                    article_id=existing_article.id,
                                    category_id=category_id,
                                    relevance_score=1.0,
                                    keyword_matched=article_data.get('keyword_matched'),
                                    search_query_used=article_data.get('search_query_used')
                                )
                                session.add(article_category)

                            session.commit()
                            logger.debug(f"Updated existing article: {existing_article.title}")
                            continue

                        # Create new article
                        new_article = Article(
                            title=article_data.get('title', '').strip(),
                            content=article_data.get('content', '').strip(),
                            source_url=source_url,
                            url_hash=url_hash,
                            author=article_data.get('author', '').strip() or None,
                            published_date=article_data.get('published_date'),
                            image_url=article_data.get('image_url', '').strip() or None,
                            summary=article_data.get('summary', '').strip() or None,
                            language=article_data.get('language', 'vi'),
                            word_count=len(article_data.get('content', '').split()) if article_data.get('content') else 0,
                            last_seen=datetime.now(timezone.utc)
                        )

                        session.add(new_article)
                        session.flush()  # Get the article ID

                        # Create category association
                        article_category = ArticleCategory(
                            article_id=new_article.id,
                            category_id=category_id,
                            relevance_score=1.0,
                            keyword_matched=article_data.get('keyword_matched'),
                            search_query_used=article_data.get('search_query_used')
                        )
                        session.add(article_category)

                        session.commit()
                        saved_count += 1

                        logger.debug(f"Saved new article: {new_article.title}")

                    except Exception as e:
                        session.rollback()
                        logger.error(f"Failed to save article {article_data.get('title', 'Unknown')}: {e}")
                        continue

        except Exception as e:
            logger.error(f"Database error during article save: {e}")

        logger.info(f"Successfully saved {saved_count} articles out of {len(articles_data)} for category {category_id}")
        return saved_count

    def get_existing_by_url_hashes(
        self,
        url_hashes: List[str]
    ) -> List[Article]:
        """Get existing articles by URL hashes."""
        if not url_hashes:
            return []

        with self.get_session() as session:
            articles = session.execute(
                select(Article).where(Article.url_hash.in_(url_hashes))
            ).scalars().all()

            return list(articles)

    def get_recent_articles(
        self,
        category_id: Optional[UUID] = None,
        limit: int = 100
    ) -> List[Article]:
        """Get recent articles, optionally filtered by category."""
        with self.get_session() as session:
            query = select(Article).order_by(Article.created_at.desc())

            if category_id:
                query = query.join(ArticleCategory).where(
                    ArticleCategory.category_id == category_id
                )

            query = query.limit(limit)

            articles = session.execute(query).scalars().all()
            return list(articles)

    def count_articles_for_category(self, category_id: UUID) -> int:
        """Count articles for a specific category."""
        with self.get_session() as session:
            count = session.execute(
                select(func.count(ArticleCategory.article_id)).where(
                    ArticleCategory.category_id == category_id
                )
            ).scalar()

            return count or 0