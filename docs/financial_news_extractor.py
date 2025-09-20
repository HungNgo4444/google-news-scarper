import json
import threading
import time
import base64
import re
import sys
import os
import hashlib
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import calendar

# Fix UTF-8 encoding on Windows
if os.name == 'nt':  # Windows
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

# Custom Exceptions for enhanced error handling
class ExtractionTimeoutError(Exception):
    """Raised when article extraction times out"""
    pass

class ExtractionNetworkError(Exception):
    """Raised for network-related failures (retryable)"""
    pass

class ExtractionParsingError(Exception):
    """Raised for content parsing failures (non-retryable)"""
    pass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import playwright for JS rendering
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
    print("Playwright imported successfully")
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("Playwright not available - using fallback method")

# Import cloudscraper for bypassing Cloudflare
try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
    print("Cloudscraper imported successfully")
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False
    print("Cloudscraper not available - using standard requests")

def setup_newspaper4k():
    """Setup newspaper4k from local source directory"""
    # Add newspaper4k-master to Python path
    newspaper_path = os.path.join(os.getcwd(), 'newspaper4k-master')
    if newspaper_path not in sys.path:
        sys.path.insert(0, newspaper_path)

    try:
        # Import newspaper module from local source
        import newspaper
        from newspaper.google_news import GoogleNewsSource, _ENCODED_URL_RE, _DECODED_URL_RE
        print("newspaper4k imported successfully from local source!")
        return newspaper, _ENCODED_URL_RE, _DECODED_URL_RE
    except ImportError as e:
        print(f"Failed to import newspaper4k from local source: {e}")
        return None, None, None

# Setup libraries
try:
    from gnews import GNews
    print("GNews imported successfully")

    # Setup newspaper4k from local source
    newspaper, _ENCODED_URL_RE, _DECODED_URL_RE = setup_newspaper4k()

    if newspaper is None:
        print("Using fallback regex patterns...")
        # Define regex patterns manually if import fails
        _ENCODED_URL_PREFIX = "https://news.google.com/rss/articles/"
        _ENCODED_URL_RE = re.compile(rf"^{re.escape(_ENCODED_URL_PREFIX)}(?P<encoded_url>[^?]+)")
        _DECODED_URL_RE = re.compile(rb'^\x08\x13".+?(?P<primary_url>http[^\xd2]+)\xd2\x01')
    else:
        # Import the proper regex patterns from newspaper4k
        from newspaper.google_news import _ENCODED_URL_RE, _DECODED_URL_RE

    print("Setup completed successfully!")

except ImportError as e:
    print(f"Error: Could not import required libraries: {e}")
    exit(1)

