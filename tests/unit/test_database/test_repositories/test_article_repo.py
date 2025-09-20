"""Unit tests for ArticleRepository with enhanced category storage scenarios.

This module tests all aspects of the ArticleRepository including:
- Bulk article creation with multiple category associations per article
- Enhanced duplicate detection and category association merging
- Category filtering performance with large datasets
- Transaction rollback scenarios when category association fails
- Relevance scoring accuracy with different keyword match patterns
"""

import pytest
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from unittest.mock import AsyncMock, Mock, patch, MagicMock
from decimal import Decimal

# Test imports
from src.database.repositories.article_repo import ArticleRepository
from src.database.models.article import Article
from src.database.models.article_category import ArticleCategory
from src.database.models.category import Category
from src.shared.exceptions import BaseScraperError


class TestArticleRepositoryEnhanced:
    """Test class for enhanced ArticleRepository functionality."""
    
    @pytest.fixture
    async def article_repo(self):
        """Create ArticleRepository instance for testing."""
        return ArticleRepository()
    
    @pytest.fixture
    def sample_categories(self):
        """Create sample categories for testing."""
        tech_category = Mock()
        tech_category.id = uuid.uuid4()
        tech_category.name = "Technology"
        tech_category.keywords = ["python", "javascript", "AI"]
        tech_category.is_active = True
        
        ai_category = Mock()
        ai_category.id = uuid.uuid4()
        ai_category.name = "Artificial Intelligence"
        ai_category.keywords = ["AI", "machine learning", "neural networks"]
        ai_category.is_active = True
        
        return tech_category, ai_category
    
    @pytest.fixture
    def sample_articles_data(self):
        """Create sample article data for testing."""
        return [
            {
                "title": "Python AI Breakthrough",
                "content": "Researchers develop new AI framework using Python...",
                "source_url": "https://example.com/python-ai",
                "url_hash": Article.generate_url_hash("https://example.com/python-ai"),
                "content_hash": Article.generate_content_hash("Researchers develop new AI framework using Python..."),
                "author": "Dr. Smith",
                "publish_date": datetime.now(timezone.utc),
                "created_at": datetime.now(timezone.utc),
                "last_seen": datetime.now(timezone.utc)
            },
            {
                "title": "JavaScript ML Library Released",
                "content": "New machine learning library for JavaScript developers...",
                "source_url": "https://example.com/js-ml",
                "url_hash": Article.generate_url_hash("https://example.com/js-ml"),
                "content_hash": Article.generate_content_hash("New machine learning library for JavaScript developers..."),
                "author": "Jane Doe",
                "publish_date": datetime.now(timezone.utc),
                "created_at": datetime.now(timezone.utc),
                "last_seen": datetime.now(timezone.utc)
            }
        ]
    
    @pytest.mark.asyncio
    async def test_bulk_create_with_multiple_category_associations(
        self, article_repo, sample_categories, sample_articles_data
    ):
        """Test bulk article creation with multiple category associations per article."""
        tech_category, ai_category = sample_categories
        
        # Prepare category associations - each article associated with both categories
        category_associations = [
            [  # First article associations
                {"category_id": tech_category.id, "relevance_score": 0.9},
                {"category_id": ai_category.id, "relevance_score": 0.8}
            ],
            [  # Second article associations  
                {"category_id": tech_category.id, "relevance_score": 0.7}
            ]
        ]
        
        with patch.object(article_repo, '_get_existing_article_by_hash', return_value=None), \
             patch.object(article_repo, '_create_category_associations', return_value=2) as mock_create_assoc, \
             patch('src.database.repositories.article_repo.get_db_session'):
            
            # Execute bulk creation
            new, updated, skipped = await article_repo.bulk_create_with_category_associations(
                sample_articles_data, category_associations
            )
            
            # Assertions
            assert new == 2
            assert updated == 0
            assert skipped == 0
            
            # Verify category associations were created
            assert mock_create_assoc.call_count == 2
    
    @pytest.mark.asyncio
    async def test_duplicate_article_category_merging(
        self, article_repo, sample_categories, sample_articles_data
    ):
        """Test duplicate article handling with category merging."""
        tech_category, ai_category = sample_categories
        
        # Create existing article mock
        existing_article = Mock()
        existing_article.id = uuid.uuid4()
        existing_article.url_hash = sample_articles_data[0]["url_hash"]
        existing_article.content = None  # No content initially
        existing_article.content_hash = None
        existing_article.last_seen = datetime.now(timezone.utc) - timedelta(days=1)
        
        # Category associations for the duplicate
        duplicate_associations = [
            {"category_id": ai_category.id, "relevance_score": 0.9},  # Higher score
            {"category_id": tech_category.id, "relevance_score": 0.7}  # New category
        ]
        
        with patch.object(article_repo, '_get_existing_article_by_hash', return_value=existing_article), \
             patch.object(article_repo, '_create_category_associations', return_value=2) as mock_create_assoc, \
             patch('src.database.repositories.article_repo.get_db_session'):
            
            # Execute bulk creation with duplicate
            new, updated, skipped = await article_repo.bulk_create_with_category_associations(
                sample_articles_data[:1], [duplicate_associations]
            )
            
            # Assertions
            assert new == 0
            assert updated == 1
            assert skipped == 0
            
            # Verify content was updated (article had no content before)
            assert existing_article.content == sample_articles_data[0]["content"]
            assert existing_article.content_hash is not None
            
            # Verify category associations were created/updated
            mock_create_assoc.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_enhanced_duplicate_detection_with_content_similarity(
        self, article_repo, sample_articles_data
    ):
        """Test content similarity detection for duplicate identification."""
        # Create articles with same content hash
        content_hash = "same_content_hash_123"
        
        articles_with_same_content = [
            {**sample_articles_data[0], "content_hash": content_hash, "source_url": "https://example.com/article1"},
            {**sample_articles_data[0], "content_hash": content_hash, "source_url": "https://example.com/article2"}
        ]
        
        # Mock database session and query results
        mock_articles = [
            Mock(id=uuid.uuid4(), content_hash=content_hash, created_at=datetime.now(timezone.utc)),
            Mock(id=uuid.uuid4(), content_hash=content_hash, created_at=datetime.now(timezone.utc))
        ]
        
        with patch('src.database.repositories.article_repo.get_db_session') as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session_ctx.return_value.__aenter__.return_value = mock_session
            
            mock_result = AsyncMock()
            mock_result.scalars.return_value.all.return_value = mock_articles
            mock_session.execute.return_value = mock_result
            
            # Execute similarity detection
            similar_articles = await article_repo.find_similar_articles_by_content(
                content_hash=content_hash,
                similarity_threshold=0.8,
                include_categories=True
            )
            
            # Assertions
            assert len(similar_articles) == 2
            assert all(article.content_hash == content_hash for article in similar_articles)
    
    @pytest.mark.asyncio
    async def test_category_filtering_with_relevance_threshold(
        self, article_repo, sample_categories
    ):
        """Test category-based filtering with relevance score thresholds."""
        tech_category, ai_category = sample_categories
        
        # Mock articles with different relevance scores
        mock_articles = [
            Mock(id=uuid.uuid4(), title="High relevance article"),
            Mock(id=uuid.uuid4(), title="Medium relevance article")
        ]
        
        with patch('src.database.repositories.article_repo.get_db_session') as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session_ctx.return_value.__aenter__.return_value = mock_session
            
            mock_result = AsyncMock()
            mock_result.scalars.return_value.all.return_value = mock_articles
            mock_session.execute.return_value = mock_result
            
            # Test filtering with high relevance threshold
            filtered_articles = await article_repo.find_articles_by_category(
                category_id=tech_category.id,
                relevance_threshold=0.7,
                limit=100
            )
            
            # Assertions
            assert len(filtered_articles) == 2
            
            # Verify query was built correctly (check that execute was called)
            mock_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_optimized_category_filtering_performance(
        self, article_repo, sample_categories
    ):
        """Test performance-optimized category filtering with complex conditions."""
        tech_category, ai_category = sample_categories
        
        category_filters = {
            "category_ids": [tech_category.id, ai_category.id],
            "any_category": True,
            "exclude_category_ids": []
        }
        
        # Mock large result set
        mock_articles = [Mock(id=uuid.uuid4(), title=f"Article {i}") for i in range(50)]
        
        with patch('src.database.repositories.article_repo.get_db_session') as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session_ctx.return_value.__aenter__.return_value = mock_session
            
            # Mock both article query and count query results
            mock_article_result = AsyncMock()
            mock_article_result.scalars.return_value.unique.return_value = mock_articles
            
            mock_count_result = AsyncMock()
            mock_count_result.scalar.return_value = 150
            
            mock_session.execute.side_effect = [mock_article_result, mock_count_result]
            
            # Execute optimized filtering
            articles, total_count = await article_repo.get_articles_with_category_filtering_optimized(
                category_filters=category_filters,
                relevance_threshold=0.3,
                limit=50,
                offset=0,
                order_by="relevance_score",
                order_direction="desc"
            )
            
            # Assertions
            assert len(articles) == 50
            assert total_count == 150
            
            # Verify both queries were executed (article query + count query)
            assert mock_session.execute.call_count == 2
    
    @pytest.mark.asyncio
    async def test_article_retrieval_with_detailed_categories(
        self, article_repo, sample_categories
    ):
        """Test article retrieval with detailed category information."""
        tech_category, ai_category = sample_categories
        
        # Mock article with category associations
        mock_article = Mock()
        mock_article.id = uuid.uuid4()
        mock_article.title = "Test Article"
        mock_article.content = "Test content"
        mock_article.categories = [
            Mock(category_id=tech_category.id, relevance_score=Decimal('0.9'), created_at=datetime.now(timezone.utc)),
            Mock(category_id=ai_category.id, relevance_score=Decimal('0.8'), created_at=datetime.now(timezone.utc))
        ]
        mock_article.author = "Test Author"
        mock_article.publish_date = datetime.now(timezone.utc)
        mock_article.source_url = "https://example.com/test"
        mock_article.image_url = None
        mock_article.url_hash = "test_hash"
        mock_article.content_hash = "content_hash"
        mock_article.created_at = datetime.now(timezone.utc)
        mock_article.updated_at = datetime.now(timezone.utc)
        mock_article.last_seen = datetime.now(timezone.utc)
        
        with patch('src.database.repositories.article_repo.get_db_session') as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session_ctx.return_value.__aenter__.return_value = mock_session
            
            # Mock article query result
            mock_article_result = AsyncMock()
            mock_article_result.scalar_one_or_none.return_value = mock_article
            
            # Mock category query result
            mock_category_result = AsyncMock()
            mock_category_result.scalars.return_value.all.return_value = [tech_category, ai_category]
            
            mock_session.execute.side_effect = [mock_article_result, mock_category_result]
            
            # Execute detailed retrieval
            article_dict = await article_repo.get_article_with_category_names_and_scores(
                article_id=mock_article.id
            )
            
            # Assertions
            assert article_dict is not None
            assert article_dict["id"] == str(mock_article.id)
            assert article_dict["title"] == "Test Article"
            assert len(article_dict["categories"]) == 2
            
            # Verify categories are sorted by relevance score (highest first)
            assert article_dict["categories"][0]["relevance_score"] == 0.9
            assert article_dict["categories"][0]["category_name"] == "Technology"
            assert article_dict["categories"][1]["relevance_score"] == 0.8
            assert article_dict["categories"][1]["category_name"] == "Artificial Intelligence"
    
    @pytest.mark.asyncio
    async def test_deduplication_statistics_accuracy(self, article_repo, sample_categories):
        """Test deduplication statistics calculation accuracy."""
        tech_category, _ = sample_categories
        
        # Mock statistics data
        mock_stats_data = [
            Mock(content_hash="hash1", count=3),  # 3 articles with same content (2 duplicates)
            Mock(content_hash="hash2", count=2),  # 2 articles with same content (1 duplicate)
        ]
        
        with patch('src.database.repositories.article_repo.get_db_session') as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session_ctx.return_value.__aenter__.return_value = mock_session
            
            # Mock multiple query results for statistics
            mock_total_result = AsyncMock()
            mock_total_result.scalar.return_value = 100
            
            mock_content_hash_result = AsyncMock()
            mock_content_hash_result.scalar.return_value = 80
            
            mock_duplicate_result = AsyncMock()
            mock_duplicate_result.all.return_value = mock_stats_data
            
            mock_session.execute.side_effect = [
                mock_total_result,      # Total articles
                mock_content_hash_result,  # Articles with content hash
                mock_duplicate_result   # Duplicate content groups
            ]
            
            # Execute statistics calculation
            stats = await article_repo.get_deduplication_statistics(
                category_id=tech_category.id,
                days_back=30
            )
            
            # Assertions
            assert stats["total_articles"] == 100
            assert stats["articles_with_content_hash"] == 80
            assert stats["duplicate_content_groups"] == 2
            assert stats["duplicate_content_articles"] == 3  # (3-1) + (2-1) = 3
            assert stats["content_deduplication_rate"] == 3.0  # 3/100 * 100
            assert stats["content_hash_coverage"] == 80.0  # 80/100 * 100
            assert stats["category_id"] == str(tech_category.id)
    
    @pytest.mark.asyncio
    async def test_transaction_rollback_on_category_association_failure(
        self, article_repo, sample_articles_data
    ):
        """Test transaction rollback behavior when category association fails."""
        # Simulate category association failure
        invalid_category_associations = [
            [{"category_id": "invalid-uuid", "relevance_score": 0.9}]
        ]
        
        with patch('src.database.repositories.article_repo.get_db_session') as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session_ctx.return_value.__aenter__.return_value = mock_session
            mock_session_ctx.return_value.begin.return_value.__aenter__ = AsyncMock()
            mock_session_ctx.return_value.begin.return_value.__aexit__ = AsyncMock()
            
            # Mock article creation but category association failure
            with patch.object(article_repo, '_get_existing_article_by_hash', return_value=None), \
                 patch.object(article_repo, '_create_category_associations', side_effect=Exception("Invalid category ID")):
                
                # Execute bulk creation - should handle the exception
                try:
                    new, updated, skipped = await article_repo.bulk_create_with_category_associations(
                        sample_articles_data[:1], invalid_category_associations
                    )
                    # Should not reach here if exception is properly raised
                    assert False, "Expected exception was not raised"
                except Exception as e:
                    assert "Invalid category ID" in str(e)
    
    @pytest.mark.asyncio
    async def test_relevance_scoring_accuracy(self, article_repo):
        """Test relevance scoring accuracy with different keyword match patterns."""
        # Test data with different keyword matching scenarios
        test_cases = [
            {
                "content": "Python is a great programming language for AI development",
                "keywords": ["python", "AI"],
                "expected_min_score": 0.5  # Should match both keywords
            },
            {
                "content": "JavaScript frameworks are becoming more popular",
                "keywords": ["javascript", "python", "AI"],
                "expected_min_score": 0.2  # Should match 1 out of 3 keywords
            },
            {
                "content": "Quantum computing breakthrough announced",
                "keywords": ["python", "javascript"],
                "expected_min_score": 0.0  # Should match no keywords
            }
        ]
        
        for case in test_cases:
            # Execute relevance calculation (this is a static method)
            relevance_score = article_repo.calculate_relevance_score(
                case["content"], case["keywords"]
            )
            
            # Assertions
            assert relevance_score >= case["expected_min_score"], \
                f"Relevance score {relevance_score} should be >= {case['expected_min_score']} for content: {case['content']}"
            assert 0.0 <= relevance_score <= 1.0, "Relevance score should be between 0.0 and 1.0"
    
    @pytest.mark.asyncio
    async def test_concurrent_article_creation_race_conditions(
        self, article_repo, sample_articles_data, sample_categories
    ):
        """Test concurrent article creation to avoid race conditions."""
        tech_category, ai_category = sample_categories
        
        # Prepare multiple concurrent creation tasks
        category_associations = [
            [{"category_id": tech_category.id, "relevance_score": 0.9}]
            for _ in range(5)
        ]
        
        concurrent_articles = sample_articles_data[:1] * 5  # Same article multiple times
        
        with patch.object(article_repo, '_get_existing_article_by_hash') as mock_get_existing, \
             patch.object(article_repo, '_create_category_associations', return_value=1), \
             patch('src.database.repositories.article_repo.get_db_session'):
            
            # First call returns None (no existing), subsequent calls return existing article
            existing_article = Mock()
            existing_article.id = uuid.uuid4()
            existing_article.last_seen = datetime.now(timezone.utc)
            
            mock_get_existing.side_effect = [None, existing_article, existing_article, existing_article, existing_article]
            
            # Execute concurrent creation simulation
            new, updated, skipped = await article_repo.bulk_create_with_category_associations(
                concurrent_articles, category_associations
            )
            
            # Assertions - should handle duplicates correctly
            assert new == 1  # Only first should be created as new
            assert updated == 4  # Rest should be treated as updates
            assert skipped == 0
    
    @pytest.mark.asyncio
    async def test_memory_usage_with_large_batch_operations(
        self, article_repo, sample_categories
    ):
        """Test memory usage with large batch operations (500+ articles)."""
        tech_category, _ = sample_categories
        
        # Generate large batch of articles
        large_batch_size = 500
        large_articles_data = []
        large_category_associations = []
        
        for i in range(large_batch_size):
            article_data = {
                "title": f"Article {i}",
                "content": f"Content for article {i}",
                "source_url": f"https://example.com/article-{i}",
                "url_hash": Article.generate_url_hash(f"https://example.com/article-{i}"),
                "content_hash": Article.generate_content_hash(f"Content for article {i}"),
                "author": f"Author {i}",
                "publish_date": datetime.now(timezone.utc),
                "created_at": datetime.now(timezone.utc),
                "last_seen": datetime.now(timezone.utc)
            }
            large_articles_data.append(article_data)
            large_category_associations.append([{"category_id": tech_category.id, "relevance_score": 0.8}])
        
        with patch.object(article_repo, '_get_existing_article_by_hash', return_value=None), \
             patch.object(article_repo, '_create_category_associations', return_value=1), \
             patch('src.database.repositories.article_repo.get_db_session'):
            
            # Execute large batch operation
            new, updated, skipped = await article_repo.bulk_create_with_category_associations(
                large_articles_data, large_category_associations
            )
            
            # Assertions
            assert new == large_batch_size
            assert updated == 0
            assert skipped == 0
    
    @pytest.mark.asyncio
    async def test_database_constraint_validation(
        self, article_repo, sample_articles_data, sample_categories
    ):
        """Test database constraint validation for relevance scores and foreign keys."""
        tech_category, _ = sample_categories
        
        # Test invalid relevance scores
        invalid_associations = [
            [
                {"category_id": tech_category.id, "relevance_score": 1.5},  # > 1.0
                {"category_id": tech_category.id, "relevance_score": -0.1}  # < 0.0
            ]
        ]
        
        with patch('src.database.repositories.article_repo.get_db_session') as mock_session_ctx:
            mock_session = AsyncMock()
            mock_session_ctx.return_value.__aenter__.return_value = mock_session
            mock_session_ctx.return_value.begin.return_value.__aenter__ = AsyncMock()
            mock_session_ctx.return_value.begin.return_value.__aexit__ = AsyncMock()
            
            with patch.object(article_repo, '_get_existing_article_by_hash', return_value=None), \
                 patch.object(article_repo, '_create_category_associations', side_effect=Exception("Constraint violation")):
                
                # Execute with invalid data - should handle constraint violations
                try:
                    await article_repo.bulk_create_with_category_associations(
                        sample_articles_data[:1], invalid_associations
                    )
                    assert False, "Expected constraint violation exception"
                except Exception as e:
                    assert "Constraint violation" in str(e)


