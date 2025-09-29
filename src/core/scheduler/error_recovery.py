"""Job recovery and failure analysis for enhanced error handling."""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple
from uuid import UUID
from dataclasses import dataclass
from enum import Enum

from src.database.repositories.job_repo import CrawlJobRepository
from src.database.repositories.category_repo import CategoryRepository
from src.shared.exceptions import BaseAppException, ErrorCode
from src.core.error_handling.alert_manager import get_alert_manager, AlertType, AlertSeverity
from src.core.scheduler.tasks import crawl_category_task

logger = logging.getLogger(__name__)


class RecoveryAction(Enum):
    """Types of recovery actions that can be taken."""
    RETRY_IMMEDIATELY = "retry_immediately"
    RETRY_DELAYED = "retry_delayed" 
    MARK_FAILED = "mark_failed"
    DISABLE_CATEGORY = "disable_category"
    ESCALATE = "escalate"
    NO_ACTION = "no_action"


@dataclass
class JobFailureAnalysis:
    """Analysis results for a failed job."""
    job_id: UUID
    category_id: UUID
    failure_count: int
    last_error: str
    error_pattern: Optional[str]
    recommended_action: RecoveryAction
    confidence_score: float
    analysis_details: Dict[str, Any]
    created_at: datetime


@dataclass
class RecoveryPlan:
    """Recovery plan for failed jobs."""
    analysis: JobFailureAnalysis
    recovery_action: RecoveryAction
    delay_seconds: Optional[int]
    retry_count: int
    escalation_required: bool
    notes: str


