#!/usr/bin/env python3
"""
Test script để export comprehensive Google News data sử dụng system crawler.

Flow: GNEWS search -> Google URLs -> Playwright redirect -> Real URLs -> Newspaper4k extract -> Export data
"""

import json
import sys
import os
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Setup paths
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
src_path = os.path.join(project_root, 'src')
sys.path.insert(0, src_path)

# Import GNews trước
try:
    from gnews import GNews
    print("✓ GNews imported")
except ImportError:
    print("❌ GNews not found. Install: pip install gnews")
    sys.exit(1)

# FORCE IMPORT - bypass tất cả lỗi
print("Force importing crawler modules...")

# Add newspaper4k path
newspaper_path = os.path.join(project_root, 'newspaper4k-master')
if os.path.exists(newspaper_path):
    sys.path.insert(0, newspaper_path)

# BRUTAL FORCE IMPORT
import importlib.util

# Load sync_engine module directly
sync_engine_path = os.path.join(src_path, 'core', 'crawler', 'sync_engine.py')
spec = importlib.util.spec_from_file_location("sync_engine", sync_engine_path)
sync_engine_module = importlib.util.module_from_spec(spec)

# MOCK TẤT CẢ CÁC MODULES CẦN THIẾT
# Mock src module
sys.modules['src'] = type(sys)('src')
sys.modules['src.shared'] = type(sys)('src.shared')
sys.modules['src.shared.config'] = type(sys)('src.shared.config')
sys.modules['src.shared.exceptions'] = type(sys)('src.shared.exceptions')
sys.modules['src.database'] = type(sys)('src.database')
sys.modules['src.database.repositories'] = type(sys)('src.database.repositories')
sys.modules['src.database.repositories.sync_article_repo'] = type(sys)('src.database.repositories.sync_article_repo')

# Mock shared modules (non-src)
sys.modules['shared'] = type(sys)('shared')
sys.modules['shared.config'] = type(sys)('shared.config')
sys.modules['shared.exceptions'] = type(sys)('shared.exceptions')

# Create mock objects
class MockSettings:
    MAX_URLS_TO_PROCESS = 15
    MAX_URL_PROCESSING_TIME = 75
    EXTRACTION_THREADS = 5
    ENABLE_JAVASCRIPT_RENDERING = True
    MAX_RESULTS_PER_SEARCH = 100
    EXTRACTION_TIMEOUT = 30
    EXTRACTION_MAX_RETRIES = 3
    EXTRACTION_RETRY_BASE_DELAY = 1.0
    EXTRACTION_RETRY_MULTIPLIER = 2.0
    PLAYWRIGHT_HEADLESS = True
    PLAYWRIGHT_TIMEOUT = 30
    PLAYWRIGHT_WAIT_TIME = 4
    NEWSPAPER_KEEP_ARTICLE_HTML = False
    NEWSPAPER_LANGUAGE = 'vi'
    NEWSPAPER_FETCH_IMAGES = True
    NEWSPAPER_HTTP_SUCCESS_ONLY = True

# Mock exceptions
class MockException(Exception):
    pass

class MockArticleRepo:
    def save_articles_with_deduplication(self, *args, **kwargs):
        return len(args[0]) if args else 0

# Assign mock objects to modules
for module_name in ['shared.config', 'src.shared.config']:
    if module_name in sys.modules:
        sys.modules[module_name].Settings = MockSettings
        sys.modules[module_name].get_settings = lambda: MockSettings()

for module_name in ['shared.exceptions', 'src.shared.exceptions']:
    if module_name in sys.modules:
        sys.modules[module_name].CrawlerError = MockException
        sys.modules[module_name].GoogleNewsUnavailableError = MockException
        sys.modules[module_name].ExtractionError = MockException
        sys.modules[module_name].BaseAppException = MockException
        sys.modules[module_name].ErrorCode = type('ErrorCode', (), {'INTERNAL_SERVER_ERROR': 500})
        sys.modules[module_name].ValidationError = MockException
        sys.modules[module_name].RateLimitExceededError = MockException
        sys.modules[module_name].ExternalServiceError = MockException
        # Add missing exceptions from extractor
        sys.modules[module_name].ExtractionTimeoutError = MockException
        sys.modules[module_name].ExtractionNetworkError = MockException
        sys.modules[module_name].ExtractionParsingError = MockException

# Mock repo
sys.modules['src.database.repositories.sync_article_repo'].SyncArticleRepository = MockArticleRepo

