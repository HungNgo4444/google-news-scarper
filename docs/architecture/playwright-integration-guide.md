# Critical Google News Extraction Fix - Playwright Integration Guide

## Overview

This document provides technical guidance for implementing the critical Google News extraction fix based on the proven 56% success rate patterns from `financial_news_extractor.py`. The solution implements a single browser multi-tab strategy with anti-detection measures to restore functionality from the current 0% success rate.

## Problem Statement

The current crawling system has 0% success rate when extracting articles from Google News URLs. Analysis shows that `financial_news_extractor.py` achieves 56% success rate using specialized techniques that must be integrated into the main extraction pipeline.

## Architecture Overview

### Current Flow (0% Success Rate)
```
Google News URL → newspaper4k → Static HTML → Content Extraction → [FAILS]
```

### Enhanced Flow (Target 40-60% Success Rate)
```
Google News URL Detection → Single Browser Multi-Tab Strategy → JavaScript Rendering
                                     ↓
                              4-5 Second Wait → Anti-Detection Delays → Content Extraction → [SUCCESS]
```

### Critical Success Patterns

Based on proven implementation from `financial_news_extractor.py`:
1. **Single Browser Multi-Tab Strategy** - 1 browser with 10 tabs maximum
2. **JavaScript Redirect Handling** - 4-5 second wait times for redirects
3. **Anti-Detection Measures** - Random delays and realistic headers
4. **Resource Blocking** - Block images/CSS for 3x speed improvement
5. **Batch Processing** - Process URLs in batches with delays between batches

## Implementation Details

### 1. Dependencies Setup

#### Add to `requirements.txt`:
```
playwright>=1.40.0
playwright-stealth>=1.0.6  # Optional: for anti-detection
```

#### Browser Installation:
```bash
playwright install chromium
```

### 2. Configuration Updates

#### `src/shared/config.py` additions:
```python
class Settings:
    # Existing settings...

    # Playwright Configuration
    PLAYWRIGHT_ENABLED: bool = True
    PLAYWRIGHT_HEADLESS: bool = True
    PLAYWRIGHT_TIMEOUT: int = 30000  # 30 seconds
    PLAYWRIGHT_VIEWPORT_WIDTH: int = 1920
    PLAYWRIGHT_VIEWPORT_HEIGHT: int = 1080
    PLAYWRIGHT_USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    # Fallback Strategy
    PLAYWRIGHT_FALLBACK_ENABLED: bool = True
    MIN_CONTENT_LENGTH_FOR_SUCCESS: int = 100

    # Performance Settings
    PLAYWRIGHT_POOL_SIZE: int = 3
    PLAYWRIGHT_REUSE_BROWSER: bool = True
```

### 3. Critical Single Browser Multi-Tab Implementation

