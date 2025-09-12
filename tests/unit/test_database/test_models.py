import pytest
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from src.database.models import Article, Category, ArticleCategory


class TestArticleModel:
    @pytest.mark.asyncio
    async def test_create_article_with_valid_data_succeeds(self, test_session, sample_article_data):
        """Test creating article with valid data succeeds."""
        # Arrange
        article = Article(**sample_article_data)
        
        # Act
        test_session.add(article)
        await test_session.commit()
        await test_session.refresh(article)
        
        # Assert
        assert article.id is not None
        assert article.title == sample_article_data["title"]
        assert article.content == sample_article_data["content"]
        assert article.author == sample_article_data["author"]
        assert article.source_url == sample_article_data["source_url"]
        assert article.url_hash == sample_article_data["url_hash"]
        assert article.created_at is not None
        assert article.updated_at is not None
        assert article.last_seen is not None
    
    @pytest.mark.asyncio
    async def test_create_article_with_empty_title_fails(self, test_session, sample_article_data):
        """Test creating article with empty title fails."""
        # Arrange
        sample_article_data["title"] = ""
        article = Article(**sample_article_data)
        
        # Act & Assert
        test_session.add(article)
        with pytest.raises(IntegrityError):
            await test_session.commit()
    
    @pytest.mark.asyncio
    async def test_create_article_with_duplicate_url_hash_fails(self, test_session, sample_article_data):
        """Test creating article with duplicate url_hash fails."""
        # Arrange
        article1 = Article(**sample_article_data)
        article2 = Article(**sample_article_data)
        
        # Act
        test_session.add(article1)
        await test_session.commit()
        
        test_session.add(article2)
        
        # Assert
        with pytest.raises(IntegrityError):
            await test_session.commit()
    
    @pytest.mark.asyncio
    async def test_article_url_hash_generation_works_correctly(self):
        """Test URL hash generation works correctly."""
        # Arrange
        url = "https://example.com/test-article"
        
        # Act
        hash_result = Article.generate_url_hash(url)
        
        # Assert
        assert len(hash_result) == 64
        assert hash_result == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    
    @pytest.mark.asyncio
    async def test_article_content_hash_generation_works_correctly(self):
        """Test content hash generation works correctly."""
        # Arrange
        content = "Test content"
        
        # Act
        hash_result = Article.generate_content_hash(content)
        
        # Assert
        assert len(hash_result) == 64
        assert isinstance(hash_result, str)
    
    @pytest.mark.asyncio
    async def test_article_representation_string_works(self, sample_article_data):
        """Test article string representation works."""
        # Arrange & Act
        article = Article(**sample_article_data)
        result = str(article)
        
        # Assert
        assert "Article" in result
        assert "Test Article Title" in result
        assert sample_article_data["url_hash"][:8] in result


class TestCategoryModel:
    @pytest.mark.asyncio
    async def test_create_category_with_valid_data_succeeds(self, test_session, sample_category_data):
        """Test creating category with valid data succeeds."""
        # Arrange
        category = Category(**sample_category_data)
        
        # Act
        test_session.add(category)
        await test_session.commit()
        await test_session.refresh(category)
        
        # Assert
        assert category.id is not None
        assert category.name == sample_category_data["name"]
        assert category.keywords == sample_category_data["keywords"]
        assert category.exclude_keywords == sample_category_data["exclude_keywords"]
        assert category.is_active == sample_category_data["is_active"]
        assert category.created_at is not None
        assert category.updated_at is not None
    
    @pytest.mark.asyncio
    async def test_create_category_with_empty_keywords_fails(self, test_session, sample_category_data):
        """Test creating category with empty keywords fails."""
        # Arrange
        sample_category_data["keywords"] = []
        category = Category(**sample_category_data)
        
        # Act & Assert
        test_session.add(category)
        with pytest.raises(IntegrityError):
            await test_session.commit()
    
    @pytest.mark.asyncio
    async def test_create_category_with_empty_name_fails(self, test_session, sample_category_data):
        """Test creating category with empty name fails."""
        # Arrange
        sample_category_data["name"] = ""
        category = Category(**sample_category_data)
        
        # Act & Assert
        test_session.add(category)
        with pytest.raises(IntegrityError):
            await test_session.commit()
    
    @pytest.mark.asyncio
    async def test_create_category_with_duplicate_name_fails(self, test_session, sample_category_data):
        """Test creating category with duplicate name fails."""
        # Arrange
        category1 = Category(**sample_category_data)
        category2 = Category(**sample_category_data)
        
        # Act
        test_session.add(category1)
        await test_session.commit()
        
        test_session.add(category2)
        
        # Assert
        with pytest.raises(IntegrityError):
            await test_session.commit()
    
    @pytest.mark.asyncio
    async def test_category_defaults_work_correctly(self, test_session):
        """Test category default values work correctly."""
        # Arrange
        category = Category(
            name="Test Category",
            keywords=["test"]
        )
        
        # Act
        test_session.add(category)
        await test_session.commit()
        await test_session.refresh(category)
        
        # Assert
        assert category.is_active is True
        assert category.exclude_keywords == []
    
    @pytest.mark.asyncio
    async def test_category_representation_string_works(self, sample_category_data):
        """Test category string representation works."""
        # Arrange & Act
        category = Category(**sample_category_data)
        result = str(category)
        
        # Assert
        assert "Category" in result
        assert "Technology" in result
        assert "active=True" in result
        assert "keywords_count=3" in result


