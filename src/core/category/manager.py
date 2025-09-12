"""Category Manager with business logic and validation.

This module provides the CategoryManager class that handles all business operations
for categories, including validation, creation, updates, and search functionality.

Key Features:
- Name uniqueness validation 
- Keywords validation (1-20 items, max 100 chars each)
- Duplicate name checking
- Search query building for OR logic
- Proper error handling with custom exceptions
- Structured logging with correlation IDs

Example:
    Basic category management operations:
    
    ```python
    from src.core.category.manager import CategoryManager
    from src.database.repositories.category_repo import CategoryRepository
    from src.shared.config import get_settings
    
    async def manage_categories():
        repo = CategoryRepository()
        settings = get_settings()
        manager = CategoryManager(repo, settings)
        
        # Create new category with validation
        try:
            category = await manager.create_category(
                name="Technology",
                keywords=["python", "javascript", "ai"],
                exclude_keywords=["deprecated"]
            )
            print(f"Created: {category.name}")
        except CategoryValidationError as e:
            print(f"Validation failed: {e}")
        
        # Get all categories
        categories = await manager.get_categories(active_only=True)
        for cat in categories:
            print(f"{cat.name}: {len(cat.keywords)} keywords")
    ```
"""

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4

from src.database.repositories.category_repo import CategoryRepository
from src.database.models.category import Category
from src.shared.config import Settings
from src.shared.exceptions import (
    CategoryValidationError,
    CategoryNotFoundError,
    DuplicateCategoryNameError
)

logger = logging.getLogger(__name__)