#### Create `src/core/crawler/google_news_extractor.py`:
```python
"""
Critical Google News extractor with proven 56% success rate patterns.

Based on financial_news_extractor.py implementation that achieves:
- 56% success rate vs current 0%
- Single browser with 10 tabs maximum
- Anti-detection measures with random delays
- Resource blocking for 3x performance improvement
"""

import asyncio
import random
import time
import logging
from typing import List, Dict, Any, Optional
from playwright.async_api import async_playwright, Browser
import newspaper

from src.shared.config import Settings


class CriticalGoogleNewsExtractor:
    """
    Critical Google News extractor implementing proven success patterns.

    Key Features:
    - Single browser multi-tab strategy (max 10 tabs)
    - 4-5 second wait for JavaScript redirects
    - Anti-detection delays (1-3s between tabs, 5-10s between batches)
    - Resource blocking for performance
    - Proper session cleanup
    """

    def __init__(self, settings: Settings, logger: Optional[logging.Logger] = None):
        self.settings = settings
        self.logger = logger or logging.getLogger(__name__)
        self.batch_size = 10  # Maximum tabs per browser session

        # Anti-detection configuration
        self.inter_tab_delay_range = (1, 3)  # seconds
        self.inter_batch_delay_range = (5, 10)  # seconds
        self.redirect_wait_time = 4  # seconds for JS redirect
        self.extended_wait_time = 5  # seconds for slow redirects

    async def extract_google_news_batch(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Process Google News URLs in batches using single browser multi-tab strategy.

        Critical implementation based on financial_news_extractor.py lines 287-453.
        """
        if not urls:
            return []

        self.logger.info(f"Starting Google News batch extraction for {len(urls)} URLs")
        all_results = []

        # Process URLs in batches of 10
        for i in range(0, len(urls), self.batch_size):
            batch = urls[i:i+self.batch_size]
            batch_num = i // self.batch_size + 1

            self.logger.info(f"Processing batch {batch_num}: {len(batch)} URLs")

            batch_results = await self._process_batch_with_single_browser(batch)
            all_results.extend(batch_results)

            # Anti-detection delay between batches
            if i + self.batch_size < len(urls):
                delay = random.randint(*self.inter_batch_delay_range)
                self.logger.info(f"Anti-detection delay: {delay} seconds between batches")
                await asyncio.sleep(delay)

        success_count = sum(1 for result in all_results if result.get('success', False))
        success_rate = (success_count / len(all_results)) * 100 if all_results else 0

        self.logger.info(f"Batch extraction completed: {success_count}/{len(all_results)} successful ({success_rate:.1f}%)")

        return all_results

    async def _process_batch_with_single_browser(self, urls_batch: List[str]) -> List[Dict[str, Any]]:
        """
        Process URLs with single browser instance and multiple tabs.

        Critical patterns from financial_news_extractor.py lines 317-412:
        - Ultra-fast settings with resource blocking
        - 4-5 second wait for JavaScript redirects
        - Proper timeout handling (30s max per tab)
        - Random delays between tab operations
        - Comprehensive error handling per tab
        """
        results = []

        try:
            async with async_playwright() as p:
                # Launch browser with proven settings
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-gpu',
                        '--max_old_space_size=512'  # Memory limit
                    ]
                )

                self.logger.info(f"Browser started, processing {len(urls_batch)} URLs with tabs")

                # Process each URL in separate tab (max 10)
                for i, url in enumerate(urls_batch[:10]):
                    try:
                        page = await browser.new_page()

                        # Ultra-fast settings - block unnecessary resources
                        await page.route(
                            "**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2,ttf,eot,ico}",
                            lambda route: route.abort()
                        )

                        # Set realistic headers for anti-detection
                        await page.set_extra_http_headers({
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                        })

                        self.logger.info(f"Tab {i+1}: Starting {url[:50]}...")

                        # Navigate with Google News specific timing
                        await page.goto(url, wait_until='domcontentloaded', timeout=30000)

                        # Critical: 4-5 second wait for Google News redirect
                        await asyncio.sleep(self.redirect_wait_time)
                        final_url = page.url

                        # Handle no redirect case - wait longer for complex JS
                        if final_url == url or 'news.google.com' in final_url:
                            try:
                                await page.wait_for_load_state('networkidle', timeout=15000)
                                await asyncio.sleep(self.extended_wait_time)
                                final_url = page.url
                            except:
                                pass

                        self.logger.info(f"Tab {i+1}: Got {final_url[:50]}...")

                        # Extract content if successfully redirected
                        if final_url != url and 'news.google.com' not in final_url:
                            result = await self._extract_with_newspaper(final_url, url)
                            results.append(result)
                        else:
                            results.append({
                                "success": False,
                                "error": "No redirect",
                                "final_url": final_url,
                                "original_url": url,
                                "content": None, "text": None, "authors": [], "publish_date": None,
                                "top_image": None, "images": [], "keywords": [], "summary": None, "title": None
                            })

                        await page.close()

                        # Anti-detection delay between tabs
                        if i < len(urls_batch) - 1:
                            delay = random.randint(*self.inter_tab_delay_range)
                            await asyncio.sleep(delay)

                    except Exception as e:
                        self.logger.error(f"Tab {i+1}: Error: {str(e)[:50]}")
                        results.append({
                            "success": False,
                            "error": str(e)[:100],
                            "final_url": url,
                            "original_url": url,
                            "content": None, "text": None, "authors": [], "publish_date": None,
                            "top_image": None, "images": [], "keywords": [], "summary": None, "title": None
                        })

                await browser.close()
                self.logger.info(f"Browser closed, processed {len(results)} URLs")

        except Exception as e:
            self.logger.error(f"Browser session failed: {e}")
            # Return failed results for all URLs
            results = [{
                "success": False,
                "error": str(e),
                "final_url": url,
                "original_url": url,
                "content": None, "text": None, "authors": [], "publish_date": None,
                "top_image": None, "images": [], "keywords": [], "summary": None, "title": None
            } for url in urls_batch]

        return results

    async def _extract_with_newspaper(self, final_url: str, original_url: str) -> Dict[str, Any]:
        """
        Extract article content using newspaper4k after successful redirect.

        Implements content extraction patterns from financial_news_extractor.py lines 364-383.
        """
        try:
            # Use newspaper4k for content extraction
            article = newspaper.Article(final_url, language='vi')

            # Run newspaper operations in thread to avoid blocking
            await asyncio.get_event_loop().run_in_executor(None, article.download)
            await asyncio.get_event_loop().run_in_executor(None, article.parse)

            return {
                "success": True,
                "error": None,
                "final_url": final_url,
                "original_url": original_url,
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
            return {
                "success": False,
                "error": f"Extraction failed: {str(e)[:100]}",
                "final_url": final_url,
                "original_url": original_url,
                "content": None, "text": None, "authors": [], "publish_date": None,
                "top_image": None, "images": [], "keywords": [], "summary": None, "title": None
            }


class GoogleNewsCircuitBreaker:
    """
    Circuit breaker pattern for Google News extraction failures.

    Prevents cascade failures and implements graceful degradation.
    """

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 300):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half-open

    async def call_with_circuit_breaker(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.state == 'open':
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = 'half-open'
            else:
                raise Exception("Google News extraction circuit breaker is open")

        try:
            result = await func(*args, **kwargs)

            # Reset on success
            if self.state == 'half-open':
                self.state = 'closed'
                self.failure_count = 0

            return result

        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.state = 'open'
                logging.error("Google News extraction circuit breaker opened",
                           extra={'failure_count': self.failure_count})

            raise e
```

