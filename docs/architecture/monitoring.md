# Monitoring and Observability

Define monitoring strategy cho fullstack application với focus trên production readiness và early problem detection.

## Monitoring Stack

- **Application Monitoring:** Custom metrics via Python logging + structured JSON logs
- **Infrastructure Monitoring:** Docker stats, system metrics (CPU, memory, disk)
- **Database Monitoring:** PostgreSQL slow query logs, connection pool metrics
- **Background Jobs Monitoring:** Celery task success/failure rates, queue depths
- **Error Tracking:** Centralized error logging với correlation IDs
- **Performance Monitoring:** Response times, throughput metrics
- **External Service Monitoring:** Google News API success rates, newspaper4k extraction metrics

## Custom Metrics Implementation

```python
import time
import json
from typing import Dict, Any
from datetime import datetime, timezone

class MetricsCollector:
    def __init__(self, logger):
        self.logger = logger
        
    def record_api_request(
        self, 
        method: str, 
        endpoint: str, 
        status_code: int, 
        duration_ms: float,
        user_agent: str = None
    ):
        self.logger.info("api_request", extra={
            "metric_type": "api_request",
            "method": method,
            "endpoint": endpoint,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "user_agent": user_agent,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    def record_crawler_activity(
        self,
        category_id: str,
        articles_found: int,
        articles_saved: int,
        duration_seconds: float,
        success: bool,
        error_type: str = None
    ):
        self.logger.info("crawler_activity", extra={
            "metric_type": "crawler_activity",
            "category_id": category_id,
            "articles_found": articles_found,
            "articles_saved": articles_saved,
            "duration_seconds": duration_seconds,
            "success": success,
            "error_type": error_type,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    def record_database_query(
        self,
        query_type: str,  # SELECT, INSERT, UPDATE, DELETE
        table_name: str,
        duration_ms: float,
        rows_affected: int = None
    ):
        self.logger.info("database_query", extra={
            "metric_type": "database_query", 
            "query_type": query_type,
            "table_name": table_name,
            "duration_ms": duration_ms,
            "rows_affected": rows_affected,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    def record_external_service_call(
        self,
        service_name: str,  # google_news, news_website
        operation: str,     # search, extract
        success: bool,
        duration_ms: float,
        status_code: int = None,
        error_type: str = None
    ):
        self.logger.info("external_service_call", extra={
            "metric_type": "external_service_call",
            "service_name": service_name,
            "operation": operation,
            "success": success,
            "duration_ms": duration_ms,
            "status_code": status_code,
            "error_type": error_type,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
```

## Health Check System

```python
from fastapi import APIRouter, Depends, HTTPException
import psutil
import redis
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

class HealthChecker:
    def __init__(self):
        self.start_time = datetime.now(timezone.utc)
    
    async def check_database(self, db: AsyncSession) -> Dict[str, Any]:
        try:
            start = time.time()
            result = await db.execute(text("SELECT 1"))
            duration = (time.time() - start) * 1000
            
            return {
                "status": "healthy",
                "response_time_ms": round(duration, 2),
                "connection_pool": {
                    "size": db.bind.pool.size(),
                    "checked_in": db.bind.pool.checkedin(),
                    "checked_out": db.bind.pool.checkedout()
                }
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def check_redis(self, redis_client) -> Dict[str, Any]:
        try:
            start = time.time()
            await redis_client.ping()
            duration = (time.time() - start) * 1000
            
            info = await redis_client.info()
            
            return {
                "status": "healthy",
                "response_time_ms": round(duration, 2),
                "memory_usage_mb": round(info['used_memory'] / 1024 / 1024, 2),
                "connected_clients": info['connected_clients']
            }
        except Exception as e:
            return {
                "status": "unhealthy", 
                "error": str(e)
            }
    
    def check_celery_workers(self) -> Dict[str, Any]:
        try:
            from src.core.scheduler.celery_app import celery_app
            inspect = celery_app.control.inspect()
            
            active_workers = inspect.active()
            if not active_workers:
                return {"status": "unhealthy", "error": "No active workers"}
            
            total_tasks = sum(len(tasks) for tasks in active_workers.values())
            
            return {
                "status": "healthy",
                "active_workers": len(active_workers),
                "total_active_tasks": total_tasks,
                "workers": list(active_workers.keys())
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    def check_system_resources(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory": {
                "percent": psutil.virtual_memory().percent,
                "available_gb": round(psutil.virtual_memory().available / 1024**3, 2)
            },
            "disk": {
                "percent": psutil.disk_usage('/').percent,
                "free_gb": round(psutil.disk_usage('/').free / 1024**3, 2)
            }
        }

@router.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_db_session),
    redis_client = Depends(get_redis_client)
):
    checker = HealthChecker()
    
    # Run all health checks
    checks = {
        "database": await checker.check_database(db),
        "redis": await checker.check_redis(redis_client), 
        "celery": checker.check_celery_workers(),
        "system": checker.check_system_resources()
    }
    
    # Determine overall status
    unhealthy_services = [
        name for name, check in checks.items() 
        if check.get("status") != "healthy"
    ]
    
    overall_status = "healthy" if not unhealthy_services else "degraded"
    
    return {
        "status": overall_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": (datetime.now(timezone.utc) - checker.start_time).total_seconds(),
        "version": "1.0.0",
        "checks": checks,
        "unhealthy_services": unhealthy_services
    }
```

