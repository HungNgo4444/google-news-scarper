# Google News Scraper Web Interface Enhancement PRD v2.0

## Executive Summary

**Project Type**: Brownfield Enhancement - Web Interface Addition
**Target Users**: Admin/Developer
**Primary Goal**: Create a comprehensive web interface for Google News Scraper management with job-centric article viewing and integrated scheduling

### Current Project State Analysis

**Existing Infrastructure** (Production Ready):

- ✅ FastAPI backend with comprehensive REST APIs
- ✅ PostgreSQL database with full article/category/job models
- ✅ Redis + Celery task queue system (37 advanced methods in ArticleRepository)
- ✅ Docker containerized architecture
- ✅ Advanced crawling engine with deduplication and error handling
- ✅ React + TypeScript frontend foundation (Categories CRUD completed)

**Enhancement Scope**:
Transform from basic category management to a comprehensive job-centric article management system with integrated scheduling capabilities.

**Core Features Redesign**:

1. ✅ **Categories Management** - COMPLETED (Foundation ready)
2. 🎯 **Enhanced Jobs Management with Articles View** - PRIMARY FOCUS
3. 🎯 **Integrated Category Scheduling** - SECONDARY FOCUS
4. 📊 **Job-Centric Article Management** - INTEGRATED APPROACH

**Technical Assessment**: 90% of backend infrastructure already exists. Frontend components need enhancement to leverage existing powerful backend capabilities.

## Goals and Success Criteria

**Primary Goals**:

- Create job-centric article management interface for direct crawl result inspection
- Implement priority-based job queue management with "Run Now" capabilities
- Integrate category scheduling within existing category management workflow
- Provide comprehensive job lifecycle management (view/edit/delete/prioritize)

**Success Criteria**:

- ✅ Admin can view articles crawled by specific jobs with key metadata (url, title, publish_date, content, keywords)
- ✅ Admin can prioritize jobs to run immediately, bypassing queue when resources available
- ✅ Admin can manage auto-crawl schedules directly within category management interface
- ✅ Admin can perform full CRUD operations on jobs with proper confirmation dialogs

**Background Context**:
Current system operates effectively via REST APIs, but lacks integrated article inspection capabilities tied to specific crawl jobs. The enhancement focuses on job-centric workflow where users can immediately see crawl results and manage job priorities dynamically.

### Implementation Status Assessment

**✅ FOUNDATION COMPLETED:**

1. **Frontend Architecture** (Ready for Enhancement)

   - ✅ Vite + React + TypeScript + TailwindCSS + Shadcn UI
   - ✅ Docker containerization with hot reload
   - ✅ API integration layer with error handling
   - ✅ Component testing framework (Vitest + Testing Library)
2. **Categories Management** (Production Ready)

   - ✅ Full CRUD with form validation
   - ✅ Components: CategoriesList, CategoryForm, DeleteConfirmationDialog
   - ✅ Integration with `/api/v1/categories` endpoints
   - ✅ TypeScript interfaces with proper error handling
3. **Jobs Infrastructure** (Backend Complete, Frontend Partial)

   - ✅ Complete Jobs API at `/api/v1/jobs` with filtering/pagination
   - ✅ Celery task system with priority queue support
   - ✅ Job tracking with comprehensive metadata (CrawlJobRepository)
   - ✅ Frontend: JobsPage, ManualCrawlTrigger, JobStatus, JobsList components
   - 🔧 **Enhancement Needed**: Articles view per job, job editing, priority management
4. **Articles Infrastructure** (Backend 90% Complete)

   - ✅ ArticleRepository with 37 advanced methods including job-specific queries
   - ✅ Advanced filtering: by category, date range, relevance scores
   - ✅ Optimized pagination and search capabilities
   - ❌ **Missing**: REST API endpoints at `/api/v1/articles` (wrapper needed)
   - ❌ **Missing**: Frontend article viewing components

**📊 Current Status:**

- **Backend Infrastructure**: 95% Complete (just API wrappers needed)
- **Frontend Foundation**: 85% Complete (components need enhancement)
- **Integration Layer**: 80% Complete (needs articles API integration)

