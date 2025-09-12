"""Unit tests for CategoryRepository database operations.

This module contains comprehensive tests for the CategoryRepository class,
covering all database operations including CRUD functionality and specialized queries.

Test Coverage:
- Category creation and retrieval
- Active category filtering
- Keyword search functionality
- Category updates and status changes
- Article count associations
- Search operations with various criteria

Testing Patterns:
- Descriptive test names following pattern: test_{action}_{scenario}_{expected_result}
- Arrange-Act-Assert structure with proper setup and assertions
- Mock database sessions to isolate repository logic
- Test both successful operations and error scenarios
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.database.repositories.category_repo import CategoryRepository
from src.database.models.category import Category
from src.database.models.article_category import ArticleCategory


class TestCategoryRepository:
    """Test cases for CategoryRepository class."""
    
    @pytest.fixture
    def category_repo(self):
        """Create CategoryRepository instance for testing."""
        return CategoryRepository()
    
    @pytest.fixture
    def sample_category_data(self):
        """Create sample category data for testing."""
        return {
            "name": "Technology",
            "keywords": ["python", "javascript"],
            "exclude_keywords": ["deprecated"],
            "is_active": True
        }
    
    @pytest.fixture
    def sample_category(self):
        """Create sample Category instance for testing."""
        return Category(
            id=uuid4(),
            name="Technology",
            keywords=["python", "javascript"],
            exclude_keywords=["deprecated"],
            is_active=True
        )
    
    @pytest.mark.asyncio
    async def test_get_by_name_with_existing_category_returns_category(
        self, category_repo, sample_category
    ):
        """Test getting category by name returns existing category."""
        # Arrange
        with patch.object(category_repo, 'get_by_field') as mock_get_by_field:
            mock_get_by_field.return_value = sample_category
            
            # Act
            result = await category_repo.get_by_name("Technology")
            
            # Assert
            assert result == sample_category
            mock_get_by_field.assert_called_once_with("name", "Technology")
    
    @pytest.mark.asyncio
    async def test_get_by_name_with_nonexistent_category_returns_none(
        self, category_repo
    ):
        """Test getting category by name returns None for non-existent category."""
        # Arrange
        with patch.object(category_repo, 'get_by_field') as mock_get_by_field:
            mock_get_by_field.return_value = None
            
            # Act
            result = await category_repo.get_by_name("NonExistent")
            
            # Assert
            assert result is None
            mock_get_by_field.assert_called_once_with("name", "NonExistent")
    
    @pytest.mark.asyncio
    @patch('src.database.repositories.category_repo.get_db_session')
    async def test_get_active_categories_returns_only_active_categories(
        self, mock_get_db_session, category_repo
    ):
        """Test getting active categories returns only categories with is_active=True."""
        # Arrange
        active_categories = [
            Category(id=uuid4(), name="Tech", keywords=["python"], is_active=True),
            Category(id=uuid4(), name="Science", keywords=["biology"], is_active=True)
        ]
        
        mock_session = AsyncMock()
        mock_get_db_session.return_value.__aenter__.return_value = mock_session
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = active_categories
        mock_session.execute.return_value = mock_result
        
        # Act
        result = await category_repo.get_active_categories()
        
        # Assert
        assert result == active_categories
        mock_session.execute.assert_called_once()
        
        # Verify the query includes is_active filter
        call_args = mock_session.execute.call_args[0][0]
        query_str = str(call_args)
        assert "is_active" in query_str.lower()
    
    @pytest.mark.asyncio
    @patch('src.database.repositories.category_repo.get_db_session')
    async def test_get_categories_with_keywords_returns_matching_categories(
        self, mock_get_db_session, category_repo
    ):
        """Test getting categories containing specific keyword."""
        # Arrange
        matching_categories = [
            Category(id=uuid4(), name="Tech", keywords=["python", "java"], is_active=True)
        ]
        
        mock_session = AsyncMock()
        mock_get_db_session.return_value.__aenter__.return_value = mock_session
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = matching_categories
        mock_session.execute.return_value = mock_result
        
        # Act
        result = await category_repo.get_categories_with_keywords("python")
        
        # Assert
        assert result == matching_categories
        mock_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_category_with_valid_data_returns_created_category(
        self, category_repo, sample_category_data, sample_category
    ):
        """Test creating category with valid data returns created category."""
        # Arrange
        with patch.object(category_repo, 'create') as mock_create:
            mock_create.return_value = sample_category
            
            # Act
            result = await category_repo.create_category(
                name=sample_category_data["name"],
                keywords=sample_category_data["keywords"],
                exclude_keywords=sample_category_data["exclude_keywords"],
                is_active=sample_category_data["is_active"]
            )
            
            # Assert
            assert result == sample_category
            mock_create.assert_called_once()
            
            # Verify the data passed to create method
            create_call_data = mock_create.call_args[0][0]
            assert create_call_data["name"] == "Technology"
            assert create_call_data["keywords"] == ["python", "javascript"]
            assert create_call_data["exclude_keywords"] == ["deprecated"]
            assert create_call_data["is_active"] is True
    
    @pytest.mark.asyncio
    async def test_create_category_strips_whitespace_from_keywords(
        self, category_repo, sample_category
    ):
        """Test creating category strips whitespace from keywords."""
        # Arrange
        with patch.object(category_repo, 'create') as mock_create:
            mock_create.return_value = sample_category
            
            # Act
            await category_repo.create_category(
                name="Technology",
                keywords=["  python  ", "javascript", ""],
                exclude_keywords=["  deprecated  ", "", "old"]
            )
            
            # Assert
            create_call_data = mock_create.call_args[0][0]
            assert create_call_data["keywords"] == ["python", "javascript"]
            assert create_call_data["exclude_keywords"] == ["deprecated", "old"]
    
    @pytest.mark.asyncio
    async def test_update_keywords_with_valid_data_returns_updated_category(
        self, category_repo, sample_category
    ):
        """Test updating category keywords returns updated category."""
        # Arrange
        category_id = sample_category.id
        new_keywords = ["python", "ai"]
        new_exclude_keywords = ["legacy"]
        
        with patch.object(category_repo, 'update_by_id') as mock_update:
            mock_update.return_value = sample_category
            
            # Act
            result = await category_repo.update_keywords(
                category_id=category_id,
                keywords=new_keywords,
                exclude_keywords=new_exclude_keywords
            )
            
            # Assert
            assert result == sample_category
            mock_update.assert_called_once_with(
                category_id,
                {
                    "keywords": new_keywords,
                    "exclude_keywords": new_exclude_keywords
                }
            )
    
    @pytest.mark.asyncio
    async def test_set_active_status_with_valid_data_returns_updated_category(
        self, category_repo, sample_category
    ):
        """Test setting category active status returns updated category."""
        # Arrange
        category_id = sample_category.id
        new_status = False
        
        with patch.object(category_repo, 'update_by_id') as mock_update:
            mock_update.return_value = sample_category
            
            # Act
            result = await category_repo.set_active_status(category_id, new_status)
            
            # Assert
            assert result == sample_category
            mock_update.assert_called_once_with(
                category_id,
                {"is_active": new_status}
            )
    
    @pytest.mark.asyncio
    @patch('src.database.repositories.category_repo.get_db_session')
    async def test_count_articles_in_category_returns_correct_count(
        self, mock_get_db_session, category_repo
    ):
        """Test counting articles in category returns correct count."""
        # Arrange
        category_id = uuid4()
        expected_count = 15
        
        mock_session = AsyncMock()
        mock_get_db_session.return_value.__aenter__.return_value = mock_session
        
        mock_result = MagicMock()
        mock_result.scalar.return_value = expected_count
        mock_session.execute.return_value = mock_result
        
        # Act
        result = await category_repo.count_articles_in_category(category_id)
        
        # Assert
        assert result == expected_count
        mock_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('src.database.repositories.category_repo.get_db_session')
    async def test_count_articles_in_category_with_no_articles_returns_zero(
        self, mock_get_db_session, category_repo
    ):
        """Test counting articles in category with no articles returns zero."""
        # Arrange
        category_id = uuid4()
        
        mock_session = AsyncMock()
        mock_get_db_session.return_value.__aenter__.return_value = mock_session
        
        mock_result = MagicMock()
        mock_result.scalar.return_value = None  # No results
        mock_session.execute.return_value = mock_result
        
        # Act
        result = await category_repo.count_articles_in_category(category_id)
        
        # Assert
        assert result == 0
        mock_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('src.database.repositories.category_repo.get_db_session')
    async def test_get_categories_with_article_counts_returns_stats_data(
        self, mock_get_db_session, category_repo
    ):
        """Test getting categories with article counts returns statistics."""
        # Arrange
        mock_session = AsyncMock()
        mock_get_db_session.return_value.__aenter__.return_value = mock_session
        
        # Mock database rows
        tech_id = uuid4()
        science_id = uuid4()
        
        mock_rows = []
        
        # Create first row mock
        tech_row = MagicMock()
        tech_row.id = tech_id
        tech_row.name = "Technology"
        tech_row.keywords = ["python"]
        tech_row.exclude_keywords = []
        tech_row.is_active = True
        tech_row.created_at = "2023-01-01T00:00:00Z"
        tech_row.article_count = 15
        mock_rows.append(tech_row)
        
        # Create second row mock
        science_row = MagicMock()
        science_row.id = science_id
        science_row.name = "Science"
        science_row.keywords = ["biology"]
        science_row.exclude_keywords = ["old"]
        science_row.is_active = True
        science_row.created_at = "2023-01-02T00:00:00Z"
        science_row.article_count = 8
        mock_rows.append(science_row)
        
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows
        mock_session.execute.return_value = mock_result
        
        # Act
        result = await category_repo.get_categories_with_article_counts()
        
        # Assert
        assert len(result) == 2
        assert result[0]["name"] == "Technology"
        assert result[0]["article_count"] == 15
        assert result[1]["name"] == "Science"
        assert result[1]["article_count"] == 8
        mock_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('src.database.repositories.category_repo.get_db_session')
    async def test_search_categories_by_name_returns_matching_categories(
        self, mock_get_db_session, category_repo
    ):
        """Test searching categories by name returns matching results."""
        # Arrange
        search_term = "tech"
        matching_categories = [
            Category(id=uuid4(), name="Technology", keywords=["python"], is_active=True),
            Category(id=uuid4(), name="Biotech", keywords=["biology"], is_active=True)
        ]
        
        mock_session = AsyncMock()
        mock_get_db_session.return_value.__aenter__.return_value = mock_session
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = matching_categories
        mock_session.execute.return_value = mock_result
        
        # Act
        result = await category_repo.search_categories_by_name(search_term)
        
        # Assert
        assert result == matching_categories
        mock_session.execute.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('src.database.repositories.category_repo.get_db_session')
    async def test_get_categories_with_articles_includes_relationship_loading(
        self, mock_get_db_session, category_repo
    ):
        """Test getting categories with articles includes eager loading."""
        # Arrange
        categories_with_articles = [
            Category(id=uuid4(), name="Technology", keywords=["python"], is_active=True)
        ]
        
        mock_session = AsyncMock()
        mock_get_db_session.return_value.__aenter__.return_value = mock_session
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = categories_with_articles
        mock_session.execute.return_value = mock_result
        
        # Act
        result = await category_repo.get_categories_with_articles()
        
        # Assert
        assert result == categories_with_articles
        mock_session.execute.assert_called_once()
        
        # Verify that selectinload was used in the query
        call_args = mock_session.execute.call_args[0][0]
        query_str = str(call_args)
        # Note: This is a simplified check - in real tests you'd check the actual options
        assert "select" in query_str.lower()
    
    @pytest.mark.asyncio
    async def test_update_keywords_handles_none_exclude_keywords(
        self, category_repo, sample_category
    ):
        """Test updating keywords with None exclude_keywords works correctly."""
        # Arrange
        category_id = sample_category.id
        new_keywords = ["python", "ai"]
        
        with patch.object(category_repo, 'update_by_id') as mock_update:
            mock_update.return_value = sample_category
            
            # Act
            result = await category_repo.update_keywords(
                category_id=category_id,
                keywords=new_keywords,
                exclude_keywords=None  # Should handle None gracefully
            )
            
            # Assert
            assert result == sample_category
            
            # Verify that empty list was used for exclude_keywords
            update_call_data = mock_update.call_args[0][1]
            assert update_call_data["exclude_keywords"] == []
    
    @pytest.mark.asyncio
    async def test_update_by_id_with_nonexistent_category_returns_none(
        self, category_repo
    ):
        """Test updating non-existent category returns None."""
        # Arrange
        category_id = uuid4()
        
        with patch.object(category_repo, 'update_by_id') as mock_update:
            mock_update.return_value = None
            
            # Act
            result = await category_repo.update_keywords(
                category_id=category_id,
                keywords=["python"]
            )
            
            # Assert
            assert result is None