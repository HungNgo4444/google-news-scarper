"""Crawler package for article extraction and processing.

This package provides the ArticleExtractor class that wraps newspaper4k-master
functionality with enhanced error handling, retry logic, and structured data extraction.

Example:
    Basic usage with default settings:
    
    ```python
    import logging
    from src.shared.config import get_settings
    from src.core.crawler.extractor import ArticleExtractor
    
    # Initialize with settings
    settings = get_settings()
    logger = logging.getLogger(__name__)
    
    # Create extractor instance
    extractor = ArticleExtractor(settings=settings, logger=logger)
    
    # Extract article metadata
    result = await extractor.extract_article_metadata("https://example.com/article")
    
    if result:
        print(f"Title: {result['title']}")
        print(f"Author: {result['author']}")
        print(f"Content length: {len(result['content'] or '')}")
    ```

Configuration:
    The extractor uses the following configuration settings from Settings:
    
    - EXTRACTION_TIMEOUT: Maximum time for extraction (default: 30 seconds)
    - EXTRACTION_MAX_RETRIES: Maximum retry attempts (default: 3)
    - EXTRACTION_RETRY_BASE_DELAY: Base delay for exponential backoff (default: 1.0s)
    - EXTRACTION_RETRY_MULTIPLIER: Backoff multiplier (default: 2.0)
    - NEWSPAPER_LANGUAGE: Language setting for newspaper4k (default: "en")
    - NEWSPAPER_KEEP_ARTICLE_HTML: Keep HTML in memory (default: True)
    - NEWSPAPER_FETCH_IMAGES: Fetch article images (default: True)
    - NEWSPAPER_HTTP_SUCCESS_ONLY: Only process successful HTTP responses (default: True)
"""

from .extractor import ArticleExtractor

__all__ = ["ArticleExtractor"]