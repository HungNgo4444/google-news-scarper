#!/usr/bin/env python3
"""Job Management Utilities for Google News Scraper.

This script provides command-line utilities for managing crawl jobs including:
- Starting, stopping, and monitoring scheduled jobs
- Triggering manual crawls
- Viewing job statistics and health
- Cleaning up old jobs

Usage:
    python scripts/manage_jobs.py --help
    python scripts/manage_jobs.py status
    python scripts/manage_jobs.py trigger --category "Technology"
    python scripts/manage_jobs.py cleanup --days 30
    python scripts/manage_jobs.py health-check
"""

import asyncio
import argparse
import sys
import os
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from uuid import UUID
import json

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.shared.config import get_settings
from src.database.repositories.job_repo import CrawlJobRepository
from src.database.repositories.category_repo import CategoryRepository
from src.core.scheduler.tasks import trigger_category_crawl_task, cleanup_old_jobs_task
from src.core.scheduler.celery_app import check_celery_health
from src.database.models.crawl_job import CrawlJobStatus


class JobManager:
    """Job management utility class."""
    
    def __init__(self):
        self.settings = get_settings()
        self.job_repo = CrawlJobRepository()
        self.category_repo = CategoryRepository()
    
    async def show_status(self, limit: int = 20) -> Dict[str, Any]:
        """Show current job queue status.
        
        Args:
            limit: Maximum number of jobs to display per status
            
        Returns:
            Status information dictionary
        """
        print("📊 Job Queue Status")
        print("=" * 50)
        
        # Get active jobs
        active_jobs = await self.job_repo.get_active_jobs(limit=limit)
        running_jobs = await self.job_repo.get_running_jobs(limit=limit)
        pending_jobs = await self.job_repo.get_pending_jobs(limit=limit)
        
        print(f"Active Jobs: {len(active_jobs)}")
        print(f"  Running: {len(running_jobs)}")
        print(f"  Pending: {len(pending_jobs)}")
        
        # Show running jobs
        if running_jobs:
            print("\n🔄 Currently Running:")
            for job in running_jobs:
                duration = self._calculate_duration(job.started_at)
                print(f"  {job.id} | {job.category.name} | Running {duration}")
        
        # Show pending jobs
        if pending_jobs:
            print("\n⏳ Pending Jobs:")
            for job in pending_jobs[:5]:  # Show top 5 by priority
                age = self._calculate_duration(job.created_at)
                print(f"  {job.id} | {job.category.name} | Priority: {job.priority} | Age: {age}")
        
        # Get recent statistics
        from_date = datetime.now(timezone.utc) - timedelta(hours=24)
        stats = await self.job_repo.get_job_statistics(from_date=from_date)
        
        print(f"\n📈 Last 24 Hours:")
        print(f"  Completed: {stats['status_counts'].get('completed', 0)}")
        print(f"  Failed: {stats['status_counts'].get('failed', 0)}")
        print(f"  Articles Found: {stats['total_articles_found']}")
        print(f"  Articles Saved: {stats['total_articles_saved']}")
        
        success_rate = stats.get('success_rate', 0)
        print(f"  Success Rate: {success_rate:.1%}")
        
        return {
            "active_jobs": len(active_jobs),
            "running_jobs": len(running_jobs),
            "pending_jobs": len(pending_jobs),
            "stats": stats
        }
    
    async def trigger_crawl(
        self, 
        category_name: str, 
        priority: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Trigger a manual crawl for a category.
        
        Args:
            category_name: Name of the category to crawl
            priority: Job priority
            metadata: Optional job metadata
            
        Returns:
            Trigger result information
        """
        print(f"🚀 Triggering crawl for category: {category_name}")
        
        # Find category by name
        categories = await self.category_repo.search_by_name(category_name)
        if not categories:
            print(f"❌ Category '{category_name}' not found")
            return {"status": "failed", "error": "Category not found"}
        
        category = categories[0]  # Use first match
        
        if not category.is_active:
            print(f"⚠️ Category '{category.name}' is not active")
            return {"status": "failed", "error": "Category not active"}
        
        # Trigger the crawl task
        result = trigger_category_crawl_task.delay(
            category_id=str(category.id),
            priority=priority,
            metadata=metadata or {}
        )
        
        print(f"✅ Crawl scheduled successfully!")
        print(f"  Category: {category.name}")
        print(f"  Task ID: {result.id}")
        print(f"  Priority: {priority}")
        
        return {
            "status": "scheduled",
            "category_id": str(category.id),
            "category_name": category.name,
            "task_id": result.id,
            "priority": priority
        }
    
    async def list_categories(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """List available categories for crawling.
        
        Args:
            active_only: Only show active categories
            
        Returns:
            List of category information
        """
        print("📂 Available Categories")
        print("=" * 50)
        
        categories = await self.category_repo.get_all()
        
        if active_only:
            categories = [cat for cat in categories if cat.is_active]
        
        results = []
        for category in categories:
            # Get recent job stats for this category
            from_date = datetime.now(timezone.utc) - timedelta(days=7)
            stats = await self.job_repo.get_job_statistics(
                category_id=category.id,
                from_date=from_date
            )
            
            recent_jobs = stats['status_counts'].get('completed', 0) + stats['status_counts'].get('failed', 0)
            
            status = "🟢 Active" if category.is_active else "🔴 Inactive"
            print(f"  {category.name} | {status} | Keywords: {len(category.keywords)} | Jobs (7d): {recent_jobs}")
            
            results.append({
                "id": str(category.id),
                "name": category.name,
                "is_active": category.is_active,
                "keywords_count": len(category.keywords),
                "recent_jobs": recent_jobs
            })
        
        return results
    
    async def cleanup_jobs(self, days_old: int = 30) -> Dict[str, Any]:
        """Clean up old completed/failed jobs.
        
        Args:
            days_old: Age threshold for cleanup
            
        Returns:
            Cleanup results
        """
        print(f"🧹 Cleaning up jobs older than {days_old} days...")
        
        # Get count before cleanup
        all_jobs = await self.job_repo.get_all()
        completed_jobs = await self.job_repo.get_completed_jobs(limit=1000)
        failed_jobs = await self.job_repo.get_failed_jobs(limit=1000)
        
        print(f"  Total jobs before cleanup: {len(all_jobs)}")
        print(f"  Completed jobs: {len(completed_jobs)}")
        print(f"  Failed jobs: {len(failed_jobs)}")
        
        # Execute cleanup
        cleaned_count = await self.job_repo.cleanup_old_jobs(days_old=days_old)
        
        print(f"✅ Cleanup completed!")
        print(f"  Jobs removed: {cleaned_count}")
        
        return {
            "status": "completed",
            "jobs_cleaned": cleaned_count,
            "days_old": days_old
        }
    
    async def check_health(self) -> Dict[str, Any]:
        """Check system health including Celery and job queue.
        
        Returns:
            Health check results
        """
        print("🏥 System Health Check")
        print("=" * 50)
        
        health_results = {
            "celery": {},
            "job_queue": {},
            "overall_status": "unknown"
        }
        
        # Check Celery health
        celery_health = check_celery_health()
        health_results["celery"] = celery_health
        
        if celery_health["status"] == "healthy":
            print("✅ Celery: Healthy")
            print(f"  Active workers: {celery_health['active_workers']}")
            print(f"  Active tasks: {celery_health['active_tasks']}")
        else:
            print("❌ Celery: Unhealthy")
            print(f"  Error: {celery_health.get('message', 'Unknown error')}")
        
        # Check job queue health
        active_jobs = await self.job_repo.get_active_jobs(limit=1000)
        stuck_jobs = await self.job_repo.get_stuck_jobs(stuck_threshold_hours=2)
        
        from_date = datetime.now(timezone.utc) - timedelta(hours=24)
        stats = await self.job_repo.get_job_statistics(from_date=from_date)
        
        total_completed = stats["status_counts"].get("completed", 0)
        total_failed = stats["status_counts"].get("failed", 0)
        total_finished = total_completed + total_failed
        success_rate = total_completed / total_finished if total_finished > 0 else 1.0
        
        health_results["job_queue"] = {
            "active_jobs": len(active_jobs),
            "stuck_jobs": len(stuck_jobs),
            "success_rate_24h": success_rate,
            "jobs_completed_24h": total_completed,
            "jobs_failed_24h": total_failed
        }
        
        print(f"\n📋 Job Queue: {'✅ Healthy' if len(stuck_jobs) == 0 and success_rate > 0.8 else '⚠️ Issues detected'}")
        print(f"  Active jobs: {len(active_jobs)}")
        print(f"  Stuck jobs: {len(stuck_jobs)}")
        print(f"  24h success rate: {success_rate:.1%}")
        
        if stuck_jobs:
            print(f"  ⚠️ Found {len(stuck_jobs)} stuck jobs")
        
        # Determine overall health
        if (celery_health["status"] == "healthy" and 
            len(stuck_jobs) == 0 and 
            success_rate > 0.8):
            health_results["overall_status"] = "healthy"
            print(f"\n🎉 Overall Status: Healthy")
        elif (celery_health["status"] == "healthy" and 
              len(stuck_jobs) < 5 and 
              success_rate > 0.6):
            health_results["overall_status"] = "degraded"
            print(f"\n⚠️ Overall Status: Degraded")
        else:
            health_results["overall_status"] = "unhealthy"
            print(f"\n❌ Overall Status: Unhealthy")
        
        return health_results
    
    async def reset_stuck_jobs(self, hours_threshold: int = 2) -> Dict[str, Any]:
        """Reset jobs that appear to be stuck.
        
        Args:
            hours_threshold: Hours threshold for considering jobs stuck
            
        Returns:
            Reset results
        """
        print(f"🔧 Resetting jobs stuck for more than {hours_threshold} hours...")
        
        stuck_jobs = await self.job_repo.get_stuck_jobs(stuck_threshold_hours=hours_threshold)
        
        if not stuck_jobs:
            print("✅ No stuck jobs found")
            return {"status": "completed", "jobs_reset": 0}
        
        print(f"Found {len(stuck_jobs)} stuck jobs:")
        for job in stuck_jobs:
            duration = self._calculate_duration(job.started_at)
            print(f"  {job.id} | {job.category.name} | Running {duration}")
        
        reset_count = await self.job_repo.reset_stuck_jobs(stuck_threshold_hours=hours_threshold)
        
        print(f"✅ Reset {reset_count} stuck jobs")
        
        return {
            "status": "completed",
            "jobs_reset": reset_count,
            "hours_threshold": hours_threshold
        }
    
    def _calculate_duration(self, start_time: datetime) -> str:
        """Calculate human-readable duration from start time.
        
        Args:
            start_time: Start timestamp
            
        Returns:
            Formatted duration string
        """
        if not start_time:
            return "unknown"
        
        duration = datetime.now(timezone.utc) - start_time
        
        if duration.days > 0:
            return f"{duration.days}d {duration.seconds//3600}h"
        elif duration.seconds >= 3600:
            return f"{duration.seconds//3600}h {(duration.seconds%3600)//60}m"
        elif duration.seconds >= 60:
            return f"{duration.seconds//60}m"
        else:
            return f"{duration.seconds}s"


async def main():
    """Main entry point for job management script."""
    parser = argparse.ArgumentParser(description="Job Management Utilities")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Show job queue status")
    status_parser.add_argument("--limit", type=int, default=20, help="Limit number of jobs to show")
    
    # Trigger command
    trigger_parser = subparsers.add_parser("trigger", help="Trigger manual crawl")
    trigger_parser.add_argument("--category", required=True, help="Category name to crawl")
    trigger_parser.add_argument("--priority", type=int, default=0, help="Job priority")
    
    # Categories command
    categories_parser = subparsers.add_parser("categories", help="List available categories")
    categories_parser.add_argument("--all", action="store_true", help="Show inactive categories too")
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Clean up old jobs")
    cleanup_parser.add_argument("--days", type=int, default=30, help="Age threshold in days")
    cleanup_parser.add_argument("--dry-run", action="store_true", help="Show what would be cleaned without doing it")
    
    # Health check command
    health_parser = subparsers.add_parser("health", help="Check system health")
    
    # Reset command
    reset_parser = subparsers.add_parser("reset-stuck", help="Reset stuck jobs")
    reset_parser.add_argument("--hours", type=int, default=2, help="Hours threshold for stuck jobs")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = JobManager()
    
    try:
        if args.command == "status":
            await manager.show_status(limit=args.limit)
        
        elif args.command == "trigger":
            await manager.trigger_crawl(category_name=args.category, priority=args.priority)
        
        elif args.command == "categories":
            await manager.list_categories(active_only=not args.all)
        
        elif args.command == "cleanup":
            if args.dry_run:
                print("🔍 Dry run mode - no jobs will be deleted")
                # Would implement dry run logic here
            else:
                await manager.cleanup_jobs(days_old=args.days)
        
        elif args.command == "health":
            await manager.check_health()
        
        elif args.command == "reset-stuck":
            await manager.reset_stuck_jobs(hours_threshold=args.hours)
        
    except KeyboardInterrupt:
        print("\n⚠️ Operation cancelled by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())