class JobRecoveryEngine:
    """Engine for analyzing job failures and orchestrating recovery."""
    
    def __init__(self):
        self.job_repo = CrawlJobRepository()
        self.category_repo = CategoryRepository()
        self.alert_manager = get_alert_manager()
        
        # Configuration for failure analysis
        self.failure_patterns = {
            "rate_limit": ["rate limit", "too many requests", "429"],
            "network": ["timeout", "connection", "network", "unreachable"],
            "parsing": ["parsing", "extraction", "invalid html", "no content"],
            "authentication": ["unauthorized", "forbidden", "401", "403"],
            "service_unavailable": ["unavailable", "503", "502", "500"]
        }
        
        # Recovery thresholds
        self.max_retries_per_category = 5
        self.failure_window_hours = 24
        self.escalation_threshold = 3
    
    async def analyze_failed_jobs(
        self, 
        hours_back: int = 24,
        category_id: Optional[UUID] = None
    ) -> List[JobFailureAnalysis]:
        """Analyze failed jobs and generate failure analysis.
        
        Args:
            hours_back: How many hours back to analyze
            category_id: Optional specific category to analyze
            
        Returns:
            List of failure analyses
        """
        correlation_id = f"failure_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        logger.info("Starting job failure analysis", extra={
            "correlation_id": correlation_id,
            "hours_back": hours_back,
            "category_id": str(category_id) if category_id else None
        })
        
        # Get failed jobs in the specified time window
        from_date = datetime.now(timezone.utc) - timedelta(hours=hours_back)
        failed_jobs = await self.job_repo.get_failed_jobs_since(
            from_date=from_date,
            category_id=category_id
        )
        
        analyses = []
        
        # Group jobs by category for pattern analysis
        jobs_by_category = {}
        for job in failed_jobs:
            if job.category_id not in jobs_by_category:
                jobs_by_category[job.category_id] = []
            jobs_by_category[job.category_id].append(job)
        
        # Analyze each category's failures
        for category_id, category_jobs in jobs_by_category.items():
            analysis = await self._analyze_category_failures(
                category_id, category_jobs, correlation_id
            )
            if analysis:
                analyses.append(analysis)
        
        logger.info("Job failure analysis completed", extra={
            "correlation_id": correlation_id,
            "analyses_generated": len(analyses),
            "categories_analyzed": len(jobs_by_category)
        })
        
        return analyses
    
    async def _analyze_category_failures(
        self,
        category_id: UUID,
        failed_jobs: List[Any],
        correlation_id: str
    ) -> Optional[JobFailureAnalysis]:
        """Analyze failures for a specific category.
        
        Args:
            category_id: Category UUID
            failed_jobs: List of failed jobs for this category
            correlation_id: Correlation ID for logging
            
        Returns:
            Failure analysis or None if no analysis needed
        """
        if not failed_jobs:
            return None
        
        # Extract error messages and patterns
        error_messages = []
        error_patterns = {}
        
        for job in failed_jobs:
            if job.error_message:
                error_messages.append(job.error_message.lower())
                
                # Classify error pattern
                pattern = self._classify_error_pattern(job.error_message)
                if pattern not in error_patterns:
                    error_patterns[pattern] = 0
                error_patterns[pattern] += 1
        
        # Determine dominant error pattern
        dominant_pattern = max(error_patterns.items(), key=lambda x: x[1])[0] if error_patterns else "unknown"
        
        # Calculate failure metrics
        failure_count = len(failed_jobs)
        latest_job = max(failed_jobs, key=lambda j: j.updated_at)
        
        # Determine recommended action
        recommended_action = self._determine_recovery_action(
            failure_count, dominant_pattern, error_patterns
        )
        
        # Calculate confidence score
        confidence_score = self._calculate_confidence_score(
            failure_count, dominant_pattern, error_patterns
        )
        
        analysis = JobFailureAnalysis(
            job_id=latest_job.id,
            category_id=category_id,
            failure_count=failure_count,
            last_error=latest_job.error_message or "Unknown error",
            error_pattern=dominant_pattern,
            recommended_action=recommended_action,
            confidence_score=confidence_score,
            analysis_details={
                "error_patterns": error_patterns,
                "failure_window_hours": self.failure_window_hours,
                "jobs_analyzed": len(failed_jobs),
                "earliest_failure": min(job.created_at for job in failed_jobs).isoformat(),
                "latest_failure": latest_job.updated_at.isoformat()
            },
            created_at=datetime.now(timezone.utc)
        )
        
        logger.debug("Category failure analysis completed", extra={
            "correlation_id": correlation_id,
            "category_id": str(category_id),
            "failure_count": failure_count,
            "dominant_pattern": dominant_pattern,
            "recommended_action": recommended_action.value,
            "confidence_score": confidence_score
        })
        
        return analysis
    
    def _classify_error_pattern(self, error_message: str) -> str:
        """Classify error message into a pattern category.
        
        Args:
            error_message: Error message to classify
            
        Returns:
            Pattern category string
        """
        if not error_message:
            return "unknown"
        
        error_lower = error_message.lower()
        
        for pattern, keywords in self.failure_patterns.items():
            if any(keyword in error_lower for keyword in keywords):
                return pattern
        
        return "unknown"
    
    def _determine_recovery_action(
        self, 
        failure_count: int, 
        dominant_pattern: str, 
        error_patterns: Dict[str, int]
    ) -> RecoveryAction:
        """Determine appropriate recovery action based on failure analysis.
        
        Args:
            failure_count: Number of failures
            dominant_pattern: Most common error pattern
            error_patterns: Dictionary of error patterns and counts
            
        Returns:
            Recommended recovery action
        """
        # High failure count - escalate or disable
        if failure_count >= self.max_retries_per_category:
            if dominant_pattern in ["authentication", "service_unavailable"]:
                return RecoveryAction.ESCALATE
            else:
                return RecoveryAction.DISABLE_CATEGORY
        
        # Pattern-based recovery decisions
        if dominant_pattern == "rate_limit":
            return RecoveryAction.RETRY_DELAYED
        elif dominant_pattern in ["network", "service_unavailable"]:
            return RecoveryAction.RETRY_DELAYED
        elif dominant_pattern in ["authentication", "parsing"]:
            if failure_count >= self.escalation_threshold:
                return RecoveryAction.ESCALATE
            else:
                return RecoveryAction.MARK_FAILED
        elif dominant_pattern == "unknown":
            if failure_count >= self.escalation_threshold:
                return RecoveryAction.ESCALATE
            else:
                return RecoveryAction.RETRY_DELAYED
        
        # Default for low failure counts
        if failure_count <= 2:
            return RecoveryAction.RETRY_IMMEDIATELY
        else:
            return RecoveryAction.RETRY_DELAYED
    
    def _calculate_confidence_score(
        self, 
        failure_count: int, 
        dominant_pattern: str, 
        error_patterns: Dict[str, int]
    ) -> float:
        """Calculate confidence score for the analysis.
        
        Args:
            failure_count: Number of failures
            dominant_pattern: Most common error pattern
            error_patterns: Dictionary of error patterns and counts
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        base_confidence = 0.5
        
        # More failures = higher confidence in pattern
        failure_factor = min(failure_count / 10.0, 0.3)
        
        # Known patterns = higher confidence
        pattern_factor = 0.2 if dominant_pattern != "unknown" else -0.1
        
        # Pattern consistency = higher confidence
        if error_patterns:
            total_errors = sum(error_patterns.values())
            max_pattern_count = max(error_patterns.values())
            consistency_factor = (max_pattern_count / total_errors) * 0.3
        else:
            consistency_factor = 0.0
        
        confidence = base_confidence + failure_factor + pattern_factor + consistency_factor
        return max(0.1, min(confidence, 1.0))
    
    async def create_recovery_plan(self, analysis: JobFailureAnalysis) -> RecoveryPlan:
        """Create a detailed recovery plan from failure analysis.
        
        Args:
            analysis: Failure analysis to create plan from
            
        Returns:
            Recovery plan
        """
        action = analysis.recommended_action
        delay_seconds = None
        escalation_required = False
        notes = f"Based on {analysis.failure_count} failures with pattern '{analysis.error_pattern}'"
        
        if action == RecoveryAction.RETRY_DELAYED:
            # Calculate delay based on pattern
            if analysis.error_pattern == "rate_limit":
                delay_seconds = 1800 + (analysis.failure_count * 300)  # 30+ minutes
            else:
                delay_seconds = 300 + (analysis.failure_count * 60)  # 5+ minutes
            notes += f". Will retry after {delay_seconds // 60} minutes."
        
        elif action == RecoveryAction.ESCALATE:
            escalation_required = True
            notes += ". Manual intervention required."
        
        elif action == RecoveryAction.DISABLE_CATEGORY:
            notes += ". Category will be temporarily disabled."
        
        plan = RecoveryPlan(
            analysis=analysis,
            recovery_action=action,
            delay_seconds=delay_seconds,
            retry_count=0,
            escalation_required=escalation_required,
            notes=notes
        )
        
        logger.info("Recovery plan created", extra={
            "category_id": str(analysis.category_id),
            "job_id": str(analysis.job_id),
            "recovery_action": action.value,
            "delay_seconds": delay_seconds,
            "escalation_required": escalation_required
        })
        
        return plan
    
    async def execute_recovery_plan(self, plan: RecoveryPlan) -> Dict[str, Any]:
        """Execute a recovery plan.
        
        Args:
            plan: Recovery plan to execute
            
        Returns:
            Execution results
        """
        correlation_id = f"recovery_{plan.analysis.job_id}"
        
        logger.info("Executing recovery plan", extra={
            "correlation_id": correlation_id,
            "recovery_action": plan.recovery_action.value,
            "category_id": str(plan.analysis.category_id),
            "job_id": str(plan.analysis.job_id)
        })
        
        try:
            if plan.recovery_action == RecoveryAction.RETRY_IMMEDIATELY:
                return await self._retry_job_immediately(plan, correlation_id)
            
            elif plan.recovery_action == RecoveryAction.RETRY_DELAYED:
                return await self._retry_job_delayed(plan, correlation_id)
            
            elif plan.recovery_action == RecoveryAction.MARK_FAILED:
                return await self._mark_job_permanently_failed(plan, correlation_id)
            
            elif plan.recovery_action == RecoveryAction.DISABLE_CATEGORY:
                return await self._disable_category(plan, correlation_id)
            
            elif plan.recovery_action == RecoveryAction.ESCALATE:
                return await self._escalate_to_operators(plan, correlation_id)
            
            else:  # NO_ACTION
                return {"status": "no_action", "message": "No recovery action needed"}
        
        except Exception as e:
            logger.error(f"Recovery plan execution failed: {e}", extra={
                "correlation_id": correlation_id,
                "recovery_action": plan.recovery_action.value
            })
            return {"status": "error", "error": str(e)}
    
    async def _retry_job_immediately(self, plan: RecoveryPlan, correlation_id: str) -> Dict[str, Any]:
        """Retry a job immediately."""
        # Schedule new crawl task
        result = crawl_category_task.delay(
            category_id=str(plan.analysis.category_id),
            job_id=str(plan.analysis.job_id),
            start_date=None,
            end_date=None,
            max_results=None
        )
        
        return {
            "status": "retried",
            "celery_task_id": result.id,
            "action": "immediate_retry",
            "correlation_id": correlation_id
        }
    
    async def _retry_job_delayed(self, plan: RecoveryPlan, correlation_id: str) -> Dict[str, Any]:
        """Schedule a delayed retry for a job."""
        # Schedule task with delay
        result = crawl_category_task.apply_async(
            args=[str(plan.analysis.category_id), str(plan.analysis.job_id), None, None, None],
            countdown=plan.delay_seconds
        )
        
        return {
            "status": "scheduled",
            "celery_task_id": result.id,
            "action": "delayed_retry",
            "delay_seconds": plan.delay_seconds,
            "correlation_id": correlation_id
        }
    
    async def _mark_job_permanently_failed(self, plan: RecoveryPlan, correlation_id: str) -> Dict[str, Any]:
        """Mark a job as permanently failed."""
        await self.job_repo.mark_permanently_failed(
            job_id=plan.analysis.job_id,
            reason=f"Recovery analysis: {plan.notes}"
        )
        
        return {
            "status": "marked_failed",
            "action": "permanent_failure",
            "reason": plan.notes,
            "correlation_id": correlation_id
        }
    
    async def _disable_category(self, plan: RecoveryPlan, correlation_id: str) -> Dict[str, Any]:
        """Temporarily disable a category due to repeated failures."""
        category = await self.category_repo.get_by_id(plan.analysis.category_id)
        if category:
            await self.category_repo.disable_temporarily(
                category_id=plan.analysis.category_id,
                reason=f"Automatic disable due to {plan.analysis.failure_count} failures",
                disable_until=datetime.now(timezone.utc) + timedelta(hours=24)
            )
            
            # Send alert about category disable
            await self.alert_manager.send_alert(
                alert_type=AlertType.SERVICE_DEGRADED,
                severity=AlertSeverity.HIGH,
                message=f"Category '{category.name}' temporarily disabled due to repeated failures",
                details={
                    "category_id": str(plan.analysis.category_id),
                    "failure_count": plan.analysis.failure_count,
                    "error_pattern": plan.analysis.error_pattern,
                    "disable_hours": 24
                },
                correlation_id=correlation_id
            )
        
        return {
            "status": "disabled",
            "action": "category_disabled",
            "disable_hours": 24,
            "correlation_id": correlation_id
        }
    
    async def _escalate_to_operators(self, plan: RecoveryPlan, correlation_id: str) -> Dict[str, Any]:
        """Escalate issue to human operators."""
        # Send critical alert for manual intervention
        await self.alert_manager.send_alert(
            alert_type=AlertType.TASK_FAILURE,
            severity=AlertSeverity.CRITICAL,
            message=f"Manual intervention required for category failures",
            details={
                "category_id": str(plan.analysis.category_id),
                "job_id": str(plan.analysis.job_id),
                "failure_count": plan.analysis.failure_count,
                "error_pattern": plan.analysis.error_pattern,
                "analysis_confidence": plan.analysis.confidence_score,
                "recovery_plan": plan.notes
            },
            correlation_id=correlation_id
        )
        
        # Mark job for manual review
        await self.job_repo.mark_for_manual_review(
            job_id=plan.analysis.job_id,
            reason=f"Escalated: {plan.notes}"
        )
        
        return {
            "status": "escalated",
            "action": "manual_intervention",
            "reason": plan.notes,
            "correlation_id": correlation_id
        }
    
    async def run_automatic_recovery(
        self, 
        hours_back: int = 6,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Run automatic recovery process for recent failures.
        
        Args:
            hours_back: How many hours back to analyze
            dry_run: If True, only analyze but don't execute recovery
            
        Returns:
            Recovery execution summary
        """
        correlation_id = f"auto_recovery_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        logger.info("Starting automatic recovery process", extra={
            "correlation_id": correlation_id,
            "hours_back": hours_back,
            "dry_run": dry_run
        })
        
        # Analyze failures
        analyses = await self.analyze_failed_jobs(hours_back=hours_back)
        
        recovery_results = []
        
        for analysis in analyses:
            # Create recovery plan
            plan = await self.create_recovery_plan(analysis)
            
            if dry_run:
                recovery_results.append({
                    "category_id": str(analysis.category_id),
                    "recommended_action": plan.recovery_action.value,
                    "confidence": analysis.confidence_score,
                    "notes": plan.notes,
                    "executed": False
                })
            else:
                # Execute recovery plan
                result = await self.execute_recovery_plan(plan)
                result["category_id"] = str(analysis.category_id)
                result["confidence"] = analysis.confidence_score
                recovery_results.append(result)
        
        summary = {
            "correlation_id": correlation_id,
            "analyses_performed": len(analyses),
            "recoveries_attempted": len([r for r in recovery_results if r.get("executed", True)]),
            "dry_run": dry_run,
            "results": recovery_results
        }
        
        logger.info("Automatic recovery process completed", extra=summary)
        
        return summary


# Global recovery engine instance
_recovery_engine: Optional[JobRecoveryEngine] = None


def get_recovery_engine() -> JobRecoveryEngine:
    """Get the global recovery engine instance."""
    global _recovery_engine
    if _recovery_engine is None:
        _recovery_engine = JobRecoveryEngine()
    return _recovery_engine