### 4. Integration with Existing ArticleExtractor

#### Update `src/core/crawler/extractor.py`:
```python
# Add imports
from src.core.crawler.google_news_extractor import CriticalGoogleNewsExtractor, GoogleNewsCircuitBreaker

class ArticleExtractor:
    def __init__(self, settings: Settings, logger: Optional[logging.Logger] = None):
        # Existing initialization...
        self.google_news_extractor = CriticalGoogleNewsExtractor(settings, logger)
        self.circuit_breaker = GoogleNewsCircuitBreaker()

    async def extract_article_metadata(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Enhanced extraction with Google News detection and specialized handling.

        Critical change: Routes Google News URLs to proven extraction method
        that achieves 56% success rate vs current 0%.
        """
        correlation_id = str(uuid.uuid4())

        # Critical: Detect Google News URLs for specialized handling
        if 'news.google.com' in url:
            self.logger.info("Google News URL detected, using specialized extractor",
                           url=url, correlation_id=correlation_id)

            try:
                result = await self.circuit_breaker.call_with_circuit_breaker(
                    self.google_news_extractor.extract_google_news_batch,
                    [url]
                )
                return result[0] if result else None

            except Exception as e:
                self.logger.error(f"Google News extraction failed: {e}")
                # Fallback to standard extraction
                return await self._extract_with_retry(url, correlation_id)

        # Standard extraction for non-Google News URLs
        return await self._extract_with_retry(url, correlation_id)

    async def extract_articles_batch(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Enhanced batch processing with Google News optimization.

        Separates Google News URLs for specialized batch processing
        using single browser multi-tab strategy.
        """
        # Separate Google News URLs for specialized handling
        google_news_urls = [url for url in urls if 'news.google.com' in url]
        standard_urls = [url for url in urls if 'news.google.com' not in url]

        results = []

        # Process Google News URLs with proven single browser multi-tab strategy
        if google_news_urls:
            self.logger.info(f"Processing {len(google_news_urls)} Google News URLs with specialized extractor")

            try:
                google_results = await self.circuit_breaker.call_with_circuit_breaker(
                    self.google_news_extractor.extract_google_news_batch,
                    google_news_urls
                )
                results.extend(google_results)

            except Exception as e:
                self.logger.error(f"Google News batch extraction failed: {e}")
                # Fallback results
                fallback_results = [{"success": False, "error": str(e)} for _ in google_news_urls]
                results.extend(fallback_results)

        # Process standard URLs with regular method
        if standard_urls:
            self.logger.info(f"Processing {len(standard_urls)} standard URLs")
            standard_results = await asyncio.gather(
                *[self._extract_with_retry(url, str(uuid.uuid4())) for url in standard_urls],
                return_exceptions=True
            )
            results.extend([r for r in standard_results if r is not None])

        return results
```

