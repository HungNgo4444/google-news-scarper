# Google News Scraper Brownfield Enhancement PRD

## Intro Project Analysis and Context

### Existing Project Overview

**Analysis Source**: IDE-based fresh analysis của Google News Scraper project

**Current Project State**: 
Dự án hiện tại là một **REST API backend system** với:
- FastAPI framework
- PostgreSQL database 
- Redis cache/message broker
- Celery task queue system
- Docker containerized architecture
- Crawling engine cho Google News
- Category management system

### Available Documentation Analysis

**Available Documentation**:
- ✅ Tech Stack Documentation (từ source code)
- ✅ Source Tree/Architecture (đã xem qua)
- ✅ API Documentation (Swagger UI available)
- ❌ UX/UI Guidelines (chưa có)
- ❌ Frontend specifications (chưa có)
- ✅ Docker deployment setup

### Enhancement Scope Definition

**Enhancement Type**: ☑️ New Feature Addition (Web Interface)

**Enhancement Description**: 
Tạo web interface đơn giản cho Admin/Developer để quản lý Google News Scraper system thay vì sử dụng API trực tiếp.

**Core Features** (Updated Status):
1. ✅ Categories Management (CRUD operations) - **COMPLETED**
2. 🔧 Manual crawl job triggering - **BACKEND READY, FRONTEND PENDING**
3. ❌ Schedule jobs configuration - **NOT STARTED**
4. ❌ View crawled articles - **NOT STARTED**

**Technical Stack Choice** (Implementation Status):
- ✅ Frontend: Vite + React + TypeScript - **IMPLEMENTED**
- ✅ Styling: TailwindCSS + Shadcn UI - **IMPLEMENTED**
- ✅ Target Users: Admin/Developer - **CONFIRMED**
- ✅ UI/UX: Simple, functional (không cầu kỳ) - **ACHIEVED**

**Impact Assessment**: ☑️ Minimal Impact (isolated additions) - vì chỉ thêm frontend không ảnh hưởng backend API hiện tại.

### Goals and Background Context

**Goals**:
- Cung cấp web interface thân thiện thay thế cho Swagger UI/curl commands
- Đơn giản hóa việc quản lý categories và crawl jobs 
- Cho phép xem và monitor articles đã crawl được
- Thiết lập và quản lý scheduled crawling jobs

**Background Context**:
Hệ thống Google News Scraper hiện tại hoạt động tốt với REST API backend, nhưng việc tương tác qua Swagger UI hoặc curl commands không thuận tiện cho việc quản lý hàng ngày. Web interface sẽ cung cấp giao diện trực quan để thực hiện các tác vụ quản trị mà không cần kiến thức technical về API calls.

### Current Implementation Progress

**✅ COMPLETED FEATURES:**

1. **Frontend Development Environment** (Story 1.1)
   - ✅ Vite + React + TypeScript + TailwindCSS + Shadcn UI setup
   - ✅ Docker containerization with frontend service
   - ✅ API integration layer (services/api.ts, categoriesService.ts)
   - ✅ Comprehensive test setup (Vitest, Testing Library, Jest-DOM)

2. **Categories Management Interface** (Story 1.2)
   - ✅ Full CRUD operations for categories
   - ✅ Components: CategoriesList, CategoryForm, DeleteConfirmationDialog
   - ✅ Integration with `/api/v1/categories` API endpoints
   - ✅ Form validation and error handling
   - ✅ TypeScript interfaces and type safety

3. **Backend Stability & API Fixes** (Hotfixes)
   - ✅ Pydantic Settings configuration fixes (src/shared/config.py)
   - ✅ Async context manager fixes (src/database/repositories/base.py)
   - ✅ Category API endpoints reliability improvements

**🔧 PARTIALLY COMPLETED:**

4. **Crawling Infrastructure** (Backend Ready)
   - ✅ Celery task system with comprehensive error handling
   - ✅ `trigger_category_crawl_task` for manual job triggering
   - ✅ Job tracking with CrawlJobRepository
   - ✅ Health monitoring and cleanup tasks
   - ❌ Frontend UI for manual job triggering (Story 2.1 - Pending)