### Change Log

| Change         | Date       | Version | Description                                                              | Author      |
| -------------- | ---------- | ------- | ------------------------------------------------------------------------ | ----------- |
| Initial PRD    | 2025-09-12 | v1.0    | Original web interface enhancement                                       | BMad Master |
| Major Revision | 2025-09-15 | v2.0    | Redesigned for job-centric article management with integrated scheduling | BMad Master |

## Requirements

### Functional Requirements

**FR1: Job-Centric Article Management**

- System shall display articles crawled by specific jobs with metadata: URL, title, publish_date, content preview, keywords
- Users shall filter articles by job ID with pagination support
- Article details shall be viewable in modal/detail view format
- System shall leverage existing ArticleRepository methods for data retrieval

**FR2: Enhanced Jobs Management**

- Users shall perform CRUD operations on crawl jobs (Create, Read, Update, Delete)
- Job editing shall allow modification of job configuration (priority, retry_count, metadata)
- Job deletion shall require user confirmation with impact warnings
- System shall integrate with existing `/api/v1/jobs` endpoints

**FR3: Priority-Based Job Queue**

- Users shall set jobs to "Run Now" priority, bypassing normal queue order
- High-priority jobs shall execute immediately when worker resources become available
- System shall maintain job priority through existing Celery priority queue infrastructure
- Priority changes shall be reflected in real-time job status monitoring

**FR4: Integrated Category Scheduling**

- Category management interface shall include "Schedules" tab within category detail/edit forms
- Users shall configure auto-crawl schedules with interval settings (minutes/hours/days)
- Category list shall display next scheduled run time for each category
- Schedule changes shall integrate with Celery Beat dynamic scheduling

**FR5: Enhanced Category Management Integration**

- Existing category CRUD operations shall be preserved and enhanced
- Category forms shall include integrated scheduling configuration
- Category status indicators shall show both active/inactive and schedule status
- System shall maintain backward compatibility with existing `/api/v1/categories` endpoints

### Non-Functional Requirements

**NFR1: Performance**

- Article listing shall load within 2 seconds for up to 1000 articles per job
- Job priority updates shall reflect in UI within 5 seconds
- Real-time job status monitoring shall update every 30 seconds maximum
- Category schedule display shall not impact category list loading performance

**NFR2: Usability**

- Interface shall be intuitive for admin/developer users without extensive training
- Job-to-articles navigation shall require maximum 2 clicks
- Form validation shall provide immediate feedback with clear error messages
- Priority job actions shall be prominently displayed and easily accessible

**NFR3: Reliability**

- System shall gracefully handle API timeouts with appropriate user feedback
- Job priority changes shall be atomic - either fully succeed or fail with rollback
- Article viewing shall degrade gracefully when content is unavailable
- Schedule configuration shall validate inputs before submission

**NFR4: Compatibility**

- Frontend shall maintain compatibility with existing Docker deployment
- API integration shall preserve existing endpoint contracts
- New features shall not impact existing Swagger UI functionality
- System shall support desktop browsers: Chrome 90+, Firefox 88+, Safari 14+

### Technical Constraints

**TC1: Backend Integration**

- Must utilize existing ArticleRepository methods without modification
- Job priority system must work within current Celery queue infrastructure
- Schedule management must integrate with existing Celery Beat configuration
- All new APIs must follow existing FastAPI patterns and error handling

**TC2: Frontend Architecture**

- Must build upon existing React + TypeScript foundation
- Component design must follow established TailwindCSS + Shadcn UI patterns
- State management must use existing React Context approach
- Testing must integrate with current Vitest + Testing Library setup

## User Experience Design

### Enhanced Interface Architecture

**Design Philosophy**: Job-centric workflow with integrated article inspection and streamlined scheduling management.

**Navigation Structure**:

```
Main Navigation:
├── Categories (Enhanced with Scheduling)
├── Jobs Management (Primary Focus)
└── System Health
```

**Key UI Enhancements**:

### 1. Enhanced Jobs Management Interface

**Jobs List View** (Primary Interface):

