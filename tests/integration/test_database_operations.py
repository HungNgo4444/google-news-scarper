import pytest
from datetime import datetime, timezone
from sqlalchemy import select, func
from src.database.models import Article, Category, ArticleCategory
from src.database.connection import DatabaseConnection


class TestDatabaseOperations:
    @pytest.mark.asyncio
    async def test_database_connection_health_check_works(self, test_settings):
        """Test database connection health check works."""
        # Arrange
        db_connection = DatabaseConnection(test_settings)
        db_connection.setup()
        
        # Act
        is_healthy = await db_connection.health_check()
        
        # Assert
        assert is_healthy is True
        
        # Cleanup
        await db_connection.close()
    
    @pytest.mark.asyncio
    async def test_full_article_crud_operations_work(self, test_session, sample_article_data):
        """Test full CRUD operations on articles work correctly."""
        # Create
        article = Article(**sample_article_data)
        test_session.add(article)
        await test_session.commit()
        await test_session.refresh(article)
        
        created_id = article.id
        assert created_id is not None
        
        # Read
        result = await test_session.execute(
            select(Article).where(Article.id == created_id)
        )
        read_article = result.scalar_one()
        assert read_article.title == sample_article_data["title"]
        
        # Update
        new_title = "Updated Article Title"
        read_article.title = new_title
        await test_session.commit()
        
        result = await test_session.execute(
            select(Article).where(Article.id == created_id)
        )
        updated_article = result.scalar_one()
        assert updated_article.title == new_title
        assert updated_article.updated_at > updated_article.created_at
        
        # Delete
        await test_session.delete(updated_article)
        await test_session.commit()
        
        result = await test_session.execute(
            select(Article).where(Article.id == created_id)
        )
        deleted_article = result.scalar_one_or_none()
        assert deleted_article is None
    
    @pytest.mark.asyncio
    async def test_full_category_crud_operations_work(self, test_session, sample_category_data):
        """Test full CRUD operations on categories work correctly."""
        # Create
        category = Category(**sample_category_data)
        test_session.add(category)
        await test_session.commit()
        await test_session.refresh(category)
        
        created_id = category.id
        assert created_id is not None
        
        # Read
        result = await test_session.execute(
            select(Category).where(Category.id == created_id)
        )
        read_category = result.scalar_one()
        assert read_category.name == sample_category_data["name"]
        assert read_category.keywords == sample_category_data["keywords"]
        
        # Update
        new_keywords = ["updated", "keywords"]
        read_category.keywords = new_keywords
        await test_session.commit()
        
        result = await test_session.execute(
            select(Category).where(Category.id == created_id)
        )
        updated_category = result.scalar_one()
        assert updated_category.keywords == new_keywords
        assert updated_category.updated_at > updated_category.created_at
        
        # Delete
        await test_session.delete(updated_category)
        await test_session.commit()
        
        result = await test_session.execute(
            select(Category).where(Category.id == created_id)
        )
        deleted_category = result.scalar_one_or_none()
        assert deleted_category is None
    
    @pytest.mark.asyncio
    async def test_complex_article_category_queries_work(self, test_session):
        """Test complex queries involving articles and categories work."""
        # Arrange - Create test data
        article1 = Article(
            title="Python Programming Guide",
            content="Learn Python programming with this comprehensive guide.",
            source_url="https://example.com/python-guide",
            url_hash=Article.generate_url_hash("https://example.com/python-guide"),
            content_hash=Article.generate_content_hash("Learn Python programming with this comprehensive guide.")
        )
        
        article2 = Article(
            title="JavaScript Essentials",
            content="Master JavaScript fundamentals and advanced concepts.",
            source_url="https://example.com/js-essentials",
            url_hash=Article.generate_url_hash("https://example.com/js-essentials"),
            content_hash=Article.generate_content_hash("Master JavaScript fundamentals and advanced concepts.")
        )
        
        tech_category = Category(
            name="Technology",
            keywords=["programming", "coding", "development"],
            is_active=True
        )
        
        python_category = Category(
            name="Python",
            keywords=["python", "django", "flask"],
            is_active=True
        )
        
        test_session.add_all([article1, article2, tech_category, python_category])
        await test_session.commit()
        await test_session.refresh(article1)
        await test_session.refresh(article2)
        await test_session.refresh(tech_category)
        await test_session.refresh(python_category)
        
        # Create associations
        association1 = ArticleCategory(
            article_id=article1.id,
            category_id=tech_category.id,
            relevance_score=0.9
        )
        association2 = ArticleCategory(
            article_id=article1.id,
            category_id=python_category.id,
            relevance_score=0.95
        )
        association3 = ArticleCategory(
            article_id=article2.id,
            category_id=tech_category.id,
            relevance_score=0.85
        )
        
        test_session.add_all([association1, association2, association3])
        await test_session.commit()
        
        # Test 1: Get articles by category
        result = await test_session.execute(
            select(Article)
            .join(ArticleCategory)
            .join(Category)
            .where(Category.name == "Technology")
        )
        tech_articles = result.scalars().all()
        assert len(tech_articles) == 2
        
        # Test 2: Get categories by article
        result = await test_session.execute(
            select(Category)
            .join(ArticleCategory)
            .join(Article)
            .where(Article.title.like("%Python%"))
        )
        python_article_categories = result.scalars().all()
        assert len(python_article_categories) == 2
        
        # Test 3: Get articles with relevance scores
        result = await test_session.execute(
            select(Article, ArticleCategory.relevance_score)
            .join(ArticleCategory)
            .where(ArticleCategory.relevance_score > 0.9)
        )
        high_relevance_articles = result.all()
        assert len(high_relevance_articles) == 1
        assert high_relevance_articles[0][1] == 0.95  # relevance_score
    
    @pytest.mark.asyncio
    async def test_database_indexes_performance(self, test_session):
        """Test that database indexes are working for performance."""
        # Arrange - Create multiple articles with different dates
        articles = []
        for i in range(10):
            article = Article(
                title=f"Test Article {i}",
                content=f"Content for article {i}",
                source_url=f"https://example.com/article-{i}",
                url_hash=Article.generate_url_hash(f"https://example.com/article-{i}"),
                publish_date=datetime.now(timezone.utc)
            )
            articles.append(article)
        
        test_session.add_all(articles)
        await test_session.commit()
        
        # Test indexed queries
        # Test 1: Query by publish_date (indexed)
        result = await test_session.execute(
            select(Article).where(Article.publish_date.isnot(None)).order_by(Article.publish_date.desc())
        )
        published_articles = result.scalars().all()
        assert len(published_articles) == 10
        
        # Test 2: Query by url_hash (indexed and unique)
        test_hash = articles[0].url_hash
        result = await test_session.execute(
            select(Article).where(Article.url_hash == test_hash)
        )
        found_article = result.scalar_one()
        assert found_article.title == "Test Article 0"
        
        # Test 3: Query by created_at (indexed)
        result = await test_session.execute(
            select(func.count(Article.id)).where(Article.created_at.isnot(None))
        )
        article_count = result.scalar()
        assert article_count == 10
    
    @pytest.mark.asyncio
    async def test_jsonb_operations_work_correctly(self, test_session):
        """Test JSONB operations on category keywords work."""
        # Arrange
        category = Category(
            name="Tech Stack",
            keywords=["python", "postgresql", "redis", "docker"],
            exclude_keywords=["php", "mysql"]
        )
        
        test_session.add(category)
        await test_session.commit()
        await test_session.refresh(category)
        
        # Test 1: Query categories with specific keyword
        result = await test_session.execute(
            select(Category).where(Category.keywords.op('?')('python'))
        )
        categories_with_python = result.scalars().all()
        assert len(categories_with_python) == 1
        assert categories_with_python[0].name == "Tech Stack"
        
        # Test 2: Query categories with keyword array contains
        result = await test_session.execute(
            select(Category).where(Category.keywords.op('@>')('["python", "docker"]'))
        )
        categories_with_both = result.scalars().all()
        assert len(categories_with_both) == 1
        
        # Test 3: Update JSONB array
        category.keywords.append("celery")
        await test_session.commit()
        await test_session.refresh(category)
        assert "celery" in category.keywords
        assert len(category.keywords) == 5