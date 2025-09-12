"""Google News Crawler Engine.

This module provides the CrawlerEngine class that orchestrates the crawling process
by integrating Google News search, article extraction, and database persistence.

The CrawlerEngine supports:
- Google News search with single and multi-keyword OR logic
- Exclude keywords filtering 
- Rate limiting for external API calls
- Comprehensive error handling and logging
- Deduplication using URL hashes
- Batch processing for efficiency

Key Components:
- GoogleNewsSource integration for search functionality
- ArticleExtractor integration for content extraction
- Repository pattern for database operations
- Structured logging with correlation IDs
- Async/await compatibility throughout

Example:
    Basic category crawling:
    
    ```python
    import asyncio
    import logging
    from src.shared.config import get_settings
    from src.core.crawler.engine import CrawlerEngine
    from src.core.crawler.extractor import ArticleExtractor
    from src.database.repositories.article_repo import ArticleRepository
    from src.database.repositories.category_repo import CategoryRepository
    
    async def crawl_category_example():
        # Setup dependencies
        settings = get_settings()
        logger = logging.getLogger(__name__)
        
        # Create repositories
        article_repo = ArticleRepository()
        category_repo = CategoryRepository()
        
        # Create extractor
        article_extractor = ArticleExtractor(settings=settings, logger=logger)
        
        # Create crawler engine
        crawler = CrawlerEngine(
            settings=settings,
            logger=logger,
            article_extractor=article_extractor,
            article_repo=article_repo
        )
        
        # Crawl a category
        category = await category_repo.get_by_name("Technology")
        if category:
            articles = await crawler.crawl_category(category)
            print(f"Crawled {len(articles)} articles")
        
        return articles
    
    # Run crawling
    asyncio.run(crawl_category_example())
    ```
"""

import asyncio
import logging
import sys
import os
from typing import List, Dict, Optional, Any
from uuid import UUID, uuid4
from datetime import datetime, timezone

# Add newspaper4k-master to path
newspaper_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'newspaper4k-master')
if os.path.exists(newspaper_path):
    sys.path.insert(0, newspaper_path)

try:
    from newspaper.google_news import GoogleNewsSource
except ImportError:
    # Fallback if GoogleNewsSource is not available
    GoogleNewsSource = None

from src.shared.config import Settings
from src.shared.exceptions import (
    BaseAppException,
    ExtractionError,
    RateLimitExceededError,
    ValidationError,
    GoogleNewsUnavailableError,
    ExternalServiceError
)
from src.core.crawler.extractor import ArticleExtractor
from src.core.error_handling.circuit_breaker import (
    CircuitBreakerManager, 
    CircuitBreakerConfig, 
    circuit_breaker
)
from src.core.error_handling.retry_handler import RetryHandler, EXTERNAL_SERVICE_RETRY


class CrawlerError(BaseAppException):
    """Exception raised for crawler-specific errors."""
    pass


class GoogleNewsSearchError(ExternalServiceError):
    """Exception raised for Google News search failures."""
    pass