**❌ REMAINING FEATURES:**

5. **Articles Viewing Interface** (Story 2.2 - Not Started)
   - ❌ Backend: `/api/v1/articles` API endpoints needed
   - ❌ Frontend: Articles listing, search, and filtering UI
   - ❌ ArticleRepository implementation gaps

6. **Job Scheduling Interface** (Story 2.3 - Not Started)
   - ❌ Backend: Dynamic scheduling API endpoints needed
   - ❌ Frontend: Schedule creation and management UI
   - ❌ Integration with Celery Beat for dynamic scheduling

**📊 Progress Summary:**
- **Epic Progress**: 50% Complete (2.5/5 major features)
- **Frontend Environment**: 100% Complete
- **Categories Management**: 100% Complete
- **Manual Job Triggering**: 70% Complete (Backend ready, Frontend pending)
- **Articles Interface**: 0% Complete
- **Job Scheduling**: 0% Complete

### Change Log

| Change | Date | Version | Description | Author |
|--------|------|---------|-------------|--------|
| Initial PRD | 2025-09-12 | v1.0 | Web Interface Enhancement PRD | BMad Master |
| Progress Update | 2025-09-14 | v1.1 | Updated to reflect actual implementation progress and roadmap realignment | BMad Master |

## Requirements

### Functional Requirements

**FR1**: Web interface sẽ cung cấp CRUD operations cho categories (Create, Read, Update, Delete) tương tác với existing `/api/v1/categories` endpoints

**FR2**: System sẽ cho phép trigger manual crawl jobs cho specific categories thông qua existing Celery task system

**FR3**: Interface sẽ cung cấp scheduling functionality để set up recurring crawl jobs cho categories với configurable intervals  

**FR4**: Web app sẽ display danh sách articles đã crawl được với filtering và search capabilities

**FR5**: System sẽ show real-time status của crawl jobs (pending, running, completed, failed) thông qua existing job tracking system

### Non Functional Requirements

**NFR1**: Web interface phải maintain existing API performance characteristics và không impact backend system response times

**NFR2**: Frontend application phải responsive và functional trên desktop browsers (Chrome, Firefox, Safari)

**NFR3**: Page load times không được vượt quá 3 seconds với typical data volumes

**NFR4**: UI phải simple, clean và intuitive cho Admin/Developer users mà không cần extensive training

**NFR5**: Application phải handle API errors gracefully với user-friendly error messages

### Compatibility Requirements

**CR1**: Web interface phải consume existing REST API endpoints (`/api/v1/categories`, `/health`, etc.) without requiring API modifications

**CR2**: Frontend application phải compatible với existing Docker containerized deployment without affecting current services

**CR3**: Authentication/authorization (nếu có) phải integrate với existing backend security model

**CR4**: New frontend service phải coexist với existing Swagger UI documentation và không conflict về ports/routing

## User Interface Enhancement Goals

### Integration with Existing UI

**Design System Approach**: 
Sẽ tạo một standalone web application với TailwindCSS + Shadcn UI component library. Vì đây là new frontend application (không có existing UI), chúng ta sẽ thiết lập design system mới nhưng consistent và professional.

**Component Strategy**:
- Sử dụng Shadcn UI components như Button, Input, Table, Dialog, Select để đảm bảo consistency
- TailwindCSS utility classes cho custom styling và responsive design
- Neutral color palette (grays, blues) phù hợp với admin interface
- Typography scale consistent throughout application

### Modified/New Screens and Views

**Core Views cần implement**:

1. **Categories Management View**
   - Categories list table với actions (Edit, Delete, Toggle Active)
   - Add new category form/modal
   - Edit category form/modal

2. **Crawl Jobs Management View** 
   - Manual crawl trigger interface với category selection
   - Job scheduling form với time/interval configuration
   - Active jobs status list với real-time updates

3. **Articles View**
   - Articles listing table với pagination
   - Search và filter functionality (by category, date range)
   - Article detail view/modal

4. **Job Status Monitor**
   - Current running jobs display
   - Job history với status indicators (success/failed/pending)

### UI Consistency Requirements

