#!/usr/bin/env python3
"""
Direct test script for Google News extraction
Tests:
1. Get URLs from GNews
2. Extract with Playwright
Limit: 100 articles
No jobs, no Celery queue
"""

import sys
import os
import time
import json
from datetime import datetime
from typing import List, Dict, Any

# Add project paths
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

# Add newspaper4k path
newspaper_path = os.path.join(os.path.dirname(__file__), '..', 'newspaper4k-master')
if os.path.exists(newspaper_path):
    sys.path.insert(0, newspaper_path)

try:
    from gnews import GNews
    from playwright.sync_api import sync_playwright

    # Import cloudscraper for enhanced reliability
    try:
        import cloudscraper
        CLOUDSCRAPER_AVAILABLE = True
        print("CloudScraper imported successfully")
    except ImportError:
        CLOUDSCRAPER_AVAILABLE = False
        print("WARNING: CloudScraper not available - using standard approach")
        cloudscraper = None

    # Import newspaper4k like worker
    try:
        import newspaper
        from newspaper import Article
        print("GNews, Playwright and newspaper4k imported successfully")
    except ImportError:
        print("WARNING: newspaper4k not available, will skip content extraction")
        newspaper = None
        Article = None
except ImportError as e:
    print(f"ERROR: Import error: {e}")
    sys.exit(1)

def extract_article_content(article_url: str) -> Dict[str, Any]:
    """Extract article content using newspaper4k with CloudScraper (like worker)"""

    if not newspaper or not Article:
        return {
            'success': False,
            'error': 'newspaper4k not available',
            'title': None,
            'content': None,
            'author': None,
            'publish_date': None
        }

    try:
        # Create article object like worker
        article = Article(article_url, language='vi')

        # Use CloudScraper session if available (newspaper4k will auto-detect and use it)
        if CLOUDSCRAPER_AVAILABLE and cloudscraper:
            # newspaper4k automatically uses cloudscraper if available
            pass

        # Download and parse
        article.download()
        article.parse()

        # Extract data exactly like worker (full content, no limits)
        return {
            'success': True,
            'error': None,
            'title': article.title if article.title else None,
            'content': article.text if article.text else None,  # Full content like worker
            'authors': article.authors if article.authors else [],  # All authors like worker
            'publish_date': str(article.publish_date) if article.publish_date else None,
            'top_image': article.top_image if article.top_image else None,
            'images': list(article.images) if article.images else [],  # All images like worker
            'keywords': list(article.keywords) if hasattr(article, 'keywords') and article.keywords else [],
            'summary': article.summary if hasattr(article, 'summary') and article.summary else None,
            'word_count': len(article.text.split()) if article.text else 0
        }

    except Exception as e:
        return {
            'success': False,
            'error': f"newspaper4k extraction failed: {str(e)[:100]}",
            'title': None,
            'content': None,
            'author': None,
            'publish_date': None
        }

def get_google_news_urls(keywords: List[str], max_results: int = 100) -> List[str]:
    """Get Google News URLs using gnews library with CloudScraper fallback"""
    print(f"\n1. Getting Google News URLs for keywords: {keywords}")

    try:
        # Try GNews first (standard approach)
        urls = get_google_news_urls_gnews(keywords, max_results)

        if urls:
            return urls

        # Fallback to CloudScraper if GNews fails
        if CLOUDSCRAPER_AVAILABLE:
            print("   GNews failed, trying CloudScraper approach...")
            return get_google_news_urls_cloudscraper(keywords, max_results)
        else:
            print("   GNews failed and CloudScraper not available")
            return []

    except Exception as e:
        print(f"ERROR: Getting Google News URLs failed: {e}")
        return []

def get_google_news_urls_gnews(keywords: List[str], max_results: int = 100) -> List[str]:
    """Get Google News URLs using standard gnews library"""
    try:
        # Configure GNews
        google_news = GNews(
            language='vi',
            country='VN',
            max_results=max_results,
            period='7d'  # Last 7 days
        )

        # Build OR query like worker
        search_query = " OR ".join(f'"{keyword}"' for keyword in keywords)
        print(f"   GNews search query: {search_query}")

        # Search with OR logic (like worker)
        articles = google_news.get_news(search_query)

        all_urls = []
        # Extract URLs
        for article in articles:
            if 'url' in article and article['url']:
                all_urls.append(article['url'])

        print(f"   Found {len(articles)} articles via GNews")

        # Remove duplicates
        unique_urls = list(set(all_urls))
        print(f"SUCCESS: GNews unique URLs: {len(unique_urls)}")

        return unique_urls[:max_results]

    except Exception as e:
        print(f"ERROR: GNews search failed: {e}")
        return []

