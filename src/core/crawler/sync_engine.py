"""Sync crawler engine for Celery tasks.

Uses synchronous operations and newspaper4k built-in threading
to avoid event loop conflicts in Celery workers.
"""

import asyncio
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
    from playwright.async_api import async_playwright
except ImportError:
    sync_playwright = None
    async_playwright = None

# Try to import cloudscraper for enhanced search reliability
try:
    import cloudscraper
except ImportError:
    cloudscraper = None

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

        # Adaptive timing statistics for performance learning
        self._timing_stats = {
            "avg_redirect_time": 4.0,  # Start with proven 4s baseline
            "max_wait": 10.0,
            "success_history": [],  # Track success patterns
            "last_update": time.time()
        }

        # Validate dependencies
        if not GoogleNewsSource:
            raise CrawlerError("GoogleNewsSource not available - check newspaper4k installation")
        if not fetch_news:
            raise CrawlerError("fetch_news not available - check newspaper4k installation")

        # Initialize CloudScraper if available
        self.scraper = None
        if cloudscraper:
            try:
                self.scraper = cloudscraper.create_scraper(
                    browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True},
                    delay=getattr(settings, 'CLOUDSCRAPER_DELAY', 1)
                )
                self.logger.info("CloudScraper initialized successfully for enhanced Google News access")
            except Exception as e:
                self.logger.warning(f"Failed to initialize CloudScraper: {e}")
                self.scraper = None
        else:
            self.logger.warning("CloudScraper not available - install with: pip install cloudscraper")

    def resolve_google_news_urls(self, google_news_urls: List[str]) -> List[str]:
        """Resolve Google News URLs using 1 browser with 10 tabs (exact pattern from financial_news_extractor.py).

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

        # CRITICAL FIX: Process in batches with 1 browser + configurable tabs
        MAX_URLS_TO_PROCESS = self.settings.MAX_URLS_TO_PROCESS

        # Limit the number of URLs to process
        urls_to_process = google_news_urls[:MAX_URLS_TO_PROCESS]

        self.logger.info(f"Resolving {len(urls_to_process)} Google News URLs using 1 browser with multi-tab strategy")

        resolved_urls = []

        if not sync_playwright:
            self.logger.error("Playwright not available for URL resolution")
            return []

        try:
            # Process URLs in batches (configurable max tabs per browser)
            batch_size = self.settings.MAX_TABS_PER_BROWSER
            for i in range(0, len(urls_to_process), batch_size):
                batch = urls_to_process[i:i+batch_size]
                self.logger.info(f"Processing batch {i//batch_size + 1}: {len(batch)} URLs with single browser")

                batch_results = self._resolve_batch_with_single_browser(batch)
                resolved_urls.extend(batch_results)

        except Exception as e:
            self.logger.error(f"Batch URL resolution failed: {e}")

        success_rate = (len(resolved_urls) / len(google_news_urls)) * 100 if google_news_urls else 0
        self.logger.info(f"URL resolution completed: {len(resolved_urls)}/{len(google_news_urls)} URLs resolved ({success_rate:.1f}% success rate)")

        if success_rate < 20:  # Less than 20% success rate
            self.logger.error(f"Very low URL resolution success rate: {success_rate:.1f}%")

        return resolved_urls

    def _resolve_batch_with_single_browser(self, urls_batch: List[str]) -> List[str]:
        """Process URLs with multi-tab strategy and adaptive monitoring (sync version)."""
        resolved_urls = []

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding'
                ]
            )

            try:
                # Open all tabs first (up to 10)
                tabs_data = []
                for i, url in enumerate(urls_batch[:10]):
                    try:
                        self.logger.info(f"      Tab {i+1}: Opening {url[:60]}...")
                        page = browser.new_page()

                        # Block resources for speed
                        page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2,ttf,eot,ico}", lambda route: route.abort())

                        # Set realistic headers
                        page.set_extra_http_headers({
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                        })

                        # Navigate to URL
                        page.goto(url, wait_until='domcontentloaded', timeout=30000)

                        # Store tab data for monitoring
                        tabs_data.append((page, url, i, time.time()))

                        # Small delay between tab openings
                        time.sleep(0.5)

                    except Exception as e:
                        self.logger.error(f"Tab {i+1} opening failed: {e}")
                        continue

                # Monitor all tabs simultaneously with sync approach
                if tabs_data:
                    self.logger.info(f"    Starting sync monitoring for {len(tabs_data)} tabs...")
                    resolved_urls = self._monitor_tabs_sync(tabs_data)

                # Close all tabs
                for page, _, _, _ in tabs_data:
                    try:
                        page.close()
                    except:
                        pass

            finally:
                browser.close()

        return resolved_urls

    def _monitor_tabs_sync(self, tabs_data: List) -> List[str]:
        """Monitor all tabs simultaneously for immediate URL extraction after JS rendering."""
        resolved_urls = []
        max_wait_time = self._timing_stats["max_wait"]

        self.logger.info(f"    Monitoring {len(tabs_data)} tabs for JS rendering completion...")

        # Monitor all tabs in a loop with round-robin checking
        start_time = time.time()
        resolved_tabs = set()  # Track which tabs are already resolved

        while time.time() - start_time < max_wait_time and len(resolved_tabs) < len(tabs_data):
            for i, (page, original_url, tab_id, _) in enumerate(tabs_data):
                if i in resolved_tabs:
                    continue

                try:
                    current_url = page.url
                    elapsed = time.time() - start_time

                    # Check if URL changed and redirected away from Google
                    if current_url != original_url and 'news.google.com' not in current_url:
                        resolved_urls.append(current_url)
                        resolved_tabs.add(i)
                        self.logger.info(f"      Tab {tab_id+1}: JS redirect found at {elapsed:.1f}s -> {current_url[:60]}...")
                        continue

                    # Try network idle fallback after 4 seconds
                    if elapsed > 4 and current_url == original_url:
                        try:
                            page.wait_for_load_state('networkidle', timeout=2000)
                            current_url = page.url
                            if current_url != original_url and 'news.google.com' not in current_url:
                                resolved_urls.append(current_url)
                                resolved_tabs.add(i)
                                self.logger.info(f"      Tab {tab_id+1}: Fallback redirect at {elapsed:.1f}s -> {current_url[:60]}...")
                                continue
                        except:
                            pass

                except Exception as e:
                    self.logger.warning(f"      Tab {tab_id+1}: Monitoring error: {e}")
                    resolved_tabs.add(i)  # Mark as failed to avoid infinite loop
                    continue

            # Small delay between rounds
            time.sleep(0.1)

        # Log failed tabs
        for i, (_, original_url, tab_id, _) in enumerate(tabs_data):
            if i not in resolved_tabs:
                self.logger.warning(f"      Tab {tab_id+1}: No redirect found within {max_wait_time}s")

        self.logger.info(f"    Sync monitoring completed: {len(resolved_urls)}/{len(tabs_data)} URLs resolved")
        return resolved_urls

    async def _monitor_tabs_with_event_detection_async(self, tabs_data: List) -> List[str]:
        """Monitor all tabs with adaptive event-driven detection for immediate URL extraction."""
        import concurrent.futures

        resolved_urls = []
        redirect_times = []  # Track individual redirect times for learning

        # Use adaptive timing based on historical performance
        max_wait_time = self._timing_stats["max_wait"]
        avg_time = self._timing_stats["avg_redirect_time"]

        self.logger.info(f"    Starting adaptive monitoring for {len(tabs_data)} tabs (avg: {avg_time:.1f}s, max: {max_wait_time:.1f}s)...")

        # Use async parallel monitoring
        tasks = []
        for i, (page, original_url, tab_id, _) in enumerate(tabs_data):
            task = asyncio.create_task(self._monitor_single_tab_adaptive_async(page, original_url, tab_id, max_wait_time))
            tasks.append(task)

        # Wait for all tasks to complete with timeout
        try:
            results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=max_wait_time + 2)
            for result in results:
                if isinstance(result, Exception):
                    self.logger.warning(f"Tab monitoring failed: {result}")
                elif result:
                    url, redirect_time = result
                    resolved_urls.append(url)
                    redirect_times.append(redirect_time)
        except asyncio.TimeoutError:
            self.logger.warning(f"Monitoring timed out after {max_wait_time + 2}s")

        # Update adaptive timing statistics
        if redirect_times:
            self._update_timing_stats(redirect_times, len(resolved_urls), len(tabs_data))

        self.logger.info(f"    Adaptive monitoring completed: {len(resolved_urls)} URLs resolved")
        return resolved_urls

    def _monitor_single_tab(self, page, original_url: str, tab_id: int, max_wait: float) -> Optional[str]:
        """Monitor a single tab for URL changes with sub-second precision."""
        import time

        start_time = time.time()
        last_url = original_url

        while time.time() - start_time < max_wait:
            try:
                current_url = page.url

                # Check if URL changed and redirected away from Google
                if current_url != last_url:
                    elapsed = time.time() - start_time
                    self.logger.info(f"      Tab {tab_id+1}: URL changed at {elapsed:.1f}s: {current_url[:50]}...")

                    if current_url != original_url and 'news.google.com' not in current_url:
                        self.logger.info(f"      Tab {tab_id+1}: Resolved in {elapsed:.1f}s -> {current_url[:50]}...")
                        return current_url

                    last_url = current_url

                # If no redirect after some time, try fallback strategy
                if time.time() - start_time > 3 and current_url == original_url:
                    try:
                        page.wait_for_load_state('networkidle', timeout=2000)
                        current_url = page.url
                        if current_url != original_url and 'news.google.com' not in current_url:
                            elapsed = time.time() - start_time
                            self.logger.info(f"      Tab {tab_id+1}: Fallback resolved in {elapsed:.1f}s -> {current_url[:50]}...")
                            return current_url
                    except:
                        pass

                time.sleep(0.1)  # Check every 100ms for responsiveness

            except Exception as e:
                self.logger.warning(f"      Tab {tab_id+1}: Monitoring error: {e}")
                break

        self.logger.warning(f"      Tab {tab_id+1}: No redirect found within {max_wait}s")
        return None

    async def _monitor_single_tab_adaptive_async(self, page, original_url: str, tab_id: int, max_wait: float) -> Optional[tuple]:
        """Monitor a single tab with adaptive timing and return URL + redirect time."""
        import time

        start_time = time.time()
        last_url = original_url

        while time.time() - start_time < max_wait:
            try:
                current_url = page.url

                # Check if URL changed and redirected away from Google
                if current_url != last_url:
                    elapsed = time.time() - start_time
                    self.logger.info(f"      Tab {tab_id+1}: URL changed at {elapsed:.1f}s: {current_url[:50]}...")

                    if current_url != original_url and 'news.google.com' not in current_url:
                        self.logger.info(f"      Tab {tab_id+1}: Resolved in {elapsed:.1f}s -> {current_url[:50]}...")
                        return (current_url, elapsed)  # Return URL and timing

                    last_url = current_url

                # Use adaptive fallback timing based on learned patterns
                avg_time = self._timing_stats["avg_redirect_time"]
                if time.time() - start_time > avg_time and current_url == original_url:
                    try:
                        await page.wait_for_load_state('networkidle', timeout=2000)
                        current_url = page.url
                        if current_url != original_url and 'news.google.com' not in current_url:
                            elapsed = time.time() - start_time
                            self.logger.info(f"      Tab {tab_id+1}: Adaptive fallback resolved in {elapsed:.1f}s -> {current_url[:50]}...")
                            return (current_url, elapsed)
                    except:
                        pass

                await asyncio.sleep(0.1)  # Check every 100ms for responsiveness

            except Exception as e:
                self.logger.warning(f"      Tab {tab_id+1}: Monitoring error: {e}")
                break

        self.logger.warning(f"      Tab {tab_id+1}: No redirect found within {max_wait}s")
        return None

    def _update_timing_stats(self, redirect_times: List[float], successful: int, total: int):
        """Update adaptive timing statistics based on current batch performance."""
        if not redirect_times:
            return

        # Calculate current batch metrics
        avg_redirect_time = sum(redirect_times) / len(redirect_times)
        success_rate = successful / total if total > 0 else 0

        # Update running averages with decay factor
        decay = 0.8  # Weight current data higher than historical
        self._timing_stats["avg_redirect_time"] = (
            decay * avg_redirect_time +
            (1 - decay) * self._timing_stats["avg_redirect_time"]
        )

        # Adjust max wait time based on success rate
        if success_rate > 0.8:  # >80% success rate
            self._timing_stats["max_wait"] = max(
                self._timing_stats["avg_redirect_time"] + 2.0,  # Give 2s buffer
                6.0  # Minimum of 6s
            )
        elif success_rate < 0.4:  # <40% success rate
            self._timing_stats["max_wait"] = min(
                self._timing_stats["max_wait"] + 2.0,  # Increase wait time
                15.0  # Maximum of 15s
            )

        # Store recent performance for analysis
        self._timing_stats["success_history"].append({
            "timestamp": time.time(),
            "avg_time": avg_redirect_time,
            "success_rate": success_rate,
            "batch_size": total
        })

        # Keep only last 10 batches for learning
        if len(self._timing_stats["success_history"]) > 10:
            self._timing_stats["success_history"] = self._timing_stats["success_history"][-10:]

        self.logger.info(
            f"    Adaptive timing updated: avg={self._timing_stats['avg_redirect_time']:.1f}s, "
            f"max={self._timing_stats['max_wait']:.1f}s, success_rate={success_rate:.1%}"
        )


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
                browser = p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--max_old_space_size=512']
                )
                page = browser.new_page()

                # Ultra-fast settings - block images/CSS for speed
                page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2,ttf,eot,ico}", lambda route: route.abort())

                # Set user agent to avoid detection
                page.set_extra_http_headers({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                })

                # Set timeout to 30 seconds max per Story 2.4
                page.set_default_timeout(30000)  # 30 seconds

                # Navigate to Google News URL
                page.goto(google_url, wait_until='domcontentloaded', timeout=30000)

                # Wait for potential redirect
                time.sleep(4)
                final_url = page.url

                # Log the current URL for debugging
                self.logger.debug(f"After initial wait, URL: {final_url}")

                # Check if URL has changed (redirect happened)
                if final_url != google_url and 'news.google.com' not in final_url:
                    self.logger.info(f"Direct redirect found: {final_url}")
                    page.close()
                    browser.close()
                    return final_url

                # If still on Google News, wait a bit more and try again
                if 'news.google.com' in final_url:
                    page.wait_for_load_state('networkidle', timeout=15000)
                    time.sleep(5)  # Additional wait
                    final_url = page.url
                    self.logger.debug(f"After network idle wait, URL: {final_url}")

                    if final_url != google_url and 'news.google.com' not in final_url:
                        self.logger.info(f"Delayed redirect found: {final_url}")
                        page.close()
                        browser.close()
                        return final_url

                page.close()
                browser.close()

        except Exception as e:
            self.logger.warning(f"Playwright URL resolution failed: {e}")
        return None

    async def _resolve_with_playwright_async(self, google_url: str) -> Optional[str]:
        """Async implementation of Playwright URL resolution."""
        import re

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--max_old_space_size=512']
                )
                page = await browser.new_page()

                # Ultra-fast settings - block images/CSS for speed
                await page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2,ttf,eot,ico}", lambda route: route.abort())

                # Set user agent to avoid detection
                await page.set_extra_http_headers({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                })

                # Set timeout to 30 seconds max per Story 2.4
                page.set_default_timeout(30000)  # 30 seconds

                # Navigate to Google News URL with domcontentloaded
                response = await page.goto(google_url, wait_until='domcontentloaded', timeout=30000)

                # Wait for JS redirect - critical 4 seconds per financial_news_extractor.py
                await asyncio.sleep(4)
                final_url = page.url

                # If no redirect, wait longer (exact logic from financial_news_extractor.py)
                if final_url == google_url or 'news.google.com' in final_url:
                    try:
                        await page.wait_for_load_state('networkidle', timeout=15000)
                        await asyncio.sleep(5)  # CRITICAL: Must be 5 seconds like financial_news_extractor.py
                        final_url = page.url
                    except:
                        pass

                    # If successfully redirected after longer wait
                    if final_url and 'google.com' not in final_url and final_url.startswith('http'):
                        await browser.close()
                        return final_url

                    # Get page content for URL extraction
                    content = await page.content()

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

                    await browser.close()

                    if found_urls:
                        # Return the first valid URL found
                        result_url = next(iter(found_urls))
                        self.logger.info(f"Extracted article URL from Google News page: {result_url}")
                        return result_url
                    else:
                        self.logger.warning(f"No external URLs found in Google News page content")
                else:
                    await browser.close()
                    self.logger.warning(f"Failed to load Google News page, status: {response.status if response else 'None'}")

        except Exception as e:
            self.logger.warning(f"Async Playwright URL resolution failed: {e}")

        return None

    def _resolve_with_playwright_enhanced(self, google_url: str) -> Optional[str]:
        """Enhanced Playwright URL resolution with CloudScraper session integration.

        Uses CloudScraper session cookies and headers to improve success rate.

        Args:
            google_url: Google News URL to resolve

        Returns:
            Final resolved URL or None if failed
        """
        if not self.scraper:
            # Fallback to standard Playwright
            return self._resolve_with_playwright(google_url)

        try:
            # Convert to sync implementation
            return self._resolve_with_playwright_enhanced_sync(google_url)
        except Exception as e:
            self.logger.warning(f"Enhanced Playwright URL resolution failed: {e}")
            # Fallback to standard Playwright
            return self._resolve_with_playwright(google_url)

    def _resolve_with_playwright_enhanced_sync(self, google_url: str) -> Optional[str]:
        """Sync enhanced Playwright URL resolution with CloudScraper integration."""
        try:
            # Pre-warm with CloudScraper request to get session cookies
            self.logger.debug(f"Pre-warming CloudScraper session for: {google_url[:50]}...")

            # Make a quick HEAD request to establish session
            head_response = self.scraper.head(google_url, timeout=10)
            cookies = head_response.cookies

            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--max_old_space_size=512']
                )

                # Create browser context with CloudScraper cookies
                context = browser.new_context()

                # Add CloudScraper cookies to context
                if cookies:
                    cookie_list = []
                    for cookie in cookies:
                        cookie_dict = {
                            'name': cookie.name,
                            'value': cookie.value,
                            'domain': cookie.domain or '.google.com',
                            'path': cookie.path or '/',
                        }
                        if cookie.secure:
                            cookie_dict['secure'] = True
                        if cookie.expires:
                            cookie_dict['expires'] = cookie.expires
                        cookie_list.append(cookie_dict)

                    if cookie_list:
                        context.add_cookies(cookie_list)
                        self.logger.debug(f"Added {len(cookie_list)} CloudScraper cookies to Playwright context")

                page = context.new_page()

                # Ultra-fast settings - block images/CSS for speed
                page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2,ttf,eot,ico}", lambda route: route.abort())

                # Use CloudScraper's User-Agent for consistency
                page.set_extra_http_headers({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en,en-US;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                })

                # Set timeout to 30 seconds max per Story 2.4
                page.set_default_timeout(30000)

                # Navigate to Google News URL
                response = page.goto(google_url, wait_until='domcontentloaded', timeout=30000)

                if response and response.status == 200:
                    # Wait for potential redirect
                    time.sleep(4)
                    final_url = page.url

                    if final_url != google_url and 'news.google.com' not in final_url:
                        self.logger.info(f"Enhanced direct redirect found: {final_url}")
                        page.close()
                        browser.close()
                        return final_url

                    # If still on Google News, wait for network idle and try again
                    if 'news.google.com' in final_url:
                        page.wait_for_load_state('networkidle', timeout=15000)
                        time.sleep(5)
                        final_url = page.url

                        if final_url != google_url and 'news.google.com' not in final_url:
                            self.logger.info(f"Enhanced delayed redirect found: {final_url}")
                            page.close()
                            browser.close()
                            return final_url

                page.close()
                browser.close()

        except Exception as e:
            self.logger.warning(f"Enhanced Playwright URL resolution failed: {e}")

        return None

    async def _resolve_with_playwright_enhanced_async(self, google_url: str) -> Optional[str]:
        """Async enhanced Playwright URL resolution."""
        try:
            # Pre-warm with CloudScraper request to get session cookies
            self.logger.debug(f"Pre-warming CloudScraper session for: {google_url[:50]}...")

            # Make a quick HEAD request to establish session
            head_response = self.scraper.head(google_url, timeout=10)
            cookies = head_response.cookies

            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--max_old_space_size=512']
                )

                # Create browser context with CloudScraper cookies
                context = await browser.new_context()

                # Add CloudScraper cookies to context
                if cookies:
                    cookie_list = []
                    for cookie in cookies:
                        cookie_dict = {
                            'name': cookie.name,
                            'value': cookie.value,
                            'domain': cookie.domain or '.google.com',
                            'path': cookie.path or '/',
                        }
                        if cookie.secure:
                            cookie_dict['secure'] = True
                        if cookie.expires:
                            cookie_dict['expires'] = cookie.expires
                        cookie_list.append(cookie_dict)

                    if cookie_list:
                        await context.add_cookies(cookie_list)
                        self.logger.debug(f"Added {len(cookie_list)} CloudScraper cookies to Playwright context")

                page = await context.new_page()

                # Ultra-fast settings - block images/CSS for speed
                await page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2,ttf,eot,ico}", lambda route: route.abort())

                # Use CloudScraper's User-Agent for consistency
                await page.set_extra_http_headers({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en,en-US;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                })

                # Set timeout to 30 seconds max
                page.set_default_timeout(30000)

                # Navigate to Google News URL
                response = await page.goto(google_url, wait_until='domcontentloaded', timeout=30000)

                # Wait for JS redirect - critical timing from financial_news_extractor.py
                await asyncio.sleep(4)
                final_url = page.url

                # If no redirect, wait longer (exact logic from financial_news_extractor.py)
                if final_url == google_url or 'news.google.com' in final_url:
                    try:
                        await page.wait_for_load_state('networkidle', timeout=15000)
                        await asyncio.sleep(5)  # CRITICAL: Must be 5 seconds like financial_news_extractor.py
                        final_url = page.url
                    except:
                        pass

                # Validate successful redirect
                if final_url and 'google.com' not in final_url and final_url.startswith('http'):
                    await browser.close()
                    self.logger.debug(f"Enhanced Playwright resolved: {final_url[:50]}...")
                    return final_url

                await browser.close()

        except Exception as e:
            self.logger.warning(f"Async enhanced Playwright URL resolution failed: {e}")

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
            search_query = " OR ".join(keywords)

            # Add exclusions if provided
            if exclude_keywords:
                exclusions = " ".join(f'-{keyword}' for keyword in exclude_keywords)
                search_query = f"{search_query} {exclusions}"

            self.logger.info(f"Searching Google News with query: {search_query}")

            # URL encode the search query to handle spaces and special characters
            from urllib.parse import quote_plus
            encoded_query = quote_plus(search_query)

            # Use GNews with enhanced URL resolution strategy
            import gnews

            gn = gnews.GNews(
                language=language.lower(),
                country=country,
                max_results=max_results
            )

            # Search using GNews directly with encoded query
            search_results = gn.get_news(encoded_query)

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

    def search_google_news_with_cloudscraper(
        self,
        keywords: List[str],
        exclude_keywords: List[str] = None,
        max_results: int = 100,
        language: str = "en",
        country: str = "US"
    ) -> List[str]:
        """Enhanced Google News search using CloudScraper for better reliability.

        This method provides an alternative search when GNews fails due to blocking.
        Uses CloudScraper to directly search Google News website and parse results.

        Args:
            keywords: List of keywords to search for (OR logic)
            exclude_keywords: List of keywords to exclude from results
            max_results: Maximum number of results to return
            language: Language code for search results
            country: Country code for search results

        Returns:
            List of Google News URLs for further processing

        Raises:
            GoogleNewsUnavailableError: If search fails
        """
        if not self.scraper:
            self.logger.warning("CloudScraper not available, falling back to standard search")
            return self.search_google_news(keywords, exclude_keywords, max_results, language, country)

        if not keywords:
            raise GoogleNewsUnavailableError("Keywords list cannot be empty")

        try:
            # Build search query with OR logic for keywords
            search_query = " OR ".join(f'"{keyword}"' for keyword in keywords)

            # Add exclusions if provided
            if exclude_keywords:
                exclusions = " ".join(f'-"{keyword}"' for keyword in exclude_keywords)
                search_query = f"{search_query} {exclusions}"

            self.logger.info(f"CloudScraper search with query: {search_query}")

            # Build Google News search URL
            import urllib.parse
            encoded_query = urllib.parse.quote(search_query)
            google_news_url = f"https://news.google.com/search?q={encoded_query}&hl={language}&gl={country}&ceid={country}:{language}"

            # Add CloudScraper delay
            delay = getattr(self.settings, 'CLOUDSCRAPER_DELAY', 1)
            if delay > 0:
                time.sleep(delay)

            # Make request with CloudScraper
            response = self.scraper.get(
                google_news_url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': f'{language},{language[:2]};q=0.9,en;q=0.8',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                }
            )

            if response.status_code != 200:
                self.logger.warning(f"CloudScraper received status code {response.status_code}")
                # Fallback to standard method
                return self.search_google_news(keywords, exclude_keywords, max_results, language, country)

            # Parse Google News HTML to extract article URLs
            google_news_urls = self._parse_google_news_html(response.text, max_results)

            if not google_news_urls:
                self.logger.warning("No URLs found in CloudScraper search results")
                return []

            self.logger.info(f"CloudScraper found {len(google_news_urls)} Google News URLs")

            # Resolve the URLs using existing methods
            resolved_urls = self.resolve_google_news_urls(google_news_urls)

            self.logger.info(f"CloudScraper resolved {len(resolved_urls)} URLs from {len(google_news_urls)} found")
            return resolved_urls

        except Exception as e:
            error_msg = f"CloudScraper search failed: {str(e)}"
            self.logger.error(error_msg)
            # Fallback to standard search
            self.logger.info("Falling back to standard Google News search")
            return self.search_google_news(keywords, exclude_keywords, max_results, language, country)

    def _parse_google_news_html(self, html_content: str, max_results: int = 100) -> List[str]:
        """Parse Google News HTML to extract article URLs.

        Args:
            html_content: HTML content from Google News page
            max_results: Maximum number of URLs to extract

        Returns:
            List of Google News article URLs
        """
        google_news_urls = []

        try:
            import re

            # Enhanced regex patterns for Google News URLs
            patterns = [
                # Current Google News format
                r'href="(\./articles/[^"]*)"',
                r'href="(https://news\.google\.com/articles/[^"]*)"',
                # Alternative patterns
                r'<a[^>]*href="([^"]*articles/[^"]*)"[^>]*>',
                r'data-url="([^"]*articles/[^"]*)"',
            ]

            for pattern in patterns:
                matches = re.findall(pattern, html_content)
                for match in matches:
                    # Clean and normalize URL
                    if match.startswith('./'):
                        url = f"https://news.google.com{match[1:]}"
                    elif match.startswith('https://'):
                        url = match
                    else:
                        url = f"https://news.google.com{match}"

                    # Validate URL format and avoid duplicates
                    if 'articles/' in url and url not in google_news_urls:
                        google_news_urls.append(url)

                        if len(google_news_urls) >= max_results:
                            break

                if len(google_news_urls) >= max_results:
                    break

            self.logger.info(f"Extracted {len(google_news_urls)} Google News URLs from HTML")
            return google_news_urls[:max_results]

        except Exception as e:
            self.logger.error(f"Failed to parse Google News HTML: {e}")
            return []

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

            # Use newspaper4k threading to download and parse with error handling
            try:
                processed_articles = fetch_news(articles, threads=threads)
            except Exception as fetch_error:
                # If fetch_news fails completely, try individual processing
                self.logger.warning(f"Batch fetch failed ({fetch_error}), falling back to individual processing")
                processed_articles = []

                # Process articles individually to isolate failures
                for article in articles:
                    try:
                        article.download()
                        article.parse()
                        processed_articles.append(article)
                    except Exception as individual_error:
                        self.logger.warning(f"Failed to process individual article {article.url}: {individual_error}")
                        continue

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
            # Only fail the job if there's a critical system error, not individual article failures
            if "No articles could be processed" in str(e) and len(urls) > 10:
                # Only fail if we have many URLs but couldn't process any
                error_msg = f"Critical extraction failure: {str(e)}"
                self.logger.error(error_msg)
                raise ExtractionError(error_msg) from e
            else:
                # Log the error but return empty results instead of failing the job
                self.logger.warning(f"Extraction encountered errors but continuing: {str(e)}")
                return []

    def crawl_category_sync(self, category: Any, job_id: str = None) -> List[Dict[str, Any]]:
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
                    extracted_articles, category.id, job_id
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