try:
    spec.loader.exec_module(sync_engine_module)
    SyncCrawlerEngine = sync_engine_module.SyncCrawlerEngine
    print("✓ FORCE imported SyncCrawlerEngine")
except Exception as e:
    print(f"❌ Force import failed: {e}")
    sys.exit(1)

# Load extractor module
extractor_path = os.path.join(src_path, 'core', 'crawler', 'extractor.py')
spec2 = importlib.util.spec_from_file_location("extractor", extractor_path)
extractor_module = importlib.util.module_from_spec(spec2)

# Mock thêm missing modules cho extractor
sys.modules['src.core'] = type(sys)('src.core')
sys.modules['src.core.error_handling'] = type(sys)('src.core.error_handling')
sys.modules['src.core.error_handling.circuit_breaker'] = type(sys)('src.core.error_handling.circuit_breaker')
sys.modules['src.core.error_handling.retry_handler'] = type(sys)('src.core.error_handling.retry_handler')

# Mock circuit breaker classes
class MockCircuitBreaker:
    def __init__(self, *args, **kwargs):
        pass

    async def call_with_circuit_breaker(self, *args, **kwargs):
        func = kwargs.get('func') or args[1]
        return await func(*args[2:], **{k:v for k,v in kwargs.items() if k not in ['service_name', 'func', 'config']})

class MockRetryHandler:
    def __init__(self, *args, **kwargs):
        pass

sys.modules['src.core.error_handling.circuit_breaker'].CircuitBreakerManager = MockCircuitBreaker
sys.modules['src.core.error_handling.circuit_breaker'].CircuitBreakerConfig = lambda **kwargs: None
sys.modules['src.core.error_handling.circuit_breaker'].circuit_breaker = lambda *args, **kwargs: lambda func: func
sys.modules['src.core.error_handling.retry_handler'].RetryHandler = MockRetryHandler
sys.modules['src.core.error_handling.retry_handler'].EXTERNAL_SERVICE_RETRY = {}

# Mock dateutil for extractor
try:
    from dateutil.parser import parse as parse_date
except ImportError:
    def parse_date(date_str):
        return None
    sys.modules['dateutil'] = type(sys)('dateutil')
    sys.modules['dateutil.parser'] = type(sys)('dateutil.parser')
    sys.modules['dateutil.parser'].parse = parse_date

try:
    spec2.loader.exec_module(extractor_module)
    ArticleExtractor = extractor_module.ArticleExtractor
    print("✓ FORCE imported REAL ArticleExtractor")