class FinancialNewsExtractor:
    """
    Enhanced financial news extractor with comprehensive error handling and data validation.

    This class provides robust article extraction from Google News with features including:
    - Asynchronous batch processing with timeout handling
    - Exponential backoff retry logic for network failures
    - Comprehensive error handling and structured logging
    - Data validation and cleaning with hash generation
    - Graceful degradation for partial extraction failures
    """

    def __init__(self, country: str = "VN", max_results: int = 100,
                 retry_attempts: int = 3, base_delay: float = 1.0):
        self.country = country
        self.max_results = max_results
        self.retry_attempts = retry_attempts
        self.base_delay = base_delay
        self.all_results = []
        self.lock = threading.Lock()

        logger.info(f"Initializing FinancialNewsExtractor for {country} with max_results={max_results}")

        # Enhanced financial and crypto keywords for comprehensive coverage
        self.financial_keywords = [
            "bitcoin", "cryptocurrency", "stock market", "finance",
            "trading", "investment", "blockchain", "fintech",
            "chứng khoán", "tài chính", "tiền điện tử", "đầu tư",
            "giao dịch", "thị trường", "ngân hàng", "kinh tế"
        ]

    def generate_url_hash(self, url: str) -> str:
        """Generate SHA-256 hash for URL deduplication"""
        return hashlib.sha256(url.encode('utf-8')).hexdigest()

    def generate_content_hash(self, content: str) -> Optional[str]:
        """Generate SHA-256 hash for content deduplication"""
        if not content:
            return None
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def validate_and_clean_data(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean extracted article data"""
        try:
            # Required fields validation
            source_url = raw_data.get('final_url', raw_data.get('google_news_url', ''))
            if not source_url:
                raise ExtractionParsingError("Missing source URL")

            # Clean and validate data
            cleaned_data = {
                "title": raw_data.get('title', '').strip()[:500] if raw_data.get('title') else None,
                "content": raw_data.get('text', '').strip()[:10000] if raw_data.get('text') else None,
                "author": ', '.join(raw_data.get('authors', [])[:3]) if raw_data.get('authors') else None,
                "publish_date": raw_data.get('publish_date'),
                "image_url": raw_data.get('top_image') if raw_data.get('top_image') else None,
                "source_url": source_url,
                "url_hash": self.generate_url_hash(source_url),
                "content_hash": self.generate_content_hash(raw_data.get('text')),
                "extracted_at": datetime.now()
            }

            # Additional metadata
            cleaned_data.update({
                "summary": raw_data.get('summary', '').strip()[:1500] if raw_data.get('summary') else None,
                "keywords": raw_data.get('keywords', [])[:15] if raw_data.get('keywords') else [],
                "images": raw_data.get('images', [])[:5] if raw_data.get('images') else [],
                "publisher": raw_data.get('publisher_title', '').strip() if raw_data.get('publisher_title') else None,
                "matched_keywords": raw_data.get('matched_keywords', []),
                "extraction_success": raw_data.get('success', False)
            })

            return cleaned_data

        except Exception as e:
            logger.error(f"Data validation failed: {e}")
            raise ExtractionParsingError(f"Data validation failed: {e}")

    def retry_with_backoff(self, func, *args, **kwargs):
        """Execute function with exponential backoff retry logic"""
        last_exception = None

        for attempt in range(self.retry_attempts):
            try:
                return func(*args, **kwargs)
            except ExtractionNetworkError as e:
                last_exception = e
                if attempt < self.retry_attempts - 1:
                    delay = self.base_delay * (2 ** attempt)
                    logger.warning(f"Network error on attempt {attempt + 1}, retrying in {delay}s: {e}")
                    time.sleep(delay)
                else:
                    logger.error(f"All {self.retry_attempts} attempts failed: {e}")
            except (ExtractionTimeoutError, ExtractionParsingError) as e:
                # Non-retryable errors
                logger.error(f"Non-retryable error: {e}")
                raise e
            except Exception as e:
                # Unexpected errors - convert to network error for retry
                last_exception = ExtractionNetworkError(f"Unexpected error: {e}")
                if attempt < self.retry_attempts - 1:
                    delay = self.base_delay * (2 ** attempt)
                    logger.warning(f"Unexpected error on attempt {attempt + 1}, retrying in {delay}s: {e}")
                    time.sleep(delay)

        raise last_exception or ExtractionNetworkError("All retry attempts failed")

    def decode_google_news_url(self, encoded_url: str) -> str:
        """Decode Google News encoded URL using improved method"""
        try:
            # First try newspaper4k's method if available
            if _ENCODED_URL_RE and _DECODED_URL_RE:
                match = _ENCODED_URL_RE.match(encoded_url)
                if match:
                    encoded_text = match.groupdict()["encoded_url"]
                    encoded_text += "==="
                    decoded_text = base64.urlsafe_b64decode(encoded_text)

                    url_match = _DECODED_URL_RE.match(decoded_text)
                    if url_match:
                        primary_url = url_match.groupdict()["primary_url"]
                        return primary_url.decode()

            # New method for current Google News format
            if 'articles/' in encoded_url:
                try:
                    # Extract encoded part after 'articles/'
                    encoded_part = encoded_url.split('articles/')[-1]
                    # Remove URL parameters
                    if '?' in encoded_part:
                        encoded_part = encoded_part.split('?')[0]

                    # Add padding for proper base64 decoding
                    encoded_part += '==='

                    # Decode the base64 encoded URL
                    decoded_bytes = base64.urlsafe_b64decode(encoded_part)

                    # Enhanced patterns for current Google News format
                    url_patterns = [
                        # Look for full URLs starting with http
                        rb'(https?://[^\x00-\x1f\x7f-\x9f\xd2]+)',
                        # Alternative pattern for common domains
                        rb'(https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}[^\x00-\x1f\x7f-\x9f\xd2]*)',
                        # Broad pattern
                        rb'(https?://[^\x00\xd2"]+)',
                        # Very broad pattern
                        rb'(https?://[^"\x00]+)',
                    ]

                    for i, pattern in enumerate(url_patterns):
                        matches = re.findall(pattern, decoded_bytes)
                        for match in matches:
                            try:
                                actual_url = match.decode('utf-8', errors='ignore')
                                # Clean up the URL
                                actual_url = actual_url.rstrip('\\x00\\xd2\\x01"\\x03\\x04')
                                # Validate URL format
                                if actual_url.startswith(('http://', 'https://')) and '.' in actual_url:
                                    # Additional cleaning
                                    if '\\x' in actual_url:
                                        actual_url = actual_url.split('\\x')[0]
                                    return actual_url
                            except:
                                continue

                    # If no URL found, try to extract from protobuf-like structure
                    # Look for common news domains
                    common_domains = [b'cnn.com', b'reuters.com', b'bloomberg.com', b'wsj.com',
                                    b'marketwatch.com', b'cnbc.com', b'yahoo.com', b'finance.yahoo.com',
                                    b'investing.com', b'seekingalpha.com', b'campaignlegal.org']

                    for domain in common_domains:
                        if domain in decoded_bytes:
                            # Try to construct URL around the domain
                            domain_str = domain.decode()
                            return f"https://{domain_str}"

                except Exception as decode_error:
                    print(f"    Specific decode error: {decode_error}")

            # Return original URL if all methods fail
            return encoded_url

        except Exception as e:
            print(f"    URL decode error: {e}")
            return encoded_url

    def extract_batch_with_playwright(self, google_urls_batch: list) -> list:
        """Extract multiple URLs using 5 browsers with 10 tabs each"""
        if not PLAYWRIGHT_AVAILABLE:
            return [{"success": False, "error": "Playwright not available"} for _ in google_urls_batch]

        results = []

        try:
            # Process URLs in batches of 50 (5 browsers x 10 tabs)
            batch_size = 50
            for i in range(0, len(google_urls_batch), batch_size):
                batch = google_urls_batch[i:i+batch_size]
                print(f"Processing mega-batch {i//batch_size + 1}: {len(batch)} URLs with 5 browsers")
                batch_results = self._process_with_browser_pool(batch)
                results.extend(batch_results)

        except Exception as e:
            print(f"Batch processing error: {e}")
            # Return failed results for all URLs
            results = [{"success": False, "error": str(e)} for _ in google_urls_batch]

        return results

    def _process_with_browser_pool(self, urls_batch: list) -> list:
        """Process URLs with 5 browsers, each handling 10 tabs"""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading

        results = [None] * len(urls_batch)

        def create_browser_worker(browser_id, urls_for_browser):
            """Each browser worker handles up to 10 URLs with tabs"""
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(
                        headless=True,
                        args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--max_old_space_size=512']
                    )

                    print(f"    Browser {browser_id+1}: Starting with {len(urls_for_browser)} URLs")

                    # Process all URLs for this browser with tabs
                    browser_results = []

                    # Create tabs for all URLs in this browser
                    for tab_id, (url_index, url) in enumerate(urls_for_browser):
                        try:
                            page = browser.new_page()

                            # Ultra-fast settings
                            page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2,ttf,eot,ico}", lambda route: route.abort())
                            page.set_extra_http_headers({
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                            })

                            print(f"      Browser {browser_id+1} Tab {tab_id+1}: Starting {url[:50]}...")

                            # Navigate with timeout
                            page.goto(url, wait_until='domcontentloaded', timeout=30000)

                            # Wait for JS redirect
                            time.sleep(4)
                            final_url = page.url

                            # If no redirect, wait longer
                            if final_url == url or 'news.google.com' in final_url:
                                try:
                                    page.wait_for_load_state('networkidle', timeout=15000)
                                    time.sleep(5)
                                    final_url = page.url
                                except:
                                    pass

                            print(f"      Browser {browser_id+1} Tab {tab_id+1}: Got {final_url[:50]}...")

                            # Extract content
                            if final_url != url and 'news.google.com' not in final_url:
                                if newspaper:
                                    try:
                                        article = newspaper.Article(final_url, language='vi')
                                        article.download()
                                        article.parse()

                                        result = {
                                            "success": True,
                                            "error": None,
                                            "final_url": final_url,
                                            "content": article.html[:1500] if article.html else None,
                                            "text": article.text[:4000] if article.text else None,
                                            "authors": article.authors[:2] if article.authors else [],
                                            "publish_date": str(article.publish_date) if article.publish_date else None,
                                            "top_image": article.top_image if article.top_image else None,
                                            "images": list(article.images)[:3] if article.images else [],
                                            "keywords": list(article.keywords)[:10] if hasattr(article, 'keywords') and article.keywords else [],
                                            "summary": article.summary[:800] if hasattr(article, 'summary') and article.summary else None,
                                            "title": article.title if article.title else None
                                        }
                                    except Exception as e:
                                        result = {
                                            "success": False,
                                            "error": f"Extraction failed: {str(e)[:100]}",
                                            "final_url": final_url,
                                            "content": None, "text": None, "authors": [], "publish_date": None,
                                            "top_image": None, "images": [], "keywords": [], "summary": None, "title": None
                                        }
                                else:
                                    result = {"success": False, "error": "newspaper4k not available", "final_url": final_url}
                            else:
                                result = {"success": False, "error": "No redirect", "final_url": final_url}

                            browser_results.append((url_index, result))
                            page.close()

                        except Exception as e:
                            print(f"      Browser {browser_id+1} Tab {tab_id+1}: Error: {str(e)[:50]}")
                            browser_results.append((url_index, {"success": False, "error": str(e)[:100], "final_url": url}))

                    browser.close()
                    print(f"    Browser {browser_id+1}: Completed {len(browser_results)} URLs")
                    return browser_results

            except Exception as e:
                print(f"    Browser {browser_id+1}: Critical error: {e}")
                return [(url_index, {"success": False, "error": str(e), "final_url": url})
                       for url_index, url in urls_for_browser]

        # Split URLs into 5 groups for 5 browsers (max 10 URLs per browser)
        browser_groups = []
        urls_per_browser = 10

        for i in range(0, len(urls_batch), urls_per_browser):
            browser_urls = []
            for j, url in enumerate(urls_batch[i:i+urls_per_browser]):
                browser_urls.append((i + j, url))  # (original_index, url)
            browser_groups.append(browser_urls)

        print(f"    Created {len(browser_groups)} browser groups")

        # Run 5 browsers in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=5) as executor:
            # Submit browser workers
            futures = {executor.submit(create_browser_worker, i, group): i
                      for i, group in enumerate(browser_groups)}

            # Collect results from all browsers
            for future in as_completed(futures, timeout=400):  # 6+ minutes for all browsers
                try:
                    browser_results = future.result(timeout=120)  # 2 minutes per browser
                    # Place results in correct positions
                    for url_index, result in browser_results:
                        results[url_index] = result

                except Exception as e:
                    browser_id = futures[future]
                    print(f"    Browser {browser_id+1}: Failed with error: {e}")
                    # Fill failed results for this browser's URLs
                    for url_index, url in browser_groups[browser_id]:
                        if results[url_index] is None:
                            results[url_index] = {"success": False, "error": f"Browser failed: {e}", "final_url": url}

        # Fill any remaining None results
        for i, result in enumerate(results):
            if result is None:
                results[i] = {"success": False, "error": "No result", "final_url": urls_batch[i]}

        return results

    def _process_tab_batch(self, browser, urls_batch):
        """Process a batch of URLs with separate browser instances per thread"""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results = [None] * len(urls_batch)

        def process_url_with_own_browser(index, url):
            """Process single URL with its own browser instance"""
            browser_instance = None
            try:
                # Create separate browser instance for this thread
                with sync_playwright() as p:
                    browser_instance = p.chromium.launch(
                        headless=True,
                        args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--max_old_space_size=256']
                    )

                    # Create page in this thread's browser
                    page = browser_instance.new_page()

                    # Ultra-fast settings
                    page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2,ttf,eot,ico}", lambda route: route.abort())
                    page.set_extra_http_headers({
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    })

                    print(f"      Thread {index+1}: Starting {url[:50]}...")

                    # Navigate with generous timeout for proper JS execution
                    page.goto(url, wait_until='domcontentloaded', timeout=30000)

                    # Wait for JS redirect to complete properly
                    time.sleep(4)  # Proper wait time for JS rendering
                    final_url = page.url

                    # If no redirect, wait longer for complex JS
                    if final_url == url or 'news.google.com' in final_url:
                        try:
                            page.wait_for_load_state('networkidle', timeout=15000)
                            time.sleep(5)  # Increased wait for slow redirects
                            final_url = page.url
                        except:
                            pass

                    print(f"      Thread {index+1}: Got {final_url[:50]}...")

                    # Extract content if redirected
                    if final_url != url and 'news.google.com' not in final_url:
                        if newspaper:
                            try:
                                # Fast extraction with minimal content
                                article = newspaper.Article(final_url, language='vi')
                                article.download()
                                article.parse()

                                # Skip NLP for speed
                                result = {
                                    "success": True,
                                    "error": None,
                                    "final_url": final_url,
                                    "content": article.html[:1500] if article.html else None,
                                    "text": article.text[:4000] if article.text else None,
                                    "authors": article.authors[:2] if article.authors else [],
                                    "publish_date": str(article.publish_date) if article.publish_date else None,
                                    "top_image": article.top_image if article.top_image else None,
                                    "images": list(article.images)[:3] if article.images else [],
                                    "keywords": list(article.keywords)[:10] if hasattr(article, 'keywords') and article.keywords else [],
                                    "summary": article.summary[:800] if hasattr(article, 'summary') and article.summary else None,
                                    "title": article.title if article.title else None
                                }
                            except Exception as e:
                                result = {
                                    "success": False,
                                    "error": f"Extraction failed: {str(e)[:100]}",
                                    "final_url": final_url,
                                    "content": None, "text": None, "authors": [], "publish_date": None,
                                    "top_image": None, "images": [], "keywords": [], "summary": None, "title": None
                                }
                        else:
                            result = {"success": False, "error": "newspaper4k not available", "final_url": final_url}
                    else:
                        result = {"success": False, "error": "No redirect", "final_url": final_url}

                    page.close()
                    browser_instance.close()
                    return index, result

            except Exception as e:
                print(f"      Thread {index+1}: Error: {str(e)[:50]}")
                if browser_instance:
                    try:
                        browser_instance.close()
                    except:
                        pass
                return index, {"success": False, "error": str(e)[:100], "final_url": url}

        # Process all URLs in parallel using ThreadPoolExecutor
        print(f"      Starting {len(urls_batch)} threads with separate browsers...")

        with ThreadPoolExecutor(max_workers=min(len(urls_batch), 6)) as executor:  # Reduced workers for stability
            # Submit all URLs
            futures = {executor.submit(process_url_with_own_browser, i, url): i for i, url in enumerate(urls_batch)}

            # Collect results as they complete with generous timeouts
            for future in as_completed(futures, timeout=180):  # 3 minutes for batch
                try:
                    index, result = future.result(timeout=45)  # 45s per URL
                    results[index] = result
                    print(f"      Thread {index+1}: Completed")
                except Exception as e:
                    index = futures[future]
                    results[index] = {"success": False, "error": f"Thread error: {e}", "final_url": urls_batch[index]}
                    print(f"      Thread {index+1}: Failed - {e}")

        # Fill any None results with failures
        for i, result in enumerate(results):
            if result is None:
                results[i] = {"success": False, "error": "No result", "final_url": urls_batch[i]}

        return results

    def extract_with_playwright(self, google_news_url: str) -> dict:
        """Single URL extraction - wrapper for batch method"""
        batch_results = self.extract_batch_with_playwright([google_news_url])
        return batch_results[0] if batch_results else {"success": False, "error": "No result"}

    def extract_article_content(self, url: str) -> dict:
        """Extract article content - try playwright for Google News URLs, fallback to regular method"""
        if not url:
            return {
                "success": False,
                "error": "No URL provided",
                "final_url": None,
                "content": None,
                "text": None,
                "authors": [],
                "publish_date": None,
                "top_image": None,
                "images": [],
                "keywords": [],
                "summary": None
            }

        # Use playwright for Google News URLs
        if 'news.google.com' in url and PLAYWRIGHT_AVAILABLE:
            return self.extract_with_playwright(url)

        # Regular newspaper4k extraction for other URLs
        try:
            if newspaper:
                # Use newspaper4k to extract article content
                article = newspaper.Article(url)
                article.download()

                # Get the final URL after redirects
                final_url = article.url if hasattr(article, 'url') and article.url else url

                article.parse()

                # Perform NLP if text is available
                try:
                    if article.text:
                        article.nlp()
                except:
                    pass  # NLP might fail, continue without it

                return {
                    "success": True,
                    "error": None,
                    "final_url": final_url,
                    "content": article.html[:5000] if article.html else None,  # Limit HTML content
                    "text": article.text[:10000] if article.text else None,  # Limit text content
                    "authors": article.authors[:5] if article.authors else [],  # Limit authors
                    "publish_date": str(article.publish_date) if article.publish_date else None,
                    "top_image": article.top_image,
                    "images": article.images[:10] if article.images else [],  # Limit images
                    "keywords": article.keywords[:20] if hasattr(article, 'keywords') and article.keywords else [],
                    "summary": article.summary[:2000] if hasattr(article, 'summary') and article.summary else None
                }
            else:
                return {
                    "success": False,
                    "error": "newspaper4k not available",
                    "final_url": None,
                    "content": None,
                    "text": None,
                    "authors": [],
                    "publish_date": None,
                    "top_image": None,
                    "images": [],
                    "keywords": [],
                    "summary": None
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "final_url": None,
                "content": None,
                "text": None,
                "authors": [],
                "publish_date": None,
                "top_image": None,
                "images": [],
                "keywords": [],
                "summary": None
            }

    def extract_urls_for_month(self, year: int, month: int) -> List[Dict[str, Any]]:
        """Extract URLs for a specific month using OR search query"""
        month_name = calendar.month_name[month]
        print(f"Processing {month_name} {year}...")

        # Calculate start and end dates for the month
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = datetime(year, month + 1, 1) - timedelta(days=1)

        month_results = []

        try:
            # Create OR query for all financial keywords
            or_query = " OR ".join(self.financial_keywords)
            print(f"  Searching with OR query: {or_query}")

            # Create GNews instance with date range
            google_news = GNews(
                language='vi',
                country=self.country,
                start_date=start_date,
                end_date=end_date,
                max_results=self.max_results
            )

            # Get news using OR query for all keywords at once
            news_results = google_news.get_news(or_query)

            # Process each result
            for item in news_results:
                try:
                    # Get original Google News URL
                    google_url = item.get('url', '')

                    # Decode to get actual article URL
                    actual_url = self.decode_google_news_url(google_url)

                    # Determine which keyword(s) this article matches
                    title_lower = item.get('title', '').lower()
                    description_lower = item.get('description', '').lower()
                    matched_keywords = []

                    for keyword in self.financial_keywords:
                        if keyword.lower() in title_lower or keyword.lower() in description_lower:
                            matched_keywords.append(keyword)

                    # If no keywords matched in title/description, use "OR query"
                    if not matched_keywords:
                        matched_keywords = ["OR query"]

                    # Use playwright to extract from Google News URL directly
                    print(f"    Extracting content with playwright: {google_url[:80]}...")
                    article_content = self.extract_article_content(google_url)

                    # Use final_url from article content if available, otherwise use publisher or original URL
                    if article_content.get('success') and article_content.get('final_url'):
                        final_url = article_content.get('final_url')
                    elif publisher_url:
                        final_url = publisher_url  # Use publisher URL as fallback
                    else:
                        final_url = google_url  # Use Google News URL as last resort

                    url_data = {
                        "url": final_url,
                        "google_news_url": google_url,
                        "decoded_url": actual_url if actual_url != google_url else None,
                        "title": item.get('title', ''),
                        "description": item.get('description', ''),
                        "published_date": item.get('published date', ''),
                        "publisher_title": item.get('publisher', {}).get('title', '') if item.get('publisher') else '',
                        "publisher_href": item.get('publisher', {}).get('href', '') if item.get('publisher') else '',
                        "matched_keywords": matched_keywords,
                        "search_query": or_query,
                        "month": f"{year}-{month:02d}",
                        "extracted_date": datetime.now().isoformat(),
                        "decoded_successfully": final_url != google_url,
                        "article_content": article_content
                    }
                    month_results.append(url_data)

                except Exception as e:
                    print(f"    Error processing article: {str(e)}")
                    continue

        except Exception as e:
            print(f"  Error searching in {month_name} {year}: {str(e)}")

        print(f"  Found {len(month_results)} URLs for {month_name} {year}")
        return month_results

    def worker_thread(self, year: int, month: int):
        """Worker thread to process one month"""
        try:
            month_data = self.extract_urls_for_month(year, month)

            with self.lock:
                self.all_results.extend(month_data)

        except Exception as e:
            print(f"Error in worker thread for {calendar.month_name[month]} {year}: {str(e)}")

    def extract_last_3_days(self) -> List[Dict[str, Any]]:
        """Extract financial news URLs for the last 3 days only"""
        print("Starting extraction for the last 3 days")
        print(f"Keywords with OR: {' OR '.join(self.financial_keywords)}")
        print(f"Max results: {self.max_results}")

        # Calculate dates for last 3 days
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=3)

        print(f"Date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

        # Extract data for the last 3 days
        data = self.extract_urls_for_date_range(start_date, end_date)

        print(f"\nExtraction completed! Total URLs found: {len(data)}")
        return data

    def extract_urls_for_date_range(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Extract URLs for a specific date range"""
        print(f"Processing date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

        results = []

        try:
            # Create OR query for all financial keywords
            or_query = " OR ".join(self.financial_keywords)
            print(f"  Searching with OR query: {or_query}")

            # Create GNews instance with date range
            google_news = GNews(
                language='vi',
                country=self.country,
                start_date=start_date,
                end_date=end_date,
                max_results=self.max_results
            )

            # Get news using OR query for all keywords at once
            news_results = google_news.get_news(or_query)

            # Process each result
            for item in news_results:
                try:
                    # Get original Google News URL
                    google_url = item.get('url', '')

                    # Decode to get actual article URL
                    actual_url = self.decode_google_news_url(google_url)

                    # Determine which keyword(s) this article matches
                    title_lower = item.get('title', '').lower()
                    description_lower = item.get('description', '').lower()
                    matched_keywords = []

                    for keyword in self.financial_keywords:
                        if keyword.lower() in title_lower or keyword.lower() in description_lower:
                            matched_keywords.append(keyword)

                    # If no keywords matched in title/description, use "OR query"
                    if not matched_keywords:
                        matched_keywords = ["OR query"]

                    # Use playwright to extract from Google News URL directly
                    print(f"    Extracting content with playwright: {google_url[:80]}...")
                    article_content = self.extract_article_content(google_url)

                    # Use final_url from article content if available
                    if article_content.get('success') and article_content.get('final_url'):
                        final_url = article_content.get('final_url')
                    else:
                        final_url = google_url  # Use Google News URL as fallback

                    url_data = {
                        "url": final_url,
                        "google_news_url": google_url,
                        "decoded_url": actual_url if actual_url != google_url else None,
                        "title": item.get('title', ''),
                        "description": item.get('description', ''),
                        "published_date": item.get('published date', ''),
                        "publisher_title": item.get('publisher', {}).get('title', '') if item.get('publisher') else '',
                        "publisher_href": item.get('publisher', {}).get('href', '') if item.get('publisher') else '',
                        "matched_keywords": matched_keywords,
                        "search_query": or_query,
                        "date_range": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
                        "extracted_date": datetime.now().isoformat(),
                        "decoded_successfully": final_url != google_url,
                        "article_content": article_content
                    }
                    results.append(url_data)

                except Exception as e:
                    print(f"    Error processing article: {str(e)}")
                    continue

        except Exception as e:
            print(f"  Error during search: {str(e)}")

        print(f"  Found {len(results)} URLs for the specified date range")
        return results

    def extract_single_month(self, year: int = 2024, month: int = 1) -> List[Dict[str, Any]]:
        """Extract financial news URLs for a single month only"""
        print(f"Starting extraction for {calendar.month_name[month]} {year}")
        print(f"Keywords with OR: {' OR '.join(self.financial_keywords)}")
        print(f"Max results: {self.max_results}")

        # Extract data for the single month
        month_data = self.extract_urls_for_month(year, month)

        print(f"\nExtraction completed! Total URLs found: {len(month_data)}")

        # Remove duplicates based on actual URL
        unique_results = []
        seen_urls = set()
        for item in month_data:
            if item['url'] not in seen_urls:
                unique_results.append(item)
                seen_urls.add(item['url'])

        print(f"Unique URLs after deduplication: {len(unique_results)}")

        # Count successful decodes and content extraction
        decoded_count = sum(1 for item in unique_results if item.get('decoded_successfully', False))
        content_extracted_count = sum(1 for item in unique_results
                                    if item.get('article_content', {}).get('success', False))

        print(f"Successfully decoded URLs: {decoded_count}/{len(unique_results)}")
        print(f"Successfully extracted content: {content_extracted_count}/{len(unique_results)}")

        return unique_results

    def extract_yearly_data(self, year: int = 2024, use_threading: bool = True) -> List[Dict[str, Any]]:
        """Extract financial news URLs for an entire year"""
        print(f"Starting extraction for year {year}")
        print(f"Keywords with OR: {' OR '.join(self.financial_keywords)}")
        print(f"Max results per month: {self.max_results}")
        print(f"Using threading: {use_threading}")

        self.all_results = []

        if use_threading:
            threads = []
            # Create one thread for each month
            for month in range(1, 13):
                thread = threading.Thread(target=self.worker_thread, args=(year, month))
                threads.append(thread)
                thread.start()

                # Stagger thread starts to be more respectful to the API
                time.sleep(0.5)

            # Wait for all threads to complete
            for thread in threads:
                thread.join()
        else:
            # Sequential processing for better rate limiting
            for month in range(1, 13):
                month_data = self.extract_urls_for_month(year, month)
                self.all_results.extend(month_data)

        print(f"\nExtraction completed! Total URLs found: {len(self.all_results)}")

        # Remove duplicates based on actual URL
        unique_results = []
        seen_urls = set()
        for item in self.all_results:
            if item['url'] not in seen_urls:
                unique_results.append(item)
                seen_urls.add(item['url'])

        print(f"Unique URLs after deduplication: {len(unique_results)}")

        # Count successful decodes and content extraction
        decoded_count = sum(1 for item in unique_results if item.get('decoded_successfully', False))
        content_extracted_count = sum(1 for item in unique_results
                                    if item.get('article_content', {}).get('success', False))

        print(f"Successfully decoded URLs: {decoded_count}/{len(unique_results)}")
        print(f"Successfully extracted content: {content_extracted_count}/{len(unique_results)}")

        return unique_results

    def save_to_json(self, data: List[Dict[str, Any]], filename: str = None):
        """Save extracted data to JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"financial_news_urls_{timestamp}.json"

        # Calculate statistics
        decoded_count = sum(1 for item in data if item.get('decoded_successfully', False))
        content_extracted_count = sum(1 for item in data
                                    if item.get('article_content', {}).get('success', False))
        keyword_stats = {}
        month_stats = {}

        for item in data:
            # Handle new matched_keywords format
            matched_keywords = item.get('matched_keywords', [])
            period_key = item.get('month', item.get('period', item.get('date_range', 'unknown')))

            for keyword in matched_keywords:
                keyword_stats[keyword] = keyword_stats.get(keyword, 0) + 1

            month_stats[period_key] = month_stats.get(period_key, 0) + 1

        output_data = {
            "extraction_info": {
                "timestamp": datetime.now().isoformat(),
                "total_urls": len(data),
                "unique_urls": len(data),
                "successfully_decoded": decoded_count,
                "decode_success_rate": f"{(decoded_count/len(data)*100):.1f}%" if data else "0%",
                "content_extracted": content_extracted_count,
                "content_extraction_rate": f"{(content_extracted_count/len(data)*100):.1f}%" if data else "0%",
                "country": self.country,
                "max_results_per_month": self.max_results,
                "keywords_used": self.financial_keywords,
                "keyword_statistics": keyword_stats,
                "month_statistics": month_stats
            },
            "urls": data
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False, default=str)

        print(f"Data saved to: {filename}")
        return filename

def main():
    """Main function to run the financial news URL extraction"""
    print("Financial News URL Extractor using GNews")
    print("=" * 50)

    # Initialize extractor with enhanced settings
    extractor = FinancialNewsExtractor(
        country="VN",
        max_results=100  # Increased for comprehensive extraction
    )

    # Extract data for last 3 days only
    try:
        # Create OR query for all financial keywords
        or_query = " OR ".join(extractor.financial_keywords)
        print(f"Searching with OR query: {or_query}")

        # Create GNews instance for last 3 days with enhanced configuration
        google_news = GNews(
            language='vi',
            country='VN',
            period='3d',  # Last 3 days
            max_results=100  # Comprehensive extraction
        )

        # Get news using OR query
        news_results = google_news.get_news(or_query)
        results = []

        # Process articles in batches using optimized Playwright
        print(f"Processing {len(news_results)} articles in batches...")

        # Extract Google URLs for batch processing
        google_urls = [item.get('url', '') for item in news_results]

        # Use batch Playwright extraction
        article_contents = extractor.extract_batch_with_playwright(google_urls)

        # Combine results with metadata
        for i, item in enumerate(news_results):
            try:
                google_url = item.get('url', '')
                article_content = article_contents[i] if i < len(article_contents) else {"success": False, "error": "No result"}

                # Use final_url from article content if available
                if article_content.get('success') and article_content.get('final_url'):
                    final_url = article_content.get('final_url')
                else:
                    final_url = google_url

                # Determine matched keywords
                title_lower = item.get('title', '').lower()
                description_lower = item.get('description', '').lower()
                matched_keywords = []

                for keyword in extractor.financial_keywords:
                    if keyword.lower() in title_lower or keyword.lower() in description_lower:
                        matched_keywords.append(keyword)

                if not matched_keywords:
                    matched_keywords = ["OR query"]

                url_data = {
                    "url": final_url,
                    "google_news_url": google_url,
                    "title": item.get('title', ''),
                    "description": item.get('description', ''),
                    "published_date": item.get('published date', ''),
                    "publisher_title": item.get('publisher', {}).get('title', '') if item.get('publisher') else '',
                    "publisher_href": item.get('publisher', {}).get('href', '') if item.get('publisher') else '',
                    "matched_keywords": matched_keywords,
                    "search_query": or_query,
                    "period": "3d",
                    "extracted_date": datetime.now().isoformat(),
                    "decoded_successfully": final_url != google_url,
                    "article_content": article_content
                }
                results.append(url_data)

            except Exception as e:
                print(f"Error processing article {i}: {str(e)}")
                continue

        if results:
            # Save to JSON
            filename = extractor.save_to_json(results)
            print(f"\nSuccess! Extracted {len(results)} unique financial/crypto URLs")
            print(f"Data saved to: {filename}")

            # Print sample results
            print("\nSample extracted content:")
            print("-" * 80)
            content_samples = [item for item in results[:10]
                             if item.get('article_content', {}).get('success', False)]

            for i, item in enumerate(content_samples[:3]):
                content = item.get('article_content', {})
                print(f"{i+1}. {item['title'][:70]}...")
                print(f"   URL: {item['url']}")
                print(f"   Publisher: {item['publisher_title']}")
                print(f"   Authors: {', '.join(content.get('authors', [])[:3])}")
                print(f"   Publish Date: {content.get('publish_date', 'N/A')}")
                print(f"   Keywords: {', '.join(item['matched_keywords'])}")
                if content.get('text'):
                    print(f"   Text Preview: {content['text'][:200]}...")
                if content.get('summary'):
                    print(f"   Summary: {content['summary'][:300]}...")
                print(f"   Top Image: {content.get('top_image', 'N/A')}")
                print()

            # Also show decode-only samples if no content samples
            if not content_samples:
                print("\nSample decoded URLs (no content extracted):")
                print("-" * 60)
                decoded_samples = [item for item in results[:10] if item.get('decoded_successfully', False)]

                for i, item in enumerate(decoded_samples[:5]):
                    print(f"{i+1}. {item['title'][:70]}...")
                    print(f"   Original: {item['google_news_url'][:80]}...")
                    print(f"   Decoded:  {item['url']}")
                    print(f"   Publisher: {item['publisher_title']}")
                    print(f"   Keywords: {', '.join(item['matched_keywords'])}")
                    print(f"   Month: {item['month']}")
                    print()

        else:
            print("No results found. This might be due to rate limiting or connection issues.")

    except Exception as e:
        print(f"Error during extraction: {str(e)}")
        return 1

    return 0

if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)