# API Integration Notes

## Common Issues and Solutions

### Frontend-Backend API Response Mapping

**Issue Discovered (2025-09-13):** Categories page not loading despite working Home page

**Root Cause:**
- Frontend `CategoriesService.getCategories()` expected `Category[]` directly
- Backend API returns wrapped response: `{categories: Category[], total: number, active_count: number}`

**Symptom:**
- Home page loads fine (static content)
- Categories page appears blank/broken (relies on API data)
- No console errors visible in production build

**Solution Applied:**
```typescript
// Before (incorrect)
static async getCategories(): Promise<Category[]> {
  return apiClient.get<Category[]>(url); // Expected Category[] directly
}

// After (correct)
static async getCategories(): Promise<Category[]> {
  const response = await apiClient.get<{categories: Category[], total: number, active_count: number}>(url);
  return response.categories; // Extract categories array from response object
}
```

**Prevention:**
1. Always check backend API documentation/schemas before writing frontend services
2. Test API responses directly with `curl` or API tools
3. Use TypeScript interfaces that match actual backend response structure
4. Consider creating response wrapper types for consistency

### Debugging API Integration Issues

**Quick Debug Steps:**
1. Test backend API directly: `curl -s http://localhost:8000/api/v1/categories`
2. Check browser Network tab for API call failures
3. Verify response structure matches frontend expectations
4. Check Docker logs: `docker-compose logs web` and `docker-compose logs frontend`

**Common Patterns:**
- Backend returns `{data: T}` but frontend expects `T`
- Backend returns `{items: T[]}` but frontend expects `T[]`
- Backend returns `{results: T[], pagination: {...}}` but frontend expects `T[]`

Always align frontend service layer with actual backend API contracts.