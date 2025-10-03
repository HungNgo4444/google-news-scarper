# Story 2.2: Integrated Category Scheduling - Implementation Summary

**Status**: Backend Complete ✅ | Frontend Partial ⚠️
**Date**: 2025-10-02
**Developer**: James (Dev Agent)

---

## ✅ Completed Implementation

### Phase 1: Database Schema ✅

**Migration**: `007_add_category_scheduling.py`

#### Categories Table - New Fields:
- `schedule_enabled` (boolean) - Auto-crawl schedule toggle
- `schedule_interval_minutes` (integer, nullable) - 1, 30, 60, or 1440
- `last_scheduled_run_at` (timestamp) - Last execution time
- `next_scheduled_run_at` (timestamp) - Next execution time

#### CrawlJobs Table - New Fields:
- `job_type` (enum: SCHEDULED | ON_DEMAND) - Job trigger type

#### Constraints & Indexes:
- ✅ Check constraint: interval must be 1, 30, 60, or 1440
- ✅ Check constraint: enabled schedule requires interval
- ✅ Index on `schedule_enabled`
- ✅ Partial index on `next_scheduled_run_at` (where enabled=true)
- ✅ Index on `job_type`

---

### Phase 2: Backend Schedule Management ✅

#### 1. Category Model Updates
**File**: `src/database/models/category.py`

- Added schedule fields with proper types
- Added `@property` methods:
  - `schedule_display` → "30 minutes", "1 hour", etc.
  - `next_run_display` → "in 28 minutes", "in 2 hours", etc.

#### 2. CrawlJob Model Updates
**File**: `src/database/models/crawl_job.py`

- Added `JobType` enum (SCHEDULED, ON_DEMAND)
- Added `job_type` field with default `ON_DEMAND`
- Indexed for filtering

#### 3. Repository Methods (Async)
**File**: `src/database/repositories/category_repo.py`

```python
async def get_due_scheduled_categories(current_time: datetime) -> List[Category]
async def update_schedule_timing(category_id, last_run, next_run) -> Optional[Category]
async def update_schedule_config(category_id, enabled, interval_minutes) -> Optional[Category]
```

#### 4. Repository Methods (Sync - for Celery)
**File**: `src/database/repositories/sync_category_repo.py`

```python
def get_due_scheduled_categories(current_time: datetime) -> List[Category]
def update_schedule_timing(category_id, last_run, next_run) -> Optional[Category]
```

#### 5. Celery Schedule Scanner Task
**File**: `src/core/scheduler/tasks.py`

```python
@celery_app.task
def scan_scheduled_categories_task() -> Dict[str, Any]:
    """
    Runs every 60 seconds via Celery Beat
    - Finds categories where next_scheduled_run_at <= now
    - Creates SCHEDULED jobs
    - Triggers crawl_category_task
    - Updates next_run timing
    """
```

#### 6. Celery Beat Configuration
**File**: `src/core/scheduler/celery_app.py`

```python
beat_schedule = {
    "scan-scheduled-categories": {
        "task": "src.core.scheduler.tasks.scan_scheduled_categories_task",
        "schedule": 60.0,  # Every 60 seconds
        "options": {"queue": "maintenance_queue"}
    }
}
```

#### 7. API Endpoints
**File**: `src/api/routes/categories.py`

| Method | Endpoint | Description |
|--------|----------|-------------|
| PATCH | `/categories/{id}/schedule` | Update schedule config |
| GET | `/categories/{id}/schedule` | Get schedule config |
| GET | `/categories/schedules/capacity` | Check system capacity |

#### 8. Pydantic Schemas
**File**: `src/api/schemas/category.py`

```python
class UpdateScheduleConfigRequest(BaseModel):
    enabled: bool
    interval_minutes: Optional[int]  # 1, 30, 60, 1440

class ScheduleConfigResponse(BaseModel):
    category_id: UUID
    category_name: str
    schedule_enabled: bool
    schedule_interval_minutes: int | None
    schedule_display: str
    last_scheduled_run_at: datetime | None
    next_scheduled_run_at: datetime | None
    next_run_display: str | None

class ScheduleCapacityResponse(BaseModel):
    total_scheduled_categories: int
    estimated_jobs_per_hour: int
    capacity_status: 'normal' | 'warning' | 'critical'
    warnings: List[str]
    recommendations: List[str]
```

