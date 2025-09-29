"""Article extraction module using newspaper4k-master.

This module provides the ArticleExtractor class that wraps newspaper4k-master 
functionality with enhanced error handling, retry logic, structured logging,
and comprehensive data validation.

Key Features:
- Asynchronous article extraction with timeout handling
- Exponential backoff retry logic for network failures
- Comprehensive error handling and logging
- Data validation and cleaning
- Hash generation for deduplication
- Graceful degradation for partial extraction failures

Configuration:
The extractor reads settings from the application configuration and supports
customization of timeouts, retry behavior, and newspaper4k settings.

Example:
    Basic usage with dependency injection:
    
    ```python
    import asyncio
    import logging
    from src.shared.config import get_settings
    from src.core.crawler.extractor import ArticleExtractor
    
    async def extract_article_example():
        # Setup
        settings = get_settings()
        logger = logging.getLogger(__name__)
        
        # Create extractor
        extractor = ArticleExtractor(settings=settings, logger=logger)
        
        # Extract article
        url = "https://example.com/news/article"
        result = await extractor.extract_article_metadata(url)
        
        if result:
            print(f"Title: {result['title']}")
            print(f"Author: {result['author']}")
            print(f"Published: {result['publish_date']}")
            print(f"Content: {result['content'][:100]}...")
            print(f"Image: {result['image_url']}")
            print(f"URL Hash: {result['url_hash']}")
            
        return result
    
    # Run extraction
    asyncio.run(extract_article_example())
    ```
    
    Batch processing with error handling:
    
    ```python
    async def process_multiple_articles(urls):
        settings = get_settings()
        extractor = ArticleExtractor(settings=settings)
        
        results = []
        for url in urls:
            try:
                result = await extractor.extract_article_metadata(url)
                if result:
                    results.append(result)
                else:
                    print(f"Failed to extract: {url}")
            except Exception as e:
                print(f"Error processing {url}: {e}")
        
        return results
    ```

Error Handling:
The module defines custom exceptions for different failure types:
- ExtractionTimeoutError: For timeout scenarios
- ExtractionNetworkError: For network-related failures (retryable)
- ExtractionParsingError: For content parsing failures (non-retryable)

Retry Logic:
Network failures are automatically retried with exponential backoff:
- Base delay: 1 second (configurable)
- Multiplier: 2.0 (configurable)
- Max retries: 3 (configurable)
- Sequence: 1s, 2s, 4s delays

Data Model:
The extracted data follows a consistent schema:
- title (str, required): Article headline
- content (str, nullable): Full article text
- author (str, nullable): Author name(s), comma-separated
- publish_date (datetime, nullable): Publication timestamp
- image_url (str, nullable): Main article image URL
- source_url (str, required): Original article URL
- url_hash (str): SHA-256 hash of source_url
- content_hash (str, nullable): SHA-256 hash of content
- extracted_at (datetime): Timestamp of extraction
"""

import asyncio
import hashlib
import logging
import random
import time
from typing import Dict, Optional, Any, List
from uuid import uuid4
from datetime import datetime, timezone

try:
    from dateutil.parser import parse as parse_date
except ImportError:
    parse_date = None

import sys
import os

# Add newspaper4k-master to path
newspaper_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'newspaper4k-master')
if os.path.exists(newspaper_path):
    sys.path.insert(0, newspaper_path)

from newspaper import Config, Article

# Import sync_playwright for JavaScript rendering
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

from src.shared.config import Settings
from src.shared.exceptions import (
    ExtractionError,
    ExtractionTimeoutError, 
    ExtractionParsingError,
    ExtractionNetworkError
)


