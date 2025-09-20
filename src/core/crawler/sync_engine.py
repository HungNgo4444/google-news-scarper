"""Sync crawler engine for Celery tasks.

Uses synchronous operations and newspaper4k built-in threading
to avoid event loop conflicts in Celery workers.
"""

import logging
import sys
import os
import requests
import time
from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs

# Add newspaper4k-master to path
newspaper_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'newspaper4k-master')
if os.path.exists(newspaper_path):
    sys.path.insert(0, newspaper_path)

try:
    from newspaper.google_news import GoogleNewsSource
    from newspaper.mthreading import fetch_news
    from newspaper import Article
except ImportError as e:
    GoogleNewsSource = None
    fetch_news = None
    Article = None
    print(f"Warning: newspaper4k imports failed: {e}")

# Try to import playwright for fallback URL resolution
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

from src.shared.config import Settings
from src.shared.exceptions import (
    CrawlerError,
    GoogleNewsUnavailableError,
    ExtractionError
)

logger = logging.getLogger(__name__)


class SyncCrawlerEngine:
    """Sync crawler engine for Celery workers.

    Uses newspaper4k threading and synchronous operations
    to avoid async/await conflicts.
    """

    def __init__(self, settings: Settings, logger: logging.Logger):
        self.settings = settings
        self.logger = logger

        # Validate dependencies
        if not GoogleNewsSource:
            raise CrawlerError("GoogleNewsSource not available - check newspaper4k installation")
        if not fetch_news:
            raise CrawlerError("fetch_news not available - check newspaper4k installation")

    def resolve_google_news_urls(self, google_news_urls: List[str]) -> List[str]:
        """Resolve Google News redirect URLs to actual article URLs.

        This is the critical fix for the 0% success rate issue.
        Google News returns redirect URLs that newspaper4k cannot process.

        Args:
            google_news_urls: List of Google News URLs from gnews

        Returns:
            List of resolved actual article URLs

        Raises:
            CrawlerError: If URL resolution fails completely
        """
        if not google_news_urls:
            return []

        # CRITICAL FIX: Optimized circuit breaker to prevent timeouts and ensure article extraction
        MAX_URLS_TO_PROCESS = getattr(self.settings, 'MAX_URLS_TO_PROCESS', 15)  # Reduced: ensure we finish URL resolution in time
        MAX_PROCESSING_TIME = getattr(self.settings, 'MAX_URL_PROCESSING_TIME', 75)   # Reduced: allow time for article extraction phase

        import time
        start_time = time.time()

        # Limit the number of URLs to process
        urls_to_process = google_news_urls[:MAX_URLS_TO_PROCESS]
        if len(google_news_urls) > MAX_URLS_TO_PROCESS:
            self.logger.warning(f"Limiting URL processing to {MAX_URLS_TO_PROCESS} out of {len(google_news_urls)} URLs to prevent infinite loops")

        resolved_urls = []
        failed_count = 0

        self.logger.info(f"Resolving {len(urls_to_process)} Google News URLs to actual article URLs (max time: {MAX_PROCESSING_TIME}s)")

        for i, google_url in enumerate(urls_to_process):
            # Circuit breaker: Check global time limit
            elapsed_time = time.time() - start_time
            if elapsed_time > MAX_PROCESSING_TIME:
                self.logger.warning(f"URL resolution stopped after {elapsed_time:.1f}s to prevent infinite loops. Processed {i}/{len(urls_to_process)} URLs.")
                break

            # CRITICAL: Per-URL timeout to prevent single URLs from blocking entire job
            url_start_time = time.time()
            MAX_URL_TIME = 5  # Maximum 5 seconds per URL

            try:
                # Strategy 1: Extract URL from Google News redirect parameter
                resolved_url = self._extract_url_from_google_redirect(google_url)

                if resolved_url:
                    resolved_urls.append(resolved_url)
                    continue

                # CRITICAL: Check per-URL timeout after each strategy
                if time.time() - url_start_time > MAX_URL_TIME:
                    self.logger.warning(f"URL {i+1} timed out after {MAX_URL_TIME}s, skipping: {google_url[:100]}...")
                    failed_count += 1
                    continue

                # Strategy 2: Follow redirects with requests
                resolved_url = self._follow_redirect_with_requests(google_url)

                if resolved_url:
                    resolved_urls.append(resolved_url)
                    continue

                # CRITICAL: Check per-URL timeout after each strategy
                if time.time() - url_start_time > MAX_URL_TIME:
                    self.logger.warning(f"URL {i+1} timed out after {MAX_URL_TIME}s, skipping: {google_url[:100]}...")
                    failed_count += 1
                    continue

                # Strategy 3: Simple regex-based URL extraction from the URL itself
                resolved_url = self._extract_url_from_base64_or_encoded(google_url)
                if resolved_url:
                    resolved_urls.append(resolved_url)
                    continue

                # Strategy 4: Playwright fallback for JavaScript redirects (only if enabled and other methods failed)
                if sync_playwright and getattr(self.settings, 'ENABLE_JAVASCRIPT_RENDERING', False):
                    resolved_url = self._resolve_with_playwright(google_url)

                    if resolved_url:
                        resolved_urls.append(resolved_url)
                        continue

                failed_count += 1
                self.logger.warning(f"Failed to resolve URL {i+1}/{len(google_news_urls)}: {google_url[:100]}...")

            except Exception as e:
                failed_count += 1
                self.logger.warning(f"Error resolving URL {i+1}/{len(google_news_urls)}: {e}")
                continue

        success_rate = (len(resolved_urls) / len(google_news_urls)) * 100 if google_news_urls else 0
        self.logger.info(f"URL resolution completed: {len(resolved_urls)}/{len(google_news_urls)} URLs resolved ({success_rate:.1f}% success rate)")

        if success_rate < 20:  # Less than 20% success rate
            self.logger.error(f"Very low URL resolution success rate: {success_rate:.1f}%")

        return resolved_urls

    def _extract_url_from_google_redirect(self, google_url: str) -> Optional[str]:
        """Extract actual URL from Google News redirect parameter.

        Google News URLs often contain the actual URL as a parameter.
        """
        try:
            parsed = urlparse(google_url)

            # Check for 'url' parameter in query string
            query_params = parse_qs(parsed.query)
            if 'url' in query_params and query_params['url']:
                actual_url = query_params['url'][0]
                if actual_url.startswith('http'):
                    return actual_url

            # Check for URL in the path (some Google News formats)
            if '/articles/' in google_url and 'url=' in google_url:
                url_start = google_url.find('url=') + 4
                url_end = google_url.find('&', url_start)
                if url_end == -1:
                    url_end = len(google_url)

                potential_url = google_url[url_start:url_end]
                if potential_url.startswith('http'):
                    return potential_url

        except Exception as e:
            self.logger.warning(f"Failed to extract URL from redirect parameter: {e}")

        return None

    def _extract_url_from_base64_or_encoded(self, google_url: str) -> Optional[str]:
        """Extract URL from base64 or encoded Google News URL components.

        Args:
            google_url: Google News URL that might contain encoded article URL

        Returns:
            Decoded article URL or None if not found
        """
        import base64
        import urllib.parse

        try:
            # Google News URLs sometimes contain the actual URL in encoded form
            # Check for base64 encoded URLs in the path
            if '/articles/' in google_url:
                # Extract the article ID part
                article_id = google_url.split('/articles/')[-1].split('?')[0]

                # Try to decode as base64 (sometimes URLs are base64 encoded)
                try:
                    # Remove any URL-safe base64 characters and try decoding
                    cleaned_id = article_id.replace('-', '+').replace('_', '/')
                    # Add padding if needed
                    while len(cleaned_id) % 4:
                        cleaned_id += '='

                    decoded = base64.b64decode(cleaned_id).decode('utf-8', errors='ignore')

                    # Look for HTTP URLs in the decoded content
                    if 'http' in decoded:
                        # Extract URL using regex
                        import re
                        url_pattern = r'https?://[^\s<>"\'\[\]{}|\\^`]*'
                        urls = re.findall(url_pattern, decoded)
                        for url in urls:
                            if 'google.com' not in url and url.startswith('http'):
                                self.logger.info(f"Extracted URL from base64: {url}")
                                return url

                except Exception:
                    pass  # Base64 decoding failed, continue with other methods

                # Try URL decoding
                try:
                    decoded_url = urllib.parse.unquote(article_id)
                    if decoded_url.startswith('http') and 'google.com' not in decoded_url:
                        self.logger.info(f"Extracted URL from URL encoding: {decoded_url}")
                        return decoded_url
                except Exception:
                    pass

        except Exception as e:
            self.logger.debug(f"Base64/encoded URL extraction failed: {e}")

        return None

    def _follow_redirect_with_requests(self, google_url: str) -> Optional[str]:
        """Follow redirects using requests to get the final URL.

        Args:
            google_url: Google News URL to resolve

        Returns:
            Final resolved URL or None if failed
        """
        try:
            # CRITICAL FIX: Aggressive circuit breaker to prevent infinite loops
            # Use minimal redirects and timeout to avoid getting stuck
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            }

            # CRITICAL: Use manual redirect following with strict limits
            MAX_REDIRECTS = 3
            current_url = google_url

            for redirect_count in range(MAX_REDIRECTS + 1):
                response = requests.head(
                    current_url,
                    headers=headers,
                    allow_redirects=False,  # Handle redirects manually
                    timeout=3,  # Optimized: 3 seconds to speed up processing
                    stream=False  # Don't download content
                )

                # If not a redirect, we're done
                if response.status_code not in (301, 302, 303, 307, 308):
                    break

                # Get redirect location
                location = response.headers.get('Location')
                if not location:
                    break

                # Stop if we reached max redirects
                if redirect_count >= MAX_REDIRECTS:
                    self.logger.warning(f"Maximum redirects ({MAX_REDIRECTS}) reached for {google_url}")
                    return None

                current_url = location

            # Get the final URL after all redirects
            final_url = current_url

            # CRITICAL: Validate that we got a real article URL (not staying on Google)
            if final_url and not 'google.com' in final_url and final_url.startswith('http'):
                return final_url

        except Exception as e:
            self.logger.warning(f"Requests redirect resolution failed: {e}")

        return None

    def _resolve_with_playwright(self, google_url: str) -> Optional[str]:
        """Resolve URL using Playwright for JavaScript-heavy redirects.

        Args:
            google_url: Google News URL to resolve

        Returns:
            Final resolved URL or None if failed
        """
        import re

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                # Set user agent to avoid detection
                page.set_extra_http_headers({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                })

                # Set timeout
                page.set_default_timeout(10000)  # 10 seconds

                # Navigate to Google News URL
                response = page.goto(google_url)

                # Check if we got redirected away from Google
                final_url = page.url
                if final_url and 'google.com' not in final_url and final_url.startswith('http'):
                    browser.close()
                    return final_url

                # If still on Google domain, try to extract the actual article URL from page content
                if response and response.status == 200:
                    # Wait briefly for any dynamic content
                    time.sleep(1)

                    # Get page content
                    content = page.content()

                    # Look for actual article URLs in the page content
                    url_patterns = [
                        r'"(https?://(?!(?:news\.)?google\.com)[^"]+\.(?:com|org|net|gov|edu|uk|ca|au|de|fr|jp|cn)[^"]*)"',  # External URLs in quotes
                        r'href="(https?://(?!(?:news\.)?google\.com)[^"]+\.(?:com|org|net|gov|edu|uk|ca|au|de|fr|jp|cn)[^"]*)"',  # href attributes
                        r'url=(https?://(?!(?:news\.)?google\.com)[^&"\\s]+\.(?:com|org|net|gov|edu|uk|ca|au|de|fr|jp|cn)[^&"\\s]*)',  # url parameter
                        r'data-url="(https?://(?!(?:news\.)?google\.com)[^"]+\.(?:com|org|net|gov|edu|uk|ca|au|de|fr|jp|cn)[^"]*)"',  # data-url attributes
                    ]

                    found_urls = set()
                    for pattern in url_patterns:
                        matches = re.findall(pattern, content, re.IGNORECASE)
                        for match in matches:
                            # Clean up URL (remove any trailing characters)
                            clean_url = match.split('&')[0].split('#')[0].split('?')[0]
                            if (clean_url.startswith('http') and
                                'google.com' not in clean_url and
                                not clean_url.endswith('.js') and
                                not clean_url.endswith('.css') and
                                not clean_url.endswith('.png') and
                                not clean_url.endswith('.jpg')):
                                found_urls.add(clean_url)

                    browser.close()

                    if found_urls:
                        # Return the first valid URL found
                        result_url = next(iter(found_urls))
                        self.logger.info(f"Extracted article URL from Google News page: {result_url}")
                        return result_url
                    else:
                        self.logger.warning(f"No external URLs found in Google News page content")
                else:
                    browser.close()
                    self.logger.warning(f"Failed to load Google News page, status: {response.status if response else 'None'}")

        except Exception as e:
            self.logger.warning(f"Playwright URL resolution failed: {e}")

        return None

    def search_google_news(
        self,
        keywords: List[str],
        exclude_keywords: List[str] = None,
        max_results: int = 100,
        language: str = "en",
        country: str = "US"
    ) -> List[str]:
        """Search Google News using sync operations.

        Args:
            keywords: List of keywords to search for (OR logic)
            exclude_keywords: List of keywords to exclude from results
            max_results: Maximum number of results to return
            language: Language code for search results
            country: Country code for search results

        Returns:
            List of resolved article URLs (not Google News URLs)

        Raises:
            GoogleNewsUnavailableError: If search fails
        """
        if not keywords:
            raise GoogleNewsUnavailableError("Keywords list cannot be empty")

        try:
            # Build search query with OR logic for keywords
            search_query = " OR ".join(f'"{keyword}"' for keyword in keywords)

            # Add exclusions if provided
            if exclude_keywords:
                exclusions = " ".join(f'-"{keyword}"' for keyword in exclude_keywords)
                search_query = f"{search_query} {exclusions}"

            self.logger.info(f"Searching Google News with query: {search_query}")

            # Use GNews with enhanced URL resolution strategy
            import gnews

            gn = gnews.GNews(
                language=language.lower(),
                country=country,
                max_results=max_results
            )

            # Search using GNews directly
            search_results = gn.get_news(search_query)

            if not search_results:
                self.logger.warning(f"No results found for query: {search_query}")
                return []

            # Log some sample results for debugging
            if search_results:
                sample = search_results[0]
                self.logger.info(f"Sample result: {sample.get('title', 'No title')}")
                self.logger.info(f"Sample Google URL: {sample.get('url', 'No URL')[:100]}...")

            # Enhanced approach: Try to get full article details first
            all_resolved_urls = []
            google_news_urls = []

            for i, result in enumerate(search_results):
                google_url = result.get('url')
                if not google_url:
                    continue

                try:
                    # Strategy 1: Try to get full article details from gnews
                    # This sometimes provides the actual article URL
                    full_article = gn.get_full_article(google_url)
                    if full_article and hasattr(full_article, 'url') and full_article.url:
                        actual_url = full_article.url
                        if actual_url.startswith('http') and 'google.com' not in actual_url:
                            all_resolved_urls.append(actual_url)
                            self.logger.info(f"Resolved via gnews full article: {actual_url}")
                            continue

                except Exception as e:
                    self.logger.debug(f"gnews full article failed for URL {i+1}: {e}")

                # Strategy 2: Add to list for traditional resolution methods
                google_news_urls.append(google_url)

            # For remaining URLs, use traditional resolution methods
            if google_news_urls:
                self.logger.info(f"Attempting traditional resolution for {len(google_news_urls)} URLs")
                traditional_resolved = self.resolve_google_news_urls(google_news_urls)
                all_resolved_urls.extend(traditional_resolved)

            self.logger.info(f"Total resolved URLs: {len(all_resolved_urls)} from {len(search_results)} Google News results")
            return all_resolved_urls

        except Exception as e:
            error_msg = f"Failed to search Google News: {str(e)}"
            self.logger.error(error_msg)
            raise GoogleNewsUnavailableError(error_msg) from e

    def extract_articles_with_threading(
        self,
        urls: List[str],
        threads: int = 5
    ) -> List[Dict[str, Any]]:
        """Extract articles using newspaper4k threading.

        Args:
            urls: List of article URLs to extract
            threads: Number of threads to use for extraction

        Returns:
            List of extracted article data

        Raises:
            ExtractionError: If extraction fails
        """
        if not urls:
            return []

        try:
            self.logger.info(f"Extracting {len(urls)} articles with {threads} threads")

            # Create Article objects for URLs
            articles = [Article(url) for url in urls]

            # Use newspaper4k threading to download and parse
            processed_articles = fetch_news(articles, threads=threads)

            # Convert to our format
            extracted_data = []
            for article in processed_articles:
                try:
                    # Enhanced validation
                    if not article.title or not article.text:
                        self.logger.warning(f"Article missing title or text: {article.url}")
                        continue

                    # Additional validation for minimum content quality
                    if len(article.text.strip()) < 100:  # Minimum content length
                        self.logger.warning(f"Article content too short: {article.url}")
                        continue

                    article_data = {
                        'url': article.url,
                        'title': article.title,
                        'content': article.text,
                        'summary': article.summary if hasattr(article, 'summary') else None,
                        'authors': list(article.authors) if article.authors else [],
                        'publish_date': article.publish_date,
                        'top_image': article.top_image,
                        'meta_keywords': article.meta_keywords if hasattr(article, 'meta_keywords') else [],
                        'extracted_at': datetime.now(timezone.utc),
                        'word_count': len(article.text.split()) if article.text else 0
                    }

                    extracted_data.append(article_data)

                except Exception as e:
                    self.logger.warning(f"Failed to process article {article.url}: {e}")
                    continue

            success_rate = (len(extracted_data) / len(urls)) * 100 if urls else 0
            self.logger.info(f"Successfully extracted {len(extracted_data)}/{len(urls)} articles ({success_rate:.1f}% success rate)")

            return extracted_data

        except Exception as e:
            error_msg = f"Failed to extract articles: {str(e)}"
            self.logger.error(error_msg)
            raise ExtractionError(error_msg) from e

    def crawl_category_sync(self, category: Any) -> List[Dict[str, Any]]:
        """Crawl articles for a category using sync operations.

        Args:
            category: Category model instance with keywords

        Returns:
            List of extracted article data

        Raises:
            CrawlerError: For general crawler failures
        """
        try:
            self.logger.info(f"Starting sync crawl for category: {category.name}")

            # Step 1: Search Google News with category-specific language/country
            max_results = getattr(self.settings, 'MAX_RESULTS_PER_SEARCH', 100)

            # Use category-specific language and country, fallback to defaults
            language = getattr(category, 'language', 'vi')
            country = getattr(category, 'country', 'VN')

            self.logger.info(f"Searching with language='{language}', country='{country}' for category: {category.name}")

            # Get resolved article URLs (not Google News URLs)
            article_urls = self.search_google_news(
                keywords=category.keywords,
                exclude_keywords=category.exclude_keywords or [],
                max_results=max_results,
                language=language,
                country=country
            )

            if not article_urls:
                self.logger.warning(f"No resolved article URLs found for category: {category.name}")
                return {
                    'articles_found': 0,
                    'articles_saved': 0,
                    'extracted_articles': []
                }

            # Step 2: Extract articles using threading
            threads = getattr(self.settings, 'EXTRACTION_THREADS', 5)
            extracted_articles = self.extract_articles_with_threading(
                urls=article_urls,
                threads=threads
            )

            # Step 3: Save articles to database
            if extracted_articles:
                from src.database.repositories.sync_article_repo import SyncArticleRepository

                article_repo = SyncArticleRepository()
                saved_count = article_repo.save_articles_with_deduplication(
                    extracted_articles, category.id
                )

                self.logger.info(f"Crawled {len(extracted_articles)} articles, saved {saved_count} to database for category: {category.name}")

                # Return results with saved count information
                return {
                    'articles_found': len(extracted_articles),
                    'articles_saved': saved_count,
                    'extracted_articles': extracted_articles
                }
            else:
                self.logger.warning(f"No articles extracted for category: {category.name}")
                return {
                    'articles_found': 0,
                    'articles_saved': 0,
                    'extracted_articles': []
                }

        except Exception as e:
            error_msg = f"Failed to crawl category {category.name}: {str(e)}"
            self.logger.error(error_msg)
            raise CrawlerError(error_msg) from e