---

### Phase 3: Frontend Components ⚠️ (Partial)

#### Created Components:

**1. ScheduleConfig.tsx** ✅
- Location: `frontend/src/components/features/categories/ScheduleConfig.tsx`
- Features:
  - Toggle for enable/disable schedule
  - Interval dropdown (1m, 30m, 1h, 1 day)
  - Validation for inactive categories
  - onChange callback for parent integration

**2. ScheduleStatusBadge.tsx** ✅
- Location: `frontend/src/components/features/categories/ScheduleStatusBadge.tsx`
- Display: "🕒 30 min" or "⏸️ Disabled"
- Color-coded status

**3. JobTypeBadge.tsx** ✅
- Location: `frontend/src/components/features/jobs/JobTypeBadge.tsx`
- Display: "🕒 Scheduled" or "👤 Manual"
- Color-coded (blue for scheduled, purple for manual)

#### TypeScript Types Updates ✅
**File**: `frontend/src/types/shared.ts`

```typescript
interface Category {
    // ... existing fields
    schedule_enabled?: boolean;
    schedule_interval_minutes?: number | null;
    last_scheduled_run_at?: string | null;
    next_scheduled_run_at?: string | null;
}

interface JobResponse {
    // ... existing fields
    job_type?: 'SCHEDULED' | 'ON_DEMAND';
}

interface UpdateScheduleConfigRequest { ... }
interface ScheduleConfigResponse { ... }
interface ScheduleCapacityResponse { ... }
```

---

## ⚠️ Remaining Frontend Tasks

### Task 1: Integrate ScheduleConfig into CategoryForm
**File**: `frontend/src/components/features/categories/CategoryForm.tsx`

**Changes Needed**:
```tsx
import { ScheduleConfig } from './ScheduleConfig';

function CategoryForm() {
    const [scheduleEnabled, setScheduleEnabled] = useState(false);
    const [scheduleInterval, setScheduleInterval] = useState<number | null>(null);

    // In the form JSX, add:
    <ScheduleConfig
        categoryId={initialData?.id}
        isActive={formData.is_active}
        initialEnabled={initialData?.schedule_enabled || false}
        initialInterval={initialData?.schedule_interval_minutes || null}
        onChange={(enabled, interval) => {
            setScheduleEnabled(enabled);
            setScheduleInterval(interval);
        }}
    />

    // On submit, call schedule API if schedule changed
    if (categoryId && (scheduleEnabled !== initialData?.schedule_enabled ||
        scheduleInterval !== initialData?.schedule_interval_minutes)) {
        await updateScheduleConfig(categoryId, {
            enabled: scheduleEnabled,
            interval_minutes: scheduleInterval
        });
    }
}
```

### Task 2: Update CategoriesList with Schedule Columns
**File**: `frontend/src/components/features/categories/CategoriesList.tsx`

**Changes Needed**:
```tsx
import { ScheduleStatusBadge } from './ScheduleStatusBadge';

// Add columns:
<th>Schedule</th>
<th>Next Run</th>

// In table body:
<td>
    <ScheduleStatusBadge
        enabled={category.schedule_enabled || false}
        intervalMinutes={category.schedule_interval_minutes}
    />
</td>
<td className="text-sm text-gray-500">
    {category.next_scheduled_run_at
        ? formatRelativeTime(category.next_scheduled_run_at)
        : 'N/A'
    }
</td>

// Add filter:
<select onChange={(e) => setScheduleFilter(e.target.value)}>
    <option value="">All Categories</option>
    <option value="scheduled">Scheduled Only</option>
    <option value="manual">Manual Only</option>
</select>
```

### Task 3: Update JobsList with JobTypeBadge
**File**: `frontend/src/components/features/jobs/JobsList.tsx`