```
Job Actions Bar:
[🚀 Run Now] [✏️ Edit] [🗑️ Delete] [👁️ View Articles]

Job Status Indicators:
● Running (with progress) ● Pending (with queue position) ● Completed ● Failed ● Priority (⚡ indicator)

Job Details Summary:
- Category Name | Status | Priority | Articles Found | Duration | Started/Completed
```

**Job-to-Articles Integration**:

```
Job Detail Modal:
├── Job Information Tab
│   ├── Status, priority, configuration
│   └── Real-time progress monitoring
├── Articles Tab (NEW)
│   ├── Articles found by this job
│   ├── Metadata: URL, title, publish_date, content preview
│   └── Filtered view with search capabilities
└── Edit Configuration Tab
    ├── Priority settings
    ├── Retry configuration
    └── Job metadata
```

### 2. Integrated Category Scheduling

**Enhanced Category Form**:

```
Category Detail Form:
├── Basic Info Tab (existing)
├── Keywords Configuration (existing)
└── Auto-Crawl Schedules Tab (NEW)
    ├── Schedule Status: [●] Active/Inactive
    ├── Interval Configuration: [Dropdown: 15min/30min/1hr/6hr/daily]
    ├── Next Run Display: "Next crawl: Dec 15, 2024 2:30 PM"
    └── Schedule History (last 5 runs with status)
```

**Category List Enhancement**:

```
Enhanced Categories Table:
Name | Keywords | Status | Last Crawl | Next Scheduled | Actions
Tech | python,ai | ● Active | 2hr ago | in 13min | [Edit][Schedule][Crawl Now]
```

### 3. Priority-Based Job Actions

**Run Now Functionality**:

```
Priority Job Controls:
┌─────────────────────────────────────────────────┐
│ [🚀 Run Now]  [⚡ High Priority]  [⏸️ Cancel]  │
│                                                 │
│ ⚠️  High priority jobs will run as soon as      │
│     worker resources become available           │
└─────────────────────────────────────────────────┘
```

### Design System Standards

**Color Coding**:

- 🟢 Running jobs: Green indicators
- 🟡 Pending jobs: Yellow with queue position
- 🔴 Failed jobs: Red with error indicators
- ⚡ Priority jobs: Lightning bolt with distinct styling
- 🔵 Scheduled items: Blue accent for next run times

**Interactive Elements**:

- **Action Buttons**: Primary (Run Now), Secondary (Edit), Destructive (Delete)
- **Status Pills**: Color-coded with appropriate icons
- **Priority Indicators**: Visual hierarchy with lightning bolt icons
- **Confirmation Dialogs**: Impact warnings for destructive actions

**Information Hierarchy**:

1. **Critical Actions** (Run Now, Priority) - Prominent placement
2. **Job Status** - Always visible with real-time updates
3. **Article Counts** - Quick metrics display
4. **Secondary Actions** (Edit, Delete) - Accessible but not dominant

## Implementation Plan

### Phase 1: Enhanced Jobs Management (Priority 1) - 2 weeks

**Backend Tasks** (4 days):

```yaml
Task 1.1: Articles API Endpoints (1.5 days)
  - Create /api/v1/articles routes with job_id filtering
  - Implement pagination, search, and metadata selection
  - Leverage existing ArticleRepository.get_articles_by_job_id()
  - Add article detail endpoint for modal display

Task 1.2: Job Priority Management API (1 day)
  - Extend /api/v1/jobs with priority update endpoint
  - Implement Celery priority queue integration
  - Add job configuration update (retry_count, metadata)

Task 1.3: Job-Article Association Tracking (1 day)
  - Ensure job_id is properly tracked in ArticleCategory associations
  - Add correlation_id tracking for job-specific article queries

Task 1.4: Enhanced Job Status API (0.5 days)
  - Add queue position information to job status responses
  - Include articles_found count in real-time updates
```

**Frontend Tasks** (6 days):

