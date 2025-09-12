"""FastAPI routes for Category management endpoints.

This module provides REST API endpoints for Category CRUD operations
including create, read, update, delete, and search functionality.

Endpoints:
- GET /categories - List all categories with filtering options
- POST /categories - Create a new category
- GET /categories/{category_id} - Get specific category by ID
- PUT /categories/{category_id} - Update category by ID
- DELETE /categories/{category_id} - Delete category by ID

Features:
- Proper HTTP status codes (200, 201, 400, 404, 409)
- Request validation using Pydantic schemas
- Error handling with custom exceptions
- Optional statistics inclusion
- Search and filtering capabilities

Example:
    Using the Category API:
    
    ```python
    import httpx
    
    async def test_category_api():
        async with httpx.AsyncClient() as client:
            # Create category
            response = await client.post("/api/v1/categories", json={
                "name": "Technology",
                "keywords": ["python", "javascript"],
                "exclude_keywords": ["deprecated"]
            })
            category = response.json()
            
            # Get category
            response = await client.get(f"/api/v1/categories/{category['id']}")
            print(f"Retrieved: {response.json()['name']}")
            
            # Update category
            response = await client.put(f"/api/v1/categories/{category['id']}", json={
                "keywords": ["python", "javascript", "ai"]
            })
            
            # Delete category
            await client.delete(f"/api/v1/categories/{category['id']}")
    ```
"""

import logging
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends, Query, status
from pydantic import ValidationError

from src.core.category.manager import CategoryManager
from src.database.repositories.category_repo import CategoryRepository
from src.shared.config import get_settings, Settings
from src.shared.exceptions import (
    CategoryValidationError,
    CategoryNotFoundError,
    DuplicateCategoryNameError
)
from src.api.schemas.category import (
    CreateCategoryRequest,
    UpdateCategoryRequest,
    CategoryResponse,
    CategoryListResponse,
    CategoryWithStatsResponse,
    ErrorResponse,
    ValidationErrorResponse
)

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/v1/categories", tags=["categories"])


def get_category_manager(settings: Settings = Depends(get_settings)) -> CategoryManager:
    """Dependency to provide CategoryManager instance."""
    repository = CategoryRepository()
    return CategoryManager(repository, settings)


@router.get(
    "",
    response_model=CategoryListResponse,
    summary="List all categories",
    description="Retrieve all categories with optional filtering by active status and statistics inclusion."
)
async def list_categories(
    active_only: bool = Query(
        True,
        description="Filter to show only active categories"
    ),
    include_stats: bool = Query(
        False,
        description="Include article count statistics (slower)"
    ),
    manager: CategoryManager = Depends(get_category_manager)
) -> CategoryListResponse:
    """List all categories with optional filtering."""
    try:
        categories = await manager.get_categories(
            active_only=active_only,
            include_stats=include_stats
        )
        
        if include_stats:
            # categories contains dict data with stats
            category_responses = [
                CategoryWithStatsResponse(
                    id=cat['id'],
                    name=cat['name'],
                    keywords=cat['keywords'],
                    exclude_keywords=cat['exclude_keywords'],
                    is_active=cat['is_active'],
                    created_at=cat['created_at'],
                    updated_at=cat['created_at'],  # Note: stats query doesn't include updated_at
                    article_count=cat['article_count']
                ) for cat in categories
            ]
            
            # Count active categories from stats data
            active_count = sum(1 for cat in categories if cat['is_active'])
            
        else:
            # categories contains Category model instances
            category_responses = [
                CategoryResponse(
                    id=cat.id,
                    name=cat.name,
                    keywords=cat.keywords,
                    exclude_keywords=cat.exclude_keywords,
                    is_active=cat.is_active,
                    created_at=cat.created_at,
                    updated_at=cat.updated_at
                ) for cat in categories
            ]
            
            if active_only:
                active_count = len(categories)
            else:
                # Need to count active categories separately
                active_categories = await manager.get_categories(active_only=True)
                active_count = len(active_categories)
        
        return CategoryListResponse(
            categories=category_responses,
            total=len(categories),
            active_count=active_count
        )
        
    except Exception as e:
        logger.error(f"Failed to list categories: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve categories"
        )