## Alert System

```python
class AlertManager:
    def __init__(self, webhook_url: str = None, email_config: dict = None):
        self.webhook_url = webhook_url
        self.email_config = email_config
        self.alert_thresholds = {
            "error_rate_percent": 5.0,      # > 5% error rate
            "response_time_ms": 2000,       # > 2 second response time
            "crawler_success_rate": 90.0,   # < 90% crawler success
            "disk_usage_percent": 85.0,     # > 85% disk usage
            "memory_usage_percent": 90.0,   # > 90% memory usage
            "failed_jobs_count": 10,        # > 10 failed jobs in 1 hour
            "database_connections": 80      # > 80% of max connections
        }
    
    async def check_alerts(self):
        alerts = []
        
        # Check error rates
        error_rate = await self.calculate_error_rate_last_hour()
        if error_rate > self.alert_thresholds["error_rate_percent"]:
            alerts.append({
                "type": "high_error_rate",
                "message": f"Error rate is {error_rate:.1f}% (threshold: {self.alert_thresholds['error_rate_percent']}%)",
                "severity": "critical" if error_rate > 10 else "warning"
            })
        
        # Check crawler performance
        crawler_success = await self.calculate_crawler_success_rate()
        if crawler_success < self.alert_thresholds["crawler_success_rate"]:
            alerts.append({
                "type": "low_crawler_success",
                "message": f"Crawler success rate is {crawler_success:.1f}% (threshold: {self.alert_thresholds['crawler_success_rate']}%)",
                "severity": "warning"
            })
        
        # Check system resources
        system_alerts = await self.check_system_resources()
        alerts.extend(system_alerts)
        
        # Send alerts
        for alert in alerts:
            await self.send_alert(alert)
        
        return alerts
    
    async def send_alert(self, alert: dict):
        timestamp = datetime.now(timezone.utc).isoformat()
        
        message = f"""
        🚨 **Alert: {alert['type']}**
        
        **Severity:** {alert['severity']}
        **Time:** {timestamp}
        **Message:** {alert['message']}
        
        **Actions:** Check logs và health endpoint for details
        """
        
        # Log alert
        logger.error(f"Alert triggered: {alert['type']}", extra={
            "alert_type": alert["type"],
            "severity": alert["severity"],
            "message": alert["message"]
        })

# Scheduled alert checking
@celery_app.task
def check_system_alerts():
    alert_manager = AlertManager()
    alerts = await alert_manager.check_alerts()
    
    if alerts:
        logger.warning(f"System alerts triggered: {len(alerts)}", extra={
            "alert_count": len(alerts),
            "alert_types": [alert["type"] for alert in alerts]
        })
```

## Performance Analysis Queries

