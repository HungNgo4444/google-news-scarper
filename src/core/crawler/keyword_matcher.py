"""Keyword matching utility for extracting matched keywords from articles.

This module provides utilities for matching category keywords against article
content and extracting the keywords that actually appear in the text.
"""

from typing import List, Dict, Any


def extract_matched_keywords_from_content(
    article: Dict[str, Any],
    category_keywords: List[str]
) -> List[str]:
    """Extract keywords that actually appear in article title/content.

    This function checks which category keywords are actually present in the
    article's title and content, returning only the matched keywords.

    Args:
        article: Article dictionary with title, content, etc.
        category_keywords: List of keywords from the category

    Returns:
        List of keywords that were actually found in the article
    """
    if not article or not category_keywords:
        return []

    # Combine title and content for keyword matching
    title = article.get('title', '') or ''
    content = article.get('content', '') or ''
    combined_text = f"{title} {content}".lower()

    if not combined_text.strip():
        return []

    matched_keywords = []

    for keyword in category_keywords:
        if not keyword:
            continue

        keyword_lower = keyword.lower().strip()

        # Check if keyword appears in the combined text
        if keyword_lower in combined_text:
            matched_keywords.append(keyword)

    # Remove duplicates while preserving order
    seen = set()
    unique_matched = []
    for keyword in matched_keywords:
        if keyword not in seen:
            seen.add(keyword)
            unique_matched.append(keyword)

    return unique_matched


def enhance_articles_with_matched_keywords(
    articles: List[Dict[str, Any]],
    category_keywords: List[str]
) -> List[Dict[str, Any]]:
    """Enhance articles with matched keywords based on content analysis.

    Args:
        articles: List of article dictionaries
        category_keywords: List of keywords from the category

    Returns:
        List of articles with keywords_matched field populated
    """
    enhanced_articles = []

    for article in articles:
        # Extract keywords that actually appear in content
        matched_keywords = extract_matched_keywords_from_content(
            article, category_keywords
        )

        # Create enhanced article with matched keywords
        enhanced_article = article.copy()
        enhanced_article['keywords_matched'] = matched_keywords
        enhanced_articles.append(enhanced_article)

    return enhanced_articles