def get_google_news_urls_cloudscraper(keywords: List[str], max_results: int = 100) -> List[str]:
    """Get Google News URLs using CloudScraper for enhanced reliability"""
    if not CLOUDSCRAPER_AVAILABLE or not cloudscraper:
        return []

    try:
        # Create CloudScraper instance
        scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True},
            delay=1
        )

        # Build OR query like worker
        search_query = " OR ".join(f'"{keyword}"' for keyword in keywords)
        print(f"   CloudScraper search query: {search_query}")

        # Build Google News search URL
        import urllib.parse
        encoded_query = urllib.parse.quote(search_query)
        google_news_url = f"https://news.google.com/search?q={encoded_query}&hl=vi&gl=VN&ceid=VN:vi"

        # Add delay for politeness
        time.sleep(1)

        # Make request with CloudScraper
        response = scraper.get(
            google_news_url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'vi,vi-VN;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
        )

        if response.status_code != 200:
            print(f"   CloudScraper received status code {response.status_code}")
            return []

        # Parse Google News HTML to extract article URLs
        google_news_urls = parse_google_news_html(response.text, max_results)

        print(f"SUCCESS: CloudScraper found {len(google_news_urls)} Google News URLs")
        return google_news_urls

    except Exception as e:
        print(f"ERROR: CloudScraper search failed: {e}")
        return []

def parse_google_news_html(html_content: str, max_results: int = 100) -> List[str]:
    """Parse Google News HTML to extract article URLs"""
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

        print(f"   Extracted {len(google_news_urls)} Google News URLs from HTML")
        return google_news_urls[:max_results]

    except Exception as e:
        print(f"   Failed to parse Google News HTML: {e}")
        return []

def extract_with_playwright(google_news_urls: List[str]) -> List[Dict[str, Any]]:
    """Extract actual article URLs using worker sync_engine multi-tab strategy"""
    print(f"\n2. Extracting actual URLs with Playwright ({len(google_news_urls)} URLs)")

    # Use worker sync_engine for URL resolution
    try:
        # Import worker components
        import sys
        sys.path.append('src')
        from src.shared.config import get_settings
        from src.core.crawler.sync_engine import SyncCrawlerEngine
        import logging

        # Setup worker
        settings = get_settings()
        logger = logging.getLogger(__name__)
        engine = SyncCrawlerEngine(settings, logger)

        print("   Using worker sync_engine with multi-tab strategy")

        # Step 1: Resolve URLs using multi-tab strategy
        resolved_urls = engine.resolve_google_news_urls(google_news_urls)
        print(f"   Resolved {len(resolved_urls)} URLs from {len(google_news_urls)} Google News URLs")

        # Step 2: Extract content with newspaper4k + CloudScraper
        results = []
        for i, final_url in enumerate(resolved_urls):
            try:
                print(f"   Extracting content {i+1}/{len(resolved_urls)}: {final_url[:50]}...")
                article_data = extract_article_content(final_url)

                result = {
                    "success": article_data['success'],
                    "error": article_data.get('error'),
                    "final_url": final_url,
                    "content": article_data.get('content'),
                    "text": article_data.get('content'),
                    "authors": article_data.get('authors', []),
                    "publish_date": article_data.get('publish_date'),
                    "top_image": article_data.get('top_image'),
                    "images": article_data.get('images', []),
                    "keywords": article_data.get('keywords', []),
                    "summary": article_data.get('summary'),
                    "title": article_data.get('title'),
                    "original_url": final_url
                }
                results.append(result)

            except Exception as e:
                print(f"   Content extraction error: {str(e)[:50]}")
                results.append({
                    "success": False,
                    "error": str(e)[:100],
                    "final_url": final_url,
                    "original_url": final_url
                })

        # Add failed URLs (no redirect)
        failed_count = len(google_news_urls) - len(resolved_urls)
        for i in range(failed_count):
            results.append({
                "success": False,
                "error": "No redirect from Google News",
                "final_url": None,
                "original_url": google_news_urls[len(resolved_urls) + i] if len(resolved_urls) + i < len(google_news_urls) else "unknown"
            })

        success_count = len([r for r in results if r.get('success')])
        success_rate = (success_count / len(google_news_urls) * 100) if google_news_urls else 0
        print(f"SUCCESS: Extraction completed: {success_count}/{len(google_news_urls)} ({success_rate:.1f}% success rate)")

        return results

    except Exception as e:
        print(f"ERROR: Worker sync_engine error: {e}")
        # Fallback to empty results
        return [{
            "success": False,
            "error": f"Worker failed: {str(e)[:100]}",
            "final_url": None,
            "original_url": url
        } for url in google_news_urls]