```sql
-- API endpoint performance (last 24h)
SELECT 
    DATE_TRUNC('hour', created_at) as hour,
    COUNT(*) as request_count,
    AVG(CASE WHEN status_code < 400 THEN response_time_ms END) as avg_response_time,
    COUNT(CASE WHEN status_code >= 400 THEN 1 END) * 100.0 / COUNT(*) as error_rate
FROM api_logs 
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY hour
ORDER BY hour;

-- Crawler performance by category
SELECT 
    c.name as category_name,
    COUNT(cj.*) as total_jobs,
    COUNT(CASE WHEN cj.status = 'completed' THEN 1 END) as completed_jobs,
    COUNT(CASE WHEN cj.status = 'failed' THEN 1 END) as failed_jobs,
    AVG(cj.articles_found) as avg_articles_per_job,
    AVG(EXTRACT(EPOCH FROM (cj.completed_at - cj.started_at))) as avg_duration_seconds
FROM crawl_jobs cj
JOIN categories c ON cj.category_id = c.id
WHERE cj.created_at > NOW() - INTERVAL '7 days'
GROUP BY c.name
ORDER BY failed_jobs DESC;

-- Database performance metrics
SELECT 
    schemaname,
    tablename,
    n_tup_ins as inserts,
    n_tup_upd as updates, 
    n_tup_del as deletes,
    seq_scan,
    idx_scan,
    n_dead_tup as dead_tuples
FROM pg_stat_user_tables
ORDER BY n_tup_ins + n_tup_upd + n_tup_del DESC;

-- Slow queries identification
SELECT 
    query,
    mean_time,
    calls,
    total_time,
    (total_time/sum(total_time) OVER()) * 100 as percentage
FROM pg_stat_statements 
WHERE calls > 100
ORDER BY mean_time DESC
LIMIT 10;
```

## Log Analysis Scripts

```bash
#!/bin/bash
# scripts/analyze_logs.sh

echo "=== API Response Times (last hour) ==="
docker logs news-scraper-app 2>&1 | \
jq -r 'select(.metric_type == "api_request") | select(.timestamp > (now - 3600 | strftime("%Y-%m-%dT%H:%M:%S"))) | "\(.endpoint): \(.duration_ms)ms"' | \
sort | uniq -c | sort -nr

echo "=== Crawler Success Rates (last 24h) ==="
docker logs news-scraper-celery-worker 2>&1 | \
jq -r 'select(.metric_type == "crawler_activity") | select(.timestamp > (now - 86400 | strftime("%Y-%m-%dT%H:%M:%S"))) | "\(.success)"' | \
sort | uniq -c

echo "=== Top Errors (last hour) ==="
docker logs news-scraper-app 2>&1 | \
jq -r 'select(.level == "ERROR") | select(.timestamp > (now - 3600 | strftime("%Y-%m-%dT%H:%M:%S"))) | .error_type // .message' | \
sort | uniq -c | sort -nr | head -10

echo "=== External Service Performance ==="
docker logs news-scraper-celery-worker 2>&1 | \
jq -r 'select(.metric_type == "external_service_call") | "\(.service_name): \(.success) (\(.duration_ms)ms)"' | \
tail -20
```

## Performance Dashboard Commands

```bash
# Monitor resource usage
docker stats

# Monitor specific service
docker stats google-news-scraper-app-1

# Check container logs
docker-compose logs -f --tail=100 app

# Database monitoring
docker-compose exec postgres psql -U postgres -d news_scraper -c "
SELECT 
    state, 
    COUNT(*) as count,
    AVG(EXTRACT(epoch FROM (now() - query_start))) as avg_duration_seconds
FROM pg_stat_activity 
WHERE state IS NOT NULL 
GROUP BY state;"

# Redis monitoring
docker-compose exec redis redis-cli info memory
docker-compose exec redis redis-cli info clients

# Celery monitoring
docker-compose exec celery-worker celery -A src.core.scheduler.celery_app inspect stats
docker-compose exec celery-worker celery -A src.core.scheduler.celery_app inspect reserved
```

## Key Metrics Tracking

### Application Metrics
- **API Response Times:** Average, 95th percentile, max response times
- **Error Rates:** 4xx và 5xx error percentages
- **Throughput:** Requests per second
- **Database Query Performance:** Query execution times, connection pool usage

### Business Metrics
- **Articles Crawled:** Daily/hourly article discovery rates
- **Crawler Success Rates:** Percentage of successful crawl jobs
- **Category Performance:** Articles found per category
- **External Service Health:** Google News và news site availability

### Infrastructure Metrics
- **System Resources:** CPU, memory, disk usage
- **Container Health:** Service uptime, restart counts
- **Network Performance:** Request latency, bandwidth usage
- **Database Performance:** Connection counts, query performance

## Monitoring Best Practices

1. **Structured Logging:** JSON logs cho easy parsing và analysis
2. **Correlation IDs:** Track requests across services
3. **Health Checks:** Comprehensive dependency checking
4. **Alert Thresholds:** Proactive problem detection
5. **Performance Baselines:** Know normal system behavior
6. **Cost-Effective Monitoring:** Built-in tools instead of expensive external services
7. **Regular Review:** Adjust thresholds based on historical data
8. **Documentation:** Keep runbooks updated cho common issues