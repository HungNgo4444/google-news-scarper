"""Unit tests for daily sliding window crawling logic.

Tests cover AC2 of Story 2.3: Daily Sliding Window for Date Ranges
"""
import pytest
from unittest.mock import Mock, patch, call
from datetime import datetime, timedelta
from src.core.crawler.sync_engine import GoogleNewsSyncEngine


class TestDailySlidingWindow:
    """Test suite for daily sliding window implementation."""

    @pytest.fixture
    def sync_engine(self):
        """Create GoogleNewsSyncEngine instance for testing."""
        return GoogleNewsSyncEngine()

    def test_date_range_split_into_daily_chunks_correctly(self, sync_engine):
        """Test that date range is split into correct number of daily chunks."""
        # Arrange
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 5)  # 5-day range

        with patch.object(sync_engine, 'search_google_news', return_value=['url1', 'url2']) as mock_search:
            # Act
            result = sync_engine.crawl_with_daily_sliding_window(
                keywords=['test'],
                exclude_keywords=[],
                start_date=start_date,
                end_date=end_date,
                max_results_total=100,
                language='vi',
                country='VN'
            )

            # Assert - Should make 5 separate calls (one per day)
            assert mock_search.call_count == 5

            # Verify each call has single-day date range
            calls = mock_search.call_args_list
            for i, call_args in enumerate(calls):
                expected_day_start = start_date + timedelta(days=i)
                expected_day_end = expected_day_start + timedelta(days=1, seconds=-1)

                assert call_args.kwargs['start_date'] == expected_day_start
                assert call_args.kwargs['end_date'] == expected_day_end
                assert call_args.kwargs['period'] is None

    def test_max_results_divided_evenly_across_days(self, sync_engine):
        """Test that max_results is distributed evenly across days."""
        # Arrange
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 10)  # 10-day range
        max_results_total = 100

        with patch.object(sync_engine, 'search_google_news', return_value=['url1']) as mock_search:
            # Act
            sync_engine.crawl_with_daily_sliding_window(
                keywords=['test'],
                exclude_keywords=[],
                start_date=start_date,
                end_date=end_date,
                max_results_total=max_results_total,
                language='vi',
                country='VN'
            )

            # Assert - Each day should get max_results_total // total_days
            expected_max_per_day = 100 // 10  # 10 results per day

            for call_args in mock_search.call_args_list:
                assert call_args.kwargs['max_results'] == expected_max_per_day

    def test_results_accumulated_and_deduplicated(self, sync_engine):
        """Test that results are accumulated across days and deduplicated."""
        # Arrange
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 3)  # 3-day range

        # Mock returns with overlapping URLs
        return_values = [
            ['url1', 'url2', 'url3'],     # Day 1
            ['url2', 'url4', 'url5'],     # Day 2 (url2 is duplicate)
            ['url5', 'url6']              # Day 3 (url5 is duplicate)
        ]

        with patch.object(sync_engine, 'search_google_news', side_effect=return_values):
            # Act
            result = sync_engine.crawl_with_daily_sliding_window(
                keywords=['test'],
                exclude_keywords=[],
                start_date=start_date,
                end_date=end_date,
                max_results_total=100,
                language='vi',
                country='VN'
            )

            # Assert - Should have 6 unique URLs (url1-6, duplicates removed)
            assert len(result) == 6
            assert set(result) == {'url1', 'url2', 'url3', 'url4', 'url5', 'url6'}

    def test_single_day_range_makes_one_call(self, sync_engine):
        """Test that a single-day range makes exactly one call."""
        # Arrange
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 1)  # Same day

        with patch.object(sync_engine, 'search_google_news', return_value=['url1']) as mock_search:
            # Act
            result = sync_engine.crawl_with_daily_sliding_window(
                keywords=['test'],
                exclude_keywords=[],
                start_date=start_date,
                end_date=end_date,
                max_results_total=100,
                language='vi',
                country='VN'
            )

            # Assert - Only 1 call for single day
            assert mock_search.call_count == 1

    def test_invalid_date_range_returns_empty_list(self, sync_engine, caplog):
        """Test that invalid date range (end before start) returns empty list."""
        # Arrange
        start_date = datetime(2024, 1, 5)
        end_date = datetime(2024, 1, 1)  # End before start

        with patch.object(sync_engine, 'search_google_news') as mock_search:
            # Act
            with caplog.at_level("WARNING"):
                result = sync_engine.crawl_with_daily_sliding_window(
                    keywords=['test'],
                    exclude_keywords=[],
                    start_date=start_date,
                    end_date=end_date,
                    max_results_total=100,
                    language='vi',
                    country='VN'
                )

            # Assert
            assert result == []
            assert mock_search.call_count == 0
            assert "Invalid date range" in caplog.text

    def test_each_day_call_uses_correct_date_range(self, sync_engine):
        """Test that each day's GNews call uses correct single-day date range."""
        # Arrange
        start_date = datetime(2024, 1, 1, 0, 0, 0)
        end_date = datetime(2024, 1, 3, 0, 0, 0)  # 3-day range

        with patch.object(sync_engine, 'search_google_news', return_value=['url1']) as mock_search:
            # Act
            sync_engine.crawl_with_daily_sliding_window(
                keywords=['test'],
                exclude_keywords=[],
                start_date=start_date,
                end_date=end_date,
                max_results_total=90,
                language='vi',
                country='VN'
            )

            # Assert - Check each call's date range
            calls = mock_search.call_args_list

            # Day 1: 2024-01-01 00:00:00 to 2024-01-01 23:59:59
            assert calls[0].kwargs['start_date'] == datetime(2024, 1, 1, 0, 0, 0)
            assert calls[0].kwargs['end_date'] == datetime(2024, 1, 1, 23, 59, 59)

            # Day 2: 2024-01-02 00:00:00 to 2024-01-02 23:59:59
            assert calls[1].kwargs['start_date'] == datetime(2024, 1, 2, 0, 0, 0)
            assert calls[1].kwargs['end_date'] == datetime(2024, 1, 2, 23, 59, 59)

            # Day 3: 2024-01-03 00:00:00 to 2024-01-03 23:59:59
            assert calls[2].kwargs['start_date'] == datetime(2024, 1, 3, 0, 0, 0)
            assert calls[2].kwargs['end_date'] == datetime(2024, 1, 3, 23, 59, 59)

    def test_day_crawl_failure_continues_to_next_day(self, sync_engine, caplog):
        """Test that failure on one day doesn't stop crawling other days."""
        # Arrange
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 3)  # 3-day range

        # Mock: Day 2 fails, but days 1 and 3 succeed
        return_values = [
            ['url1', 'url2'],           # Day 1 succeeds
            Exception("API error"),      # Day 2 fails
            ['url3', 'url4']            # Day 3 succeeds
        ]

        with patch.object(sync_engine, 'search_google_news', side_effect=return_values):
            # Act
            with caplog.at_level("WARNING"):
                result = sync_engine.crawl_with_daily_sliding_window(
                    keywords=['test'],
                    exclude_keywords=[],
                    start_date=start_date,
                    end_date=end_date,
                    max_results_total=90,
                    language='vi',
                    country='VN'
                )

            # Assert - Should still return results from days 1 and 3
            assert len(result) == 4
            assert set(result) == {'url1', 'url2', 'url3', 'url4'}

            # Verify warning logged for day 2 failure
            assert "Failed to crawl" in caplog.text

    def test_keywords_and_exclude_keywords_passed_to_each_day(self, sync_engine):
        """Test that keywords and exclude_keywords are passed to each daily search."""
        # Arrange
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 2)  # 2-day range
        keywords = ['technology', 'AI']
        exclude_keywords = ['spam', 'ads']

        with patch.object(sync_engine, 'search_google_news', return_value=['url1']) as mock_search:
            # Act
            sync_engine.crawl_with_daily_sliding_window(
                keywords=keywords,
                exclude_keywords=exclude_keywords,
                start_date=start_date,
                end_date=end_date,
                max_results_total=100,
                language='vi',
                country='VN'
            )

            # Assert - All calls should have same keywords/exclude_keywords
            for call_args in mock_search.call_args_list:
                assert call_args.kwargs['keywords'] == keywords
                assert call_args.kwargs['exclude_keywords'] == exclude_keywords

    def test_language_and_country_passed_to_each_day(self, sync_engine):
        """Test that language and country are passed to each daily search."""
        # Arrange
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 2)  # 2-day range

        with patch.object(sync_engine, 'search_google_news', return_value=['url1']) as mock_search:
            # Act
            sync_engine.crawl_with_daily_sliding_window(
                keywords=['test'],
                exclude_keywords=[],
                start_date=start_date,
                end_date=end_date,
                max_results_total=100,
                language='en',
                country='US'
            )

            # Assert
            for call_args in mock_search.call_args_list:
                assert call_args.kwargs['language'] == 'en'
                assert call_args.kwargs['country'] == 'US'

    def test_logging_includes_progress_information(self, sync_engine, caplog):
        """Test that logging includes day progress information."""
        # Arrange
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 3)  # 3-day range

        with patch.object(sync_engine, 'search_google_news', return_value=['url1', 'url2']):
            # Act
            with caplog.at_level("INFO"):
                sync_engine.crawl_with_daily_sliding_window(
                    keywords=['test'],
                    exclude_keywords=[],
                    start_date=start_date,
                    end_date=end_date,
                    max_results_total=90,
                    language='vi',
                    country='VN'
                )

            # Assert - Verify progress logging
            assert "Day 1/3" in caplog.text
            assert "Day 2/3" in caplog.text
            assert "Day 3/3" in caplog.text
            assert "Daily sliding window complete" in caplog.text

    def test_empty_results_from_all_days_returns_empty_list(self, sync_engine):
        """Test that all days returning empty results gives empty final list."""
        # Arrange
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 3)  # 3-day range

        with patch.object(sync_engine, 'search_google_news', return_value=[]):
            # Act
            result = sync_engine.crawl_with_daily_sliding_window(
                keywords=['test'],
                exclude_keywords=[],
                start_date=start_date,
                end_date=end_date,
                max_results_total=90,
                language='vi',
                country='VN'
            )

            # Assert
            assert result == []

    def test_minimum_max_results_per_day_is_one(self, sync_engine):
        """Test that max_results_per_day has a minimum of 1 even with low total."""
        # Arrange
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 10)  # 10-day range
        max_results_total = 5  # Very low total (less than days)

        with patch.object(sync_engine, 'search_google_news', return_value=['url1']) as mock_search:
            # Act
            sync_engine.crawl_with_daily_sliding_window(
                keywords=['test'],
                exclude_keywords=[],
                start_date=start_date,
                end_date=end_date,
                max_results_total=max_results_total,
                language='vi',
                country='VN'
            )

            # Assert - Each day should get at least 1 result (not 0)
            for call_args in mock_search.call_args_list:
                assert call_args.kwargs['max_results'] >= 1