except Exception as e:
    print(f"❌ Force import extractor failed: {e}")
    print(f"Will exit - NEED REAL EXTRACTOR for real data")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TestDataExporter:
    """Export Google News data - Flow: GNews -> Google URLs -> Playwright -> Real URLs -> Newspaper4k -> Data"""

    def __init__(self):
        """Initialize exporter với basic settings."""
        self.settings = self._create_settings()

        # Initialize sync engine và extractor
        self.sync_engine = SyncCrawlerEngine(self.settings, logger)
        self.extractor = ArticleExtractor(self.settings, logger)

        # Financial keywords
        self.financial_keywords = [
            "bitcoin", "cryptocurrency", "stock market", "finance",
            "trading", "investment", "blockchain", "fintech",
            "chứng khoán", "tài chính", "tiền điện tử", "đầu tư",
            "giao dịch", "thị trường", "ngân hàng", "kinh tế"
        ]

        print(f"✓ Initialized với {len(self.financial_keywords)} keywords")

    def _create_settings(self):
        """Tạo basic settings object."""
        class Settings:
            # Google News settings
            MAX_RESULTS_PER_SEARCH = 100
            MAX_URLS_TO_PROCESS = 15
            MAX_URL_PROCESSING_TIME = 75

            # Extraction settings
            EXTRACTION_TIMEOUT = 30
            EXTRACTION_MAX_RETRIES = 3
            EXTRACTION_RETRY_BASE_DELAY = 1.0
            EXTRACTION_RETRY_MULTIPLIER = 2.0
            EXTRACTION_THREADS = 5

            # Playwright settings
            ENABLE_JAVASCRIPT_RENDERING = True
            PLAYWRIGHT_HEADLESS = True
            PLAYWRIGHT_TIMEOUT = 30
            PLAYWRIGHT_WAIT_TIME = 4

            # Newspaper settings
            NEWSPAPER_KEEP_ARTICLE_HTML = False
            NEWSPAPER_LANGUAGE = 'vi'
            NEWSPAPER_FETCH_IMAGES = True
            NEWSPAPER_HTTP_SUCCESS_ONLY = True

        return Settings()

    def export_comprehensive_data(self, max_results: int = 100) -> List[Dict[str, Any]]:
        """
        Export comprehensive Google News data.
        Flow: GNews search -> Google URLs -> resolve_google_news_urls -> extract_articles_batch
        """
        print(f"\n🚀 Starting comprehensive export (max_results={max_results})")
        print("=" * 60)

        # Step 1: GNews search để lấy Google News URLs
        print("Step 1: GNews search...")
        google_urls = self._search_with_gnews(max_results)

        if not google_urls:
            print("❌ No Google URLs found")
            return []

        print(f"✓ Found {len(google_urls)} Google URLs")

        # Step 2: Resolve Google URLs to real URLs using sync_engine
        print("\nStep 2: Resolving Google URLs to real URLs...")
        resolved_urls = self.sync_engine.resolve_google_news_urls(google_urls)

        print(f"✓ Resolved {len(resolved_urls)} real URLs")
        if len(resolved_urls) == 0:
            print("❌ No URLs could be resolved")
            return []

        # Step 3: Extract articles using extractor batch method
        print(f"\nStep 3: Extracting articles using batch method...")
        extracted_articles = []

        # Sử dụng async wrapper cho extract_articles_batch
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            extracted_articles = loop.run_until_complete(
                self.extractor.extract_articles_batch(resolved_urls)
            )
            loop.close()
        except Exception as e:
            print(f"❌ Batch extraction failed: {e}")
            # Fallback: extract one by one
            print("Fallback: extracting one by one...")
            extracted_articles = self._extract_one_by_one(resolved_urls)

        print(f"✓ Extracted {len(extracted_articles)} articles")

        # Step 4: Format results
        print(f"\nStep 4: Formatting results...")
        formatted_results = self._format_articles(extracted_articles, google_urls)

        print(f"✓ Formatted {len(formatted_results)} articles")

        return formatted_results

    def _search_with_gnews(self, max_results: int) -> List[str]:
        """Search Google News with GNews để lấy Google URLs."""
        try:
            # Create OR query
            or_query = " OR ".join(f'"{keyword}"' for keyword in self.financial_keywords[:8])
            print(f"Query: {or_query}")

            # Initialize GNews
            google_news = GNews(
                language='vi',
                country='VN',
                period='3d',
                max_results=max_results
            )

            # Search
            news_results = google_news.get_news(or_query)
            print(f"GNews returned {len(news_results)} results")

            # Extract Google URLs
            google_urls = []
            for item in news_results:
                url = item.get('url', '')
                if url and 'news.google.com' in url:
                    google_urls.append(url)

            return google_urls

        except Exception as e:
            print(f"❌ GNews search error: {e}")
            return []

    def _extract_one_by_one(self, urls: List[str]) -> List[Dict[str, Any]]:
        """Fallback: extract articles one by one."""
        results = []

        for i, url in enumerate(urls[:10]):  # Limit to 10 for testing
            try:
                print(f"Extracting {i+1}/{min(10, len(urls))}: {url[:50]}...")

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    self.extractor.extract_article_metadata(url)
                )
                loop.close()

                if result:
                    results.append(result)
                    print(f"  ✓ Success: {result.get('title', 'No title')[:40]}...")
                else:
                    print(f"  ❌ Failed to extract")

            except Exception as e:
                print(f"  ❌ Error: {e}")
                continue

        return results

    def _format_articles(self, articles: List[Dict[str, Any]], google_urls: List[str]) -> List[Dict[str, Any]]:
        """Format extracted articles."""
        formatted = []

        for article in articles:
            try:
                # Find matched keywords
                matched_keywords = self._find_matched_keywords(
                    article.get('title', ''),
                    article.get('content', '')
                )

                formatted_article = {
                    "url": article.get('source_url', ''),
                    "title": article.get('title', ''),
                    "content": article.get('content', '')[:5000] if article.get('content') else None,
                    "author": article.get('author', ''),
                    "publish_date": str(article.get('publish_date')) if article.get('publish_date') else None,
                    "image_url": article.get('image_url', ''),
                    "url_hash": article.get('url_hash', ''),
                    "content_hash": article.get('content_hash', ''),
                    "extracted_at": article.get('extracted_at', datetime.utcnow()).isoformat(),
                    "matched_keywords": matched_keywords,
                    "extraction_method": "system_crawler",
                    "success": True
                }

                formatted.append(formatted_article)

            except Exception as e:
                print(f"❌ Format error: {e}")
                continue

        return formatted

    def _find_matched_keywords(self, title: str, content: str) -> List[str]:
        """Find which keywords match the article content."""
        matched = []
        combined_text = f"{title} {content}".lower()

        for keyword in self.financial_keywords:
            if keyword.lower() in combined_text:
                matched.append(keyword)

        return matched[:5]  # Limit to top 5 matches

    def save_to_json(self, data: List[Dict[str, Any]], filename: str = None) -> str:
        """Save exported data to JSON file with comprehensive statistics."""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"system_export_data_{timestamp}.json"

        # Calculate comprehensive statistics
        total_articles = len(data)
        successful_extractions = sum(1 for item in data if item.get('success', False))
        articles_with_content = sum(1 for item in data if item.get('content'))
        articles_with_images = sum(1 for item in data if item.get('top_image'))

        # Keyword statistics
        keyword_stats = {}
        for item in data:
            matched_keywords = item.get('matched_keywords', [])
            for keyword in matched_keywords:
                keyword_stats[keyword] = keyword_stats.get(keyword, 0) + 1

        # Category statistics (if available)
        category_stats = {}
        for item in data:
            category = item.get('category_name', 'general')
            category_stats[category] = category_stats.get(category, 0) + 1

        # Create comprehensive output
        output_data = {
            "export_info": {
                "timestamp": datetime.now().isoformat(),
                "script_version": "1.0.0",
                "extraction_method": "system_sync_engine",
                "total_articles": total_articles,
                "successful_extractions": successful_extractions,
                "success_rate": f"{(successful_extractions/total_articles*100):.1f}%" if total_articles > 0 else "0%",
                "articles_with_content": articles_with_content,
                "content_extraction_rate": f"{(articles_with_content/total_articles*100):.1f}%" if total_articles > 0 else "0%",
                "articles_with_images": articles_with_images,
                "image_extraction_rate": f"{(articles_with_images/total_articles*100):.1f}%" if total_articles > 0 else "0%",
                "keyword_statistics": keyword_stats,
                "category_statistics": category_stats,
                "settings": {
                    "max_results": getattr(self.settings, 'MAX_RESULTS_PER_SEARCH', 100),
                    "extraction_timeout": getattr(self.settings, 'EXTRACTION_TIMEOUT', 30),
                    "extraction_threads": getattr(self.settings, 'EXTRACTION_THREADS', 5)
                }
            },
            "articles": data
        }

        # Save to file
        filepath = os.path.join(os.path.dirname(__file__), filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"Data saved to: {filepath}")
        return filepath