```yaml
Task 1.5: Job Actions Enhancement (2 days)
  - Add "Run Now", "Edit", "Delete" buttons to JobsList
  - Implement job priority update with confirmation dialogs
  - Create JobEditModal with configuration options

Task 1.6: Job-Articles Integration (2 days)
  - Create JobArticlesModal/Tab component
  - Implement ArticlesService for /api/v1/articles integration
  - Add article listing with metadata display (URL, title, date, content preview)

Task 1.7: Priority Queue UI (1 day)
  - Add priority indicators (lightning bolt) to job status
  - Implement queue position display for pending jobs
  - Create priority job confirmation dialogs

Task 1.8: Job Management Testing (1 day)
  - Unit tests for new components
  - Integration tests with enhanced APIs
```

### Phase 2: Integrated Category Scheduling (Priority 2) - 2 weeks

**Backend Tasks** (5 days):

```yaml
Task 2.1: Dynamic Scheduling Infrastructure (2 days)
  - Integrate Celery Beat with database-driven schedules
  - Create Schedule model with category associations
  - Implement schedule CRUD operations

Task 2.2: Category-Schedule API Integration (2 days)
  - Add /api/v1/categories/{id}/schedules endpoints
  - Extend category responses to include schedule status
  - Implement schedule validation and conflict detection

Task 2.3: Celery Beat Dynamic Updates (1 day)
  - Enable schedule changes without container restarts
  - Add schedule monitoring and next run calculations
```

**Frontend Tasks** (5 days):

```yaml
Task 2.4: Enhanced Category Forms (2 days)
  - Add "Schedules" tab to CategoryForm component
  - Implement schedule configuration UI (interval selection)
  - Create schedule history display

Task 2.5: Category List Schedule Integration (1.5 days)
  - Add "Next Scheduled" column to categories table
  - Implement schedule status indicators
  - Add quick "Crawl Now" action from category list

Task 2.6: Schedule Management Components (1.5 days)
  - Create ScheduleConfigModal for advanced settings
  - Implement schedule activation/deactivation toggles
  - Add schedule conflict warnings and validation
```

### Phase 3: Polish and Optimization (Priority 3) - 1 week

**Integration and Testing** (3 days):

```yaml
Task 3.1: End-to-End Integration (1 day)
  - Complete workflow testing: Category → Schedule → Job → Articles
  - Performance optimization for large article datasets
  - Real-time updates verification

Task 3.2: User Experience Polish (1 day)
  - UI/UX refinements based on workflow testing
  - Loading states and error handling improvements
  - Mobile responsiveness verification

Task 3.3: Documentation and Deployment (1 day)
  - Update API documentation
  - Docker configuration validation
  - Deployment process documentation
```

### Technical Implementation Details

**API Integration Strategy**:

- Leverage existing FastAPI infrastructure and patterns
- Maintain backward compatibility with current endpoints
- Use existing database models and relationships
- Implement proper error handling and validation

**Frontend Architecture**:

- Build upon existing React + TypeScript foundation
- Follow established component patterns and styling
- Integrate with existing state management approach
- Maintain consistency with current testing frameworks

## Risk Assessment and Mitigation

### Technical Risks

**High Priority Risks**:

**R1: Job Priority Queue Conflicts**

- **Risk**: Priority job changes might conflict with existing Celery queue operations
- **Impact**: Job execution order inconsistencies or queue deadlocks
- **Mitigation**: Implement atomic priority updates with rollback mechanisms; test with existing queue infrastructure
- **Validation**: Create test scenarios with concurrent priority changes

**R2: Article-Job Association Tracking**

- **Risk**: Historical jobs might not have proper article associations
- **Impact**: "View Articles" function showing empty or incorrect results
- **Mitigation**: Implement correlation_id backfill for historical data; graceful handling of missing associations
- **Validation**: Test with existing job data before frontend release

**R3: Schedule Integration Complexity**

- **Risk**: Celery Beat dynamic scheduling might require container restarts
- **Impact**: Schedule changes not taking effect until deployment
- **Mitigation**: Research celery-beat-scheduler library; implement database-driven scheduling
- **Validation**: Test schedule updates without container restarts

**Medium Priority Risks**:

**R4: Performance with Large Article Datasets**

- **Risk**: Jobs with 1000+ articles might cause UI performance issues
- **Impact**: Slow page loads, browser freezing on article viewing
- **Mitigation**: Implement pagination, virtual scrolling, lazy loading
- **Validation**: Test with high-volume article datasets