class CategoryManager:
    """Business logic manager for Category operations.
    
    This class handles all category-related business logic including validation,
    creation, updates, and search functionality with proper error handling.
    """
    
    def __init__(self, repository: CategoryRepository, settings: Settings):
        """Initialize the CategoryManager.
        
        Args:
            repository: CategoryRepository instance for database operations
            settings: Application settings for configuration values
        """
        self.repository = repository
        self.settings = settings
        self.max_keywords = getattr(settings, 'MAX_KEYWORDS_PER_CATEGORY', 20)
        self.max_keyword_length = getattr(settings, 'MAX_KEYWORD_LENGTH', 100)
        self.max_name_length = getattr(settings, 'MAX_CATEGORY_NAME_LENGTH', 255)
    
    async def create_category(
        self,
        name: str,
        keywords: List[str],
        exclude_keywords: Optional[List[str]] = None,
        is_active: bool = True
    ) -> Category:
        """Create a new category with validation.
        
        Args:
            name: Category name (must be unique)
            keywords: List of keywords for search (1-20 items)
            exclude_keywords: Optional list of keywords to exclude
            is_active: Whether category is active for crawling
            
        Returns:
            Created Category instance
            
        Raises:
            CategoryValidationError: If validation fails
            DuplicateCategoryNameError: If category name already exists
        """
        correlation_id = str(uuid4())
        
        logger.info(f"Creating category: {name}", extra={
            "correlation_id": correlation_id,
            "category_name": name,
            "keywords_count": len(keywords),
            "exclude_keywords_count": len(exclude_keywords) if exclude_keywords else 0
        })
        
        try:
            # Validate input data
            self._validate_name(name)
            self._validate_keywords(keywords)
            if exclude_keywords:
                self._validate_exclude_keywords(exclude_keywords)
            
            # Check for duplicate name
            existing_category = await self.repository.get_by_name(name.strip())
            if existing_category:
                raise DuplicateCategoryNameError(f"Category with name '{name}' already exists")
            
            # Create category
            category = await self.repository.create_category(
                name=name,
                keywords=keywords,
                exclude_keywords=exclude_keywords or [],
                is_active=is_active
            )
            
            logger.info(f"Successfully created category", extra={
                "correlation_id": correlation_id,
                "category_id": str(category.id),
                "category_name": category.name
            })
            
            return category
            
        except (CategoryValidationError, DuplicateCategoryNameError):
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(f"Failed to create category: {e}", extra={
                "correlation_id": correlation_id,
                "category_name": name,
                "error_type": type(e).__name__
            })
            raise CategoryValidationError(f"Failed to create category: {str(e)}")
    
    async def update_category(
        self,
        category_id: UUID,
        name: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        exclude_keywords: Optional[List[str]] = None,
        is_active: Optional[bool] = None
    ) -> Optional[Category]:
        """Update an existing category.
        
        Args:
            category_id: UUID of category to update
            name: New category name (optional)
            keywords: New keywords list (optional)
            exclude_keywords: New exclude keywords list (optional)
            is_active: New active status (optional)
            
        Returns:
            Updated Category instance if found, None otherwise
            
        Raises:
            CategoryValidationError: If validation fails
            CategoryNotFoundError: If category not found
            DuplicateCategoryNameError: If new name already exists
        """
        correlation_id = str(uuid4())
        
        logger.info(f"Updating category {category_id}", extra={
            "correlation_id": correlation_id,
            "category_id": str(category_id)
        })
        
        try:
            # Check if category exists
            existing_category = await self.repository.get_by_id(category_id)
            if not existing_category:
                raise CategoryNotFoundError(f"Category with ID {category_id} not found")
            
            # Build update data with validation
            update_data = {}
            
            if name is not None:
                self._validate_name(name)
                # Check for duplicate name (excluding current category)
                name_conflict = await self.repository.get_by_name(name.strip())
                if name_conflict and name_conflict.id != category_id:
                    raise DuplicateCategoryNameError(f"Category with name '{name}' already exists")
                update_data['name'] = name.strip()
            
            if keywords is not None:
                self._validate_keywords(keywords)
                update_data['keywords'] = [kw.strip() for kw in keywords if kw.strip()]
            
            if exclude_keywords is not None:
                self._validate_exclude_keywords(exclude_keywords)
                update_data['exclude_keywords'] = [kw.strip() for kw in exclude_keywords if kw.strip()]
            
            if is_active is not None:
                update_data['is_active'] = is_active
            
            if not update_data:
                logger.warning(f"No update data provided for category {category_id}", extra={
                    "correlation_id": correlation_id
                })
                return existing_category
            
            # Update category
            updated_category = await self.repository.update_by_id(category_id, update_data)
            
            logger.info(f"Successfully updated category", extra={
                "correlation_id": correlation_id,
                "category_id": str(category_id),
                "updated_fields": list(update_data.keys())
            })
            
            return updated_category
            
        except (CategoryValidationError, CategoryNotFoundError, DuplicateCategoryNameError):
            # Re-raise known errors
            raise
        except Exception as e:
            logger.error(f"Failed to update category {category_id}: {e}", extra={
                "correlation_id": correlation_id,
                "category_id": str(category_id),
                "error_type": type(e).__name__
            })
            raise CategoryValidationError(f"Failed to update category: {str(e)}")
    
    async def delete_category(self, category_id: UUID) -> bool:
        """Delete a category by ID.
        
        Args:
            category_id: UUID of category to delete
            
        Returns:
            True if deleted, False if not found
            
        Raises:
            CategoryNotFoundError: If category not found
        """
        correlation_id = str(uuid4())
        
        logger.info(f"Deleting category {category_id}", extra={
            "correlation_id": correlation_id,
            "category_id": str(category_id)
        })
        
        try:
            # Check if category exists first
            existing_category = await self.repository.get_by_id(category_id)
            if not existing_category:
                raise CategoryNotFoundError(f"Category with ID {category_id} not found")
            
            # Delete category
            deleted = await self.repository.delete_by_id(category_id)
            
            if deleted:
                logger.info(f"Successfully deleted category", extra={
                    "correlation_id": correlation_id,
                    "category_id": str(category_id),
                    "category_name": existing_category.name
                })
            
            return deleted
            
        except CategoryNotFoundError:
            # Re-raise known errors
            raise
        except Exception as e:
            logger.error(f"Failed to delete category {category_id}: {e}", extra={
                "correlation_id": correlation_id,
                "category_id": str(category_id),
                "error_type": type(e).__name__
            })
            raise CategoryValidationError(f"Failed to delete category: {str(e)}")
    
    async def get_category_by_id(self, category_id: UUID) -> Optional[Category]:
        """Get a category by ID.
        
        Args:
            category_id: UUID of category to retrieve
            
        Returns:
            Category instance if found, None otherwise
        """
        try:
            return await self.repository.get_by_id(category_id)
        except Exception as e:
            logger.error(f"Failed to get category {category_id}: {e}")
            return None
    
    async def get_categories(
        self,
        active_only: bool = True,
        include_stats: bool = False
    ) -> List[Category]:
        """Get all categories with optional filtering.
        
        Args:
            active_only: If True, return only active categories
            include_stats: If True, include article counts (slower)
            
        Returns:
            List of Category instances
        """
        try:
            if include_stats:
                # Return categories with article counts
                stats_data = await self.repository.get_categories_with_article_counts()
                if active_only:
                    return [item for item in stats_data if item['is_active']]
                return stats_data
            
            if active_only:
                return await self.repository.get_active_categories()
            else:
                return await self.repository.get_all()
                
        except Exception as e:
            logger.error(f"Failed to get categories: {e}")
            return []
    
    async def search_categories(self, search_term: str) -> List[Category]:
        """Search categories by name.
        
        Args:
            search_term: Text to search for in category names
            
        Returns:
            List of matching Category instances
        """
        if not search_term or not search_term.strip():
            return []
        
        try:
            return await self.repository.search_categories_by_name(search_term.strip())
        except Exception as e:
            logger.error(f"Failed to search categories: {e}")
            return []
    
    def build_search_query(self, keywords: List[str]) -> str:
        """Build OR search query from keywords list.
        
        This method constructs a search query string that can be used
        for Google News searches with OR logic between keywords.
        
        Args:
            keywords: List of keywords to combine
            
        Returns:
            Search query string with OR logic
            
        Example:
            >>> manager.build_search_query(["python", "javascript"])
            "python OR javascript"
        """
        if not keywords:
            return ""
        
        # Clean and filter keywords
        cleaned_keywords = [kw.strip() for kw in keywords if kw and kw.strip()]
        if not cleaned_keywords:
            return ""
        
        # Build OR query
        return " OR ".join(f'"{kw}"' for kw in cleaned_keywords)
    
    def build_advanced_search_query(
        self, 
        keywords: List[str], 
        exclude_keywords: List[str] = None
    ) -> str:
        """Build advanced Google News search query with enhanced OR logic and exclusions.
        
        Creates a more sophisticated search query string that:
        1. Uses OR logic for keywords with proper quoting: "(python OR javascript OR AI)"
        2. Adds exclusions with minus prefix: "-java -php"  
        3. Handles special characters and validates input
        4. Supports complex query patterns
        
        Args:
            keywords: List of keywords to search for
            exclude_keywords: List of keywords to exclude
            
        Returns:
            Formatted search query string with advanced OR logic
            
        Example:
            >>> manager.build_advanced_search_query(
            ...     ["machine learning", "AI"], 
            ...     ["cryptocurrency"]
            ... )
            '("machine learning" OR "AI") -"cryptocurrency"'
        """
        if not keywords:
            return ""
        
        # Validate and sanitize keywords  
        cleaned_keywords = self._sanitize_search_keywords(keywords)
        if not cleaned_keywords:
            return ""
        
        # Build OR query for keywords with proper quoting
        if len(cleaned_keywords) == 1:
            base_query = f'"{cleaned_keywords[0]}"'
        else:
            quoted_keywords = [f'"{kw}"' for kw in cleaned_keywords]
            base_query = f"({' OR '.join(quoted_keywords)})"
        
        # Add exclusions with proper quoting
        if exclude_keywords:
            cleaned_exclusions = self._sanitize_search_keywords(exclude_keywords)
            if cleaned_exclusions:
                exclude_part = " ".join([f'-"{kw}"' for kw in cleaned_exclusions])
                base_query = f"{base_query} {exclude_part}"
        
        return base_query
    
    def validate_search_query_complexity(self, keywords: List[str], exclude_keywords: List[str] = None) -> Dict[str, Any]:
        """Validate and analyze search query complexity.
        
        Args:
            keywords: List of keywords to analyze
            exclude_keywords: List of exclude keywords to analyze
            
        Returns:
            Dictionary with validation results and complexity metrics
        """
        result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "complexity": "simple",
            "total_keywords": 0,
            "cleaned_keywords_count": 0,
            "estimated_query_length": 0
        }
        
        try:
            # Validate keywords
            if not keywords:
                result["is_valid"] = False
                result["errors"].append("Keywords list cannot be empty")
                return result
            
            cleaned_keywords = self._sanitize_search_keywords(keywords)
            cleaned_exclusions = self._sanitize_search_keywords(exclude_keywords or [])
            
            if not cleaned_keywords:
                result["is_valid"] = False
                result["errors"].append("No valid keywords after sanitization")
                return result
            
            # Calculate metrics
            total_keywords = len(cleaned_keywords) + len(cleaned_exclusions)
            result["total_keywords"] = total_keywords
            result["cleaned_keywords_count"] = len(cleaned_keywords)
            
            # Determine complexity
            if total_keywords <= 2:
                result["complexity"] = "simple"
            elif total_keywords <= 5:
                result["complexity"] = "medium"
            else:
                result["complexity"] = "complex"
                result["warnings"].append("Complex queries may have slower performance")
            
            # Estimate query length
            test_query = self.build_advanced_search_query(cleaned_keywords, cleaned_exclusions)
            result["estimated_query_length"] = len(test_query)
            
            if result["estimated_query_length"] > 500:
                result["warnings"].append("Very long query - may hit search API limits")
            
        except Exception as e:
            result["is_valid"] = False
            result["errors"].append(f"Query validation failed: {str(e)}")
        
        return result
    
    def _sanitize_search_keywords(self, keywords: List[str]) -> List[str]:
        """Sanitize and validate keywords for search queries.
        
        Args:
            keywords: Raw keywords list
            
        Returns:
            List of cleaned and validated keywords
        """
        if not keywords:
            return []
        
        cleaned = []
        for keyword in keywords:
            if not keyword or not isinstance(keyword, str):
                continue
                
            # Strip whitespace 
            clean_kw = keyword.strip()
            if not clean_kw:
                continue
            
            # Remove potentially problematic characters but keep essential ones
            # Allow letters, numbers, spaces, hyphens, and basic punctuation
            sanitized = ''.join(c for c in clean_kw if c.isalnum() or c in ' -._')
            sanitized = ' '.join(sanitized.split())  # Normalize whitespace
            
            if sanitized and len(sanitized) <= self.max_keyword_length:
                cleaned.append(sanitized)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_cleaned = []
        for kw in cleaned:
            if kw.lower() not in seen:
                seen.add(kw.lower())
                unique_cleaned.append(kw)
        
        return unique_cleaned
    
    def _validate_name(self, name: str) -> None:
        """Validate category name.
        
        Args:
            name: Category name to validate
            
        Raises:
            CategoryValidationError: If validation fails
        """
        if not name or not name.strip():
            raise CategoryValidationError("Category name cannot be empty")
        
        if len(name.strip()) > self.max_name_length:
            raise CategoryValidationError(
                f"Category name cannot exceed {self.max_name_length} characters"
            )
        
        # Check for invalid characters (optional - could add more restrictions)
        if any(char in name for char in ['<', '>', '&', '"', "'"]):
            raise CategoryValidationError("Category name contains invalid characters")
    
    def _validate_keywords(self, keywords: List[str]) -> None:
        """Validate keywords list.
        
        Args:
            keywords: List of keywords to validate
            
        Raises:
            CategoryValidationError: If validation fails
        """
        if not keywords:
            raise CategoryValidationError("Keywords list cannot be empty")
        
        # Filter and clean keywords
        cleaned_keywords = [kw.strip() for kw in keywords if kw.strip()]
        
        if not cleaned_keywords:
            raise CategoryValidationError("At least one valid keyword is required")
        
        if len(cleaned_keywords) > self.max_keywords:
            raise CategoryValidationError(
                f"Cannot exceed {self.max_keywords} keywords per category"
            )
        
        # Validate individual keywords
        for keyword in cleaned_keywords:
            if len(keyword) > self.max_keyword_length:
                raise CategoryValidationError(
                    f"Keyword '{keyword}' exceeds maximum length of {self.max_keyword_length} characters"
                )
        
        # Check for duplicates
        if len(cleaned_keywords) != len(set(cleaned_keywords)):
            raise CategoryValidationError("Duplicate keywords are not allowed")
    
    def _validate_exclude_keywords(self, exclude_keywords: List[str]) -> None:
        """Validate exclude keywords list.
        
        Args:
            exclude_keywords: List of exclude keywords to validate
            
        Raises:
            CategoryValidationError: If validation fails
        """
        if not exclude_keywords:
            return  # Empty list is valid
        
        # Filter and clean keywords
        cleaned_keywords = [kw.strip() for kw in exclude_keywords if kw.strip()]
        
        if len(cleaned_keywords) > self.max_keywords:
            raise CategoryValidationError(
                f"Cannot exceed {self.max_keywords} exclude keywords per category"
            )
        
        # Validate individual keywords
        for keyword in cleaned_keywords:
            if len(keyword) > self.max_keyword_length:
                raise CategoryValidationError(
                    f"Exclude keyword '{keyword}' exceeds maximum length of {self.max_keyword_length} characters"
                )
        
        # Check for duplicates
        if len(cleaned_keywords) != len(set(cleaned_keywords)):
            raise CategoryValidationError("Duplicate exclude keywords are not allowed")