def export_results_to_json(results: List[Dict[str, Any]], keywords: List[str], success_rate: float):
    """Export test results to JSON file"""

    # Create export data
    export_data = {
        'test_info': {
            'timestamp': datetime.now().isoformat(),
            'keywords': keywords,
            'total_urls': len(results),
            'successful_extractions': len([r for r in results if r['success']]),
            'failed_extractions': len([r for r in results if not r['success']]),
            'success_rate_percent': round(success_rate, 1),
            'target_rate_percent': 40,
            'test_passed': success_rate >= 40
        },
        'extraction_results': []
    }

    # Add results
    for i, result in enumerate(results, 1):
        result_data = {
            'id': i,
            'original_google_news_url': result['original_url'],
            'final_article_url': result['final_url'],
            'extraction_success': result['success'],
            'error_message': result.get('error', None)
        }

        # Add article content if successful - export FULL DATA
        if result['success']:
            result_data['article_content'] = {
                'title': result.get('title'),
                'content': result.get('content'),
                'text': result.get('text'),  # Same as content but keep both
                'authors': result.get('authors', []),
                'publish_date': result.get('publish_date'),
                'top_image': result.get('top_image'),
                'images': result.get('images', []),
                'keywords': result.get('keywords', []),
                'summary': result.get('summary'),
                'word_count': len(result.get('content', '').split()) if result.get('content') else 0
            }

        export_data['extraction_results'].append(result_data)

    # Create filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'google_news_extraction_test_{timestamp}.json'
    filepath = os.path.join(os.path.dirname(__file__), '..', 'output', filename)

    # Create output directory if not exists
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    # Export to JSON
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        print(f"\nFILE: Results exported to: {filepath}")
        print(f"   - Total articles: {len(results)}")
        print(f"   - Successful: {len([r for r in results if r['success']])}")
        print(f"   - With full content: {len([r for r in results if r['success'] and 'article_data' in r])}")

    except Exception as e:
        print(f"\nERROR: Failed to export JSON: {e}")

def main():
    """Main test function"""
    print("SEARCH: Direct Google News Extraction Test")
    print("=" * 50)

    # Test keywords with OR logic like worker (use ASCII-safe keywords for Windows)
    keywords = ['bitcoin', 'ethereum', 'cryptocurrency']
    max_articles = 10  # Standard testing size

    # Step 1: Get Google News URLs
    google_urls = get_google_news_urls(keywords, max_articles)

    if not google_urls:
        print("ERROR: No Google News URLs found. Exiting.")
        return

    # Step 2: Extract with Playwright
    results = extract_with_playwright(google_urls)

    # Step 3: Summary
    print(f"\nRESULTS: FINAL RESULTS")
    print("=" * 50)

    successful_results = [r for r in results if r['success']]
    failed_results = [r for r in results if not r['success']]

    print(f"SUCCESS: Successful extractions: {len(successful_results)}")
    print(f"ERROR: Failed extractions: {len(failed_results)}")
    print(f"RATE: Success rate: {len(successful_results)/len(results)*100:.1f}%")

    if successful_results:
        print(f"\nSAMPLE: Sample successful URLs:")
        for i, result in enumerate(successful_results[:3], 1):
            print(f"  {i}. {result['final_url']}")

    if failed_results:
        print(f"\nFAILED: Common failure reasons:")
        error_counts = {}
        for result in failed_results:
            error = result.get('error', 'Unknown')
            error_counts[error] = error_counts.get(error, 0) + 1

        for error, count in error_counts.items():
            print(f"  - {error}: {count} times")

    # Target check
    target_rate = 40
    actual_rate = len(successful_results)/len(results)*100 if results else 0

    if actual_rate >= target_rate:
        print(f"\nSUCCESS: SUCCESS: Achieved {actual_rate:.1f}% (target: >{target_rate}%)")
        print("   Google News extraction fix is working!")
    else:
        print(f"\nFAILED: FAILED: Only {actual_rate:.1f}% success rate (target: >{target_rate}%)")
        print("   Need further optimization")

    # Export to JSON
    export_results_to_json(results, keywords, actual_rate)

if __name__ == "__main__":
    main()