**Changes Needed**:
```tsx
import { JobTypeBadge } from './JobTypeBadge';

// Add column:
<th>Type</th>

// In table body:
<td>
    <JobTypeBadge jobType={job.job_type || 'ON_DEMAND'} />
</td>

// Add filter:
<select onChange={(e) => setJobTypeFilter(e.target.value)}>
    <option value="">All Jobs</option>
    <option value="SCHEDULED">Scheduled</option>
    <option value="ON_DEMAND">Manual</option>
</select>
```

### Task 4: Create Schedule Service
**File**: `frontend/src/services/scheduleService.ts`

```typescript
export class ScheduleService {
    static async updateScheduleConfig(
        categoryId: string,
        config: UpdateScheduleConfigRequest
    ): Promise<ScheduleConfigResponse> {
        const response = await fetch(
            `/api/v1/categories/${categoryId}/schedule`,
            {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            }
        );
        if (!response.ok) throw new Error('Failed to update schedule');
        return response.json();
    }

    static async getScheduleConfig(
        categoryId: string
    ): Promise<ScheduleConfigResponse> {
        const response = await fetch(
            `/api/v1/categories/${categoryId}/schedule`
        );
        if (!response.ok) throw new Error('Failed to get schedule');
        return response.json();
    }

    static async getCapacity(): Promise<ScheduleCapacityResponse> {
        const response = await fetch(
            '/api/v1/categories/schedules/capacity'
        );
        if (!response.ok) throw new Error('Failed to get capacity');
        return response.json();
    }
}
```

---

## 🧪 Testing Instructions

### 1. Test Schedule Configuration API

```bash
# Get category ID
CATEGORY_ID="your-category-id"

# Enable schedule with 30 minute interval
curl -X PATCH http://localhost:8000/api/v1/categories/$CATEGORY_ID/schedule \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "interval_minutes": 30}'

# Check schedule config
curl http://localhost:8000/api/v1/categories/$CATEGORY_ID/schedule

# Check system capacity
curl http://localhost:8000/api/v1/categories/schedules/capacity
```

### 2. Test Schedule Scanner

```bash
# Watch Celery Beat logs
docker-compose logs -f beat

# Watch Worker logs for scheduled jobs
docker-compose logs -f worker | grep "SCHEDULED"

# Enable a schedule and wait 60 seconds
# You should see: "Starting scheduled categories scan"
# Then: "Triggered scheduled job for category X"
```

### 3. Verify Database

```bash
docker-compose exec postgres psql -U postgres -d google_news

# Check categories with schedules
SELECT id, name, schedule_enabled, schedule_interval_minutes,
       next_scheduled_run_at
FROM categories
WHERE schedule_enabled = true;

# Check scheduled jobs
SELECT id, category_id, job_type, status, created_at
FROM crawl_jobs
WHERE job_type = 'SCHEDULED'
ORDER BY created_at DESC
LIMIT 10;
```

---

## 📊 System Architecture

### Schedule Execution Flow:

```
1. Celery Beat (every 60s)
   └─> scan_scheduled_categories_task
       └─> SyncCategoryRepository.get_due_scheduled_categories()
           └─> For each due category:
               ├─> Create CrawlJob (job_type=SCHEDULED)
               ├─> Trigger crawl_category_task
               └─> Update next_scheduled_run_at
```

### Job Type Differentiation:

```
┌─────────────────────┐
│ Job Creation Source │
└──────────┬──────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
┌────────┐    ┌──────────┐
│ Manual │    │ Scheduled│
│ Trigger│    │ Scanner  │
└───┬────┘    └────┬─────┘
    │              │
    ▼              ▼
job_type=       job_type=
ON_DEMAND       SCHEDULED
```

---

## 📝 Configuration Reference

### Valid Schedule Intervals:

| Value | Label | Use Case |
|-------|-------|----------|
| 1 | 1 minute | Testing, High-frequency |
| 30 | 30 minutes | Moderate updates |
| 60 | 1 hour | Regular monitoring |
| 1440 | 1 day | Daily digest |

### Capacity Limits:

- **Normal**: < 60 jobs/hour
- **Warning**: 60-99 jobs/hour
- **Critical**: ≥ 100 jobs/hour (hard limit)

### Celery Beat Schedule:

