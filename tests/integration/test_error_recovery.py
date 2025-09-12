"""Integration tests for complete error recovery workflows."""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4

from src.shared.exceptions import (
    ExternalServiceError,
    GoogleNewsUnavailableError,
    RateLimitExceededError,
    DatabaseConnectionError,
    CircuitBreakerOpenError
)
from src.core.error_handling.circuit_breaker import CircuitBreakerManager, CircuitBreakerConfig
from src.core.error_handling.retry_handler import RetryHandler, RetryConfig
from src.core.error_handling.alert_manager import get_alert_manager, AlertType, AlertSeverity
from src.core.scheduler.error_recovery import (
    JobRecoveryEngine,
    RecoveryAction,
    JobFailureAnalysis,
    get_recovery_engine
)


class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker with retry and alerts."""
    
    @pytest.fixture
    def circuit_breaker_manager(self):
        """Create circuit breaker manager for testing."""
        return CircuitBreakerManager()
    
    @pytest.fixture
    def mock_service(self):
        """Create mock external service for testing."""
        class MockExternalService:
            def __init__(self):
                self.call_count = 0
                self.failure_mode = None
                self.failure_count = 0
            
            async def call_api(self, endpoint: str):
                self.call_count += 1
                
                if self.failure_mode == "always_fail":
                    raise GoogleNewsUnavailableError("Service is down")
                elif self.failure_mode == "intermittent" and self.call_count <= self.failure_count:
                    raise ExternalServiceError(code="TEMP_ERROR", message="Temporary failure")
                elif self.failure_mode == "rate_limit":
                    raise RateLimitExceededError("Rate limit exceeded", retry_after=1)
                
                return f"Success from {endpoint}"
        
        return MockExternalService()
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self, circuit_breaker_manager, mock_service):
        """Test that circuit breaker opens after repeated failures."""
        config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=1)
        
        # Configure service to always fail
        mock_service.failure_mode = "always_fail"
        
        # Make calls that will cause circuit breaker to open
        for i in range(4):
            try:
                await circuit_breaker_manager.call_with_circuit_breaker(
                    "google_news",
                    mock_service.call_api,
                    "/search",
                    config=config
                )
            except (GoogleNewsUnavailableError, CircuitBreakerOpenError):
                pass  # Expected failures
        
        # Verify circuit breaker is open
        cb = circuit_breaker_manager.get_circuit_breaker("google_news")
        assert cb.is_open
        
        # Next call should fail fast
        with pytest.raises(CircuitBreakerOpenError):
            await circuit_breaker_manager.call_with_circuit_breaker(
                "google_news",
                mock_service.call_api,
                "/search",
                config=config
            )
        
        # Service calls should stop (fail fast)
        initial_call_count = mock_service.call_count
        
        try:
            await circuit_breaker_manager.call_with_circuit_breaker(
                "google_news",
                mock_service.call_api,
                "/search",
                config=config
            )
        except CircuitBreakerOpenError:
            pass
        
        assert mock_service.call_count == initial_call_count  # No additional calls
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_recovery_after_service_restoration(self, circuit_breaker_manager, mock_service):
        """Test circuit breaker recovery when service is restored."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.1,  # Very short for testing
            success_threshold=1
        )
        
        # Cause circuit to open
        mock_service.failure_mode = "always_fail"
        for _ in range(2):
            try:
                await circuit_breaker_manager.call_with_circuit_breaker(
                    "google_news",
                    mock_service.call_api,
                    "/search",
                    config=config
                )
            except GoogleNewsUnavailableError:
                pass
        
        cb = circuit_breaker_manager.get_circuit_breaker("google_news")
        assert cb.is_open
        
        # Wait for recovery timeout
        await asyncio.sleep(0.2)
        
        # Service is now working
        mock_service.failure_mode = None
        
        # Circuit should transition to half-open and then closed
        result = await circuit_breaker_manager.call_with_circuit_breaker(
            "google_news",
            mock_service.call_api,
            "/search",
            config=config
        )
        
        assert result == "Success from /search"
        assert cb.is_closed
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_with_retry_handler_integration(self, circuit_breaker_manager):
        """Test circuit breaker working with retry handler."""
        retry_config = RetryConfig(max_retries=2, base_delay=0.01)
        retry_handler = RetryHandler(retry_config)
        
        cb_config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=1)
        
        call_count = 0
        
        async def flaky_service():
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ExternalServiceError(code="TEMP", message="Temporary error")
            return "Success after retries"
        
        # Wrap service call with both retry handler and circuit breaker
        async def protected_service_call():
            return await circuit_breaker_manager.call_with_circuit_breaker(
                "protected_service",
                flaky_service,
                config=cb_config
            )
        
        result = await retry_handler.execute_with_retry(protected_service_call)
        
        assert result == "Success after retries"
        assert call_count == 3  # Initial + 2 retries
        
        # Circuit breaker should still be closed
        cb = circuit_breaker_manager.get_circuit_breaker("protected_service")
        assert cb.is_closed