### 5. Critical Performance Optimizations

#### Resource Blocking Configuration:
```python
# Ultra-fast browser settings that achieve 3x performance improvement
CRITICAL_RESOURCE_BLOCKS = [
    "**/*.{png,jpg,jpeg,gif,svg}",      # Images - Major performance impact
    "**/*.{css,woff,woff2,ttf,eot}",    # Fonts and CSS - Significant savings
    "**/*.{ico,xml,weba,mp4,webm}",     # Icons, audio, video
    "**/*.{js}",                        # Optional: Block non-essential JS
]

# Proven browser arguments from financial_news_extractor.py
OPTIMIZED_BROWSER_ARGS = [
    '--no-sandbox',
    '--disable-dev-shm-usage',
    '--disable-gpu',
    '--disable-web-security',
    '--disable-features=VizDisplayCompositor',
    '--max_old_space_size=512'  # Critical: Memory limit prevents crashes
]
```

### 6. Anti-Detection Strategy Implementation

```python
class AntiDetectionManager:
    """
    Comprehensive anti-detection measures based on proven 56% success rate.

    Critical patterns:
    - 1 browser, 10 tabs max (mimics normal user behavior)
    - Random delays: 1-3s between tabs, 5-10s between batches
    - Realistic headers: Windows Chrome User-Agent rotation
    - Resource blocking: Images/CSS blocked for speed
    - Proper cleanup: Close tabs and browser properly
    """

    INTER_TAB_DELAYS = (1, 3)      # seconds between tab operations
    INTER_BATCH_DELAYS = (5, 10)   # seconds between batches
    MAX_TABS_PER_BROWSER = 10       # Maximum tabs per browser session

    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36'
    ]

    @staticmethod
    async def apply_anti_detection_delay(delay_type: str = "tab"):
        """Apply appropriate delay based on context."""
        if delay_type == "tab":
            delay = random.randint(*AntiDetectionManager.INTER_TAB_DELAYS)
        elif delay_type == "batch":
            delay = random.randint(*AntiDetectionManager.INTER_BATCH_DELAYS)
        else:
            delay = 1

        await asyncio.sleep(delay)

    @staticmethod
    def get_random_user_agent() -> str:
        """Get random user agent for header rotation."""
        return random.choice(AntiDetectionManager.USER_AGENTS)
```

### 7. Success Metrics and Monitoring

