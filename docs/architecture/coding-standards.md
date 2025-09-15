# Coding Standards

## Critical Fullstack Rules

- **Type Sharing:** Always define shared types in a common location (`frontend/src/types/shared.ts`) and ensure backend Pydantic models match frontend TypeScript interfaces
- **API Calls:** Never make direct fetch/axios calls in components - use the centralized service layer (`frontend/src/services/`) for all API interactions
- **Environment Variables:** Access only through config objects (`src/shared/config.py` for backend, `vite.config.ts` env handling for frontend), never process.env directly
- **Error Handling:** All API routes must use the standard error handler middleware, frontend must handle all error states with user-friendly messages
- **State Updates:** Never mutate state directly - use proper React state patterns (useState, useReducer) and immutable update patterns
- **Container Communication:** Frontend must communicate with backend only through the defined API contracts, no direct database access
- **Docker Port Management:** Use defined ports consistently (3000 for frontend, 8000 for backend) and update docker-compose.yml for any changes
- **Database Migrations:** All schema changes must go through Alembic migrations, never modify database directly in production

## Naming Conventions

| Element | Frontend | Backend | Example |
|---------|----------|---------|---------|
| Components | PascalCase | - | `CategoryForm.tsx` |
| Hooks | camelCase with 'use' | - | `useCategories.ts` |
| API Routes | - | kebab-case | `/api/v1/crawl-jobs` |
| Database Tables | - | snake_case | `crawl_jobs` |
| Service Methods | camelCase | snake_case | `createCategory` / `create_category` |
| Constants | UPPER_SNAKE_CASE | UPPER_SNAKE_CASE | `API_BASE_URL` |
| Environment Variables | UPPER_SNAKE_CASE | UPPER_SNAKE_CASE | `VITE_API_BASE_URL` |