class TestJobRecoveryIntegration:
    """Integration tests for job recovery system."""
    
    @pytest.fixture
    def mock_job_repo(self):
        """Mock job repository for testing."""
        repo = Mock()
        
        # Mock failed jobs data
        failed_jobs = []
        for i in range(5):
            job = Mock()
            job.id = uuid4()
            job.category_id = uuid4()
            job.error_message = "Google News service unavailable"
            job.created_at = datetime.now(timezone.utc) - timedelta(hours=i)
            job.updated_at = datetime.now(timezone.utc) - timedelta(hours=i)
            failed_jobs.append(job)
        
        repo.get_failed_jobs_since = AsyncMock(return_value=failed_jobs)
        repo.mark_permanently_failed = AsyncMock()
        repo.mark_for_manual_review = AsyncMock()
        return repo
    
    @pytest.fixture
    def mock_category_repo(self):
        """Mock category repository for testing."""
        repo = Mock()
        
        category = Mock()
        category.id = uuid4()
        category.name = "Technology"
        category.is_active = True
        
        repo.get_by_id = AsyncMock(return_value=category)
        repo.disable_temporarily = AsyncMock()
        return repo
    
    @pytest.fixture
    def recovery_engine(self, mock_job_repo, mock_category_repo):
        """Create job recovery engine with mocked dependencies."""
        engine = JobRecoveryEngine()
        engine.job_repo = mock_job_repo
        engine.category_repo = mock_category_repo
        return engine
    
    @pytest.mark.asyncio
    async def test_job_failure_analysis(self, recovery_engine):
        """Test job failure analysis and pattern recognition."""
        analyses = await recovery_engine.analyze_failed_jobs(hours_back=24)
        
        assert len(analyses) == 1  # All jobs are for same category
        
        analysis = analyses[0]
        assert analysis.failure_count == 5
        assert analysis.error_pattern == "service_unavailable"
        assert analysis.recommended_action in [RecoveryAction.RETRY_DELAYED, RecoveryAction.ESCALATE]
        assert 0.0 < analysis.confidence_score <= 1.0
    
    @pytest.mark.asyncio
    async def test_recovery_plan_creation_and_execution(self, recovery_engine):
        """Test creating and executing recovery plans."""
        # Create a failure analysis
        analysis = JobFailureAnalysis(
            job_id=uuid4(),
            category_id=uuid4(),
            failure_count=3,
            last_error="Rate limit exceeded",
            error_pattern="rate_limit",
            recommended_action=RecoveryAction.RETRY_DELAYED,
            confidence_score=0.8,
            analysis_details={},
            created_at=datetime.now(timezone.utc)
        )
        
        # Create recovery plan
        plan = await recovery_engine.create_recovery_plan(analysis)
        
        assert plan.recovery_action == RecoveryAction.RETRY_DELAYED
        assert plan.delay_seconds is not None
        assert plan.delay_seconds > 0
        assert "rate limit" in plan.notes.lower()
        
        # Mock task scheduling for execution
        with patch('src.core.scheduler.error_recovery.crawl_category_task') as mock_task:
            mock_task.apply_async.return_value = Mock(id="task-123")
            
            result = await recovery_engine.execute_recovery_plan(plan)
            
            assert result["status"] == "scheduled"
            assert result["action"] == "delayed_retry"
            assert result["delay_seconds"] == plan.delay_seconds
            mock_task.apply_async.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_automatic_recovery_workflow(self, recovery_engine):
        """Test complete automatic recovery workflow."""
        # Mock alert manager
        with patch('src.core.scheduler.error_recovery.get_alert_manager') as mock_get_alert_mgr:
            mock_alert_mgr = Mock()
            mock_alert_mgr.send_alert = AsyncMock()
            mock_get_alert_mgr.return_value = mock_alert_mgr
            
            # Mock task scheduling
            with patch('src.core.scheduler.error_recovery.crawl_category_task') as mock_task:
                mock_task.delay.return_value = Mock(id="retry-task-456")
                mock_task.apply_async.return_value = Mock(id="delayed-task-789")
                
                # Run automatic recovery
                summary = await recovery_engine.run_automatic_recovery(hours_back=6)
                
                assert summary["analyses_performed"] > 0
                assert summary["recoveries_attempted"] > 0
                assert not summary["dry_run"]
                assert len(summary["results"]) > 0
                
                # Verify recovery actions were taken
                for result in summary["results"]:
                    assert "category_id" in result
                    assert "confidence" in result
                    assert result.get("executed", True)  # Should be executed (not dry run)
    
    @pytest.mark.asyncio
    async def test_escalation_with_alerts(self, recovery_engine):
        """Test escalation workflow with alert notifications."""
        # Create analysis that requires escalation
        analysis = JobFailureAnalysis(
            job_id=uuid4(),
            category_id=uuid4(),
            failure_count=8,  # High failure count
            last_error="Authentication failed",
            error_pattern="authentication",
            recommended_action=RecoveryAction.ESCALATE,
            confidence_score=0.9,
            analysis_details={},
            created_at=datetime.now(timezone.utc)
        )
        
        plan = await recovery_engine.create_recovery_plan(analysis)
        
        # Mock alert manager for escalation
        with patch.object(recovery_engine, 'alert_manager') as mock_alert_mgr:
            mock_alert_mgr.send_alert = AsyncMock()
            
            result = await recovery_engine.execute_recovery_plan(plan)
            
            assert result["status"] == "escalated"
            assert result["action"] == "manual_intervention"
            
            # Verify alert was sent
            mock_alert_mgr.send_alert.assert_called_once()
            call_args = mock_alert_mgr.send_alert.call_args
            assert call_args[1]["alert_type"] == AlertType.TASK_FAILURE
            assert call_args[1]["severity"] == AlertSeverity.CRITICAL
            
            # Verify job was marked for manual review
            recovery_engine.job_repo.mark_for_manual_review.assert_called_once()