@router.post(
    "",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new category",
    description="Create a new category with name, keywords, and optional exclude keywords.",
    responses={
        201: {"description": "Category created successfully"},
        400: {"model": ValidationErrorResponse, "description": "Validation error"},
        409: {"model": ErrorResponse, "description": "Category name already exists"}
    }
)
async def create_category(
    request: CreateCategoryRequest,
    manager: CategoryManager = Depends(get_category_manager)
) -> CategoryResponse:
    """Create a new category."""
    try:
        category = await manager.create_category(
            name=request.name,
            keywords=request.keywords,
            exclude_keywords=request.exclude_keywords,
            is_active=request.is_active
        )
        
        return CategoryResponse(
            id=category.id,
            name=category.name,
            keywords=category.keywords,
            exclude_keywords=category.exclude_keywords,
            is_active=category.is_active,
            created_at=category.created_at,
            updated_at=category.updated_at
        )
        
    except DuplicateCategoryNameError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except CategoryValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to create category: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create category"
        )


@router.get(
    "/{category_id}",
    response_model=CategoryResponse,
    summary="Get category by ID",
    description="Retrieve a specific category by its UUID.",
    responses={
        200: {"description": "Category found"},
        404: {"model": ErrorResponse, "description": "Category not found"}
    }
)
async def get_category(
    category_id: UUID,
    manager: CategoryManager = Depends(get_category_manager)
) -> CategoryResponse:
    """Get a category by ID."""
    try:
        category = await manager.get_category_by_id(category_id)
        
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Category with ID {category_id} not found"
            )
        
        return CategoryResponse(
            id=category.id,
            name=category.name,
            keywords=category.keywords,
            exclude_keywords=category.exclude_keywords,
            is_active=category.is_active,
            created_at=category.created_at,
            updated_at=category.updated_at
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Failed to get category {category_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve category"
        )


@router.put(
    "/{category_id}",
    response_model=CategoryResponse,
    summary="Update category by ID",
    description="Update an existing category's name, keywords, exclude keywords, or active status.",
    responses={
        200: {"description": "Category updated successfully"},
        400: {"model": ValidationErrorResponse, "description": "Validation error"},
        404: {"model": ErrorResponse, "description": "Category not found"},
        409: {"model": ErrorResponse, "description": "Category name already exists"}
    }
)
async def update_category(
    category_id: UUID,
    request: UpdateCategoryRequest,
    manager: CategoryManager = Depends(get_category_manager)
) -> CategoryResponse:
    """Update a category by ID."""
    try:
        # Check if any fields are provided for update
        update_data = request.dict(exclude_unset=True)
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields provided for update"
            )
        
        updated_category = await manager.update_category(
            category_id=category_id,
            name=request.name,
            keywords=request.keywords,
            exclude_keywords=request.exclude_keywords,
            is_active=request.is_active
        )
        
        if not updated_category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Category with ID {category_id} not found"
            )
        
        return CategoryResponse(
            id=updated_category.id,
            name=updated_category.name,
            keywords=updated_category.keywords,
            exclude_keywords=updated_category.exclude_keywords,
            is_active=updated_category.is_active,
            created_at=updated_category.created_at,
            updated_at=updated_category.updated_at
        )
        
    except CategoryNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except DuplicateCategoryNameError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except CategoryValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to update category {category_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update category"
        )


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete category by ID",
    description="Delete a category and all its associations. This is a hard delete operation.",
    responses={
        204: {"description": "Category deleted successfully"},
        404: {"model": ErrorResponse, "description": "Category not found"}
    }
)
async def delete_category(
    category_id: UUID,
    manager: CategoryManager = Depends(get_category_manager)
):
    """Delete a category by ID."""
    try:
        deleted = await manager.delete_category(category_id)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Category with ID {category_id} not found"
            )
        
        # Return 204 No Content on successful deletion
        return None
        
    except CategoryNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to delete category {category_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete category"
        )


@router.get(
    "/search/{search_term}",
    response_model=List[CategoryResponse],
    summary="Search categories by name",
    description="Search for categories by name using case-insensitive partial matching.",
    responses={
        200: {"description": "Search results (may be empty list)"}
    }
)
async def search_categories(
    search_term: str,
    manager: CategoryManager = Depends(get_category_manager)
) -> List[CategoryResponse]:
    """Search categories by name."""
    try:
        categories = await manager.search_categories(search_term)
        
        return [
            CategoryResponse(
                id=cat.id,
                name=cat.name,
                keywords=cat.keywords,
                exclude_keywords=cat.exclude_keywords,
                is_active=cat.is_active,
                created_at=cat.created_at,
                updated_at=cat.updated_at
            ) for cat in categories
        ]
        
    except Exception as e:
        logger.error(f"Failed to search categories with term '{search_term}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search categories"
        )