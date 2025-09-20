#!/usr/bin/env python3
"""
Test REAL GNEWS only - NO FAKE DATA
Neu GNEWS tra ve 0 thi export 0, khong fake
"""

import asyncio
import json
import sys
import os
import logging
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

async def test_real_gnews_only():
    """Test REAL GNEWS - chi export data that, khong fake"""
    print("=== TEST REAL GNEWS ONLY ===")
    print("NO FAKE DATA - CHI EXPORT DATA THAT")

    error_report = {
        "import_errors": [],
        "init_errors": [],
        "crawl_errors": [],
        "success_steps": [],
        "final_data": None
    }

    try:
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)

        # Import components tu @src
        from src.shared.config import get_settings
        from src.core.crawler.engine import CrawlerEngine
        from src.core.crawler.extractor import ArticleExtractor
        from src.database.repositories.article_repo import ArticleRepository

        error_report["success_steps"].append("OK Imported @src components")
        print("OK Imported components from @src")

        # Initialize components
        settings = get_settings()
        article_repo = ArticleRepository()
        article_extractor = ArticleExtractor(settings=settings, logger=logger)

        crawler = CrawlerEngine(
            settings=settings,
            logger=logger,
            article_extractor=article_extractor,
            article_repo=article_repo
        )

        error_report["success_steps"].append("OK CrawlerEngine initialized")
        print("OK CrawlerEngine initialized")

        # Vietnamese crypto keywords
        keywords = ["bitcoin", "tai san ma hoa", "ethusd", "cryptocurrency", "crypto"]
        print(f"Keywords: {keywords}")

        # REAL GNEWS search - chi export ket qua that
        print("\n=== REAL GNEWS SEARCH ===")
        real_gnews_urls = []

        try:
            real_gnews_urls = await crawler.search_google_news(
                keywords=keywords,
                exclude_keywords=[],
                max_results=20,
                language="vi",  # Vietnamese
                country="VN"    # Vietnam
            )

            print(f"REAL GNEWS result: {len(real_gnews_urls)} URLs")
            error_report["success_steps"].append(f"OK REAL GNEWS: {len(real_gnews_urls)} URLs")

            if real_gnews_urls:
                print("REAL URLs from GNEWS:")
                for i, url in enumerate(real_gnews_urls[:5]):
                    print(f"  {i+1}. {url}")
            else:
                print("GNEWS returned 0 URLs - this is REAL result")
                error_report["crawl_errors"].append("GNEWS returned 0 URLs (real result)")

        except Exception as e:
            error_report["crawl_errors"].append(f"GNEWS search failed: {e}")
            print(f"ERROR GNEWS search: {e}")
            real_gnews_urls = []  # Keep empty if failed

        # REAL newspaper4k extract - chi extract neu co URLs
        print("\n=== REAL NEWSPAPER4K EXTRACT ===")
        real_extracted_articles = []

        if real_gnews_urls:
            try:
                print(f"Extracting from {len(real_gnews_urls)} REAL GNEWS URLs...")

                real_extracted_articles = await crawler.extract_articles_batch(real_gnews_urls[:5])

                if real_extracted_articles:
                    print(f"SUCCESS: newspaper4k extracted {len(real_extracted_articles)} REAL articles")
                    error_report["success_steps"].append(f"OK REAL extract: {len(real_extracted_articles)} articles")

                    print("REAL extracted articles (FULL DATA):")
                    for i, article in enumerate(real_extracted_articles):
                        title = article.get('title', 'No title')
                        url = article.get('source_url', 'No URL')
                        content = article.get('content', 'No content')

                        print(f"\n--- REAL ARTICLE {i+1} ---")
                        print(f"Title: {title}")
                        print(f"URL: {url}")
                        print(f"Content: {content[:200]}...")  # Preview only for console
                        print("-" * 50)

                else:
                    print("newspaper4k extracted 0 articles from REAL URLs")
                    error_report["crawl_errors"].append("newspaper4k extracted 0 from real URLs")

            except Exception as e:
                error_report["crawl_errors"].append(f"REAL extraction failed: {e}")
                print(f"ERROR REAL extraction: {e}")
                real_extracted_articles = []

        else:
            print("No REAL GNEWS URLs to extract from")
            error_report["crawl_errors"].append("No real GNEWS URLs available")

        # Export REAL data only
        print("\n=== EXPORT REAL DATA ONLY ===")
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Export chi data that - NO FAKE
            export_data = {
                "test_info": {
                    "timestamp": timestamp,
                    "method": "real_gnews_only_test",
                    "region": "Vietnam",
                    "language": "vi",
                    "keywords_used": keywords,
                    "data_policy": "REAL_ONLY_NO_FAKE",
                    "gnews_urls_found": len(real_gnews_urls),
                    "articles_extracted": len(real_extracted_articles),
                    "success_steps": len(error_report["success_steps"]),
                    "total_errors": len(error_report["import_errors"]) + len(error_report["init_errors"]) + len(error_report["crawl_errors"])
                },
                "real_gnews_urls": real_gnews_urls,  # Chi URLs that tu GNEWS
                "real_articles": real_extracted_articles,  # Chi articles that tu newspaper4k
                "error_report": error_report
            }

            # Export to JSON
            filename = f"scripts/real_gnews_only_{timestamp}.json"

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)

            print(f"SUCCESS: REAL data exported to: {filename}")
            error_report["success_steps"].append(f"OK Exported REAL data to {filename}")
            error_report["final_data"] = export_data

            # Summary
            print(f"\n=== REAL GNEWS TEST SUMMARY ===")
            print(f"Data policy: REAL ONLY - NO FAKE DATA")
            print(f"GNEWS URLs found: {export_data['test_info']['gnews_urls_found']}")
            print(f"Articles extracted: {export_data['test_info']['articles_extracted']}")
            print(f"Success steps: {export_data['test_info']['success_steps']}")
            print(f"Total errors: {export_data['test_info']['total_errors']}")

            if real_extracted_articles:
                print(f"\nREAL article titles:")
                for i, article in enumerate(real_extracted_articles):
                    print(f"  {i+1}. {article.get('title', 'No title')}")

            return export_data

        except Exception as e:
            error_report["crawl_errors"].append(f"Export failed: {e}")
            print(f"ERROR Export: {e}")
            return None

    except Exception as e:
        error_report["import_errors"].append(f"Test failed: {e}")
        print(f"ERROR Test failed: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    try:
        result = asyncio.run(test_real_gnews_only())
        if result:
            print("\nREAL GNEWS TEST COMPLETED!")
            print(f"File: real_gnews_only_*.json")
            print(f"GNEWS URLs: {result['test_info']['gnews_urls_found']}")
            print(f"Articles: {result['test_info']['articles_extracted']}")
            print("REAL DATA ONLY - NO FAKE")
        else:
            print("\nREAL GNEWS TEST FAILED")
    except Exception as e:
        print(f"Script error: {e}")