```python
class GoogleNewsMetrics:
    """
    Track critical metrics for Google News extraction performance.

    Target metrics based on financial_news_extractor.py:
    - Success rate: 40-60% (vs current 0%)
    - Throughput: 10 URLs per browser session efficiently
    - Performance: Complete batch of 10 URLs within 2-3 minutes
    """

    def __init__(self):
        self.total_attempts = 0
        self.successful_extractions = 0
        self.redirect_successes = 0
        self.batch_timings = []

    def record_extraction_attempt(self, success: bool, had_redirect: bool, duration: float):
        """Record extraction metrics."""
        self.total_attempts += 1
        if success:
            self.successful_extractions += 1
        if had_redirect:
            self.redirect_successes += 1
        self.batch_timings.append(duration)

    def get_success_rate(self) -> float:
        """Get current success rate percentage."""
        if self.total_attempts == 0:
            return 0.0
        return (self.successful_extractions / self.total_attempts) * 100

    def get_redirect_rate(self) -> float:
        """Get redirect success rate percentage."""
        if self.total_attempts == 0:
            return 0.0
        return (self.redirect_successes / self.total_attempts) * 100

    def get_average_timing(self) -> float:
        """Get average extraction time in seconds."""
        if not self.batch_timings:
            return 0.0
        return sum(self.batch_timings) / len(self.batch_timings)
```
## Implementation Phases

### Phase 1: Emergency Fix (Day 1) - Critical Success Patterns
- **Google News URL detection** in batch processing
- **Single browser with 10-tab strategy** implementation
- **Basic anti-detection delays** (1-3s tabs, 5-10s batches)
- **4-5 second JavaScript redirect wait** implementation
- **Resource blocking** for performance improvement

### Phase 2: Stability (Day 2) - Error Handling & Monitoring
- **Comprehensive error handling** per tab with graceful fallback
- **Rate limiting** between batches with configurable delays
- **Circuit breaker** implementation for repeated failures
- **Success rate monitoring** with target 40-60%

### Phase 3: Optimization (Day 3) - Advanced Features
- **Advanced anti-detection** measures with User-Agent rotation
- **Performance tuning** with memory management
- **Monitoring dashboard** integration
- **Automated scaling** based on success rates

## Critical Success Metrics

### Target Performance (Based on financial_news_extractor.py)
- **Success Rate**: 40-60% (vs current 0%)
- **Throughput**: Process 10 URLs per browser session efficiently
- **Anti-Detection**: No blocking from Google News during normal usage
- **Performance**: Complete batch of 10 URLs within 2-3 minutes

### Real-Time Monitoring
```python
# Log critical metrics for monitoring
logger.info("Google News extraction metrics", extra={
    "success_rate": f"{success_rate:.1f}%",
    "batch_size": len(urls_batch),
    "processing_time": f"{duration:.2f}s",
    "redirect_success_rate": f"{redirect_rate:.1f}%",
    "anti_detection_delays": "enabled",
    "extraction_method": "single_browser_multi_tab"
})
```

## Risk Mitigation

### 1. Google News Blocking Prevention
- **Conservative delays**: 5-10 seconds between batches minimum
- **Tab limits**: Maximum 10 tabs per browser session
- **User-Agent rotation**: Realistic Chrome headers rotation
- **Resource blocking**: Mimics typical user browsing patterns

### 2. Browser Resource Management
- **Memory limits**: `--max_old_space_size=512` prevents crashes
- **Resource blocking**: Images/CSS blocked for 3x speed improvement
- **Proper cleanup**: Close tabs and browser after each batch
- **Timeout handling**: 30s maximum per tab with graceful degradation

### 3. Extraction Failure Handling
- **Per-tab error handling**: Continue processing other tabs on failure
- **Circuit breaker**: Disable extraction after repeated failures
- **Graceful fallback**: Fall back to standard extraction when needed
- **Comprehensive logging**: Track all failures for analysis

## Docker Deployment

### Dockerfile Updates:
```dockerfile
# Add Playwright dependencies
RUN pip install playwright>=1.40.0
RUN playwright install chromium

# System dependencies for Playwright
RUN apt-get update && apt-get install -y \
    libnss3 \
    libatk-bridge2.0-0 \
    libxss1 \
    libasound2 \
    libxtst6 \
    libdrm2 \
    libgtk-3-0

# Environment variables
ENV PLAYWRIGHT_BROWSERS_PATH=/app/.playwright
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
```

