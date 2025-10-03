"""Unit tests for GNews period parameter handling in sync_engine.

Tests cover AC1 of Story 2.3: Scheduled Crawl Period implementation
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from src.core.crawler.sync_engine import GoogleNewsSyncEngine


class TestGNewsPeriodParameterHandling:
    """Test suite for GNews period parameter usage."""

    @pytest.fixture
    def sync_engine(self):
        """Create GoogleNewsSyncEngine instance for testing."""
        return GoogleNewsSyncEngine()

    @patch('gnews.GNews')
    def test_search_with_period_passes_period_to_gnews_constructor(self, mock_gnews_class, sync_engine):
        """Test that period parameter is passed to GNews constructor for scheduled jobs."""
        # Arrange
        mock_instance = Mock()
        mock_instance.get_news.return_value = [
            {'url': 'https://news.google.com/article1', 'title': 'Test Article 1'}
        ]
        mock_gnews_class.return_value = mock_instance

        # Act
        sync_engine.search_google_news(
            keywords=['test'],
            exclude_keywords=[],
            max_results=10,
            language='vi',
            country='VN',
            period='2h'  # Period for scheduled job
        )

        # Assert - Verify GNews constructor called with period parameter
        mock_gnews_class.assert_called_once_with(
            language='vi',
            country='VN',
            max_results=10,
            period='2h'
        )

        # Verify start_date/end_date were NOT set (mutually exclusive with period)
        assert not hasattr(mock_instance, 'start_date') or mock_instance.start_date is None
        assert not hasattr(mock_instance, 'end_date') or mock_instance.end_date is None

    @patch('gnews.GNews')
    def test_search_without_period_does_not_pass_period_to_constructor(self, mock_gnews_class, sync_engine):
        """Test that period is NOT passed when dates are provided (on-demand job)."""
        # Arrange
        mock_instance = Mock()
        mock_instance.get_news.return_value = [
            {'url': 'https://news.google.com/article1', 'title': 'Test Article 1'}
        ]
        mock_gnews_class.return_value = mock_instance

        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 5)

        # Act
        sync_engine.search_google_news(
            keywords=['test'],
            exclude_keywords=[],
            max_results=10,
            language='vi',
            country='VN',
            start_date=start_date,
            end_date=end_date,
            period=None  # No period for on-demand job
        )

        # Assert - Verify GNews constructor called WITHOUT period
        call_args = mock_gnews_class.call_args
        assert 'period' not in call_args.kwargs or call_args.kwargs.get('period') is None

        # Verify dates were set via properties
        assert mock_instance.start_date == start_date
        assert mock_instance.end_date == end_date

    @patch('gnews.GNews')
    def test_search_with_both_period_and_dates_logs_warning(self, mock_gnews_class, sync_engine, caplog):
        """Test that providing both period and dates logs a warning (period takes precedence)."""
        # Arrange
        mock_instance = Mock()
        mock_instance.get_news.return_value = [
            {'url': 'https://news.google.com/article1', 'title': 'Test Article 1'}
        ]
        mock_gnews_class.return_value = mock_instance

        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 5)

        # Act
        with caplog.at_level("WARNING"):
            sync_engine.search_google_news(
                keywords=['test'],
                exclude_keywords=[],
                max_results=10,
                language='vi',
                country='VN',
                start_date=start_date,
                end_date=end_date,
                period='7d'  # Both period and dates provided
            )

        # Assert - Verify warning was logged
        assert "Both period (7d) and dates provided" in caplog.text
        assert "Period will be used for scheduled crawls" in caplog.text

        # Verify period was passed to constructor (takes precedence)
        call_args = mock_gnews_class.call_args
        assert call_args.kwargs.get('period') == '7d'

    @patch('gnews.GNews')
    def test_search_with_various_period_formats_works(self, mock_gnews_class, sync_engine):
        """Test that various period formats (h/d/m/w/y) are passed correctly."""
        # Arrange
        mock_instance = Mock()
        mock_instance.get_news.return_value = [
            {'url': 'https://news.google.com/article1', 'title': 'Test Article 1'}
        ]
        mock_gnews_class.return_value = mock_instance

        period_formats = ['1h', '7d', '1m', '2w', '1y']

        for period in period_formats:
            # Reset mock
            mock_gnews_class.reset_mock()

            # Act
            sync_engine.search_google_news(
                keywords=['test'],
                exclude_keywords=[],
                max_results=10,
                language='vi',
                country='VN',
                period=period
            )

            # Assert - Verify each period format passed correctly
            call_args = mock_gnews_class.call_args
            assert call_args.kwargs.get('period') == period, f"Period {period} not passed correctly"

    @patch('gnews.GNews')
    def test_search_with_period_logs_info_message(self, mock_gnews_class, sync_engine, caplog):
        """Test that using period logs an informational message."""
        # Arrange
        mock_instance = Mock()
        mock_instance.get_news.return_value = [
            {'url': 'https://news.google.com/article1', 'title': 'Test Article 1'}
        ]
        mock_gnews_class.return_value = mock_instance

        # Act
        with caplog.at_level("INFO"):
            sync_engine.search_google_news(
                keywords=['test'],
                exclude_keywords=[],
                max_results=10,
                language='vi',
                country='VN',
                period='2h'
            )

        # Assert - Verify info log message
        assert "Using period '2h' for scheduled crawl" in caplog.text

    @patch('gnews.GNews')
    def test_search_without_period_or_dates_works(self, mock_gnews_class, sync_engine):
        """Test that search works without period or dates (all-time search)."""
        # Arrange
        mock_instance = Mock()
        mock_instance.get_news.return_value = [
            {'url': 'https://news.google.com/article1', 'title': 'Test Article 1'}
        ]
        mock_gnews_class.return_value = mock_instance

        # Act
        sync_engine.search_google_news(
            keywords=['test'],
            exclude_keywords=[],
            max_results=10,
            language='vi',
            country='VN'
            # No period, no dates
        )

        # Assert - Verify GNews constructor called without period or dates
        call_args = mock_gnews_class.call_args
        assert 'period' not in call_args.kwargs or call_args.kwargs.get('period') is None
        assert not hasattr(mock_instance, 'start_date') or mock_instance.start_date is None
        assert not hasattr(mock_instance, 'end_date') or mock_instance.end_date is None

    @patch('gnews.GNews')
    def test_period_parameter_mutually_exclusive_with_dates(self, mock_gnews_class, sync_engine):
        """Test that period and dates are mutually exclusive (period takes precedence when both provided)."""
        # Arrange
        mock_instance = Mock()
        mock_instance.get_news.return_value = [
            {'url': 'https://news.google.com/article1', 'title': 'Test Article 1'}
        ]
        mock_gnews_class.return_value = mock_instance

        # Act - Provide both period and dates
        sync_engine.search_google_news(
            keywords=['test'],
            exclude_keywords=[],
            max_results=10,
            language='vi',
            country='VN',
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 5),
            period='7d'
        )

        # Assert - Period passed to constructor (takes precedence)
        call_args = mock_gnews_class.call_args
        assert call_args.kwargs.get('period') == '7d'

        # Dates should NOT be set when period is used
        assert not hasattr(mock_instance, 'start_date') or mock_instance.start_date is None
        assert not hasattr(mock_instance, 'end_date') or mock_instance.end_date is None