class TestArticleCategoryModel:
    @pytest.mark.asyncio
    async def test_create_article_category_association_succeeds(self, test_session, sample_article_data, sample_category_data):
        """Test creating article-category association succeeds."""
        # Arrange
        article = Article(**sample_article_data)
        category = Category(**sample_category_data)
        
        test_session.add(article)
        test_session.add(category)
        await test_session.commit()
        await test_session.refresh(article)
        await test_session.refresh(category)
        
        association = ArticleCategory(
            article_id=article.id,
            category_id=category.id,
            relevance_score=Decimal("0.85")
        )
        
        # Act
        test_session.add(association)
        await test_session.commit()
        await test_session.refresh(association)
        
        # Assert
        assert association.id is not None
        assert association.article_id == article.id
        assert association.category_id == category.id
        assert association.relevance_score == Decimal("0.85")
        assert association.created_at is not None
    
    @pytest.mark.asyncio
    async def test_create_duplicate_article_category_association_fails(self, test_session, sample_article_data, sample_category_data):
        """Test creating duplicate article-category association fails."""
        # Arrange
        article = Article(**sample_article_data)
        category = Category(**sample_category_data)
        
        test_session.add(article)
        test_session.add(category)
        await test_session.commit()
        await test_session.refresh(article)
        await test_session.refresh(category)
        
        association1 = ArticleCategory(
            article_id=article.id,
            category_id=category.id
        )
        association2 = ArticleCategory(
            article_id=article.id,
            category_id=category.id
        )
        
        # Act
        test_session.add(association1)
        await test_session.commit()
        
        test_session.add(association2)
        
        # Assert
        with pytest.raises(IntegrityError):
            await test_session.commit()
    
    @pytest.mark.asyncio
    async def test_relevance_score_validation_works(self, test_session, sample_article_data, sample_category_data):
        """Test relevance score validation works."""
        # Arrange
        article = Article(**sample_article_data)
        category = Category(**sample_category_data)
        
        test_session.add(article)
        test_session.add(category)
        await test_session.commit()
        await test_session.refresh(article)
        await test_session.refresh(category)
        
        # Test invalid relevance score > 1.0
        association_invalid = ArticleCategory(
            article_id=article.id,
            category_id=category.id,
            relevance_score=Decimal("1.5")
        )
        
        # Act & Assert
        test_session.add(association_invalid)
        with pytest.raises(IntegrityError):
            await test_session.commit()
    
    @pytest.mark.asyncio
    async def test_cascade_delete_works_correctly(self, test_session, sample_article_data, sample_category_data):
        """Test cascade deletion works correctly."""
        # Arrange
        article = Article(**sample_article_data)
        category = Category(**sample_category_data)
        
        test_session.add(article)
        test_session.add(category)
        await test_session.commit()
        await test_session.refresh(article)
        await test_session.refresh(category)
        
        association = ArticleCategory(
            article_id=article.id,
            category_id=category.id
        )
        test_session.add(association)
        await test_session.commit()
        
        # Act - Delete article
        await test_session.delete(article)
        await test_session.commit()
        
        # Assert - Association should be deleted too
        result = await test_session.execute(
            select(ArticleCategory).where(ArticleCategory.article_id == article.id)
        )
        associations = result.scalars().all()
        assert len(associations) == 0
    
    @pytest.mark.asyncio
    async def test_article_category_relationships_work(self, test_session, sample_article_data, sample_category_data):
        """Test article-category relationships work correctly."""
        # Arrange
        article = Article(**sample_article_data)
        category = Category(**sample_category_data)
        
        test_session.add(article)
        test_session.add(category)
        await test_session.commit()
        await test_session.refresh(article)
        await test_session.refresh(category)
        
        association = ArticleCategory(
            article_id=article.id,
            category_id=category.id
        )
        test_session.add(association)
        await test_session.commit()
        
        # Act - Refresh to load relationships
        await test_session.refresh(article, ["categories"])
        await test_session.refresh(category, ["articles"])
        
        # Assert
        assert len(article.categories) == 1
        assert len(category.articles) == 1
        assert article.categories[0].category_id == category.id
        assert category.articles[0].article_id == article.id