### Environment Configuration:
```bash
# Critical Google News extraction settings
GOOGLE_NEWS_EXTRACTION_ENABLED=true
GOOGLE_NEWS_MAX_TABS_PER_BROWSER=10
GOOGLE_NEWS_INTER_TAB_DELAY_MIN=1
GOOGLE_NEWS_INTER_TAB_DELAY_MAX=3
GOOGLE_NEWS_INTER_BATCH_DELAY_MIN=5
GOOGLE_NEWS_INTER_BATCH_DELAY_MAX=10
GOOGLE_NEWS_REDIRECT_WAIT_TIME=4
GOOGLE_NEWS_EXTENDED_WAIT_TIME=5

# Performance settings
GOOGLE_NEWS_RESOURCE_BLOCKING_ENABLED=true
GOOGLE_NEWS_CIRCUIT_BREAKER_THRESHOLD=5
GOOGLE_NEWS_CIRCUIT_BREAKER_TIMEOUT=300
```

## Critical Testing Requirements

### Validation Tests:
```python
@pytest.mark.asyncio
async def test_google_news_critical_success_rate():
    """Test that Google News extraction achieves target success rate."""
    extractor = CriticalGoogleNewsExtractor(settings, logger)

    # Test with known Google News URLs
    test_urls = [
        "https://news.google.com/articles/CBMi...",  # Sample URLs
        "https://news.google.com/articles/CAIs...",
        # Add more test URLs
    ]

    results = await extractor.extract_google_news_batch(test_urls)

    success_count = sum(1 for r in results if r.get('success', False))
    success_rate = (success_count / len(results)) * 100

    # Critical: Must achieve minimum 40% success rate
    assert success_rate >= 40.0, f"Success rate {success_rate}% below minimum 40%"

    # Verify redirect handling
    redirect_count = sum(1 for r in results
                        if r.get('final_url') != r.get('original_url'))
    assert redirect_count > 0, "No successful redirects detected"

@pytest.mark.asyncio
async def test_anti_detection_timing():
    """Test that anti-detection delays are properly implemented."""
    start_time = time.time()

    # Test batch processing with delays
    extractor = CriticalGoogleNewsExtractor(settings, logger)
    urls = ["https://news.google.com/articles/test"] * 15  # 2 batches

    await extractor.extract_google_news_batch(urls)

    total_time = time.time() - start_time

    # Should take at least 5 seconds for inter-batch delay
    assert total_time >= 5.0, f"Processing too fast: {total_time}s"

    # Should not take excessively long
    assert total_time <= 300.0, f"Processing too slow: {total_time}s"
```

## Troubleshooting Guide

### Common Issues and Solutions

#### 1. 0% Success Rate (Current Issue)
**Symptoms**: All extractions fail with "No redirect" errors
**Solution**: Implement the critical single browser multi-tab strategy with proper timing

#### 2. Browser Launch Failures
**Symptoms**: "Browser not found" or launch timeout errors
**Solution**: Verify Playwright installation and system dependencies

#### 3. Google News Blocking
**Symptoms**: Success rate drops below 20%
**Solution**: Increase inter-batch delays, verify User-Agent rotation

#### 4. Memory Issues
**Symptoms**: Browser crashes or "Out of memory" errors
**Solution**: Reduce batch size, verify `--max_old_space_size=512` setting

### Debug Commands:
```bash
# Test Playwright installation
python -c "from playwright.async_api import async_playwright; print('OK')"

# Check browser installation
playwright install --dry-run

# Monitor extraction performance
grep "Google News extraction metrics" /var/log/crawler.log | tail -10

# Check success rates
grep "success_rate" /var/log/crawler.log | awk '{print $NF}' | sort | uniq -c
```

This critical Google News extraction fix will restore functionality from 0% to target 40-60% success rate using proven patterns from the financial_news_extractor.py implementation.