**Visual Consistency Standards**:
- **Color Scheme**: Consistent với admin interface conventions (neutral với accent colors cho actions)
- **Spacing**: TailwindCSS spacing scale (4px increments) 
- **Typography**: Consistent font family và size hierarchy
- **Interactive States**: Hover, focus, disabled states cho tất cả interactive elements

**Component Consistency**:
- Buttons: Consistent sizing (sm, md, lg) và variants (primary, secondary, destructive)
- Forms: Consistent form field styling, validation states, error messaging
- Tables: Consistent row styling, sorting indicators, action buttons placement
- Modals/Dialogs: Consistent overlay styling, header/footer layout

**Responsive Behavior**:
- Desktop-first approach (admin tool primarily used on desktop)
- Minimum mobile compatibility cho basic functionality
- Tables responsive với horizontal scroll on smaller screens

## Technical Constraints and Integration Requirements

### Existing Technology Stack

**Languages**: Python 3.11 (Backend), JavaScript/TypeScript (New Frontend)
**Frameworks**: FastAPI, Celery, SQLAlchemy, Alembic
**Database**: PostgreSQL 15
**Infrastructure**: Docker Compose, Uvicorn ASGI server
**External Dependencies**: Google News APIs, newspaper4k library

**New Frontend Stack**:
**Frontend Framework**: Node.js application 
**Styling**: TailwindCSS + Shadcn UI components
**Build Tool**: Vite/Next.js (to be determined)
**Package Manager**: npm/yarn

### Integration Approach

**Database Integration Strategy**: Frontend sẽ KHÔNG directly access database, chỉ consume REST APIs từ existing FastAPI backend

**API Integration Strategy**: 
- Consume existing `/api/v1/categories` endpoints
- Use existing `/health` endpoints cho system monitoring
- Có thể cần thêm API endpoints cho articles listing và job management
- Authentication headers (nếu cần) sẽ được forward đến backend APIs

**Frontend Integration Strategy**: 
- Standalone Single Page Application (SPA) 
- Axios/Fetch cho API calls đến FastAPI backend
- Client-side routing (React Router hoặc similar)
- State management với React Context hoặc lightweight solution

**Testing Integration Strategy**: 
- Frontend unit tests với Jest/Vitest
- Integration tests với existing API endpoints  
- E2E testing với Playwright/Cypress
- Separate test suite không impact existing backend tests

### Code Organization and Standards

**File Structure Approach**:
```
frontend/
├── src/
│   ├── components/     # Reusable UI components
│   ├── pages/         # Main application views
│   ├── services/      # API integration layer
│   ├── hooks/         # Custom React hooks
│   └── utils/         # Helper functions
├── public/
└── package.json
```

**Naming Conventions**: 
- PascalCase cho React components
- camelCase cho functions và variables
- kebab-case cho file names
- Consistent với existing Python backend snake_case cho API data

**Coding Standards**:
- ESLint + Prettier cho code formatting
- TypeScript cho type safety
- Component composition over inheritance
- Functional components với hooks

**Documentation Standards**:
- JSDoc comments cho complex functions
- README với setup và development instructions
- Component documentation với Storybook (optional)

### Deployment and Operations

**Build Process Integration**:
- Separate Docker container cho frontend application
- Multi-stage build với Node.js base image
- Static asset optimization và minification
- Environment-specific configuration

**Deployment Strategy**:
- Add frontend service vào existing docker-compose.yml
- Expose trên port khác với backend (ví dụ: 3000)
- Nginx reverse proxy (optional) cho production routing
- Health check endpoint cho container orchestration

**Monitoring and Logging**:
- Browser console logging cho development
- Error boundary components cho production error handling
- Integration với existing backend logging correlation IDs
- Basic performance monitoring

**Configuration Management**:
- Environment variables cho API endpoints
- Build-time configuration cho different environments  
- Runtime configuration cho feature flags (nếu cần)

### Risk Assessment and Mitigation

**Technical Risks**:
- API endpoint limitations cho articles listing → **Mitigation**: Survey existing endpoints, identify gaps sớm
- CORS issues khi frontend call backend APIs → **Mitigation**: Configure CORS properly trong FastAPI settings
- Performance với large datasets → **Mitigation**: Implement pagination và lazy loading

