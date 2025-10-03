"""Unit tests for Category model crawl_period field validation.

Tests cover AC1 of Story 2.3: Scheduled Crawl Period Limit
"""
import pytest
from sqlalchemy.exc import IntegrityError
from src.database.models import Category


class TestCategoryCrawlPeriodValidation:
    """Test suite for crawl_period field validation."""

    @pytest.mark.asyncio
    async def test_create_category_with_valid_hour_period_succeeds(self, test_session):
        """Test creating category with valid hour period (e.g., '2h') succeeds."""
        # Arrange
        category = Category(
            name="Test Category Hours",
            keywords=["test"],
            crawl_period="2h"
        )

        # Act
        test_session.add(category)
        await test_session.commit()
        await test_session.refresh(category)

        # Assert
        assert category.id is not None
        assert category.crawl_period == "2h"
        assert category.crawl_period_display == "2 hours"

    @pytest.mark.asyncio
    async def test_create_category_with_valid_day_period_succeeds(self, test_session):
        """Test creating category with valid day period (e.g., '7d') succeeds."""
        # Arrange
        category = Category(
            name="Test Category Days",
            keywords=["test"],
            crawl_period="7d"
        )

        # Act
        test_session.add(category)
        await test_session.commit()
        await test_session.refresh(category)

        # Assert
        assert category.id is not None
        assert category.crawl_period == "7d"
        assert category.crawl_period_display == "7 days"

    @pytest.mark.asyncio
    async def test_create_category_with_valid_month_period_succeeds(self, test_session):
        """Test creating category with valid month period (e.g., '1m') succeeds."""
        # Arrange
        category = Category(
            name="Test Category Months",
            keywords=["test"],
            crawl_period="1m"
        )

        # Act
        test_session.add(category)
        await test_session.commit()
        await test_session.refresh(category)

        # Assert
        assert category.id is not None
        assert category.crawl_period == "1m"
        assert category.crawl_period_display == "1 month"

    @pytest.mark.asyncio
    async def test_create_category_with_valid_week_period_succeeds(self, test_session):
        """Test creating category with valid week period (e.g., '2w') succeeds."""
        # Arrange
        category = Category(
            name="Test Category Weeks",
            keywords=["test"],
            crawl_period="2w"
        )

        # Act
        test_session.add(category)
        await test_session.commit()
        await test_session.refresh(category)

        # Assert
        assert category.id is not None
        assert category.crawl_period == "2w"
        assert category.crawl_period_display == "2 weeks"

    @pytest.mark.asyncio
    async def test_create_category_with_valid_year_period_succeeds(self, test_session):
        """Test creating category with valid year period (e.g., '1y') succeeds."""
        # Arrange
        category = Category(
            name="Test Category Years",
            keywords=["test"],
            crawl_period="1y"
        )

        # Act
        test_session.add(category)
        await test_session.commit()
        await test_session.refresh(category)

        # Assert
        assert category.id is not None
        assert category.crawl_period == "1y"
        assert category.crawl_period_display == "1 year"

    @pytest.mark.asyncio
    async def test_create_category_with_null_crawl_period_succeeds(self, test_session):
        """Test creating category with NULL crawl_period is allowed."""
        # Arrange
        category = Category(
            name="Test Category No Period",
            keywords=["test"],
            crawl_period=None
        )

        # Act
        test_session.add(category)
        await test_session.commit()
        await test_session.refresh(category)

        # Assert
        assert category.id is not None
        assert category.crawl_period is None
        assert category.crawl_period_display == "No limit"

    @pytest.mark.asyncio
    async def test_create_category_with_invalid_format_x_fails(self, test_session):
        """Test creating category with invalid format '2x' fails validation."""
        # Arrange
        category = Category(
            name="Test Category Invalid X",
            keywords=["test"],
            crawl_period="2x"
        )

        # Act & Assert
        test_session.add(category)
        with pytest.raises(IntegrityError) as exc_info:
            await test_session.commit()

        # Verify constraint violation
        assert "crawl_period_format_valid" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_category_with_invalid_format_abc_fails(self, test_session):
        """Test creating category with invalid format 'abc' fails validation."""
        # Arrange
        category = Category(
            name="Test Category Invalid ABC",
            keywords=["test"],
            crawl_period="abc"
        )

        # Act & Assert
        test_session.add(category)
        with pytest.raises(IntegrityError) as exc_info:
            await test_session.commit()

        # Verify constraint violation
        assert "crawl_period_format_valid" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_category_with_invalid_format_number_only_fails(self, test_session):
        """Test creating category with invalid format '7' (no unit) fails validation."""
        # Arrange
        category = Category(
            name="Test Category Number Only",
            keywords=["test"],
            crawl_period="7"
        )

        # Act & Assert
        test_session.add(category)
        with pytest.raises(IntegrityError) as exc_info:
            await test_session.commit()

        # Verify constraint violation
        assert "crawl_period_format_valid" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_category_with_invalid_format_unit_first_fails(self, test_session):
        """Test creating category with invalid format 'd7' (unit before number) fails validation."""
        # Arrange
        category = Category(
            name="Test Category Unit First",
            keywords=["test"],
            crawl_period="d7"
        )

        # Act & Assert
        test_session.add(category)
        with pytest.raises(IntegrityError) as exc_info:
            await test_session.commit()

        # Verify constraint violation
        assert "crawl_period_format_valid" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_crawl_period_display_with_plural_works(self, test_session):
        """Test crawl_period_display property handles pluralization correctly."""
        # Arrange - Multiple units
        category_plural = Category(
            name="Test Category Plural",
            keywords=["test"],
            crawl_period="5d"
        )

        test_session.add(category_plural)
        await test_session.commit()
        await test_session.refresh(category_plural)

        # Assert - Plural form
        assert category_plural.crawl_period_display == "5 days"

        # Arrange - Single unit
        category_singular = Category(
            name="Test Category Singular",
            keywords=["test"],
            crawl_period="1d"
        )

        test_session.add(category_singular)
        await test_session.commit()
        await test_session.refresh(category_singular)

        # Assert - Singular form
        assert category_singular.crawl_period_display == "1 day"

    @pytest.mark.asyncio
    async def test_crawl_period_display_with_invalid_format_returns_original(self):
        """Test crawl_period_display returns original value if format invalid (edge case)."""
        # Arrange - Create category without committing to database (to bypass CHECK constraint)
        from src.database.models.category import Category as CategoryClass
        category = CategoryClass(
            name="Test Category Edge Case",
            keywords=["test"]
        )

        # Manually set invalid period (bypasses validation for property test)
        category.crawl_period = "invalid"

        # Act & Assert
        assert category.crawl_period_display == "invalid"
