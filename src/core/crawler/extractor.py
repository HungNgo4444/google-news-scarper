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
from typing import Dict, Optional, Any
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
                f"Final extraction failure: {e}",
                extra={
                    "correlation_id": correlation_id,
                    "url": url,
                    "error_type": type(e).__name__
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
                
                # Download article content (this is a sync operation)
                await asyncio.get_event_loop().run_in_executor(
                    None, article.download
                )
                
                # Parse article content (this is a sync operation)
                await asyncio.get_event_loop().run_in_executor(
                    None, article.parse
                )
                
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