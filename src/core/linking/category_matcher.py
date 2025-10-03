"""Category matching for multi-category article linking.

This module provides utilities for matching articles with multiple categories
based on keyword matching and relevance scoring.
"""

from typing import List, Dict, Any
from decimal import Decimal


class CategoryMatcher:
    """Matches articles with multiple categories based on keyword relevance."""

    def find_matching_categories(
        self,
        article_dict: Dict[str, Any],
        all_categories: List[Any],
        min_relevance: float = 0.3
    ) -> List[Dict[str, Any]]:
        """Find all categories matching article content.

        Args:
            article_dict: Article dictionary with title, content, etc.
            all_categories: List of Category model instances
            min_relevance: Minimum relevance threshold (default 0.3)

        Returns:
            List of dicts with category_id and relevance_score, sorted by relevance desc
        """
        if not article_dict or not all_categories:
            return []

        # Combine title and content for matching
        title = (article_dict.get('title', '') or '').lower()
        content = (article_dict.get('content', '') or '').lower()
        combined_text = f"{title} {content}"

        if not combined_text.strip():
            return []

        matches = []

        for category in all_categories:
            # Skip inactive categories
            if not category.is_active:
                continue

            # Check exclude keywords first (if any match, skip this category)
            exclude_keywords = category.exclude_keywords or []
            if exclude_keywords:
                has_excluded = any(
                    kw.lower() in combined_text
                    for kw in exclude_keywords if kw
                )
                if has_excluded:
                    continue

            # Find matched keywords
            category_keywords = category.keywords or []
            if not category_keywords:
                continue

            matched_keywords = []
            for keyword in category_keywords:
                if keyword and keyword.lower() in combined_text:
                    matched_keywords.append(keyword)

            # Calculate relevance score if keywords matched
            if matched_keywords:
                # Binary scoring: 50% title + 50% content
                has_title_match = any(kw.lower() in title for kw in matched_keywords)
                has_content_match = any(kw.lower() in content for kw in matched_keywords)

                title_score = 0.5 if has_title_match else 0.0
                content_score = 0.5 if has_content_match else 0.0
                relevance = title_score + content_score

                # Only add if meets minimum threshold
                if relevance >= min_relevance:
                    matches.append({
                        'category_id': str(category.id),
                        'relevance_score': Decimal(str(relevance))
                    })

        # Sort by relevance score descending
        matches.sort(key=lambda x: x['relevance_score'], reverse=True)

        return matches