**Integration Risks**:
- Breaking changes trong existing APIs → **Mitigation**: Version API calls và backward compatibility
- Authentication/authorization complexity → **Mitigation**: Start với no-auth, add incrementally
- Docker networking issues → **Mitigation**: Use docker-compose networking, test early

**Deployment Risks**:
- Port conflicts với existing services → **Mitigation**: Document port allocation, use different ports
- Build process complexity → **Mitigation**: Keep build simple, avoid complex toolchains initially
- Resource consumption → **Mitigation**: Lightweight Node.js setup, monitor resource usage

**Mitigation Strategies**:
- **Incremental Development**: Build và deploy incrementally để test integration sớm
- **API Documentation**: Maintain clear documentation về API contracts
- **Rollback Plan**: Keep existing Swagger UI available như fallback option
- **Testing Strategy**: Comprehensive testing với real backend APIs

## Epic and Story Structure

### Epic Approach

**Epic Structure Decision**: **Single Epic** với rationale: Web interface là một cohesive feature set với shared frontend architecture, common API integration patterns, và unified user experience. Breaking into multiple epics sẽ tạo ra artificial boundaries và complicate deployment/testing.

# Epic 1: Google News Scraper Web Interface

**Epic Goal**: Tạo web interface đơn giản cho Admin/Developer để quản lý categories, trigger crawl jobs, set schedules, và view articles mà không cần sử dụng Swagger UI hoặc command line tools.

**Integration Requirements**: 
- Frontend app sẽ consume existing FastAPI REST endpoints
- Minimal hoặc không có changes đến existing backend architecture  
- Coexist với current Docker containerized deployment
- Maintain existing system performance và reliability

## Story Sequence (Updated with Implementation Status)

### ✅ Story 1.1: Setup Frontend Development Environment - **COMPLETED**
As an **Admin/Developer**,
I want **a properly configured frontend development environment**,
so that **I can develop the web interface efficiently without affecting the existing backend system**.

**Acceptance Criteria:**
1. Node.js frontend project initialized với TailwindCSS + Shadcn UI
2. Development server chạy trên port 3000 (không conflict với existing services)
3. API integration layer configured để call existing FastAPI endpoints
4. Docker configuration updated để include frontend service
5. Build và deployment pipeline working end-to-end

**Integration Verification:**
- **IV1**: Existing backend services continue running unaffected when frontend development server starts
- **IV2**: API calls từ frontend successfully reach existing `/health` endpoint
- **IV3**: Docker compose up hoàn toàn functional với cả frontend và backend services

### ✅ Story 1.2: Categories Management Interface - **COMPLETED**
As an **Admin/Developer**,
I want **a web interface to manage categories (view, create, edit, delete)**,
so that **I can manage crawling categories without using Swagger UI or curl commands**.

**Acceptance Criteria:**
1. Categories list view displaying all categories từ `/api/v1/categories`
2. Create category form/modal với validation
3. Edit category functionality với existing data population
4. Delete category với confirmation dialog
5. Toggle active/inactive status cho categories
6. Error handling cho API failures với user-friendly messages

**Integration Verification:**
- **IV1**: All category operations use existing `/api/v1/categories` endpoints without modifications
- **IV2**: Existing Swagger UI category endpoints continue working alongside new interface
- **IV3**: No performance degradation trong category API response times

### 🔧 Story 2.1: Manual Crawl Job Triggering - **BACKEND READY, FRONTEND PENDING**
As an **Admin/Developer**,
I want **to trigger crawl jobs manually through the web interface**,
so that **I can start crawling for specific categories on-demand**.

**Acceptance Criteria:**
1. Category selection dropdown cho manual crawl triggering
2. Trigger crawl button với confirmation
3. Job status display sau khi trigger (job ID, status)
4. Integration với existing Celery task system
5. Real-time job status updates (polling-based)

