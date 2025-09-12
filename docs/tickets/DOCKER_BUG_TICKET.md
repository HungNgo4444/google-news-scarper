# 🐛 **BUG TICKET: Docker Container Deployment Issues**

## **📋 Ticket ID:** DOCKER-FIX-001
**Priority:** HIGH  
**Status:** Open  
**Assignee:** Development Team  
**Reporter:** BMad Master  
**Created:** 2025-09-12

---

## **🎯 Summary**
Docker containers đang gặp nhiều lỗi nghiêm trọng ngăn cản application startup, bao gồm SQLAlchemy model conflicts và database connection issues.

## **🚨 Current Status**
- ✅ **postgres**: HEALTHY - Database running correctly
- ✅ **redis**: HEALTHY - Cache/message broker running
- ❌ **web**: RESTARTING (exit code 3) - Application startup failed  
- ❌ **migration**: FAILED (exit code 1) - Database migration failed

## **🔍 Root Cause Analysis**

### **1. SQLAlchemy Declarative API Conflict**
**Error:** `sqlalchemy.exc.InvalidRequestError: Attribute name 'metadata' is reserved`

**Location:** `src/database/models/crawl_job.py:19`

**Issue:** Model uses reserved attribute name `metadata` which conflicts with SQLAlchemy's Declarative API

**Impact:** Prevents model loading, blocks both migration and web services

### **2. Config Function Reference Error** 
**Error:** `NameError: name '_get_env_file' is not defined`

**Location:** `src/shared/config.py:371`

**Issue:** Function `_get_env_file()` được reference trong `model_config` trước khi được define

**Impact:** Prevents config loading, blocks all services requiring settings

### **3. Database Health Check SQL Syntax**
**Error:** `Textual SQL expression 'SELECT 1' should be explicitly declared as text('SELECT 1')`

**Location:** `src/database/connection.py` (health check function)

**Issue:** SQLAlchemy 2.0+ requires explicit text() wrapper for raw SQL

**Impact:** Database connection health check fails, web service can't start

## **🛠️ Required Fixes**

### **Fix 1: Rename Reserved Field [CRITICAL]**
```python
# File: src/database/models/crawl_job.py
# Line 93: Change field name from 'metadata' to avoid conflict

# BEFORE:
metadata: Mapped[Optional[dict]] = mapped_column(
    JSONB,
    nullable=True,
    default=dict
)

# AFTER:  
job_metadata: Mapped[Optional[dict]] = mapped_column(
    JSONB,
    nullable=True,
    default=dict
)

# Also update index reference:
# Line 148: Update index name
Index("idx_crawl_jobs_job_metadata_gin", "job_metadata", postgresql_using="gin")
```

### **Fix 2: Fix Config Function Order [HIGH]**
```python
# File: src/shared/config.py
# Move _get_env_file() function definition BEFORE Settings class

# Current location: Line 377
# Required location: Before line 38 (before Settings class definition)
```

### **Fix 3: Fix SQL Health Check [MEDIUM]**
```python
# File: src/database/connection.py
# Find health check function and wrap SQL in text()

from sqlalchemy import text

# BEFORE:
result = await session.execute("SELECT 1")

# AFTER:
result = await session.execute(text("SELECT 1"))
```

### **Fix 4: Update Migration Files [MEDIUM]**
- Update any existing migration files that reference `metadata` field
- Ensure alembic.ini script_location points to correct directory
- Verify migration dependencies and imports

## **🧪 Testing Requirements**

### **Pre-deployment Testing:**
```bash
# 1. Test model loading
python -c "from src.database.models import CrawlJob; print('Model loads successfully')"

# 2. Test config loading  
python -c "from src.shared.config import get_settings; print(get_settings())"

# 3. Test database connection
docker-compose up postgres -d
python -c "from src.database.connection import get_database_connection; print('DB connects')"
```

### **Post-fix Verification:**
```bash
# 1. Full stack deployment
docker-compose down -v
docker-compose up -d --build

# 2. Health checks
curl http://localhost:8000/health
curl http://localhost:8000/health/detailed

# 3. Service status verification
docker-compose ps  # All services should be 'healthy' or 'running'
```

## **📊 Expected Resolution Time**
- **Fix 1-3:** ~2 hours (straightforward code changes)
- **Fix 4:** ~1 hour (migration updates) 
- **Testing:** ~1 hour
- **Total:** ~4 hours

## **🚨 Business Impact**
- **HIGH:** Application completely non-functional in Docker environment
- **CRITICAL:** Production deployment blocked
- **USER IMPACT:** No API services available
- **INFRASTRUCTURE:** Database resources running but unused

## **✅ Acceptance Criteria**
- [ ] All Docker containers start successfully without errors
- [ ] Health endpoints return HTTP 200
- [ ] Database migrations complete successfully
- [ ] Web API responds to requests
- [ ] Worker and Beat services start without issues
- [ ] No error logs in container startup

## **📝 Additional Notes**
- Database and Redis infrastructure working correctly
- Issues are primarily in application layer, not infrastructure
- Fixes are well-defined and low-risk
- No data loss expected from fixes

## **🔧 Container Logs Summary**

### **Migration Service Errors:**
```
migration-1 | sqlalchemy.exc.InvalidRequestError: Attribute name 'metadata' is reserved when using the Declarative API.
migration-1 | NameError: name '_get_env_file' is not defined
```

### **Web Service Errors:**
```
web-1 | ERROR:src.database.connection:Database health check failed: Textual SQL expression 'SELECT 1' should be explicitly declared as text('SELECT 1')
web-1 | ERROR:src.api.main:Database connection failed
web-1 | RuntimeError: Database connection failed
```

### **Infrastructure Status:**
```
postgres-1 | database system is ready to accept connections ✅
redis-1    | Ready to accept connections tcp ✅
```

---

**Next Steps:** Assign to development team for immediate resolution. Priority should be Fix 1 & 2 (critical path blockers), then Fix 3 & 4.

**Contact:** BMad Master for any clarification or additional debugging support.