**R5: Real-time Updates Overhead**

- **Risk**: Frequent job status polling might impact backend performance
- **Impact**: API response delays during high job activity periods
- **Mitigation**: Implement intelligent polling intervals, WebSocket consideration for future
- **Validation**: Load testing with multiple concurrent users

### Integration Risks

**I1: Backward Compatibility**

- **Risk**: Enhanced APIs might break existing Swagger UI functionality
- **Impact**: Existing integrations or manual API usage fails
- **Mitigation**: Maintain separate endpoint versions; thorough API contract testing
- **Validation**: Automated tests for existing API contracts

**I2: Database Migration Complexity**

- **Risk**: Schedule model additions might require complex migrations
- **Impact**: Downtime during deployment, data consistency issues
- **Mitigation**: Design additive-only schema changes; test migrations on staging data
- **Validation**: Database migration testing with production-like datasets

### Mitigation Strategy Summary

**Phase 1 Safeguards** (Enhanced Jobs Management):

- Implement job priority changes as optional features with fallback to normal queue
- Add extensive logging for job-article association tracking
- Create manual override capabilities for critical job operations

**Phase 2 Safeguards** (Category Scheduling):

- Implement scheduling as additive feature - existing manual workflows remain unchanged
- Design schedule activation as opt-in per category
- Maintain manual crawl capabilities as primary method

**Phase 3 Safeguards** (Polish):

- Comprehensive rollback testing for all enhanced features
- Performance benchmarking with realistic data volumes
- User acceptance testing with actual admin workflows

**Rollback Plan**:

- All enhancements are additive - existing functionality remains unchanged
- Feature flags for new UI components allow selective disabling
- Database changes are non-destructive - original data remains intact
- Swagger UI continues to provide full API access as fallback

## Epic Definition

# Epic: Job-Centric Article Management with Integrated Scheduling

**Epic Goal**: Transform the Google News Scraper interface into a job-centric management system where administrators can directly view articles crawled by specific jobs, manage job priorities with "Run Now" capabilities, and configure automated scheduling within the category management workflow.

**Epic Value**: Provides immediate visibility into crawl results through job-specific article views, streamlines job priority management for urgent crawling needs, and integrates scheduling seamlessly into existing category management workflows.

## Story Structure (Updated v2.0)

### ✅ Foundation Stories - **COMPLETED**

**Story 1.1: Frontend Development Environment** - ✅ **COMPLETED**

- React + TypeScript + TailwindCSS foundation established
- Docker integration with hot reload configured
- API integration layer and testing framework ready

**Story 1.2: Categories Management Interface** - ✅ **COMPLETED**

- Full CRUD operations with form validation
- Integration with existing `/api/v1/categories` endpoints
- Component foundation ready for scheduling integration

**Story 1.3: Basic Jobs Management** - ✅ **COMPLETED**

- JobsPage, ManualCrawlTrigger, JobStatus, JobsList components
- Integration with `/api/v1/jobs` endpoints
- Real-time job monitoring capabilities

### 🎯 Enhanced Stories - **IMPLEMENTATION FOCUS**

### **Story 2.1: Enhanced Jobs Management with Article Viewing** - **PRIMARY FOCUS**

As an **Admin/Developer**,
I want **to view articles crawled by specific jobs and manage job priorities**,
so that **I can immediately inspect crawl results and prioritize urgent crawling tasks**.

**Acceptance Criteria:**

1. **Job Actions Enhancement**: Add "Run Now", "Edit", "Delete" buttons to each job in JobsList
2. **Article Viewing Integration**: "View Articles" button opens modal/tab showing articles found by that specific job
3. **Article Metadata Display**: Show URL, title, publish_date, content preview, matched keywords for each article
4. **Job Priority Management**: "Run Now" sets job to high priority, bypassing normal queue order
5. **Job Configuration Editing**: Modal for editing job settings (priority, retry_count, metadata)
6. **Job Deletion with Confirmation**: Confirmation dialog showing impact before job deletion
7. **Data Export from Article View** : In the "View Articles" interface, an "Export Data" button must be present. Upon clicking, the user must be prompted to choose an export format from  **JSON** ,  **Excel (.xlsx)** , and  **CSV** . All exported files must be encoded in **UTF-8** to ensure full support for Vietnamese characters.