**Implementation Status:**
- ✅ **Backend Complete**: `trigger_category_crawl_task` Celery task implemented
- ✅ **Backend Complete**: Job tracking with CrawlJobRepository
- ✅ **Backend Complete**: Comprehensive error handling and retry logic
- ❌ **Frontend Pending**: UI components for job triggering
- ❌ **Frontend Pending**: Real-time job status monitoring interface

**Integration Verification:**
- **IV1**: Manual triggers use existing `trigger_category_crawl_task` Celery task ✅ **VERIFIED**
- **IV2**: Existing worker containers process new jobs without issues ✅ **VERIFIED**
- **IV3**: Job monitoring doesn't interfere với existing Celery Beat scheduled jobs ✅ **VERIFIED**

### ❌ Story 2.2: Articles Viewing Interface - **NOT STARTED**
As an **Admin/Developer**,
I want **to view articles that have been crawled**,
so that **I can verify crawling results and monitor content quality**.

**Acceptance Criteria:**
1. Articles list view với pagination
2. Filter by category và date range
3. Search functionality across article titles/content
4. Article detail view/modal
5. Sort by crawl date, category, status

**Implementation Requirements:**
- ❌ **Backend**: `/api/v1/articles` API endpoints (GET with filtering/pagination)
- ❌ **Backend**: ArticleRepository method implementations
- ❌ **Frontend**: Articles listing table with pagination
- ❌ **Frontend**: Search and filter components
- ❌ **Frontend**: Article detail modal/view

**Integration Verification:**
- **IV1**: May require new API endpoint `/api/v1/articles` - backend impact assessment needed ❌ **PENDING**
- **IV2**: Article queries don't impact crawling performance ❌ **PENDING**
- **IV3**: Large article datasets handled efficiently với pagination ❌ **PENDING**

### ❌ Story 2.3: Job Scheduling Interface - **NOT STARTED**
As an **Admin/Developer**,
I want **to set up recurring crawl schedules for categories**,
so that **I can automate crawling without manual intervention**.

**Acceptance Criteria:**
1. Schedule creation form với category selection
2. Time interval configuration (1 minute, 5 minutes, 15 minutes, 30 minutes, 1 hour)
3. Schedule activation/deactivation
4. View existing schedules với next run times
5. Integration với Celery Beat scheduler

**Implementation Requirements:**
- ❌ **Backend**: Dynamic Celery Beat scheduling API endpoints
- ❌ **Backend**: Schedule configuration persistence and management
- ❌ **Frontend**: Schedule creation form with interval configuration
- ❌ **Frontend**: Schedule management table with activation/deactivation
- ❌ **Frontend**: Next run time display and schedule monitoring

**Integration Verification:**
- **IV1**: Schedules integrate với existing Celery Beat configuration ❌ **PENDING**
- **IV2**: Existing scheduled tasks continue running unaffected ❌ **PENDING**
- **IV3**: Schedule changes don't require container restarts ❌ **PENDING**

## Updated Story Sequence Analysis

**✅ COMPLETED DEPENDENCIES:**
- ✅ Story 1.1 → 1.2 (Frontend environment → Categories UI) - **SATISFIED**
- ✅ Story 1.2 Foundation → 2.1 (Categories exist → Manual crawl triggers) - **SATISFIED**

**🔧 CURRENT STATUS:**
- Story 2.1 (Manual Crawl Triggering): Backend ready, Frontend pending
- Story 2.2 (Articles Interface): Can develop parallel, no blocking dependencies
- Story 2.3 (Job Scheduling): Depends on Story 2.1 completion for validation

**📋 RECOMMENDED NEXT STEPS:**
1. **Priority 1**: Complete Story 2.1 Frontend (Manual job triggering UI)
2. **Priority 2**: Implement Story 2.2 Backend (Articles API endpoints)
3. **Priority 3**: Develop Story 2.2 Frontend (Articles viewing interface)
4. **Priority 4**: Implement Story 2.3 (Job scheduling system)

**Risk mitigation trong updated sequence:**
- ✅ Each completed story delivers standalone value
- ✅ Rollback possible tại any point without breaking existing functionality
- ✅ Progressive complexity maintained from simple CRUD → job management → scheduling
- 🔧 Hotfixes integrated without disrupting main story flow