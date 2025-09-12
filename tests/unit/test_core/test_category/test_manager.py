"""Unit tests for CategoryManager business logic.

This module contains comprehensive tests for the CategoryManager class,
covering all business logic scenarios including validation, error handling,
and successful operations.

Test Coverage:
- Category creation with validation
- Category updates with partial data
- Category deletion and error handling
- Name uniqueness validation
- Keywords validation (count, length, duplicates)
- Search functionality
- Query building for OR logic

Testing Patterns:
- Descriptive test names following pattern: test_{action}_{scenario}_{expected_result}
- Arrange-Act-Assert structure with proper setup and assertions
- Mock external dependencies to isolate units under test
- Test both successful operations and error scenarios
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

from src.core.category.manager import CategoryManager
from src.database.repositories.category_repo import CategoryRepository
from src.database.models.category import Category
from src.shared.config import Settings
from src.shared.exceptions import (
    CategoryValidationError,
    CategoryNotFoundError,
    DuplicateCategoryNameError
)


class TestCategoryManager:
    """Test cases for CategoryManager class."""
    
    @pytest.fixture
    def mock_repository(self):
        """Create a mock CategoryRepository."""
        return AsyncMock(spec=CategoryRepository)
    
    @pytest.fixture
    def test_settings(self):
        """Create test settings."""
        settings = MagicMock(spec=Settings)
        settings.MAX_KEYWORDS_PER_CATEGORY = 20
        settings.MAX_KEYWORD_LENGTH = 100
        settings.MAX_CATEGORY_NAME_LENGTH = 255
        return settings
    
    @pytest.fixture
    def category_manager(self, mock_repository, test_settings):
        """Create CategoryManager instance with mocked dependencies."""
        return CategoryManager(mock_repository, test_settings)
    
    @pytest.fixture
    def sample_category(self):
        """Create a sample Category instance for testing."""
        return Category(
            id=uuid4(),
            name="Technology",
            keywords=["python", "javascript"],
            exclude_keywords=["deprecated"],
            is_active=True
        )
    
    @pytest.mark.asyncio
    async def test_create_category_with_valid_data_succeeds(
        self, category_manager, mock_repository, sample_category
    ):
        """Test successful category creation with valid data."""
        # Arrange
        mock_repository.get_by_name.return_value = None  # No existing category
        mock_repository.create_category.return_value = sample_category
        
        # Act
        result = await category_manager.create_category(
            name="Technology",
            keywords=["python", "javascript"],
            exclude_keywords=["deprecated"],
            is_active=True
        )
        
        # Assert
        assert result == sample_category
        mock_repository.get_by_name.assert_called_once_with("Technology")
        mock_repository.create_category.assert_called_once_with(
            name="Technology",
            keywords=["python", "javascript"],
            exclude_keywords=["deprecated"],
            is_active=True
        )
    
    @pytest.mark.asyncio
    async def test_create_category_with_duplicate_name_raises_error(
        self, category_manager, mock_repository, sample_category
    ):
        """Test category creation fails with duplicate name."""
        # Arrange
        mock_repository.get_by_name.return_value = sample_category  # Existing category
        
        # Act & Assert
        with pytest.raises(DuplicateCategoryNameError) as exc_info:
            await category_manager.create_category(
                name="Technology",
                keywords=["python", "javascript"]
            )
        
        assert "already exists" in str(exc_info.value)
        mock_repository.get_by_name.assert_called_once_with("Technology")
        mock_repository.create_category.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_create_category_with_empty_name_raises_validation_error(
        self, category_manager
    ):
        """Test category creation fails with empty name."""
        # Act & Assert
        with pytest.raises(CategoryValidationError) as exc_info:
            await category_manager.create_category(
                name="",
                keywords=["python"]
            )
        
        assert "cannot be empty" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_create_category_with_empty_keywords_raises_validation_error(
        self, category_manager
    ):
        """Test category creation fails with empty keywords list."""
        # Act & Assert
        with pytest.raises(CategoryValidationError) as exc_info:
            await category_manager.create_category(
                name="Technology",
                keywords=[]
            )
        
        assert "cannot be empty" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_create_category_with_too_many_keywords_raises_validation_error(
        self, category_manager
    ):
        """Test category creation fails with too many keywords."""
        # Arrange
        keywords = [f"keyword{i}" for i in range(25)]  # Exceeds max of 20
        
        # Act & Assert
        with pytest.raises(CategoryValidationError) as exc_info:
            await category_manager.create_category(
                name="Technology",
                keywords=keywords
            )
        
        assert "Cannot exceed" in str(exc_info.value)
        assert "keywords per category" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_create_category_with_long_keyword_raises_validation_error(
        self, category_manager
    ):
        """Test category creation fails with keyword exceeding length limit."""
        # Arrange
        long_keyword = "a" * 150  # Exceeds max of 100
        
        # Act & Assert
        with pytest.raises(CategoryValidationError) as exc_info:
            await category_manager.create_category(
                name="Technology",
                keywords=["python", long_keyword]
            )
        
        assert "exceeds maximum length" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_create_category_with_duplicate_keywords_raises_validation_error(
        self, category_manager
    ):
        """Test category creation fails with duplicate keywords."""
        # Act & Assert
        with pytest.raises(CategoryValidationError) as exc_info:
            await category_manager.create_category(
                name="Technology",
                keywords=["python", "python", "javascript"]
            )
        
        assert "Duplicate keywords are not allowed" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_update_category_with_valid_data_succeeds(
        self, category_manager, mock_repository, sample_category
    ):
        """Test successful category update with valid data."""
        # Arrange
        category_id = sample_category.id
        updated_category = Category(
            id=category_id,
            name="Updated Technology",
            keywords=["python", "javascript", "ai"],
            exclude_keywords=["deprecated", "old"],
            is_active=True
        )
        
        mock_repository.get_by_id.return_value = sample_category
        mock_repository.get_by_name.return_value = None  # No name conflict
        mock_repository.update_by_id.return_value = updated_category
        
        # Act
        result = await category_manager.update_category(
            category_id=category_id,
            name="Updated Technology",
            keywords=["python", "javascript", "ai"],
            exclude_keywords=["deprecated", "old"]
        )
        
        # Assert
        assert result == updated_category
        mock_repository.get_by_id.assert_called_once_with(category_id)
        mock_repository.get_by_name.assert_called_once_with("Updated Technology")
        mock_repository.update_by_id.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_category_with_nonexistent_id_raises_error(
        self, category_manager, mock_repository
    ):
        """Test category update fails with non-existent ID."""
        # Arrange
        category_id = uuid4()
        mock_repository.get_by_id.return_value = None
        
        # Act & Assert
        with pytest.raises(CategoryNotFoundError) as exc_info:
            await category_manager.update_category(
                category_id=category_id,
                name="Updated Technology"
            )
        
        assert "not found" in str(exc_info.value)
        mock_repository.get_by_id.assert_called_once_with(category_id)
    
    @pytest.mark.asyncio
    async def test_update_category_with_duplicate_name_raises_error(
        self, category_manager, mock_repository, sample_category
    ):
        """Test category update fails with duplicate name."""
        # Arrange
        category_id = uuid4()
        existing_category = Category(id=category_id, name="Original", keywords=["test"])
        conflicting_category = Category(id=uuid4(), name="Technology", keywords=["test"])
        
        mock_repository.get_by_id.return_value = existing_category
        mock_repository.get_by_name.return_value = conflicting_category
        
        # Act & Assert
        with pytest.raises(DuplicateCategoryNameError) as exc_info:
            await category_manager.update_category(
                category_id=category_id,
                name="Technology"  # Conflicts with existing category
            )
        
        assert "already exists" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_update_category_with_no_changes_returns_existing(
        self, category_manager, mock_repository, sample_category
    ):
        """Test category update with no changes returns existing category."""
        # Arrange
        category_id = sample_category.id
        mock_repository.get_by_id.return_value = sample_category
        
        # Act
        result = await category_manager.update_category(category_id=category_id)
        
        # Assert
        assert result == sample_category
        mock_repository.get_by_id.assert_called_once_with(category_id)
        mock_repository.update_by_id.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_delete_category_with_existing_id_succeeds(
        self, category_manager, mock_repository, sample_category
    ):
        """Test successful category deletion with existing ID."""
        # Arrange
        category_id = sample_category.id
        mock_repository.get_by_id.return_value = sample_category
        mock_repository.delete_by_id.return_value = True
        
        # Act
        result = await category_manager.delete_category(category_id)
        
        # Assert
        assert result is True
        mock_repository.get_by_id.assert_called_once_with(category_id)
        mock_repository.delete_by_id.assert_called_once_with(category_id)
    
    @pytest.mark.asyncio
    async def test_delete_category_with_nonexistent_id_raises_error(
        self, category_manager, mock_repository
    ):
        """Test category deletion fails with non-existent ID."""
        # Arrange
        category_id = uuid4()
        mock_repository.get_by_id.return_value = None
        
        # Act & Assert
        with pytest.raises(CategoryNotFoundError) as exc_info:
            await category_manager.delete_category(category_id)
        
        assert "not found" in str(exc_info.value)
        mock_repository.get_by_id.assert_called_once_with(category_id)
        mock_repository.delete_by_id.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_get_categories_active_only_returns_filtered_results(
        self, category_manager, mock_repository
    ):
        """Test getting categories with active_only filter."""
        # Arrange
        active_categories = [
            Category(id=uuid4(), name="Active1", keywords=["test"], is_active=True),
            Category(id=uuid4(), name="Active2", keywords=["test"], is_active=True)
        ]
        mock_repository.get_active_categories.return_value = active_categories
        
        # Act
        result = await category_manager.get_categories(active_only=True)
        
        # Assert
        assert result == active_categories
        mock_repository.get_active_categories.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_categories_with_stats_returns_statistics(
        self, category_manager, mock_repository
    ):
        """Test getting categories with statistics included."""
        # Arrange
        stats_data = [
            {
                'id': str(uuid4()),
                'name': 'Technology',
                'keywords': ['python'],
                'exclude_keywords': [],
                'is_active': True,
                'created_at': '2023-01-01T00:00:00Z',
                'article_count': 15
            }
        ]
        mock_repository.get_categories_with_article_counts.return_value = stats_data
        
        # Act
        result = await category_manager.get_categories(include_stats=True)
        
        # Assert
        assert result == stats_data
        mock_repository.get_categories_with_article_counts.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_categories_with_valid_term_returns_results(
        self, category_manager, mock_repository, sample_category
    ):
        """Test category search with valid search term."""
        # Arrange
        search_results = [sample_category]
        mock_repository.search_categories_by_name.return_value = search_results
        
        # Act
        result = await category_manager.search_categories("Tech")
        
        # Assert
        assert result == search_results
        mock_repository.search_categories_by_name.assert_called_once_with("Tech")
    
    @pytest.mark.asyncio
    async def test_search_categories_with_empty_term_returns_empty_list(
        self, category_manager, mock_repository
    ):
        """Test category search with empty search term returns empty list."""
        # Act
        result = await category_manager.search_categories("")
        
        # Assert
        assert result == []
        mock_repository.search_categories_by_name.assert_not_called()
    
    def test_build_search_query_with_multiple_keywords_creates_or_query(
        self, category_manager
    ):
        """Test building OR search query from multiple keywords."""
        # Arrange
        keywords = ["python", "javascript", "artificial intelligence"]
        
        # Act
        result = category_manager.build_search_query(keywords)
        
        # Assert
        expected = '"python" OR "javascript" OR "artificial intelligence"'
        assert result == expected
    
    def test_build_search_query_with_empty_keywords_returns_empty_string(
        self, category_manager
    ):
        """Test building search query with empty keywords returns empty string."""
        # Act
        result = category_manager.build_search_query([])
        
        # Assert
        assert result == ""
    
    def test_build_search_query_with_whitespace_keywords_filters_empty_ones(
        self, category_manager
    ):
        """Test building search query filters out empty/whitespace keywords."""
        # Arrange
        keywords = ["python", "", "  ", "javascript", None]
        
        # Act
        result = category_manager.build_search_query(keywords)
        
        # Assert
        expected = '"python" OR "javascript"'
        assert result == expected
    
    def test_validate_name_with_invalid_characters_raises_error(
        self, category_manager
    ):
        """Test name validation fails with invalid characters."""
        # Act & Assert
        with pytest.raises(CategoryValidationError) as exc_info:
            category_manager._validate_name("Category<script>")
        
        assert "invalid characters" in str(exc_info.value)
    
    def test_validate_keywords_with_long_name_raises_error(
        self, category_manager
    ):
        """Test name validation fails with name exceeding length limit."""
        # Arrange
        long_name = "a" * 300  # Exceeds max of 255
        
        # Act & Assert
        with pytest.raises(CategoryValidationError) as exc_info:
            category_manager._validate_name(long_name)
        
        assert "cannot exceed" in str(exc_info.value)
        assert "characters" in str(exc_info.value)
    
    def test_validate_exclude_keywords_with_duplicates_raises_error(
        self, category_manager
    ):
        """Test exclude keywords validation fails with duplicates."""
        # Act & Assert
        with pytest.raises(CategoryValidationError) as exc_info:
            category_manager._validate_exclude_keywords(["deprecated", "deprecated", "old"])
        
        assert "Duplicate exclude keywords are not allowed" in str(exc_info.value)