**Technical Implementation:**

```yaml
Backend (1.5 days):
  - Create /api/v1/articles?job_id={id} endpoint
  - Add /api/v1/jobs/{id}/priority endpoint for priority updates
  - Enhance job status responses with queue position info

Frontend (2.5 days):
  - Create JobArticlesModal component with article listing
  - Add JobEditModal for configuration updates
  - Implement priority update with confirmation dialogs
  - Add article metadata display with search/filter
```

**Integration Requirements:**

- Leverage existing ArticleRepository.get_articles_with_categories() method
- Utilize existing Celery priority queue infrastructure
- Maintain compatibility with current job tracking system

### **Story 2.2: Integrated Category Scheduling** - **SECONDARY FOCUS**

As an **Admin/Developer**,
I want **to configure auto-crawl schedules within category management**,
so that **I can set up automated crawling without leaving the category interface**.

**Acceptance Criteria:**

1. **Enhanced Category Forms**: Add "Schedules" tab to CategoryForm component
2. **Schedule Configuration**: Interval selection (15min/30min/1hr/6hr/daily) with next run display
3. **Category List Integration**: "Next Scheduled" column showing countdown to next crawl
4. **Quick Actions**: "Crawl Now" button in category list for immediate manual triggering
5. **Schedule History**: Display last 5 scheduled runs with success/failure status
6. **Schedule Activation**: Toggle to enable/disable scheduling per category

**Technical Implementation:**

```yaml
Backend (3 days):
  - Create Schedule model with category_id relationships
  - Implement /api/v1/categories/{id}/schedules endpoints
  - Integrate with Celery Beat dynamic scheduling
  - Add schedule monitoring and next run calculations

Frontend (2 days):
  - Add Schedules tab to existing CategoryForm
  - Create ScheduleConfigModal for advanced settings
  - Enhance Categories table with schedule status column
  - Implement schedule activation toggles
```

**Integration Requirements:**

- Build upon existing Categories CRUD infrastructure
- Integrate with current Celery Beat configuration
- Maintain category form validation and error handling patterns

### **Story 2.3: System Integration and Polish** - **FINAL PHASE**

As an **Admin/Developer**,
I want **seamless integration between job management, article viewing, and scheduling**,
so that **I have a unified workflow for managing the entire crawling system**.

**Acceptance Criteria:**

1. **Workflow Integration**: Smooth navigation between Categories → Schedules → Jobs → Articles
2. **Performance Optimization**: Fast loading for jobs with 1000+ articles using pagination
3. **Real-time Updates**: Job status changes reflect across all relevant UI components
4. **Error Handling**: Graceful degradation when articles or job data is unavailable
5. **Mobile Responsiveness**: Basic functionality works on tablet/mobile devices

## Implementation Sequence and Dependencies

**Phase 1 (Week 1-2)**: Story 2.1 - Enhanced Jobs Management

- **Dependencies**: ✅ All foundation stories completed
- **Deliverable**: Job-centric article viewing with priority management
- **Value**: Immediate visibility into crawl results per job

**Phase 2 (Week 3-4)**: Story 2.2 - Integrated Category Scheduling

- **Dependencies**: Story 2.1 completion for job triggering validation
- **Deliverable**: Schedule management within category interface
- **Value**: Streamlined automation setup without context switching

**Phase 3 (Week 5)**: Story 2.3 - Integration and Polish

- **Dependencies**: Stories 2.1 and 2.2 completion
- **Deliverable**: Unified, polished user experience
- **Value**: Production-ready comprehensive management interface

**Success Metrics**:

- ✅ Job-to-articles navigation completed in ≤ 2 clicks
- ✅ High priority jobs execute within 5 seconds when workers available
- ✅ Schedule configuration completed without leaving category management
- ✅ Article viewing supports 1000+ articles with <2 second load times