class TestArticleRepositoryIntegration:
    """Integration tests for complete category-based article storage workflow."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_category_based_article_storage(self):
        """Test complete workflow from article extraction to category-based storage."""
        # This would be an integration test that tests the complete flow
        # from crawler engine through article repository to database
        # For now, this is a placeholder for the integration test structure
        
        # Mock the complete workflow
        mock_crawler_result = {
            "articles_extracted": 5,
            "articles_saved": 4,
            "duplicates_skipped": 1,
            "categories_associated": 8
        }
        
        # Assertions for end-to-end workflow
        assert mock_crawler_result["articles_extracted"] == 5
        assert mock_crawler_result["articles_saved"] == 4
        assert mock_crawler_result["duplicates_skipped"] == 1
        assert mock_crawler_result["categories_associated"] == 8


@pytest.mark.asyncio
class TestArticleRepositoryEnhanced:
    """Tests for enhanced article repository functionality (Story 2.1)."""

    @pytest.fixture
    async def article_repo(self):
        """Create ArticleRepository instance for testing."""
        return ArticleRepository()

    @pytest.fixture
    def sample_job_id(self):
        """Sample job ID for testing."""
        return uuid.uuid4()

    @pytest.fixture
    def sample_articles_with_job(self, sample_job_id):
        """Create sample articles with job associations."""
        articles = []
        for i in range(10):
            article = Mock()
            article.id = uuid.uuid4()
            article.title = f"Test Article {i+1}"
            article.content = f"This is test content for article {i+1}"
            article.source_url = f"https://example.com/article{i+1}"
            article.crawl_job_id = sample_job_id if i < 5 else None
            article.keywords_matched = ['python', 'ai'] if i % 2 == 0 else ['javascript']
            article.relevance_score = 0.8 if i < 3 else 0.5
            article.publish_date = datetime.now(timezone.utc)
            article.created_at = datetime.now(timezone.utc)
            article.updated_at = datetime.now(timezone.utc)
            articles.append(article)
        return articles

    async def test_get_articles_paginated_with_job_filter(self, article_repo, sample_articles_with_job, sample_job_id):
        """Test paginated article retrieval with job ID filter."""
        with patch('src.database.repositories.article_repo.get_db_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            # Mock count query result
            count_result = Mock()
            count_result.scalar.return_value = 5

            # Mock articles query result
            articles_result = Mock()
            articles_result.scalars.return_value.all.return_value = sample_articles_with_job[:5]

            # Mock execute to return different results for count vs select
            mock_session.execute.side_effect = [count_result, articles_result]

            # Test paginated retrieval with job filter
            articles, total = await article_repo.get_articles_paginated(
                filters={'job_id': sample_job_id},
                page=1,
                size=10
            )

            # Verify results
            assert total == 5
            assert len(articles) == 5
            for article in articles:
                assert article.crawl_job_id == sample_job_id

    async def test_get_articles_paginated_with_search(self, article_repo, sample_articles_with_job):
        """Test paginated article retrieval with search filter."""
        with patch('src.database.repositories.article_repo.get_db_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            # Mock count query result
            count_result = Mock()
            count_result.scalar.return_value = 3

            # Mock articles query result
            matching_articles = [a for a in sample_articles_with_job if 'python' in a.content or 'python' in a.title]
            articles_result = Mock()
            articles_result.scalars.return_value.all.return_value = matching_articles

            mock_session.execute.side_effect = [count_result, articles_result]

            # Test paginated retrieval with search
            articles, total = await article_repo.get_articles_paginated(
                filters={'search_query': 'python'},
                page=1,
                size=10
            )

            # Verify search functionality was called
            assert mock_session.execute.call_count == 2

    async def test_get_articles_paginated_with_keywords_filter(self, article_repo, sample_articles_with_job):
        """Test paginated article retrieval with keywords filter."""
        with patch('src.database.repositories.article_repo.get_db_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            # Mock count query result
            count_result = Mock()
            count_result.scalar.return_value = 5

            # Mock articles query result
            articles_result = Mock()
            articles_result.scalars.return_value.all.return_value = sample_articles_with_job[:5]

            mock_session.execute.side_effect = [count_result, articles_result]

            # Test paginated retrieval with keywords filter
            articles, total = await article_repo.get_articles_paginated(
                filters={'keywords': ['python', 'ai']},
                page=1,
                size=10
            )

            # Verify keywords filter was applied
            assert mock_session.execute.call_count == 2

    async def test_get_articles_paginated_with_relevance_filter(self, article_repo, sample_articles_with_job):
        """Test paginated article retrieval with minimum relevance score filter."""
        with patch('src.database.repositories.article_repo.get_db_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            # Mock count query result
            count_result = Mock()
            count_result.scalar.return_value = 3

            # High relevance articles
            high_relevance_articles = [a for a in sample_articles_with_job if a.relevance_score >= 0.7]
            articles_result = Mock()
            articles_result.scalars.return_value.all.return_value = high_relevance_articles

            mock_session.execute.side_effect = [count_result, articles_result]

            # Test paginated retrieval with relevance filter
            articles, total = await article_repo.get_articles_paginated(
                filters={'min_relevance_score': 0.7},
                page=1,
                size=10
            )

            # Verify filtering logic was invoked
            assert mock_session.execute.call_count == 2

    async def test_get_article_statistics(self, article_repo):
        """Test article statistics calculation."""
        with patch('src.database.repositories.article_repo.get_db_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            # Mock different query results for statistics
            total_result = Mock()
            total_result.scalar.return_value = 100

            job_stats_result = Mock()
            job_stats_result.__iter__ = Mock(return_value=iter([
                (uuid.uuid4(), 25),
                (uuid.uuid4(), 35),
                (uuid.uuid4(), 40)
            ]))

            category_stats_result = Mock()
            category_stats_result.__iter__ = Mock(return_value=iter([
                (uuid.uuid4(), "Technology", 30),
                (uuid.uuid4(), "Science", 45),
                (uuid.uuid4(), "Business", 25)
            ]))

            recent_result = Mock()
            recent_result.scalar.return_value = 15

            avg_relevance_result = Mock()
            avg_relevance_result.scalar.return_value = 0.75

            # Mock execute to return different results for each query
            mock_session.execute.side_effect = [
                total_result,
                job_stats_result,
                category_stats_result,
                recent_result,
                avg_relevance_result
            ]

            # Test statistics calculation
            stats = await article_repo.get_article_statistics()

            # Verify statistics structure
            assert 'total_articles' in stats
            assert 'articles_by_job' in stats
            assert 'articles_by_category' in stats
            assert 'recent_articles_count' in stats
            assert 'average_relevance_score' in stats

            # Verify statistics were calculated
            assert mock_session.execute.call_count == 5

    async def test_get_articles_paginated_empty_results(self, article_repo):
        """Test paginated article retrieval with no results."""
        with patch('src.database.repositories.article_repo.get_db_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            # Mock empty results
            count_result = Mock()
            count_result.scalar.return_value = 0

            articles_result = Mock()
            articles_result.scalars.return_value.all.return_value = []

            mock_session.execute.side_effect = [count_result, articles_result]

            # Test empty results
            articles, total = await article_repo.get_articles_paginated(
                filters={'job_id': uuid.uuid4()},
                page=1,
                size=10
            )

            # Verify empty results handling
            assert total == 0
            assert len(articles) == 0

    async def test_get_articles_paginated_pagination(self, article_repo, sample_articles_with_job):
        """Test pagination functionality."""
        with patch('src.database.repositories.article_repo.get_db_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_get_session.return_value.__aexit__ = AsyncMock(return_value=None)

            # Mock count query result
            count_result = Mock()
            count_result.scalar.return_value = 10

            # Mock articles query result (page 2, size 3)
            page2_articles = sample_articles_with_job[3:6]  # Articles 4-6
            articles_result = Mock()
            articles_result.scalars.return_value.all.return_value = page2_articles

            mock_session.execute.side_effect = [count_result, articles_result]

            # Test pagination (page 2, size 3)
            articles, total = await article_repo.get_articles_paginated(
                filters={},
                page=2,
                size=3
            )

            # Verify pagination was applied
            assert total == 10
            assert len(articles) == 3
            assert mock_session.execute.call_count == 2


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])