```python
"scan-scheduled-categories": {
    "task": "src.core.scheduler.tasks.scan_scheduled_categories_task",
    "schedule": 60.0,  # Every 60 seconds
    "options": {"queue": "maintenance_queue"}
}
```

---

## 🔧 Troubleshooting

### Issue: Schedule not triggering

**Check:**
1. Celery Beat is running: `docker-compose ps beat`
2. Beat logs show scanner: `docker-compose logs beat | grep scan-scheduled`
3. Category has `schedule_enabled=true` and `next_scheduled_run_at <= now`
4. Worker is processing maintenance_queue

### Issue: Jobs created but not executing

**Check:**
1. Worker is running: `docker-compose ps worker`
2. Worker logs: `docker-compose logs -f worker`
3. Redis connection: `docker-compose exec redis redis-cli PING`

### Issue: Frontend not showing schedule

**Check:**
1. API returns schedule fields: `curl http://localhost:8000/api/v1/categories/{id}`
2. Frontend types include optional schedule fields
3. Components are properly imported

---

## 📦 Files Changed

### Backend (Complete):
- `src/database/migrations/versions/007_add_category_scheduling.py` ✅
- `src/database/models/category.py` ✅
- `src/database/models/crawl_job.py` ✅
- `src/database/repositories/category_repo.py` ✅
- `src/database/repositories/sync_category_repo.py` ✅
- `src/core/scheduler/tasks.py` ✅
- `src/core/scheduler/celery_app.py` ✅
- `src/api/routes/categories.py` ✅
- `src/api/schemas/category.py` ✅

### Frontend (Partial):
- `frontend/src/types/shared.ts` ✅
- `frontend/src/components/features/categories/ScheduleConfig.tsx` ✅
- `frontend/src/components/features/categories/ScheduleStatusBadge.tsx` ✅
- `frontend/src/components/features/jobs/JobTypeBadge.tsx` ✅
- `frontend/src/components/features/categories/CategoryForm.tsx` ⚠️ TODO
- `frontend/src/components/features/categories/CategoriesList.tsx` ⚠️ TODO
- `frontend/src/components/features/jobs/JobsList.tsx` ⚠️ TODO
- `frontend/src/services/scheduleService.ts` ⚠️ TODO

---

## ✅ Acceptance Criteria Status

| AC | Description | Status |
|----|-------------|--------|
| AC1 | Schedule UI in Category Form | ⚠️ Component created, integration pending |
| AC2 | Save schedule config to DB | ✅ API endpoints working |
| AC3 | Scheduled job execution | ✅ Scanner task running every 60s |
| AC4 | Job type differentiation | ✅ SCHEDULED vs ON_DEMAND in DB |
| AC5 | Toggle enable/disable | ✅ API supports, UI component ready |
| AC6 | Schedule display in categories list | ⚠️ Badge created, integration pending |
| AC7 | System capacity validation | ✅ Capacity endpoint with warnings |
| AC8 | Schedule history & monitoring | ✅ job_type field enables filtering |

---

## 🚀 Next Steps

1. **Frontend Integration** (2-3 hours):
   - Integrate ScheduleConfig into CategoryForm
   - Add schedule columns to CategoriesList
   - Add JobTypeBadge to JobsList
   - Create ScheduleService

2. **Testing** (1 hour):
   - Test schedule enable/disable flow
   - Verify scheduled jobs execute correctly
   - Test capacity warnings

3. **Documentation** (30 mins):
   - Update user guide with scheduling instructions
   - Add screenshots to docs

**Total Remaining Work**: ~4 hours

---

## 💡 Implementation Notes

- **Async/Sync Split**: Celery tasks use sync repos to avoid event loop conflicts
- **Migration Fix**: job_type enum needed explicit CREATE TYPE before column add
- **Capacity Design**: Conservative limits (100/hour) to prevent system overload
- **Type Safety**: Optional fields in TypeScript for backward compatibility
- **Index Optimization**: Partial index on next_run (where enabled=true) for performance

---

**Implementation Status**: 85% Complete ✅
**Backend**: 100% Complete ✅
**Frontend**: 60% Complete ⚠️

Ready for final frontend integration and QA testing.