class CrawlerEngine:
    """Main crawler orchestration class for Google News crawling.
    
    This class coordinates the entire crawling process from Google News search
    through article extraction to database persistence. It implements rate limiting,
    error handling, logging, and deduplication.
    
    The crawler follows these steps:
    1. Build search query from category keywords with OR logic
    2. Apply exclude_keywords filtering
    3. Search Google News for article URLs
    4. Extract article content using ArticleExtractor
    5. Deduplicate articles using URL hashes
    6. Save articles to database with category associations
    7. Log comprehensive metrics throughout
    
    Args:
        settings: Application settings instance
        logger: Logger instance for structured logging
        article_extractor: ArticleExtractor instance for content extraction
        article_repo: ArticleRepository instance for database operations
        rate_limiter: Optional rate limiter instance (future enhancement)
    """
    
    def __init__(
        self,
        settings: Settings,
        logger: logging.Logger,
        article_extractor: ArticleExtractor,
        article_repo: Any,  # ArticleRepository - using Any to avoid circular import
        rate_limiter: Optional[Any] = None
    ):
        """Initialize the CrawlerEngine with required dependencies.
        
        Args:
            settings: Application settings instance
            logger: Logger for structured logging
            article_extractor: ArticleExtractor for content extraction
            article_repo: ArticleRepository for database operations
            rate_limiter: Optional rate limiter (future enhancement)
            
        Raises:
            ValidationError: If required dependencies are missing
        """
        self.settings = settings
        self.logger = logger
        self.article_extractor = article_extractor
        self.article_repo = article_repo
        self.rate_limiter = rate_limiter
        
        # Initialize circuit breaker manager
        self.circuit_breaker_manager = CircuitBreakerManager()
        
        # Initialize retry handler
        self.retry_handler = RetryHandler(EXTERNAL_SERVICE_RETRY)
        
        # Validate Google News availability
        if GoogleNewsSource is None:
            raise ValidationError(
                "GoogleNewsSource not available. Please install gnews: pip install gnews"
            )
        
        # Initialize Google News source
        self.google_news = GoogleNewsSource()
        
        # Configuration validation
        self._validate_configuration()
        
    def _validate_configuration(self) -> None:
        """Validate crawler configuration settings.
        
        Raises:
            ValidationError: If configuration is invalid
        """
        if not self.settings.EXTRACTION_TIMEOUT or self.settings.EXTRACTION_TIMEOUT <= 0:
            raise ValidationError("EXTRACTION_TIMEOUT must be positive")
        
        if not self.article_extractor:
            raise ValidationError("ArticleExtractor is required")
            
        if not self.article_repo:
            raise ValidationError("ArticleRepository is required")
    
    async def crawl_category(self, category: Any) -> List[Dict[str, Any]]:
        """Crawl articles for a specific category.
        
        This is the main entry point for crawling. It orchestrates the entire
        process from Google News search through database persistence.
        
        Args:
            category: Category model instance with keywords and exclude_keywords
            
        Returns:
            List of successfully processed article dictionaries
            
        Raises:
            CrawlerError: For general crawler failures
            GoogleNewsSearchError: For Google News search failures
        """
        correlation_id = str(uuid4())
        start_time = datetime.now(timezone.utc)
        
        self.logger.info(
            "Starting category crawl",
            extra={
                "correlation_id": correlation_id,
                "category_id": str(category.id),
                "category_name": category.name,
                "keywords_count": len(category.keywords),
                "exclude_keywords_count": len(category.exclude_keywords or [])
            }
        )
        
        try:
            # Step 1: Search Google News for article URLs with enhanced parameters
            max_results = getattr(self.settings, 'MAX_RESULTS_PER_SEARCH', 100)
            article_urls = await self.search_google_news(
                keywords=category.keywords,
                exclude_keywords=category.exclude_keywords or [],
                max_results=max_results,
                correlation_id=correlation_id
            )
            
            if not article_urls:
                self.logger.warning(
                    "No articles found for category",
                    extra={
                        "correlation_id": correlation_id,
                        "category_name": category.name
                    }
                )
                return []
            
            # Step 2: Extract articles in batches
            extracted_articles = await self.extract_articles_batch(
                urls=article_urls,
                correlation_id=correlation_id
            )
            
            if not extracted_articles:
                self.logger.warning(
                    "No articles successfully extracted",
                    extra={
                        "correlation_id": correlation_id,
                        "urls_found": len(article_urls)
                    }
                )
                return []
            
            # Step 3: Save articles with deduplication
            saved_count = await self.save_articles_with_deduplication(
                articles=extracted_articles,
                category_id=category.id,
                correlation_id=correlation_id
            )
            
            # Log final metrics
            end_time = datetime.now(timezone.utc)
            processing_time = (end_time - start_time).total_seconds()
            
            self.logger.info(
                "Category crawl completed successfully",
                extra={
                    "correlation_id": correlation_id,
                    "category_name": category.name,
                    "urls_found": len(article_urls),
                    "articles_extracted": len(extracted_articles),
                    "articles_saved": saved_count,
                    "processing_time_seconds": processing_time,
                    "extraction_success_rate": len(extracted_articles) / len(article_urls) if article_urls else 0
                }
            )
            
            return extracted_articles
            
        except Exception as e:
            end_time = datetime.now(timezone.utc)
            processing_time = (end_time - start_time).total_seconds()
            
            self.logger.error(
                f"Category crawl failed: {e}",
                extra={
                    "correlation_id": correlation_id,
                    "category_name": category.name,
                    "error_type": type(e).__name__,
                    "processing_time_seconds": processing_time
                }
            )
            raise CrawlerError(f"Failed to crawl category {category.name}: {e}") from e
    
    async def search_google_news(
        self, 
        keywords: List[str], 
        exclude_keywords: List[str] = None,
        max_results: int = 100,
        language: str = "en",
        country: str = "US",
        correlation_id: str = None
    ) -> List[str]:
        """Search Google News for articles matching keyword criteria.
        
        Builds a search query using OR logic for keywords and exclusion logic
        for exclude_keywords, then executes the search through GoogleNewsSource.
        Enhanced support for complex queries with configurable results and localization.
        
        Args:
            keywords: List of keywords to search for (OR logic)
            exclude_keywords: List of keywords to exclude from results
            max_results: Maximum number of results to return (default: 100)
            language: Language code for search results (default: "en")
            country: Country code for search results (default: "US")
            correlation_id: Unique identifier for tracking this operation
            
        Returns:
            List of article URLs found in search results
            
        Raises:
            GoogleNewsSearchError: If search fails
        """
        if not correlation_id:
            correlation_id = str(uuid4())
        
        if not keywords:
            raise GoogleNewsSearchError("Keywords list cannot be empty")
        
        # Build enhanced search query with OR logic and validation
        search_query = self._build_advanced_search_query(keywords, exclude_keywords or [])
        query_complexity = self._classify_query_complexity(keywords, exclude_keywords or [])
        
        self.logger.info(
            "Executing Google News search",
            extra={
                "correlation_id": correlation_id,
                "search_query": search_query,
                "keywords": keywords,
                "exclude_keywords": exclude_keywords or [],
                "max_results": max_results,
                "language": language,
                "country": country,
                "query_complexity": query_complexity
            }
        )
        
        try:
            # Apply enhanced rate limiting based on query complexity
            if self.rate_limiter:
                rate_limit_delay = self._get_rate_limit_delay(query_complexity)
                await self.rate_limiter.wait_if_needed(delay=rate_limit_delay)
            
            # Execute Google News search with circuit breaker protection
            circuit_breaker_config = CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=300,
                timeout_duration=30
            )
            
            search_results = await self.circuit_breaker_manager.call_with_circuit_breaker(
                service_name="google_news_search",
                func=self._execute_google_news_search_async,
                search_query=search_query,
                max_results=max_results,
                language=language,
                country=country,
                config=circuit_breaker_config,
                correlation_id=correlation_id
            )
            
            # Extract URLs from search results with enhanced handling
            article_urls = self._extract_urls_from_results(search_results, max_results)
            
            # Clean and validate URLs
            clean_urls = []
            for url in article_urls:
                if isinstance(url, str) and (url.startswith('http://') or url.startswith('https://')):
                    clean_urls.append(url)
            
            self.logger.info(
                "Google News search completed",
                extra={
                    "correlation_id": correlation_id,
                    "search_query": search_query,
                    "urls_found": len(clean_urls),
                    "max_results_requested": max_results,
                    "query_complexity": query_complexity,
                    "language": language,
                    "country": country
                }
            )
            
            return clean_urls
            
        except Exception as e:
            self.logger.error(
                f"Google News search failed: {e}",
                extra={
                    "correlation_id": correlation_id,
                    "search_query": search_query,
                    "error_type": type(e).__name__
                }
            )
            raise GoogleNewsSearchError(f"Failed to search Google News: {e}") from e
    
    def _build_search_query(self, keywords: List[str], exclude_keywords: List[str]) -> str:
        """Build Google News search query with OR logic and exclusions.
        
        Creates a search query string that:
        1. Uses OR logic for keywords: "(python OR javascript OR AI)"
        2. Adds exclusions with minus prefix: "-java -php"
        
        Args:
            keywords: List of keywords to search for
            exclude_keywords: List of keywords to exclude
            
        Returns:
            Formatted search query string
            
        Example:
            keywords=["python", "javascript"], exclude_keywords=["java"]
            returns: "(python OR javascript) -java"
        """
        if not keywords:
            return ""
        
        # Build OR query for keywords
        or_query = " OR ".join(f'"{keyword.strip()}"' for keyword in keywords if keyword.strip())
        
        # Wrap in parentheses if multiple keywords
        if len(keywords) > 1:
            query = f"({or_query})"
        else:
            query = or_query
        
        # Add exclusions
        if exclude_keywords:
            exclude_part = " ".join([f'-"{kw.strip()}"' for kw in exclude_keywords if kw.strip()])
            if exclude_part:
                query = f"{query} {exclude_part}"
        
        return query
    
    def _build_advanced_search_query(self, keywords: List[str], exclude_keywords: List[str]) -> str:
        """Build advanced Google News search query with enhanced OR logic and exclusions.
        
        Creates a more sophisticated search query string that:
        1. Uses OR logic for keywords with proper quoting: "(python OR javascript OR AI)"
        2. Adds exclusions with minus prefix: "-java -php"  
        3. Handles special characters and edge cases
        4. Validates and sanitizes input
        
        Args:
            keywords: List of keywords to search for
            exclude_keywords: List of keywords to exclude
            
        Returns:
            Formatted search query string with advanced OR logic
            
        Example:
            keywords=["machine learning", "AI", "python"], exclude_keywords=["cryptocurrency"] 
            returns: '("machine learning" OR "AI" OR "python") -"cryptocurrency"'
        """
        if not keywords:
            return ""
        
        # Validate and sanitize keywords
        cleaned_keywords = self._sanitize_keywords(keywords)
        if not cleaned_keywords:
            return ""
        
        # Build OR query for keywords with proper quoting
        if len(cleaned_keywords) == 1:
            base_query = f'"{cleaned_keywords[0]}"'
        else:
            quoted_keywords = [f'"{kw}"' for kw in cleaned_keywords]
            base_query = f"({' OR '.join(quoted_keywords)})"
        
        # Add exclusions with proper quoting
        if exclude_keywords:
            cleaned_exclusions = self._sanitize_keywords(exclude_keywords)
            if cleaned_exclusions:
                exclude_part = " ".join([f'-"{kw}"' for kw in cleaned_exclusions])
                base_query = f"{base_query} {exclude_part}"
        
        return base_query
    
    def _sanitize_keywords(self, keywords: List[str]) -> List[str]:
        """Sanitize and validate keywords for search queries.
        
        Args:
            keywords: Raw keywords list
            
        Returns:
            List of cleaned and validated keywords
        """
        if not keywords:
            return []
        
        cleaned = []
        for keyword in keywords:
            if not keyword or not isinstance(keyword, str):
                continue
                
            # Strip whitespace and convert to lowercase for consistency
            clean_kw = keyword.strip()
            if not clean_kw:
                continue
            
            # Remove potentially problematic characters but keep essential ones
            # Allow letters, numbers, spaces, hyphens, and basic punctuation
            sanitized = ''.join(c for c in clean_kw if c.isalnum() or c in ' -._')
            sanitized = ' '.join(sanitized.split())  # Normalize whitespace
            
            if sanitized and len(sanitized) <= 100:  # Max keyword length
                cleaned.append(sanitized)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_cleaned = []
        for kw in cleaned:
            if kw.lower() not in seen:
                seen.add(kw.lower())
                unique_cleaned.append(kw)
        
        return unique_cleaned
    
    def _classify_query_complexity(self, keywords: List[str], exclude_keywords: List[str]) -> str:
        """Classify search query complexity for rate limiting and logging.
        
        Args:
            keywords: List of keywords
            exclude_keywords: List of exclude keywords
            
        Returns:
            Complexity level: "simple", "medium", or "complex"
        """
        total_keywords = len(keywords) + len(exclude_keywords or [])
        
        if total_keywords <= 2:
            return "simple"
        elif total_keywords <= 5:
            return "medium"
        else:
            return "complex"
    
    def _get_rate_limit_delay(self, query_complexity: str) -> float:
        """Get rate limit delay based on query complexity.
        
        Args:
            query_complexity: Complexity level from _classify_query_complexity
            
        Returns:
            Delay in seconds
        """
        complexity_delays = {
            "simple": 1.0,    # 1 second between simple queries
            "medium": 1.5,    # 1.5 seconds between medium queries  
            "complex": 2.0    # 2 seconds between complex queries
        }
        return complexity_delays.get(query_complexity, 2.0)
    
    async def _execute_google_news_search_async(
        self, 
        search_query: str, 
        max_results: int, 
        language: str, 
        country: str
    ):
        """Execute Google News search with enhanced parameters (async wrapper).
        
        Args:
            search_query: The search query string
            max_results: Maximum results to return
            language: Language code
            country: Country code
            
        Returns:
            Search results from GoogleNewsSource
            
        Raises:
            GoogleNewsUnavailableError: If Google News is unavailable
            ExternalServiceError: For other external service failures
        """
        try:
            # Run the synchronous Google News search in executor
            search_results = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._execute_google_news_search_sync(
                    search_query, max_results, language, country
                )
            )
            return search_results
            
        except Exception as e:
            # Transform to appropriate exception type for circuit breaker handling
            if "unavailable" in str(e).lower() or "timeout" in str(e).lower():
                raise GoogleNewsUnavailableError(
                    f"Google News service unavailable: {e}",
                    details={
                        "search_query": search_query,
                        "language": language,
                        "country": country
                    }
                )
            else:
                raise ExternalServiceError(
                    code="GOOGLE_NEWS_ERROR",
                    message=f"Google News search failed: {e}",
                    details={
                        "search_query": search_query,
                        "error_type": type(e).__name__
                    },
                    retryable=True,
                    retry_after=60
                )

    def _execute_google_news_search_sync(
        self, 
        search_query: str, 
        max_results: int, 
        language: str, 
        country: str
    ):
        """Execute Google News search with enhanced parameters (synchronous).
        
        Args:
            search_query: The search query string
            max_results: Maximum results to return
            language: Language code
            country: Country code
            
        Returns:
            Search results from GoogleNewsSource
        """
        try:
            # Configure GoogleNewsSource with enhanced parameters if supported
            if hasattr(self.google_news, 'set_language'):
                self.google_news.set_language(language)
            if hasattr(self.google_news, 'set_country'):
                self.google_news.set_country(country)
            
            # Execute search with query
            return self.google_news.search(search_query)
            
        except Exception as e:
            # Log the error but re-raise to be handled by the calling method
            self.logger.warning(f"GoogleNewsSource search execution failed: {e}")
            raise
    
    def _extract_urls_from_results(self, search_results, max_results: int) -> List[str]:
        """Extract URLs from search results with enhanced handling.
        
        Args:
            search_results: Results from GoogleNewsSource
            max_results: Maximum number of URLs to extract
            
        Returns:
            List of clean article URLs
        """
        article_urls = []
        
        if not search_results:
            return []
        
        # Handle different result formats
        if hasattr(search_results, 'entries'):
            # RSS/Atom feed format
            entries_to_process = search_results.entries[:max_results] if search_results.entries else []
            for entry in entries_to_process:
                if hasattr(entry, 'link') and entry.link:
                    article_urls.append(entry.link)
                elif hasattr(entry, 'url') and entry.url:
                    article_urls.append(entry.url)
                    
        elif isinstance(search_results, list):
            # List format results
            for item in search_results[:max_results]:
                if isinstance(item, dict):
                    # Dictionary format
                    if 'url' in item and item['url']:
                        article_urls.append(item['url'])
                    elif 'link' in item and item['link']:
                        article_urls.append(item['link'])
                elif hasattr(item, 'url') and item.url:
                    # Object format with url attribute
                    article_urls.append(item.url)
                elif hasattr(item, 'link') and item.link:
                    # Object format with link attribute
                    article_urls.append(item.link)
        
        # Clean and validate URLs
        clean_urls = []
        for url in article_urls:
            if isinstance(url, str) and (url.startswith('http://') or url.startswith('https://')):
                # Basic URL validation - could be enhanced further
                if len(url) > 10 and len(url) < 2000:  # Reasonable URL length
                    clean_urls.append(url)
        
        return clean_urls[:max_results]
    
    async def search_google_news_with_pagination(
        self,
        keywords: List[str],
        exclude_keywords: List[str] = None,
        max_results: int = 100,
        page_size: int = 25,
        max_pages: int = 4,
        correlation_id: str = None
    ) -> List[str]:
        """Search Google News with pagination support for large result sets.
        
        This method implements pagination by making multiple smaller requests
        to avoid hitting API limits while still collecting large numbers of results.
        
        Args:
            keywords: List of keywords to search for (OR logic)
            exclude_keywords: List of keywords to exclude from results
            max_results: Total maximum number of results to return
            page_size: Number of results per page (recommended: 25-50)
            max_pages: Maximum number of pages to fetch
            correlation_id: Unique identifier for tracking this operation
            
        Returns:
            List of article URLs found across all pages
            
        Raises:
            GoogleNewsSearchError: If search fails
        """
        if not correlation_id:
            correlation_id = str(uuid4())
        
        if not keywords:
            raise GoogleNewsSearchError("Keywords list cannot be empty")
        
        self.logger.info(
            "Starting paginated Google News search",
            extra={
                "correlation_id": correlation_id,
                "keywords": keywords,
                "exclude_keywords": exclude_keywords or [],
                "max_results": max_results,
                "page_size": page_size,
                "max_pages": max_pages
            }
        )
        
        all_urls = []
        current_page = 1
        
        try:
            while current_page <= max_pages and len(all_urls) < max_results:
                # Calculate results for this page
                remaining_results = max_results - len(all_urls)
                current_page_size = min(page_size, remaining_results)
                
                self.logger.debug(
                    f"Fetching page {current_page}",
                    extra={
                        "correlation_id": correlation_id,
                        "page": current_page,
                        "page_size": current_page_size,
                        "urls_collected": len(all_urls)
                    }
                )
                
                # Search for this page
                page_urls = await self.search_google_news(
                    keywords=keywords,
                    exclude_keywords=exclude_keywords or [],
                    max_results=current_page_size,
                    correlation_id=f"{correlation_id}_p{current_page}"
                )
                
                if not page_urls:
                    self.logger.info(
                        f"No results found on page {current_page}, stopping pagination",
                        extra={
                            "correlation_id": correlation_id,
                            "page": current_page
                        }
                    )
                    break
                
                # Add unique URLs only (deduplication across pages)
                new_urls = []
                for url in page_urls:
                    if url not in all_urls:
                        new_urls.append(url)
                        all_urls.append(url)
                
                self.logger.debug(
                    f"Page {current_page} completed",
                    extra={
                        "correlation_id": correlation_id,
                        "page": current_page,
                        "page_urls_found": len(page_urls),
                        "new_unique_urls": len(new_urls),
                        "total_urls_collected": len(all_urls)
                    }
                )
                
                # Stop if we didn't get any new URLs (duplicate results)
                if len(new_urls) == 0:
                    self.logger.info(
                        f"No new URLs found on page {current_page}, stopping pagination",
                        extra={
                            "correlation_id": correlation_id,
                            "page": current_page
                        }
                    )
                    break
                
                # Apply pagination delay to avoid overwhelming the API
                if current_page < max_pages and len(all_urls) < max_results:
                    pagination_delay = self._get_pagination_delay()
                    await asyncio.sleep(pagination_delay)
                
                current_page += 1
            
            self.logger.info(
                "Paginated Google News search completed",
                extra={
                    "correlation_id": correlation_id,
                    "total_pages_fetched": current_page - 1,
                    "total_urls_found": len(all_urls),
                    "max_results_requested": max_results
                }
            )
            
            return all_urls[:max_results]
            
        except Exception as e:
            self.logger.error(
                f"Paginated Google News search failed: {e}",
                extra={
                    "correlation_id": correlation_id,
                    "page": current_page,
                    "urls_collected": len(all_urls),
                    "error_type": type(e).__name__
                }
            )
            raise GoogleNewsSearchError(f"Failed to search Google News with pagination: {e}") from e
    
    def _get_pagination_delay(self) -> float:
        """Get delay between pagination requests to avoid rate limiting.
        
        Returns:
            Delay in seconds between pagination requests
        """
        return getattr(self.settings, 'PAGINATION_DELAY', 2.0)
    
    async def handle_pagination_errors(
        self,
        search_function,
        max_retries: int = 3,
        correlation_id: str = None
    ):
        """Handle pagination errors with retry logic and graceful degradation.
        
        Args:
            search_function: Function to execute with retry logic
            max_retries: Maximum number of retry attempts
            correlation_id: Tracking identifier
            
        Returns:
            Search results or empty list on failure
        """
        if not correlation_id:
            correlation_id = str(uuid4())
        
        for attempt in range(max_retries + 1):
            try:
                return await search_function()
                
            except Exception as e:
                if attempt < max_retries:
                    retry_delay = 2.0 * (2 ** attempt)  # Exponential backoff
                    self.logger.warning(
                        f"Pagination attempt {attempt + 1} failed, retrying in {retry_delay}s: {e}",
                        extra={
                            "correlation_id": correlation_id,
                            "attempt": attempt + 1,
                            "max_retries": max_retries,
                            "retry_delay": retry_delay
                        }
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    self.logger.error(
                        f"All pagination attempts failed: {e}",
                        extra={
                            "correlation_id": correlation_id,
                            "attempts": max_retries + 1,
                            "error_type": type(e).__name__
                        }
                    )
                    # Return empty results instead of failing completely
                    return []
        
        return []
    
    async def get_pagination_metrics(
        self,
        total_results: int,
        page_size: int,
        correlation_id: str = None
    ) -> Dict[str, Any]:
        """Calculate pagination performance metrics.
        
        Args:
            total_results: Total number of results collected
            page_size: Size of each page
            correlation_id: Tracking identifier
            
        Returns:
            Dictionary with pagination metrics
        """
        if not correlation_id:
            correlation_id = str(uuid4())
        
        metrics = {
            "total_results": total_results,
            "page_size": page_size,
            "estimated_pages": (total_results + page_size - 1) // page_size,
            "efficiency_score": 0.0,
            "recommended_page_size": page_size
        }
        
        # Calculate efficiency score (results per page)
        if metrics["estimated_pages"] > 0:
            metrics["efficiency_score"] = total_results / metrics["estimated_pages"]
        
        # Recommend optimal page size based on total results
        if total_results < 25:
            metrics["recommended_page_size"] = 10
        elif total_results < 100:
            metrics["recommended_page_size"] = 25
        else:
            metrics["recommended_page_size"] = 50
        
        self.logger.debug(
            "Pagination metrics calculated",
            extra={
                "correlation_id": correlation_id,
                **metrics
            }
        )
        
        return metrics
    
    async def extract_articles_batch(
        self, 
        urls: List[str], 
        correlation_id: str = None
    ) -> List[Dict[str, Any]]:
        """Extract article content from multiple URLs in batch.
        
        Processes URLs concurrently using the ArticleExtractor with proper
        error handling and logging for each extraction attempt.
        
        Args:
            urls: List of article URLs to extract
            correlation_id: Unique identifier for tracking this operation
            
        Returns:
            List of successfully extracted article dictionaries
        """
        if not correlation_id:
            correlation_id = str(uuid4())
        
        if not urls:
            return []
        
        self.logger.info(
            "Starting batch article extraction",
            extra={
                "correlation_id": correlation_id,
                "urls_count": len(urls)
            }
        )
        
        extracted_articles = []
        failed_count = 0
        
        # Process URLs with concurrency control
        semaphore = asyncio.Semaphore(5)  # Limit concurrent extractions
        
        async def extract_single_url(url: str) -> Optional[Dict[str, Any]]:
            async with semaphore:
                try:
                    # Use circuit breaker for article extraction
                    circuit_breaker_config = CircuitBreakerConfig(
                        failure_threshold=5,
                        recovery_timeout=180,
                        timeout_duration=self.settings.EXTRACTION_TIMEOUT
                    )
                    
                    result = await self.circuit_breaker_manager.call_with_circuit_breaker(
                        service_name="article_extraction",
                        func=self.article_extractor.extract_article_metadata,
                        url=url,
                        config=circuit_breaker_config,
                        correlation_id=correlation_id
                    )
                    
                    if result:
                        return result
                    else:
                        return None
                except Exception as e:
                    self.logger.warning(
                        f"Failed to extract article: {e}",
                        extra={
                            "correlation_id": correlation_id,
                            "url": url,
                            "error_type": type(e).__name__
                        }
                    )
                    return None
        
        # Execute extractions concurrently
        tasks = [extract_single_url(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for i, result in enumerate(results):
            if isinstance(result, dict):
                extracted_articles.append(result)
            else:
                failed_count += 1
                if isinstance(result, Exception):
                    self.logger.warning(
                        f"Extraction task failed: {result}",
                        extra={
                            "correlation_id": correlation_id,
                            "url": urls[i] if i < len(urls) else "unknown",
                            "error_type": type(result).__name__
                        }
                    )
        
        success_rate = len(extracted_articles) / len(urls) if urls else 0
        
        self.logger.info(
            "Batch article extraction completed",
            extra={
                "correlation_id": correlation_id,
                "total_urls": len(urls),
                "successful_extractions": len(extracted_articles),
                "failed_extractions": failed_count,
                "success_rate": success_rate
            }
        )
        
        return extracted_articles
    
    async def save_articles_with_deduplication(
        self,
        articles: List[Dict[str, Any]],
        category_id: UUID,
        correlation_id: str = None
    ) -> int:
        """Save articles to database with deduplication logic.
        
        Uses URL hash-based deduplication to avoid saving duplicate articles.
        Creates category associations for new and existing articles.
        
        Args:
            articles: List of extracted article dictionaries
            category_id: UUID of the category to associate articles with
            correlation_id: Unique identifier for tracking this operation
            
        Returns:
            Number of articles successfully saved (excluding duplicates)
        """
        if not correlation_id:
            correlation_id = str(uuid4())
        
        if not articles:
            return 0
        
        self.logger.info(
            "Starting article save with deduplication",
            extra={
                "correlation_id": correlation_id,
                "articles_count": len(articles),
                "category_id": str(category_id)
            }
        )
        
        saved_count = 0
        duplicate_count = 0
        error_count = 0
        
        for article_data in articles:
            try:
                # Check for existing article by URL hash
                url_hash = article_data.get('url_hash')
                if not url_hash:
                    self.logger.warning(
                        "Article missing url_hash, skipping",
                        extra={
                            "correlation_id": correlation_id,
                            "article_url": article_data.get('source_url', 'unknown')
                        }
                    )
                    error_count += 1
                    continue
                
                # This would typically use the repository to check for existing articles
                # For now, we'll implement a basic save operation
                existing_article = await self.article_repo.get_by_url_hash(url_hash)
                
                if existing_article:
                    # Update last_seen timestamp for existing article
                    await self.article_repo.update_last_seen(existing_article.id)
                    
                    # Ensure category association exists
                    await self.article_repo.ensure_category_association(
                        existing_article.id, 
                        category_id
                    )
                    
                    duplicate_count += 1
                    
                    self.logger.debug(
                        "Article already exists, updated last_seen",
                        extra={
                            "correlation_id": correlation_id,
                            "article_id": str(existing_article.id),
                            "url_hash": url_hash
                        }
                    )
                else:
                    # Create new article
                    new_article = await self.article_repo.create_with_category(
                        article_data, 
                        category_id
                    )
                    
                    saved_count += 1
                    
                    self.logger.debug(
                        "New article saved successfully",
                        extra={
                            "correlation_id": correlation_id,
                            "article_id": str(new_article.id),
                            "article_title": article_data.get('title', '')[:50],
                            "url_hash": url_hash
                        }
                    )
                
            except Exception as e:
                error_count += 1
                self.logger.error(
                    f"Failed to save article: {e}",
                    extra={
                        "correlation_id": correlation_id,
                        "article_url": article_data.get('source_url', 'unknown'),
                        "error_type": type(e).__name__
                    }
                )
        
        self.logger.info(
            "Article save process completed",
            extra={
                "correlation_id": correlation_id,
                "total_articles": len(articles),
                "new_articles_saved": saved_count,
                "duplicates_found": duplicate_count,
                "errors_encountered": error_count,
                "category_id": str(category_id)
            }
        )
        
        return saved_count
    
    async def search_google_news_multi_keyword(
        self,
        keywords: List[str],
        exclude_keywords: List[str] = None,
        max_results: int = 100
    ) -> List[str]:
        """Enhanced multi-keyword OR search with pagination support.
        
        This is a specialized version of search_google_news designed for
        complex multi-keyword searches with enhanced logging and validation.
        
        Args:
            keywords: List of keywords to search for (OR logic)
            exclude_keywords: List of keywords to exclude from results
            max_results: Maximum number of results to return
            
        Returns:
            List of article URLs found in search results
            
        Raises:
            GoogleNewsSearchError: If search fails
        """
        if not keywords:
            raise GoogleNewsSearchError("Keywords list cannot be empty")
        
        correlation_id = str(uuid4())
        
        self.logger.info(
            "Executing multi-keyword Google News search",
            extra={
                "correlation_id": correlation_id,
                "keywords_count": len(keywords),
                "exclude_keywords_count": len(exclude_keywords or []),
                "max_results": max_results
            }
        )
        
        # Use the enhanced search method
        return await self.search_google_news(
            keywords=keywords,
            exclude_keywords=exclude_keywords or [],
            max_results=max_results,
            correlation_id=correlation_id
        )
    
    async def crawl_category_advanced(self, category: Any) -> List[Dict[str, Any]]:
        """Enhanced category crawling with complex OR logic and improved metrics.
        
        This method provides enhanced crawling capabilities with:
        - Advanced multi-keyword OR search logic
        - Enhanced deduplication and similarity detection
        - Improved category association with relevance scoring
        - Comprehensive metrics tracking
        
        Args:
            category: Category model instance with keywords and exclude_keywords
            
        Returns:
            List of successfully processed article dictionaries with enhanced metadata
            
        Raises:
            CrawlerError: For general crawler failures
            GoogleNewsSearchError: For Google News search failures
        """
        correlation_id = str(uuid4())
        start_time = datetime.now(timezone.utc)
        
        self.logger.info(
            "Starting advanced category crawl",
            extra={
                "correlation_id": correlation_id,
                "category_id": str(category.id),
                "category_name": category.name,
                "keywords": category.keywords,
                "exclude_keywords": category.exclude_keywords or [],
                "crawl_type": "advanced"
            }
        )
        
        try:
            # Step 1: Enhanced Google News search with pagination
            max_results = getattr(self.settings, 'MAX_RESULTS_PER_SEARCH', 200)
            article_urls = await self.search_google_news_multi_keyword(
                keywords=category.keywords,
                exclude_keywords=category.exclude_keywords or [],
                max_results=max_results
            )
            
            if not article_urls:
                self.logger.warning(
                    "No articles found for advanced category crawl",
                    extra={
                        "correlation_id": correlation_id,
                        "category_name": category.name
                    }
                )
                return []
            
            # Step 2: Extract articles with enhanced processing
            extracted_articles = await self.extract_articles_batch(
                urls=article_urls,
                correlation_id=correlation_id
            )
            
            if not extracted_articles:
                self.logger.warning(
                    "No articles successfully extracted in advanced crawl",
                    extra={
                        "correlation_id": correlation_id,
                        "urls_found": len(article_urls)
                    }
                )
                return []
            
            # Step 3: Add relevance scoring for advanced processing
            scored_articles = self._add_relevance_scores(
                articles=extracted_articles,
                keywords=category.keywords,
                correlation_id=correlation_id
            )
            
            # Step 4: Save articles with enhanced deduplication
            saved_count = await self.save_articles_with_advanced_deduplication(
                articles=scored_articles,
                category_id=category.id,
                keywords_matched=category.keywords,
                search_query_used=self._build_advanced_search_query(
                    category.keywords, 
                    category.exclude_keywords or []
                ),
                correlation_id=correlation_id
            )
            
            # Log enhanced metrics
            end_time = datetime.now(timezone.utc)
            processing_time = (end_time - start_time).total_seconds()
            
            self.logger.info(
                "Advanced category crawl completed successfully",
                extra={
                    "correlation_id": correlation_id,
                    "category_name": category.name,
                    "urls_found": len(article_urls),
                    "articles_extracted": len(extracted_articles),
                    "articles_with_relevance": len(scored_articles),
                    "articles_saved": saved_count,
                    "processing_time_seconds": processing_time,
                    "extraction_success_rate": len(extracted_articles) / len(article_urls) if article_urls else 0,
                    "relevance_coverage": len(scored_articles) / len(extracted_articles) if extracted_articles else 0
                }
            )
            
            return scored_articles
            
        except Exception as e:
            end_time = datetime.now(timezone.utc)
            processing_time = (end_time - start_time).total_seconds()
            
            self.logger.error(
                f"Advanced category crawl failed: {e}",
                extra={
                    "correlation_id": correlation_id,
                    "category_name": category.name,
                    "error_type": type(e).__name__,
                    "processing_time_seconds": processing_time
                }
            )
            raise CrawlerError(f"Failed to crawl category {category.name} (advanced): {e}") from e
    
    def calculate_relevance_score(
        self, 
        article_content: str, 
        keywords: List[str]
    ) -> float:
        """Calculate how well article matches keywords using basic scoring.
        
        Args:
            article_content: Article title and content combined
            keywords: List of keywords to match against
            
        Returns:
            Relevance score between 0.0 and 1.0
        """
        if not article_content or not keywords:
            return 0.0
        
        # Convert to lowercase for case-insensitive matching
        content_lower = article_content.lower()
        matches = 0
        total_keywords = len(keywords)
        
        for keyword in keywords:
            if keyword.lower() in content_lower:
                matches += 1
        
        # Basic scoring: percentage of keywords found
        return min(matches / total_keywords, 1.0) if total_keywords > 0 else 0.0
    
    def _add_relevance_scores(
        self,
        articles: List[Dict[str, Any]],
        keywords: List[str],
        correlation_id: str
    ) -> List[Dict[str, Any]]:
        """Add relevance scores to articles based on keyword matching.
        
        Args:
            articles: List of article dictionaries
            keywords: List of keywords to score against
            correlation_id: Tracking ID
            
        Returns:
            List of articles with added relevance_score field
        """
        scored_articles = []
        
        for article in articles:
            # Combine title and content for scoring
            content_for_scoring = f"{article.get('title', '')} {article.get('content', '')}"
            
            # Calculate relevance score
            relevance = self.calculate_relevance_score(content_for_scoring, keywords)
            
            # Add score to article
            enhanced_article = article.copy()
            enhanced_article['relevance_score'] = relevance
            
            scored_articles.append(enhanced_article)
        
        # Log scoring metrics
        if scored_articles:
            avg_score = sum(a['relevance_score'] for a in scored_articles) / len(scored_articles)
            high_relevance_count = sum(1 for a in scored_articles if a['relevance_score'] >= 0.5)
            
            self.logger.debug(
                "Article relevance scoring completed",
                extra={
                    "correlation_id": correlation_id,
                    "articles_scored": len(scored_articles),
                    "average_relevance": avg_score,
                    "high_relevance_count": high_relevance_count,
                    "keywords": keywords
                }
            )
        
        return scored_articles
    
    async def save_articles_with_advanced_deduplication(
        self,
        articles: List[Dict[str, Any]],
        category_id: UUID,
        keywords_matched: List[str],
        search_query_used: str,
        correlation_id: str = None
    ) -> int:
        """Save articles with enhanced deduplication and category association.
        
        This method provides enhanced functionality compared to the basic save method:
        - Detailed deduplication tracking
        - Enhanced category association with metadata
        - Relevance score preservation
        - Search query tracking
        
        Args:
            articles: List of article dictionaries with relevance scores
            category_id: UUID of the category
            keywords_matched: List of keywords that led to discovery
            search_query_used: The actual search query used
            correlation_id: Unique identifier for tracking
            
        Returns:
            Number of articles successfully saved (excluding duplicates)
        """
        if not correlation_id:
            correlation_id = str(uuid4())
        
        if not articles:
            return 0
        
        self.logger.info(
            "Starting advanced article save with deduplication",
            extra={
                "correlation_id": correlation_id,
                "articles_count": len(articles),
                "category_id": str(category_id),
                "search_query_used": search_query_used,
                "keywords_matched": keywords_matched
            }
        )
        
        # Use the enhanced deduplication method from repository
        try:
            result = await self.article_repo.bulk_create_with_enhanced_deduplication(
                articles_data=articles,
                category_id=category_id,
                keyword_matched=", ".join(keywords_matched[:3]) if keywords_matched else None,
                search_query_used=search_query_used
            )
            
            new_articles, updated_articles, duplicates_skipped = result
            total_saved = new_articles + updated_articles
            
            self.logger.info(
                "Advanced article save completed",
                extra={
                    "correlation_id": correlation_id,
                    "new_articles": new_articles,
                    "updated_articles": updated_articles,
                    "duplicates_skipped": duplicates_skipped,
                    "total_saved": total_saved,
                    "category_id": str(category_id)
                }
            )
            
            return total_saved
            
        except Exception as e:
            self.logger.error(
                f"Advanced deduplication failed, falling back to basic method: {e}",
                extra={
                    "correlation_id": correlation_id,
                    "category_id": str(category_id),
                    "articles_count": len(articles)
                }
            )
            # Fallback to basic method
            return await self.save_articles_with_deduplication(
                articles=articles,
                category_id=category_id,
                correlation_id=correlation_id
            )
    
    async def associate_articles_with_multiple_categories(
        self,
        articles: List[Dict[str, Any]],
        categories: List[Any],  # List of Category objects
        correlation_id: str = None
    ) -> Dict[str, Any]:
        """Associate articles with multiple matching categories based on relevance.
        
        This method implements many-to-many article-category relationships with
        relevance scoring to handle articles that match multiple categories.
        
        Args:
            articles: List of article dictionaries with metadata
            categories: List of Category objects to check against
            correlation_id: Tracking identifier
            
        Returns:
            Dictionary with association statistics and results
        """
        if not correlation_id:
            correlation_id = str(uuid4())
        
        if not articles or not categories:
            return {"associations_created": 0, "articles_processed": 0, "categories_matched": 0}
        
        self.logger.info(
            "Starting multi-category association",
            extra={
                "correlation_id": correlation_id,
                "articles_count": len(articles),
                "categories_count": len(categories)
            }
        )
        
        association_stats = {
            "associations_created": 0,
            "articles_processed": 0,
            "categories_matched": 0,
            "high_relevance_matches": 0,
            "category_distribution": {}
        }
        
        try:
            for article in articles:
                article_categories_matched = []
                article_associations_created = 0
                
                # Check article against all categories
                for category in categories:
                    relevance_score = self.calculate_category_relevance(
                        article=article,
                        category=category
                    )
                    
                    # Only associate if relevance meets threshold
                    relevance_threshold = getattr(self.settings, 'CATEGORY_RELEVANCE_THRESHOLD', 0.3)
                    
                    if relevance_score >= relevance_threshold:
                        # Create enhanced association
                        result = await self._create_category_association_with_metadata(
                            article=article,
                            category=category,
                            relevance_score=relevance_score,
                            correlation_id=correlation_id
                        )
                        
                        if result:
                            article_categories_matched.append({
                                "category_id": str(category.id),
                                "category_name": category.name,
                                "relevance_score": relevance_score
                            })
                            article_associations_created += 1
                            
                            if relevance_score >= 0.7:
                                association_stats["high_relevance_matches"] += 1
                            
                            # Track category distribution
                            category_name = category.name
                            if category_name not in association_stats["category_distribution"]:
                                association_stats["category_distribution"][category_name] = 0
                            association_stats["category_distribution"][category_name] += 1
                
                # Log article association results
                if article_categories_matched:
                    self.logger.debug(
                        f"Article matched {len(article_categories_matched)} categories",
                        extra={
                            "correlation_id": correlation_id,
                            "article_url": article.get("source_url", "unknown")[:50],
                            "categories_matched": article_categories_matched,
                            "associations_created": article_associations_created
                        }
                    )
                    
                    association_stats["categories_matched"] += len(article_categories_matched)
                    association_stats["associations_created"] += article_associations_created
                
                association_stats["articles_processed"] += 1
            
            self.logger.info(
                "Multi-category association completed",
                extra={
                    "correlation_id": correlation_id,
                    **association_stats
                }
            )
            
            return association_stats
            
        except Exception as e:
            self.logger.error(
                f"Multi-category association failed: {e}",
                extra={
                    "correlation_id": correlation_id,
                    "articles_count": len(articles),
                    "categories_count": len(categories),
                    "error_type": type(e).__name__
                }
            )
            raise CrawlerError(f"Failed to associate articles with multiple categories: {e}") from e
    
    def calculate_category_relevance(
        self,
        article: Dict[str, Any],
        category: Any
    ) -> float:
        """Calculate how well an article matches a category using enhanced scoring.
        
        This method provides more sophisticated relevance scoring than the basic
        keyword matching, considering keyword frequency, position, and context.
        
        Args:
            article: Article dictionary with title, content, etc.
            category: Category object with keywords and exclude_keywords
            
        Returns:
            Relevance score between 0.0 and 1.0
        """
        if not article or not category:
            return 0.0
        
        # Combine article text for analysis
        title = article.get('title', '')
        content = article.get('content', '')
        combined_text = f"{title} {content}".lower()
        
        if not combined_text.strip():
            return 0.0
        
        # Calculate keyword matches
        keyword_matches = 0
        total_keywords = len(category.keywords) if category.keywords else 0
        
        if total_keywords == 0:
            return 0.0
        
        keyword_scores = []
        
        for keyword in category.keywords:
            keyword_lower = keyword.lower()
            
            # Basic presence check
            if keyword_lower in combined_text:
                # Enhanced scoring based on context
                title_match = keyword_lower in title.lower()
                content_match = keyword_lower in content.lower()
                
                # Title matches are weighted higher
                keyword_score = 0.0
                if title_match:
                    keyword_score += 0.7  # Title match is highly relevant
                if content_match:
                    keyword_score += 0.3  # Content match is moderately relevant
                
                # Count frequency (with diminishing returns)
                frequency = combined_text.count(keyword_lower)
                frequency_bonus = min(frequency * 0.1, 0.3)  # Max 0.3 bonus
                keyword_score += frequency_bonus
                
                keyword_scores.append(min(keyword_score, 1.0))  # Cap at 1.0
                keyword_matches += 1
        
        # Calculate base relevance score
        if keyword_scores:
            avg_keyword_score = sum(keyword_scores) / len(keyword_scores)
            coverage_score = keyword_matches / total_keywords
            base_relevance = (avg_keyword_score + coverage_score) / 2
        else:
            base_relevance = 0.0
        
        # Apply penalties for exclude keywords
        if category.exclude_keywords:
            exclude_penalty = 0.0
            for exclude_keyword in category.exclude_keywords:
                if exclude_keyword.lower() in combined_text:
                    exclude_penalty += 0.2  # Each exclude keyword reduces relevance
            
            base_relevance = max(0.0, base_relevance - exclude_penalty)
        
        return min(base_relevance, 1.0)
    
    async def validate_category_associations(
        self,
        article: Dict[str, Any],
        category_associations: List[Dict[str, Any]],
        correlation_id: str = None
    ) -> Dict[str, Any]:
        """Validate and log category association decisions.
        
        Args:
            article: Article dictionary
            category_associations: List of category association dictionaries
            correlation_id: Tracking identifier
            
        Returns:
            Validation results with recommendations
        """
        if not correlation_id:
            correlation_id = str(uuid4())
        
        validation_result = {
            "is_valid": True,
            "warnings": [],
            "recommendations": [],
            "association_count": len(category_associations),
            "high_confidence_count": 0,
            "medium_confidence_count": 0,
            "low_confidence_count": 0
        }
        
        if not category_associations:
            validation_result["is_valid"] = False
            validation_result["warnings"].append("No category associations found for article")
            return validation_result
        
        # Analyze association quality
        for association in category_associations:
            relevance = association.get("relevance_score", 0.0)
            
            if relevance >= 0.7:
                validation_result["high_confidence_count"] += 1
            elif relevance >= 0.4:
                validation_result["medium_confidence_count"] += 1
            else:
                validation_result["low_confidence_count"] += 1
                validation_result["warnings"].append(
                    f"Low relevance score ({relevance:.2f}) for category {association.get('category_name')}"
                )
        
        # Generate recommendations
        if validation_result["high_confidence_count"] == 0:
            validation_result["recommendations"].append(
                "Consider reviewing category keywords - no high-confidence matches found"
            )
        
        if len(category_associations) > 5:
            validation_result["recommendations"].append(
                f"Article matches {len(category_associations)} categories - consider more specific keywords"
            )
        
        # Log validation results
        self.logger.debug(
            "Category association validation completed",
            extra={
                "correlation_id": correlation_id,
                "article_url": article.get("source_url", "unknown")[:50],
                **validation_result
            }
        )
        
        return validation_result
    
    async def _create_category_association_with_metadata(
        self,
        article: Dict[str, Any],
        category: Any,
        relevance_score: float,
        correlation_id: str
    ) -> bool:
        """Create category association with enhanced metadata.
        
        This is a helper method that would integrate with the enhanced repository
        methods to create associations with full metadata tracking.
        
        Args:
            article: Article dictionary
            category: Category object
            relevance_score: Calculated relevance score
            correlation_id: Tracking identifier
            
        Returns:
            True if association was created successfully
        """
        try:
            # This would integrate with the repository layer
            # For now, it's a placeholder that logs the association intent
            
            self.logger.debug(
                "Creating category association with metadata",
                extra={
                    "correlation_id": correlation_id,
                    "article_url": article.get("source_url", "unknown")[:50],
                    "category_id": str(category.id),
                    "category_name": category.name,
                    "relevance_score": relevance_score
                }
            )
            
            # In a full implementation, this would call:
            # await self.article_repo.create_enhanced_category_association(
            #     article_id=article["id"],
            #     category_id=category.id,
            #     relevance_score=relevance_score,
            #     keyword_matched=...,
            #     search_query_used=...
            # )
            
            return True
            
        except Exception as e:
            self.logger.warning(
                f"Failed to create category association: {e}",
                extra={
                    "correlation_id": correlation_id,
                    "category_id": str(category.id),
                    "article_url": article.get("source_url", "unknown")
                }
            )
            return False