def main():
    """Main function - Test system crawler với full flow."""
    print("Google News System Data Exporter")
    print("=" * 50)
    print("Flow: GNews -> Google URLs -> Playwright -> Real URLs -> Newspaper4k -> Data Export")
    print("=" * 50)

    try:
        # Initialize exporter
        print("Initializing exporter...")
        exporter = TestDataExporter()

        # Run comprehensive export
        print("\n🚀 Running comprehensive export...")
        exported_data = exporter.export_comprehensive_data(max_results=50)

        if exported_data:
            # Save results
            filename = exporter.save_to_json(exported_data)

            print(f"\n📊 Export Summary:")
            print(f"Total articles: {len(exported_data)}")
            print(f"File saved: {filename}")

            # Show sample results
            print(f"\n📰 Sample articles:")
            print("-" * 60)

            for i, article in enumerate(exported_data[:5]):
                print(f"{i+1}. {article.get('title', 'No title')[:70]}...")
                print(f"   URL: {article.get('url', '')}")
                print(f"   Author: {article.get('author', 'Unknown')}")
                print(f"   Keywords: {', '.join(article.get('matched_keywords', [])[:3])}")
                if article.get('content'):
                    print(f"   Content: {article.get('content', '')[:100]}...")
                print()

            # Statistics
            with_content = sum(1 for a in exported_data if a.get('content'))
            print(f"📈 Statistics:")
            print(f"Articles with content: {with_content}/{len(exported_data)} ({with_content/len(exported_data)*100:.1f}%)")

            print(f"\n🎉 Export completed successfully!")
            return 0

        else:
            print("\n⚠ No data was exported")
            return 1

    except Exception as e:
        print(f"\n❌ Export failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)