class TestFullErrorHandlingWorkflow:
    """End-to-end tests for complete error handling workflow."""
    
    @pytest.fixture
    def error_handling_stack(self):
        """Create complete error handling stack."""
        return {
            'circuit_breaker_manager': CircuitBreakerManager(),
            'retry_handler': RetryHandler(RetryConfig(max_retries=3, base_delay=0.01)),
            'alert_manager': get_alert_manager(),
            'recovery_engine': get_recovery_engine()
        }
    
    @pytest.mark.asyncio
    async def test_external_service_failure_recovery_workflow(self, error_handling_stack):
        """Test complete workflow from service failure to recovery."""
        cb_manager = error_handling_stack['circuit_breaker_manager']
        retry_handler = error_handling_stack['retry_handler']
        alert_manager = error_handling_stack['alert_manager']
        
        # Mock service that fails initially then recovers
        service_state = {"failures": 0, "recovered": False}
        
        async def external_service():
            service_state["failures"] += 1
            
            # Fail for first 4 calls, then recover
            if service_state["failures"] <= 4:
                if service_state["failures"] <= 2:
                    raise GoogleNewsUnavailableError("Service temporarily down")
                else:
                    raise RateLimitExceededError("Rate limited", retry_after=0.01)
            else:
                service_state["recovered"] = True
                return "Service recovered successfully"
        
        # Mock alert manager to track alerts
        mock_alert_handler = Mock()
        mock_alert_handler.send_alert = AsyncMock(return_value=True)
        alert_manager.handlers = {channel: mock_alert_handler for channel in alert_manager.handlers}
        
        # Configure circuit breaker
        cb_config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=0.1,
            success_threshold=1
        )
        
        # Function that combines retry + circuit breaker protection
        async def protected_service_call():
            return await cb_manager.call_with_circuit_breaker(
                "external_service",
                external_service,
                config=cb_config
            )
        
        # First attempt - should eventually succeed after retries and recovery
        with pytest.raises((GoogleNewsUnavailableError, RateLimitExceededError, CircuitBreakerOpenError)):
            await retry_handler.execute_with_retry(protected_service_call)
        
        # Circuit breaker should be open now
        cb = cb_manager.get_circuit_breaker("external_service")
        assert cb.is_open
        
        # Wait for circuit breaker recovery timeout
        await asyncio.sleep(0.2)
        
        # Service should now work (simulating service recovery)
        result = await retry_handler.execute_with_retry(protected_service_call)
        
        assert result == "Service recovered successfully"
        assert service_state["recovered"] is True
        assert cb.is_closed
    
    @pytest.mark.asyncio
    async def test_cascading_failure_protection(self, error_handling_stack):
        """Test protection against cascading failures."""
        cb_manager = error_handling_stack['circuit_breaker_manager']
        
        # Multiple services with different failure patterns
        services = {
            "service_a": {"failure_rate": 0.8, "calls": 0},
            "service_b": {"failure_rate": 0.3, "calls": 0},
            "service_c": {"failure_rate": 0.9, "calls": 0}
        }
        
        async def mock_service(service_name: str):
            service = services[service_name]
            service["calls"] += 1
            
            if service["calls"] / 10 < service["failure_rate"]:
                raise ExternalServiceError(code="ERROR", message=f"{service_name} failed")
            return f"{service_name} success"
        
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=0.1)
        
        # Make calls to all services
        results = {"successful_calls": 0, "failed_calls": 0, "circuit_breaker_rejections": 0}
        
        for _ in range(20):  # Multiple rounds of calls
            for service_name in services:
                try:
                    result = await cb_manager.call_with_circuit_breaker(
                        service_name,
                        mock_service,
                        service_name,
                        config=config
                    )
                    results["successful_calls"] += 1
                except CircuitBreakerOpenError:
                    results["circuit_breaker_rejections"] += 1
                except ExternalServiceError:
                    results["failed_calls"] += 1
        
        # Verify circuit breakers protected against cascading failures
        assert results["circuit_breaker_rejections"] > 0
        assert results["successful_calls"] > 0
        
        # High-failure services should have open circuit breakers
        cb_a = cb_manager.get_circuit_breaker("service_a")
        cb_c = cb_manager.get_circuit_breaker("service_c")
        
        # These should likely be open due to high failure rates
        assert cb_a.is_open or cb_c.is_open
    
    @pytest.mark.asyncio
    async def test_error_correlation_and_alerting(self, error_handling_stack):
        """Test error correlation and appropriate alerting."""
        alert_manager = error_handling_stack['alert_manager']
        
        # Mock alert handlers to track alerts
        alert_log = []
        
        async def mock_alert_handler(alert):
            alert_log.append(alert.to_dict())
            return True
        
        # Replace handlers with mock
        for channel in alert_manager.handlers:
            alert_manager.handlers[channel].send_alert = mock_alert_handler
        
        # Add rules for different alert types
        from src.core.error_handling.alert_manager import AlertRule, AlertChannel
        
        rules = [
            AlertRule(AlertType.EXTERNAL_SERVICE_UNAVAILABLE, AlertSeverity.HIGH, [AlertChannel.LOG_ONLY]),
            AlertRule(AlertType.CIRCUIT_BREAKER_OPENED, AlertSeverity.CRITICAL, [AlertChannel.LOG_ONLY]),
            AlertRule(AlertType.RATE_LIMIT_EXCEEDED, AlertSeverity.MEDIUM, [AlertChannel.LOG_ONLY])
        ]
        
        for rule in rules:
            alert_manager.add_alert_rule(rule)
        
        # Simulate various error scenarios
        error_scenarios = [
            (AlertType.EXTERNAL_SERVICE_UNAVAILABLE, AlertSeverity.HIGH, "Google News down"),
            (AlertType.CIRCUIT_BREAKER_OPENED, AlertSeverity.CRITICAL, "Circuit breaker opened"),
            (AlertType.RATE_LIMIT_EXCEEDED, AlertSeverity.MEDIUM, "Rate limit hit")
        ]
        
        for alert_type, severity, message in error_scenarios:
            await alert_manager.send_alert(
                alert_type=alert_type,
                severity=severity,
                message=message,
                details={"timestamp": datetime.now().isoformat()},
                service_name="test_service"
            )
        
        # Verify alerts were generated
        assert len(alert_log) == len(error_scenarios)
        
        # Verify alert content
        alert_types_sent = {alert["alert_type"] for alert in alert_log}
        expected_types = {"external_service_unavailable", "circuit_breaker_opened", "rate_limit_exceeded"}
        assert alert_types_sent == expected_types
        
        # Verify severity mapping
        severity_map = {alert["alert_type"]: alert["severity"] for alert in alert_log}
        assert severity_map["circuit_breaker_opened"] == "critical"
        assert severity_map["external_service_unavailable"] == "high"
        assert severity_map["rate_limit_exceeded"] == "medium"
    
    @pytest.mark.asyncio
    async def test_performance_under_load(self, error_handling_stack):
        """Test error handling performance under load."""
        cb_manager = error_handling_stack['circuit_breaker_manager']
        retry_handler = error_handling_stack['retry_handler']
        
        # Simulate high-load scenario
        async def load_test_service(request_id: int):
            # Simulate 20% failure rate
            if request_id % 5 == 0:
                raise ExternalServiceError(code="LOAD_ERROR", message="Service overloaded")
            return f"Request {request_id} processed"
        
        config = CircuitBreakerConfig(failure_threshold=5, recovery_timeout=0.1)
        
        # Make concurrent requests
        start_time = time.time()
        
        async def protected_request(request_id):
            try:
                return await cb_manager.call_with_circuit_breaker(
                    "load_test_service",
                    load_test_service,
                    request_id,
                    config=config
                )
            except (ExternalServiceError, CircuitBreakerOpenError):
                return None
        
        # Run 100 concurrent requests
        tasks = [protected_request(i) for i in range(100)]
        results = await asyncio.gather(*tasks)
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Analyze results
        successful_requests = [r for r in results if r is not None]
        failed_requests = [r for r in results if r is None]
        
        # Verify performance characteristics
        assert len(successful_requests) > 0  # Some requests should succeed
        assert len(failed_requests) > 0  # Some should fail (due to circuit breaker)
        assert execution_time < 10.0  # Should complete within reasonable time
        
        # Circuit breaker should have activated
        cb = cb_manager.get_circuit_breaker("load_test_service")
        assert cb.metrics.total_calls > 0
        assert cb.metrics.total_failures > 0