class ArticleExtractor:
    """Wrapper for newspaper4k-master with enhanced error handling and retry logic."""
    
    def __init__(self, settings: Settings, logger: Optional[logging.Logger] = None):
        """Initialize the ArticleExtractor with configuration and logger.
        
        Args:
            settings: Application settings instance
            logger: Logger instance for structured logging
        """
        self.settings = settings
        self.logger = logger or logging.getLogger(__name__)
        
        # Configure newspaper4k
        self.config = self._setup_newspaper_config()
        
    def _setup_newspaper_config(self) -> Config:
        """Configure newspaper4k based on application settings.
        
        Returns:
            Configured newspaper4k Config instance
        """
        config = Config()
        config.keep_article_html = self.settings.NEWSPAPER_KEEP_ARTICLE_HTML
        config.language = self.settings.NEWSPAPER_LANGUAGE
        config.memoize_articles = False  # Disable caching for fresh data
        config.fetch_images = self.settings.NEWSPAPER_FETCH_IMAGES
        config.http_success_only = self.settings.NEWSPAPER_HTTP_SUCCESS_ONLY
        
        # Set timeout configurations
        config.request_timeout = self.settings.EXTRACTION_TIMEOUT
        config.number_threads = 1  # Single-threaded for predictable behavior
        
        return config
    
    async def extract_article_metadata(self, url: str) -> Optional[Dict[str, Any]]:
        """Extract article metadata from URL with retry logic.
        
        Args:
            url: Article URL to extract
            
        Returns:
            Dictionary containing extracted article metadata or None if extraction fails
            
        Raises:
            ExtractionError: For critical extraction failures
        """
        correlation_id = str(uuid4())
        
        self.logger.info(
            "Starting article extraction",
            extra={
                "correlation_id": correlation_id,
                "url": url
            }
        )
        
        try:
            return await self._extract_with_retry(url, correlation_id)
        except Exception as e:
            self.logger.error(
                f"Standard extraction failed: {e}",
                extra={
                    "correlation_id": correlation_id,
                    "url": url,
                    "error_type": type(e).__name__
                }
            )

            # Try JavaScript rendering as fallback
            if self.settings.ENABLE_JAVASCRIPT_RENDERING:
                self.logger.info(
                    "Standard extraction failed, attempting JavaScript rendering fallback",
                    extra={
                        "correlation_id": correlation_id,
                        "url": url,
                        "error_type": type(e).__name__
                    }
                )

                try:
                    result = await self._extract_with_javascript_rendering(url, correlation_id)
                    if result:
                        return result
                except Exception as fallback_error:
                    self.logger.error(
                        f"JavaScript rendering fallback also failed: {fallback_error}",
                        extra={
                            "correlation_id": correlation_id,
                            "url": url,
                            "fallback_error": str(fallback_error)
                        }
                    )

            return None
    
    async def _extract_with_retry(self, url: str, correlation_id: str) -> Optional[Dict[str, Any]]:
        """Execute extraction with exponential backoff retry logic.
        
        Args:
            url: Article URL to extract
            correlation_id: Unique identifier for tracking this extraction
            
        Returns:
            Dictionary containing extracted article metadata
        """
        max_retries = self.settings.EXTRACTION_MAX_RETRIES
        base_delay = self.settings.EXTRACTION_RETRY_BASE_DELAY
        multiplier = self.settings.EXTRACTION_RETRY_MULTIPLIER
        
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                # Execute extraction with timeout
                return await self._extract_single_article(url, correlation_id)
                
            except ExtractionTimeoutError as e:
                last_exception = e
                if attempt < max_retries:
                    delay = base_delay * (multiplier ** attempt)
                    self.logger.warning(
                        f"Extraction timeout, retrying in {delay}s",
                        extra={
                            "correlation_id": correlation_id,
                            "attempt": attempt + 1,
                            "max_retries": max_retries,
                            "delay": delay
                        }
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    raise
                    
            except ExtractionNetworkError as e:
                last_exception = e
                if attempt < max_retries:
                    delay = base_delay * (multiplier ** attempt)
                    self.logger.warning(
                        f"Network error, retrying in {delay}s",
                        extra={
                            "correlation_id": correlation_id,
                            "attempt": attempt + 1,
                            "max_retries": max_retries,
                            "delay": delay,
                            "error": str(e)
                        }
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    raise
                    
            except ExtractionParsingError as e:
                # Don't retry parsing errors - they won't resolve with retries
                self.logger.error(
                    f"Parsing error, not retrying: {e}",
                    extra={
                        "correlation_id": correlation_id,
                        "attempt": attempt + 1
                    }
                )
                raise
        
        # This should not be reached, but just in case
        if last_exception:
            raise last_exception
        return None
    
    async def _extract_single_article(self, url: str, correlation_id: str) -> Dict[str, Any]:
        """Extract article data from a single URL.
        
        Args:
            url: Article URL to extract
            correlation_id: Unique identifier for tracking
            
        Returns:
            Dictionary containing extracted article metadata
            
        Raises:
            ExtractionTimeoutError: When extraction times out
            ExtractionParsingError: When article content cannot be parsed
            ExtractionNetworkError: When network-related errors occur
        """
        try:
            # Create Article instance with timeout
            async with asyncio.timeout(self.settings.EXTRACTION_TIMEOUT):
                article = Article(url, config=self.config)

                # Download and parse article content using proper async wrapper
                await self._download_and_parse_article_async(article)
                
        except asyncio.TimeoutError:
            raise ExtractionTimeoutError(f"Extraction timed out after {self.settings.EXTRACTION_TIMEOUT} seconds")
        except Exception as e:
            if "network" in str(e).lower() or "connection" in str(e).lower():
                raise ExtractionNetworkError(f"Network error during extraction: {e}")
            else:
                raise ExtractionParsingError(f"Parsing error during extraction: {e}")
        
        # Extract and validate metadata
        try:
            extracted_data = self._extract_metadata_from_article(article, url)
            
            self.logger.info(
                "Article extraction successful",
                extra={
                    "correlation_id": correlation_id,
                    "url": url,
                    "title_length": len(extracted_data.get("title", "")),
                    "content_length": len(extracted_data.get("content", "")),
                    "has_author": bool(extracted_data.get("author")),
                    "has_publish_date": bool(extracted_data.get("publish_date")),
                    "has_image": bool(extracted_data.get("image_url"))
                }
            )
            
            return extracted_data
            
        except Exception as e:
            raise ExtractionParsingError(f"Failed to extract metadata: {e}")
    
    def _extract_metadata_from_article(self, article: Article, source_url: str) -> Dict[str, Any]:
        """Extract structured metadata from newspaper4k Article object.
        
        Args:
            article: Parsed newspaper4k Article instance
            source_url: Original source URL
            
        Returns:
            Dictionary containing structured article metadata
            
        Raises:
            ExtractionParsingError: If required fields are missing or invalid
        """
        # Extract title (required field)
        title = self._extract_title(article)
        if not title:
            raise ExtractionParsingError("Article title is required but not found")
        
        # Extract content (nullable)
        content = self._extract_content(article)
        
        # Extract author (nullable)
        author = self._extract_author(article)
        
        # Extract publish_date (nullable)
        publish_date = self._extract_publish_date(article)
        
        # Extract image_url (nullable)
        image_url = self._extract_image_url(article)
        
        # Generate hashes for deduplication
        url_hash = hashlib.sha256(source_url.encode('utf-8')).hexdigest()
        content_hash = None
        if content and len(content) > 0:
            content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        
        return {
            "title": title,
            "content": content,
            "author": author,
            "publish_date": publish_date,
            "image_url": image_url,
            "source_url": source_url,
            "url_hash": url_hash,
            "content_hash": content_hash,
            "extracted_at": datetime.now(timezone.utc)
        }
    
    def _extract_title(self, article: Article) -> Optional[str]:
        """Extract and clean article title with fallback strategies.
        
        Args:
            article: newspaper4k Article instance
            
        Returns:
            Cleaned title string or None
        """
        # Primary: Use newspaper4k title
        if hasattr(article, 'title') and article.title:
            title = article.title.strip()
            if title:
                return title
        
        # Fallback: Try meta title
        if hasattr(article, 'meta_data') and article.meta_data:
            meta_title = article.meta_data.get('title', '').strip()
            if meta_title:
                return meta_title
        
        return None
    
    def _extract_content(self, article: Article) -> Optional[str]:
        """Extract and clean article content.
        
        Args:
            article: newspaper4k Article instance
            
        Returns:
            Cleaned content string or None
        """
        if hasattr(article, 'text') and article.text is not None:
            content = article.text.strip()
            # Only return non-empty content with reasonable length
            if content and len(content) > 50:  # Minimum content length
                return content
        
        return None
    
    def _extract_author(self, article: Article) -> Optional[str]:
        """Extract article author with multiple format handling.
        
        Args:
            article: newspaper4k Article instance
            
        Returns:
            Author name string or None
        """
        if hasattr(article, 'authors') and article.authors:
            # Handle list of authors
            if isinstance(article.authors, list) and article.authors:
                # Join multiple authors with comma
                authors = [author.strip() for author in article.authors if author.strip()]
                if authors:
                    return ", ".join(authors)
        
        # Fallback: Check if authors is a string
        if hasattr(article, 'authors') and isinstance(article.authors, str):
            author = article.authors.strip()
            if author:
                return author
        
        return None
    
    def _extract_publish_date(self, article: Article) -> Optional[datetime]:
        """Extract and parse article publish date with validation.
        
        Args:
            article: newspaper4k Article instance
            
        Returns:
            Parsed datetime object or None
        """
        if hasattr(article, 'publish_date') and article.publish_date:
            try:
                # newspaper4k should return datetime object
                if isinstance(article.publish_date, datetime):
                    return article.publish_date
                
                # Fallback: Try to parse if it's a string
                if isinstance(article.publish_date, str) and parse_date:
                    return parse_date(article.publish_date)
                    
            except Exception as e:
                self.logger.warning(f"Failed to parse publish_date: {e}")
        
        return None
    
    def _extract_image_url(self, article: Article) -> Optional[str]:
        """Extract main article image URL with validation.
        
        Args:
            article: newspaper4k Article instance
            
        Returns:
            Valid image URL string or None
        """
        if hasattr(article, 'top_image') and article.top_image:
            image_url = str(article.top_image).strip()
            
            # Basic URL validation
            if image_url and (image_url.startswith('http://') or image_url.startswith('https://')):
                # Optional: Validate image extension
                valid_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')
                if any(image_url.lower().endswith(ext) for ext in valid_extensions):
                    return image_url
                
                # Return URL even without extension - might be dynamic image
                return image_url

        return None

    async def _download_and_parse_article_async(self, article: Article) -> None:
        """Download and parse article using proper async wrappers with timeout handling.

        Args:
            article: newspaper4k Article instance to download and parse

        Raises:
            ExtractionTimeoutError: When download or parse times out
            ExtractionNetworkError: When network-related errors occur
            ExtractionParsingError: When parsing fails
        """
        import concurrent.futures

        # Use a ThreadPoolExecutor for better control over sync operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            try:
                # Download with proper timeout handling
                download_future = executor.submit(article.download)
                try:
                    await asyncio.wait_for(
                        asyncio.wrap_future(download_future),
                        timeout=self.settings.EXTRACTION_TIMEOUT / 2  # Half timeout for download
                    )
                except asyncio.TimeoutError:
                    download_future.cancel()
                    raise ExtractionTimeoutError(
                        url=getattr(article, 'url', 'unknown'),
                        timeout=int(self.settings.EXTRACTION_TIMEOUT / 2)
                    )

                # Parse with proper timeout handling
                parse_future = executor.submit(article.parse)
                try:
                    await asyncio.wait_for(
                        asyncio.wrap_future(parse_future),
                        timeout=self.settings.EXTRACTION_TIMEOUT / 2  # Half timeout for parsing
                    )
                except asyncio.TimeoutError:
                    parse_future.cancel()
                    raise ExtractionTimeoutError(
                        url=getattr(article, 'url', 'unknown'),
                        timeout=int(self.settings.EXTRACTION_TIMEOUT / 2)
                    )

            except ExtractionTimeoutError:
                # Re-raise timeout errors without modification
                raise
            except concurrent.futures.CancelledError:
                raise ExtractionTimeoutError(
                    url=getattr(article, 'url', 'unknown'),
                    timeout=self.settings.EXTRACTION_TIMEOUT
                )
            except Exception as e:
                if "network" in str(e).lower() or "connection" in str(e).lower():
                    raise ExtractionNetworkError(f"Network error during article processing: {e}")
                else:
                    raise ExtractionParsingError(f"Parsing error during article processing: {e}")

    async def _extract_with_javascript_rendering(self, url: str, correlation_id: str) -> Optional[Dict[str, Any]]:
        """Extract article using sync_playwright for JavaScript rendering.

        This method follows the proven pattern from newspaper4k examples.rst (lines 120-168)
        for integrating sync_playwright with newspaper4k.

        Args:
            url: Article URL to extract with JavaScript rendering
            correlation_id: Unique identifier for tracking

        Returns:
            Dictionary containing extracted article metadata or None

        Raises:
            ExtractionTimeoutError: When JavaScript rendering times out
            ExtractionParsingError: When content parsing fails
        """
        if not self.settings.ENABLE_JAVASCRIPT_RENDERING:
            return None

        if sync_playwright is None:
            self.logger.warning(
                "sync_playwright not available, skipping JavaScript rendering",
                extra={"correlation_id": correlation_id, "url": url}
            )
            return None

        self.logger.info(
            "Attempting JavaScript rendering extraction",
            extra={"correlation_id": correlation_id, "url": url}
        )

        try:
            # Use sync_playwright as per newspaper4k-master examples
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=self.settings.PLAYWRIGHT_HEADLESS)
                page = browser.new_page()

                # Set timeout for page operations
                page.set_default_timeout(self.settings.PLAYWRIGHT_TIMEOUT * 1000)

                # Navigate to URL and wait for JavaScript to render
                page.goto(url)
                time.sleep(self.settings.PLAYWRIGHT_WAIT_TIME)  # Allow JavaScript to render

                # Get rendered HTML content
                content = page.content()
                browser.close()

            # Use newspaper4k to parse the rendered content (proven pattern)
            article = Article(url, config=self.config)
            article.set_html(content)  # Use rendered HTML
            article.parse()

            # Extract and validate metadata
            extracted_data = self._extract_metadata_from_article(article, url)

            self.logger.info(
                "JavaScript rendering extraction successful",
                extra={
                    "correlation_id": correlation_id,
                    "url": url,
                    "title_length": len(extracted_data.get("title", "")),
                    "content_length": len(extracted_data.get("content", "")),
                    "method": "sync_playwright"
                }
            )

            return extracted_data

        except Exception as e:
            self.logger.error(
                f"JavaScript rendering extraction failed: {e}",
                extra={
                    "correlation_id": correlation_id,
                    "url": url,
                    "error_type": type(e).__name__,
                    "method": "sync_playwright"
                }
            )
            return None

    async def extract_articles_batch(self, urls: List[str]) -> List[Dict[str, Any]]:
        """Extract articles in batch with Google News optimization.

        Args:
            urls: List of article URLs to extract

        Returns:
            List of dictionaries containing extracted article metadata
        """
        if not urls:
            return []

        # Separate Google News URLs from regular URLs
        google_news_urls = [url for url in urls if 'news.google.com' in url]
        regular_urls = [url for url in urls if 'news.google.com' not in url]

        results = []

        # Process Google News URLs in optimized batches
        if google_news_urls:
            self.logger.info(
                f"Processing {len(google_news_urls)} Google News URLs in batches",
                extra={"batch_size": 10, "total_google_news_urls": len(google_news_urls)}
            )
            google_results = await self._extract_google_news_batch(google_news_urls)
            results.extend(google_results)

        # Process regular URLs with standard method
        if regular_urls:
            self.logger.info(
                f"Processing {len(regular_urls)} regular URLs",
                extra={"total_regular_urls": len(regular_urls)}
            )
            for url in regular_urls:
                try:
                    result = await self.extract_article_metadata(url)
                    if result:
                        results.append(result)
                except Exception as e:
                    self.logger.error(
                        f"Failed to extract regular URL: {e}",
                        extra={"url": url, "error": str(e)}
                    )

        return results

    async def _extract_google_news_batch(self, urls: List[str]) -> List[Dict[str, Any]]:
        """Process Google News URLs in batches of 10 with single browser multi-tab strategy.

        Args:
            urls: List of Google News URLs to process

        Returns:
            List of extracted article metadata
        """
        batch_size = 10
        all_results = []

        for i in range(0, len(urls), batch_size):
            batch = urls[i:i+batch_size]

            self.logger.info(
                f"Processing Google News batch {i//batch_size + 1}",
                extra={
                    "batch_start": i,
                    "batch_size": len(batch),
                    "total_batches": (len(urls) + batch_size - 1) // batch_size
                }
            )

            try:
                batch_results = await self._process_batch_with_single_browser(batch)
                all_results.extend(batch_results)

                # Anti-detection delay between batches (except for last batch)
                if i + batch_size < len(urls):
                    delay = random.randint(5, 10)
                    self.logger.info(
                        f"Anti-detection delay between batches: {delay}s",
                        extra={"delay_seconds": delay}
                    )
                    await asyncio.sleep(delay)

            except Exception as e:
                self.logger.error(
                    f"Batch processing failed: {e}",
                    extra={
                        "batch_start": i,
                        "batch_size": len(batch),
                        "error": str(e)
                    }
                )
                # Add failed results for this batch
                for url in batch:
                    all_results.append({
                        "title": None,
                        "content": None,
                        "author": None,
                        "publish_date": None,
                        "image_url": None,
                        "source_url": url,
                        "url_hash": hashlib.sha256(url.encode('utf-8')).hexdigest(),
                        "content_hash": None,
                        "extracted_at": datetime.now(timezone.utc),
                        "extraction_success": False,
                        "extraction_error": str(e),
                        "extraction_method": "google_news_batch_failed"
                    })

        return all_results

    async def _process_batch_with_single_browser(self, urls_batch: List[str]) -> List[Dict[str, Any]]:
        """Process batch of URLs with single browser multi-tab strategy (max 10 tabs).

        Based on proven pattern from financial_news_extractor.py lines 317-412.

        Args:
            urls_batch: List of URLs to process (max 10)

        Returns:
            List of extracted article metadata
        """
        if sync_playwright is None:
            self.logger.error("sync_playwright not available for Google News extraction")
            return []

        results = []

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
                )

                self.logger.info(
                    f"Started browser for batch processing {len(urls_batch)} URLs",
                    extra={"batch_size": len(urls_batch)}
                )

                # Process each URL in separate tab (configurable limit)
                max_tabs = getattr(self.settings, 'MAX_TABS_PER_BROWSER', 10)
                for i, url in enumerate(urls_batch[:max_tabs]):
                    try:
                        page = browser.new_page()

                        # Ultra-fast settings - block unnecessary resources
                        await page.route(
                            "**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2,ttf,eot,ico}",
                            lambda route: route.abort()
                        )

                        page.set_extra_http_headers({
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                        })

                        self.logger.debug(
                            f"Processing URL {i+1}/{len(urls_batch)}: {url[:80]}...",
                            extra={"tab_index": i, "url_preview": url[:80]}
                        )

                        # Navigate with Google News specific timing
                        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                        await asyncio.sleep(4)  # Critical for Google News redirect
                        final_url = page.url

                        # Handle no redirect case
                        if final_url == url or 'news.google.com' in final_url:
                            try:
                                await page.wait_for_load_state('networkidle', timeout=15000)
                                await asyncio.sleep(5)
                                final_url = page.url
                            except:
                                pass

                        # Extract content if successfully redirected
                        if final_url != url and 'news.google.com' not in final_url:
                            # Use newspaper4k extraction on final URL
                            result = await self._extract_with_newspaper(final_url)
                            if result:
                                result["extraction_method"] = "google_news_playwright"
                                result["google_news_url"] = url
                                result["final_redirected_url"] = final_url
                                results.append(result)
                            else:
                                # Failed extraction but successful redirect
                                results.append({
                                    "title": None,
                                    "content": None,
                                    "author": None,
                                    "publish_date": None,
                                    "image_url": None,
                                    "source_url": final_url,
                                    "url_hash": hashlib.sha256(final_url.encode('utf-8')).hexdigest(),
                                    "content_hash": None,
                                    "extracted_at": datetime.now(timezone.utc),
                                    "extraction_success": False,
                                    "extraction_error": "Content extraction failed after redirect",
                                    "extraction_method": "google_news_playwright_failed",
                                    "google_news_url": url,
                                    "final_redirected_url": final_url
                                })
                        else:
                            # No redirect - failed
                            results.append({
                                "title": None,
                                "content": None,
                                "author": None,
                                "publish_date": None,
                                "image_url": None,
                                "source_url": url,
                                "url_hash": hashlib.sha256(url.encode('utf-8')).hexdigest(),
                                "content_hash": None,
                                "extracted_at": datetime.now(timezone.utc),
                                "extraction_success": False,
                                "extraction_error": "No redirect from Google News URL",
                                "extraction_method": "google_news_no_redirect",
                                "google_news_url": url
                            })

                        page.close()

                        # Anti-detection delay between tabs
                        if i < len(urls_batch) - 1:
                            delay = random.randint(1, 3)
                            await asyncio.sleep(delay)

                    except Exception as e:
                        self.logger.error(
                            f"Tab {i+1} processing failed: {e}",
                            extra={"tab_index": i, "url": url, "error": str(e)}
                        )
                        # Log error but continue with other tabs
                        results.append({
                            "title": None,
                            "content": None,
                            "author": None,
                            "publish_date": None,
                            "image_url": None,
                            "source_url": url,
                            "url_hash": hashlib.sha256(url.encode('utf-8')).hexdigest(),
                            "content_hash": None,
                            "extracted_at": datetime.now(timezone.utc),
                            "extraction_success": False,
                            "extraction_error": str(e),
                            "extraction_method": "google_news_tab_failed",
                            "google_news_url": url
                        })

                browser.close()

        except Exception as e:
            self.logger.error(
                f"Browser session failed: {e}",
                extra={"batch_size": len(urls_batch), "error": str(e)}
            )
            # Return failed results for all URLs
            for url in urls_batch:
                results.append({
                    "title": None,
                    "content": None,
                    "author": None,
                    "publish_date": None,
                    "image_url": None,
                    "source_url": url,
                    "url_hash": hashlib.sha256(url.encode('utf-8')).hexdigest(),
                    "content_hash": None,
                    "extracted_at": datetime.now(timezone.utc),
                    "extraction_success": False,
                    "extraction_error": str(e),
                    "extraction_method": "google_news_browser_failed",
                    "google_news_url": url
                })

        return results

    async def _extract_google_news_with_playwright(self, url: str, correlation_id: str) -> Optional[Dict[str, Any]]:
        """Extract single Google News URL using Playwright as PRIMARY method.

        Args:
            url: Google News URL to extract
            correlation_id: Unique identifier for tracking

        Returns:
            Dictionary containing extracted article metadata or None
        """
        batch_results = await self._process_batch_with_single_browser([url])
        if batch_results:
            result = batch_results[0]
            if result.get("extraction_success", False) or result.get("final_redirected_url"):
                return result
        return None

    async def _extract_with_newspaper(self, url: str) -> Optional[Dict[str, Any]]:
        """Extract article using newspaper4k with async wrapper.

        Args:
            url: Article URL to extract

        Returns:
            Dictionary containing extracted article metadata or None
        """
        try:
            article = Article(url, config=self.config)
            await self._download_and_parse_article_async(article)

            extracted_data = self._extract_metadata_from_article(article, url)
            extracted_data["extraction_success"] = True
            return extracted_data

        except Exception as e:
            self.logger.error(
                f"Newspaper extraction failed: {e}",
                extra={"url": url, "error": str(e)}
            )
            return None
