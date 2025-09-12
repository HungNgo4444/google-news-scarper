"""Comprehensive health monitoring system for containerized services.

This module provides health check functionality for all application components
including database, Redis, Celery workers, and external dependencies.

Features:
- Individual component health checks
- Aggregated system health status
- Dependency health validation
- Container-aware health reporting
- Prometheus metrics integration (future)

Usage:
    from src.shared.health import HealthChecker
    
    health_checker = HealthChecker()
    status = await health_checker.check_system_health()
    print(f"System healthy: {status.is_healthy}")
"""

import asyncio
import logging
import os
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

import redis.asyncio as aioredis
from celery import Celery
from sqlalchemy import text

from src.shared.config import get_settings
from src.database.connection import get_database_connection

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status enumeration."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """Health status for individual component."""
    name: str
    status: HealthStatus
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    response_time_ms: float = 0.0
    last_checked: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def is_healthy(self) -> bool:
        """Check if component is healthy."""
        return self.status == HealthStatus.HEALTHY


@dataclass
class SystemHealth:
    """Overall system health status."""
    is_healthy: bool
    status: HealthStatus
    components: Dict[str, ComponentHealth] = field(default_factory=dict)
    total_response_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "status": self.status.value,
            "healthy": self.is_healthy,
            "timestamp": self.timestamp.isoformat(),
            "total_response_time_ms": self.total_response_time_ms,
            "components": {
                name: {
                    "status": comp.status.value,
                    "healthy": comp.is_healthy,
                    "message": comp.message,
                    "response_time_ms": comp.response_time_ms,
                    "last_checked": comp.last_checked.isoformat(),
                    "details": comp.details
                }
                for name, comp in self.components.items()
            }
        }


class HealthChecker:
    """Comprehensive health checker for all system components."""
    
    def __init__(self):
        self.settings = get_settings()
        self._redis_client: Optional[aioredis.Redis] = None
        self._celery_app: Optional[Celery] = None
        
    async def check_system_health(self, include_detailed: bool = False) -> SystemHealth:
        """Check health of all system components.
        
        Args:
            include_detailed: Include detailed component information
            
        Returns:
            SystemHealth: Aggregated system health status
        """
        start_time = time.perf_counter()
        components = {}
        
        # Run all health checks concurrently
        health_checks = {
            "database": self.check_database_health(),
            "redis": self.check_redis_health(),
            "celery_worker": self.check_celery_worker_health(),
            "celery_beat": self.check_celery_beat_health(),
            "disk_space": self.check_disk_space(),
            "memory": self.check_memory_usage(),
        }
        
        # Execute all checks concurrently
        results = await asyncio.gather(
            *health_checks.values(),
            return_exceptions=True
        )
        
        # Process results
        for component_name, result in zip(health_checks.keys(), results):
            if isinstance(result, Exception):
                logger.error(f"Health check failed for {component_name}: {result}")
                components[component_name] = ComponentHealth(
                    name=component_name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Health check failed: {str(result)}"
                )
            else:
                components[component_name] = result
        
        # Calculate overall health
        total_time = (time.perf_counter() - start_time) * 1000
        is_healthy = all(comp.is_healthy for comp in components.values())
        
        # Determine overall status
        if is_healthy:
            overall_status = HealthStatus.HEALTHY
        elif any(comp.status == HealthStatus.HEALTHY for comp in components.values()):
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.UNHEALTHY
        
        return SystemHealth(
            is_healthy=is_healthy,
            status=overall_status,
            components=components,
            total_response_time_ms=total_time
        )
    
    async def check_database_health(self) -> ComponentHealth:
        """Check PostgreSQL database health."""
        start_time = time.perf_counter()
        
        try:
            db_connection = get_database_connection()
            
            # Test basic connectivity
            async with db_connection.get_session() as session:
                # Check connection
                result = await session.execute(text("SELECT 1 as health_check"))
                if result.scalar() != 1:
                    raise ValueError("Database connectivity test failed")
                
                # Check database version and stats
                version_result = await session.execute(text("SELECT version()"))
                version = version_result.scalar()
                
                # Check connection pool status
                pool_info = {
                    "pool_size": db_connection.engine.pool.size(),
                    "checked_in": db_connection.engine.pool.checkedin(),
                    "checked_out": db_connection.engine.pool.checkedout(),
                    "overflow": db_connection.engine.pool.overflow(),
                }
                
                response_time = (time.perf_counter() - start_time) * 1000
                
                return ComponentHealth(
                    name="database",
                    status=HealthStatus.HEALTHY,
                    message="Database connection successful",
                    details={
                        "version": version,
                        "pool_info": pool_info,
                        "url": db_connection.settings.DATABASE_URL.split('@')[1] if '@' in db_connection.settings.DATABASE_URL else "hidden"
                    },
                    response_time_ms=response_time
                )
                
        except Exception as e:
            response_time = (time.perf_counter() - start_time) * 1000
            logger.error(f"Database health check failed: {e}")
            
            return ComponentHealth(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=f"Database connection failed: {str(e)}",
                response_time_ms=response_time
            )
    
    async def check_redis_health(self) -> ComponentHealth:
        """Check Redis connectivity and status."""
        start_time = time.perf_counter()
        
        try:
            # Create Redis connection
            redis_url = self.settings.CELERY_BROKER_URL
            redis_client = aioredis.from_url(redis_url, decode_responses=True)
            
            # Test connectivity
            pong = await redis_client.ping()
            if not pong:
                raise ValueError("Redis ping failed")
            
            # Get Redis info
            info = await redis_client.info()
            memory_info = {
                "used_memory": info.get("used_memory_human", "unknown"),
                "used_memory_peak": info.get("used_memory_peak_human", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
            }
            
            response_time = (time.perf_counter() - start_time) * 1000
            await redis_client.close()
            
            return ComponentHealth(
                name="redis",
                status=HealthStatus.HEALTHY,
                message="Redis connection successful",
                details={
                    "version": info.get("redis_version", "unknown"),
                    "memory": memory_info,
                    "uptime_seconds": info.get("uptime_in_seconds", 0)
                },
                response_time_ms=response_time
            )
            
        except Exception as e:
            response_time = (time.perf_counter() - start_time) * 1000
            logger.error(f"Redis health check failed: {e}")
            
            return ComponentHealth(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                message=f"Redis connection failed: {str(e)}",
                response_time_ms=response_time
            )
    
    async def check_celery_worker_health(self) -> ComponentHealth:
        """Check Celery worker status."""
        start_time = time.perf_counter()
        
        try:
            from src.core.scheduler.celery_app import celery_app
            
            # Check worker status using inspect
            inspect = celery_app.control.inspect()
            
            # Run in thread pool since celery inspect is synchronous
            loop = asyncio.get_event_loop()
            
            # Check active workers
            active_workers = await loop.run_in_executor(None, inspect.active)
            ping_result = await loop.run_in_executor(None, inspect.ping)
            stats = await loop.run_in_executor(None, inspect.stats)
            
            if not ping_result:
                raise ValueError("No Celery workers responding to ping")
            
            worker_count = len(ping_result) if ping_result else 0
            response_time = (time.perf_counter() - start_time) * 1000
            
            return ComponentHealth(
                name="celery_worker",
                status=HealthStatus.HEALTHY if worker_count > 0 else HealthStatus.DEGRADED,
                message=f"{worker_count} Celery workers active",
                details={
                    "worker_count": worker_count,
                    "workers": list(ping_result.keys()) if ping_result else [],
                    "stats": stats
                },
                response_time_ms=response_time
            )
            
        except Exception as e:
            response_time = (time.perf_counter() - start_time) * 1000
            logger.error(f"Celery worker health check failed: {e}")
            
            return ComponentHealth(
                name="celery_worker",
                status=HealthStatus.UNHEALTHY,
                message=f"Celery worker check failed: {str(e)}",
                response_time_ms=response_time
            )
    
    async def check_celery_beat_health(self) -> ComponentHealth:
        """Check Celery beat scheduler status."""
        start_time = time.perf_counter()
        
        try:
            from src.core.scheduler.celery_app import celery_app
            
            # Check beat status
            inspect = celery_app.control.inspect()
            loop = asyncio.get_event_loop()
            
            # Check scheduled tasks
            scheduled = await loop.run_in_executor(None, inspect.scheduled)
            
            response_time = (time.perf_counter() - start_time) * 1000
            
            # Beat is healthy if we can query scheduled tasks
            return ComponentHealth(
                name="celery_beat",
                status=HealthStatus.HEALTHY,
                message="Celery beat scheduler accessible",
                details={
                    "scheduled_tasks": len(scheduled) if scheduled else 0
                },
                response_time_ms=response_time
            )
            
        except Exception as e:
            response_time = (time.perf_counter() - start_time) * 1000
            logger.warning(f"Celery beat health check failed: {e}")
            
            # Beat failure is not critical for API operation
            return ComponentHealth(
                name="celery_beat",
                status=HealthStatus.DEGRADED,
                message=f"Celery beat check failed: {str(e)}",
                response_time_ms=response_time
            )
    
    async def check_disk_space(self) -> ComponentHealth:
        """Check available disk space."""
        start_time = time.perf_counter()
        
        try:
            import shutil
            
            # Check disk space for current directory
            total, used, free = shutil.disk_usage("/app" if os.path.exists("/app") else ".")
            
            free_gb = free / (1024**3)
            total_gb = total / (1024**3)
            used_percent = (used / total) * 100
            
            response_time = (time.perf_counter() - start_time) * 1000
            
            # Consider unhealthy if less than 1GB free or >95% used
            if free_gb < 1.0 or used_percent > 95:
                status = HealthStatus.UNHEALTHY
                message = f"Low disk space: {free_gb:.1f}GB free ({used_percent:.1f}% used)"
            elif free_gb < 5.0 or used_percent > 85:
                status = HealthStatus.DEGRADED
                message = f"Disk space warning: {free_gb:.1f}GB free ({used_percent:.1f}% used)"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk space OK: {free_gb:.1f}GB free ({used_percent:.1f}% used)"
            
            return ComponentHealth(
                name="disk_space",
                status=status,
                message=message,
                details={
                    "total_gb": round(total_gb, 1),
                    "used_gb": round((total - free) / (1024**3), 1),
                    "free_gb": round(free_gb, 1),
                    "used_percent": round(used_percent, 1)
                },
                response_time_ms=response_time
            )
            
        except Exception as e:
            response_time = (time.perf_counter() - start_time) * 1000
            logger.error(f"Disk space check failed: {e}")
            
            return ComponentHealth(
                name="disk_space",
                status=HealthStatus.UNKNOWN,
                message=f"Disk space check failed: {str(e)}",
                response_time_ms=response_time
            )
    
    async def check_memory_usage(self) -> ComponentHealth:
        """Check memory usage."""
        start_time = time.perf_counter()
        
        try:
            import psutil
            
            memory = psutil.virtual_memory()
            used_percent = memory.percent
            available_gb = memory.available / (1024**3)
            
            response_time = (time.perf_counter() - start_time) * 1000
            
            # Memory status thresholds
            if used_percent > 95:
                status = HealthStatus.UNHEALTHY
                message = f"Critical memory usage: {used_percent:.1f}% used"
            elif used_percent > 85:
                status = HealthStatus.DEGRADED
                message = f"High memory usage: {used_percent:.1f}% used"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memory usage OK: {used_percent:.1f}% used"
            
            return ComponentHealth(
                name="memory",
                status=status,
                message=message,
                details={
                    "total_gb": round(memory.total / (1024**3), 1),
                    "used_gb": round(memory.used / (1024**3), 1),
                    "available_gb": round(available_gb, 1),
                    "used_percent": round(used_percent, 1)
                },
                response_time_ms=response_time
            )
            
        except ImportError:
            # psutil not available, skip memory check
            response_time = (time.perf_counter() - start_time) * 1000
            return ComponentHealth(
                name="memory",
                status=HealthStatus.UNKNOWN,
                message="Memory monitoring not available (psutil not installed)",
                response_time_ms=response_time
            )
        except Exception as e:
            response_time = (time.perf_counter() - start_time) * 1000
            logger.error(f"Memory check failed: {e}")
            
            return ComponentHealth(
                name="memory",
                status=HealthStatus.UNKNOWN,
                message=f"Memory check failed: {str(e)}",
                response_time_ms=response_time
            )


# Global health checker instance
_health_checker: Optional[HealthChecker] = None


def get_health_checker() -> HealthChecker:
    """Get global health checker instance."""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthChecker()
    return _health_checker