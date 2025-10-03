"""
Backfill script to update keywords_matched and relevance_score for existing articles.

This script:
1. Loads all articles with empty keywords_matched
2. Fetches their associated categories
3. Re-runs keyword matching logic
4. Calculates binary relevance score (50% title + 50% content)
5. Updates articles and article_categories tables

Usage:
    docker-compose exec web python -m src.scripts.backfill_keywords_relevance
"""

import logging
from typing import List, Dict, Any
from decimal import Decimal

from src.database.repositories.sync_base import SyncBaseRepository
from src.database.models.article import Article
from src.database.models.article_category import ArticleCategory
from src.database.models.category import Category
from src.core.crawler.keyword_matcher import extract_matched_keywords_from_content
from src.core.linking.category_matcher import CategoryMatcher
from src.database.repositories.sync_category_repo import SyncCategoryRepository

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def calculate_relevance_score(article_data: Dict[str, Any], matched_keywords: List[str]) -> float:
    """Calculate binary relevance score (50% title + 50% content)."""
    if not matched_keywords:
        return 0.0

    title = (article_data.get('title', '') or '').lower()
    content = (article_data.get('content', '') or '').lower()

    # Check if ANY keyword appears in title or content
    has_title_match = any(kw.lower() in title for kw in matched_keywords)
    has_content_match = any(kw.lower() in content for kw in matched_keywords)

    # Binary scoring: 50% if matched in title, 50% if matched in content
    title_score = 0.5 if has_title_match else 0.0
    content_score = 0.5 if has_content_match else 0.0

    return title_score + content_score


def backfill_article(article: Article, session) -> bool:
    """Backfill keywords and relevance for a single article.

    Returns:
        True if article was updated, False otherwise
    """
    try:
        # Get article's categories from article_categories junction table
        article_categories = session.query(ArticleCategory).filter(
            ArticleCategory.article_id == article.id
        ).all()

        if not article_categories:
            logger.warning(f"Article {article.id} has no categories, skipping")
            return False

        # Get primary category (first one, or from crawl_job)
        primary_category_id = article_categories[0].category_id

        # Load primary category
        primary_category = session.query(Category).filter(
            Category.id == primary_category_id
        ).first()

        if not primary_category or not primary_category.keywords:
            logger.warning(f"Article {article.id} primary category has no keywords, skipping")
            return False

        # Build article dict for keyword matching
        article_data = {
            'title': article.title,
            'content': article.content,
        }

        # Extract matched keywords
        matched_keywords = extract_matched_keywords_from_content(
            article_data,
            primary_category.keywords
        )

        # Calculate relevance score
        relevance_score = calculate_relevance_score(article_data, matched_keywords)

        # Update article
        article.keywords_matched = matched_keywords
        article.relevance_score = relevance_score

        # Update primary ArticleCategory association
        for article_cat in article_categories:
            if article_cat.category_id == primary_category_id:
                article_cat.relevance_score = Decimal(str(relevance_score))
                break

        # Multi-category linking: check if article matches other categories
        category_repo = SyncCategoryRepository()
        all_categories = category_repo.get_active_categories()

        # Filter out already linked categories
        linked_category_ids = {str(ac.category_id) for ac in article_categories}
        other_categories = [c for c in all_categories if str(c.id) not in linked_category_ids]

        if other_categories:
            matcher = CategoryMatcher()
            matches = matcher.find_matching_categories(
                article_data,
                other_categories,
                min_relevance=0.3
            )

            # Create new ArticleCategory associations for matches
            for match in matches:
                new_link = ArticleCategory(
                    article_id=article.id,
                    category_id=match['category_id'],
                    relevance_score=match['relevance_score']
                )
                session.add(new_link)

            if matches:
                logger.info(f"Article {article.id} linked to {len(matches)} additional categories")

        session.commit()

        logger.info(
            f"Updated article {str(article.id)[:8]}... - "
            f"keywords: {len(matched_keywords)}, relevance: {relevance_score:.2f}"
        )
        return True

    except Exception as e:
        session.rollback()
        logger.error(f"Failed to backfill article {article.id}: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main backfill process."""
    logger.info("Starting keywords & relevance backfill process...")

    # Create a simple Article repo
    class ArticleRepo(SyncBaseRepository):
        model_class = Article

    repo = ArticleRepo()

    with repo.get_session() as session:
        # Get all articles with empty keywords_matched
        articles = session.query(Article).filter(
            (Article.keywords_matched == []) | (Article.keywords_matched == None)
        ).all()

        total = len(articles)
        logger.info(f"Found {total} articles to backfill")

        if total == 0:
            logger.info("No articles need backfilling. Exiting.")
            return

        # Process articles (auto-confirm for Docker execution)
        logger.info(f"Processing {total} articles...")
        logger.info(f"This will update: keywords_matched, relevance_score, article_categories")

        updated_count = 0
        failed_count = 0

        for idx, article in enumerate(articles, 1):
            logger.info(f"Processing {idx}/{total}: {article.title[:50]}...")

            if backfill_article(article, session):
                updated_count += 1
            else:
                failed_count += 1

            # Progress update every 50 articles
            if idx % 50 == 0:
                logger.info(f"Progress: {idx}/{total} ({updated_count} updated, {failed_count} failed)")

        # Final summary
        logger.info(f"\n{'='*60}")
        logger.info(f"Backfill complete!")
        logger.info(f"  Total processed: {total}")
        logger.info(f"  Successfully updated: {updated_count}")
        logger.info(f"  Failed: {failed_count}")
        logger.info(f"{'='*60}\n")


if __name__ == "__main__":
    main()
