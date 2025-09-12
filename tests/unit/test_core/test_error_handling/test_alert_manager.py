"""Tests for alert manager and notification system."""

import pytest
import time
import json
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from typing import Dict, Any

from src.core.error_handling.alert_manager import (
    AlertType,
    AlertSeverity,
    AlertChannel,
    AlertRule,
    AlertConfig,
    Alert,
    AlertHandler,
    LogAlertHandler,
    EmailAlertHandler,
    WebhookAlertHandler,
    AlertManager,
    DEFAULT_ALERT_RULES,
    setup_default_alert_rules,
    get_alert_manager
)


class TestAlertEnums:
    """Tests for alert enumeration classes."""
    
    def test_alert_type_values(self):
        """Test AlertType enum values."""
        assert AlertType.ERROR_THRESHOLD.value == "error_threshold"
        assert AlertType.CIRCUIT_BREAKER_OPENED.value == "circuit_breaker_opened"
        assert AlertType.TASK_FAILURE.value == "task_failure"
        assert AlertType.RATE_LIMIT_EXCEEDED.value == "rate_limit_exceeded"
        assert AlertType.DATABASE_CONNECTION_FAILED.value == "database_connection_failed"
    
    def test_alert_severity_values(self):
        """Test AlertSeverity enum values."""
        assert AlertSeverity.LOW.value == "low"
        assert AlertSeverity.MEDIUM.value == "medium"
        assert AlertSeverity.HIGH.value == "high"
        assert AlertSeverity.CRITICAL.value == "critical"
    
    def test_alert_channel_values(self):
        """Test AlertChannel enum values."""
        assert AlertChannel.EMAIL.value == "email"
        assert AlertChannel.WEBHOOK.value == "webhook"
        assert AlertChannel.LOG_ONLY.value == "log_only"


class TestAlertRule:
    """Tests for AlertRule dataclass."""
    
    def test_alert_rule_creation(self):
        """Test AlertRule creation with all parameters."""
        rule = AlertRule(
            alert_type=AlertType.TASK_FAILURE,
            severity=AlertSeverity.HIGH,
            channels=[AlertChannel.EMAIL, AlertChannel.LOG_ONLY],
            error_codes={"EXTERNAL_SERVICE_ERROR"},
            circuit_breaker_states={"open"},
            threshold_count=5,
            threshold_window=3600,
            cooldown_period=1800,
            enabled=True
        )
        
        assert rule.alert_type == AlertType.TASK_FAILURE
        assert rule.severity == AlertSeverity.HIGH
        assert AlertChannel.EMAIL in rule.channels
        assert AlertChannel.LOG_ONLY in rule.channels
        assert "EXTERNAL_SERVICE_ERROR" in rule.error_codes
        assert "open" in rule.circuit_breaker_states
        assert rule.threshold_count == 5
        assert rule.threshold_window == 3600
        assert rule.cooldown_period == 1800
        assert rule.enabled is True
    
    def test_alert_rule_default_values(self):
        """Test AlertRule with default values."""
        rule = AlertRule(
            alert_type=AlertType.CIRCUIT_BREAKER_OPENED,
            severity=AlertSeverity.MEDIUM,
            channels=[AlertChannel.LOG_ONLY]
        )
        
        assert rule.error_codes is None
        assert rule.circuit_breaker_states is None
        assert rule.threshold_count is None
        assert rule.threshold_window is None
        assert rule.cooldown_period == 3600  # Default 1 hour
        assert rule.enabled is True


class TestAlertConfig:
    """Tests for AlertConfig dataclass."""
    
    def test_alert_config_defaults(self):
        """Test AlertConfig with default values."""
        config = AlertConfig()
        
        assert config.max_alerts_per_hour == 10
        assert config.default_cooldown_period == 3600
        assert config.smtp_host is None
        assert config.smtp_port == 587
        assert config.smtp_use_tls is True
        assert config.to_emails == []
        assert config.webhook_urls == []
        assert config.webhook_timeout == 30
    
    def test_alert_config_custom_values(self):
        """Test AlertConfig with custom values."""
        config = AlertConfig(
            max_alerts_per_hour=20,
            smtp_host="smtp.example.com",
            smtp_username="user@example.com",
            smtp_password="password",
            from_email="alerts@example.com",
            to_emails=["admin@example.com"],
            webhook_urls=["https://webhook.example.com"],
            webhook_timeout=60
        )
        
        assert config.max_alerts_per_hour == 20
        assert config.smtp_host == "smtp.example.com"
        assert config.smtp_username == "user@example.com"
        assert config.from_email == "alerts@example.com"
        assert config.to_emails == ["admin@example.com"]
        assert config.webhook_urls == ["https://webhook.example.com"]
        assert config.webhook_timeout == 60


class TestAlert:
    """Tests for Alert dataclass."""
    
    def test_alert_creation(self):
        """Test Alert creation with all parameters."""
        details = {"error_count": 5, "service": "crawler"}
        
        alert = Alert(
            alert_type=AlertType.TASK_FAILURE,
            severity=AlertSeverity.HIGH,
            message="Task failed repeatedly",
            details=details,
            correlation_id="test-123",
            service_name="crawler_service"
        )
        
        assert alert.alert_type == AlertType.TASK_FAILURE
        assert alert.severity == AlertSeverity.HIGH
        assert alert.message == "Task failed repeatedly"
        assert alert.details == details
        assert alert.correlation_id == "test-123"
        assert alert.service_name == "crawler_service"
        assert isinstance(alert.timestamp, float)
    
    def test_alert_to_dict(self):
        """Test Alert serialization to dictionary."""
        alert = Alert(
            alert_type=AlertType.CIRCUIT_BREAKER_OPENED,
            severity=AlertSeverity.CRITICAL,
            message="Circuit breaker opened",
            details={"service": "google_news"},
            correlation_id="cb-456",
            service_name="news_service"
        )
        
        result = alert.to_dict()
        
        expected_keys = {
            "alert_type", "severity", "message", "details",
            "correlation_id", "timestamp", "service_name", "readable_time"
        }
        assert set(result.keys()) == expected_keys
        
        assert result["alert_type"] == "circuit_breaker_opened"
        assert result["severity"] == "critical"
        assert result["message"] == "Circuit breaker opened"
        assert result["details"] == {"service": "google_news"}
        assert result["correlation_id"] == "cb-456"
        assert result["service_name"] == "news_service"
        assert isinstance(result["timestamp"], float)
        assert isinstance(result["readable_time"], str)


class TestLogAlertHandler:
    """Tests for LogAlertHandler."""
    
    @pytest.fixture
    def log_handler(self):
        """Create log alert handler for testing."""
        return LogAlertHandler()
    
    @pytest.mark.asyncio
    async def test_log_alert_handler_different_severities(self, log_handler, caplog):
        """Test log handler with different severity levels."""
        alerts = [
            Alert(AlertType.TASK_FAILURE, AlertSeverity.LOW, "Low severity alert", {}),
            Alert(AlertType.TASK_FAILURE, AlertSeverity.MEDIUM, "Medium severity alert", {}),
            Alert(AlertType.TASK_FAILURE, AlertSeverity.HIGH, "High severity alert", {}),
            Alert(AlertType.TASK_FAILURE, AlertSeverity.CRITICAL, "Critical alert", {})
        ]
        
        for alert in alerts:
            result = await log_handler.send_alert(alert)
            assert result is True
        
        # Check that all alerts were logged
        assert len(caplog.records) == 4
        
        # Check severity levels in logs
        severity_levels = [record.levelname for record in caplog.records]
        assert "INFO" in severity_levels
        assert "WARNING" in severity_levels
        assert "ERROR" in severity_levels
        assert "CRITICAL" in severity_levels
    
    @pytest.mark.asyncio
    async def test_log_alert_handler_with_details(self, log_handler, caplog):
        """Test log handler includes alert details."""
        details = {"service": "crawler", "error_count": 3}
        alert = Alert(
            AlertType.SERVICE_DEGRADED,
            AlertSeverity.HIGH,
            "Service degraded",
            details,
            correlation_id="test-789"
        )
        
        result = await log_handler.send_alert(alert)
        
        assert result is True
        assert len(caplog.records) == 1
        
        log_record = caplog.records[0]
        assert "SERVICE_DEGRADED" in log_record.getMessage()
        assert "Service degraded" in log_record.getMessage()
        assert log_record.correlation_id == "test-789"
        assert log_record.alert_details == details


class TestEmailAlertHandler:
    """Tests for EmailAlertHandler."""
    
    @pytest.fixture
    def email_config(self):
        """Create email configuration for testing."""
        return AlertConfig(
            smtp_host="smtp.test.com",
            smtp_port=587,
            smtp_username="alerts@test.com",
            smtp_password="password123",
            smtp_use_tls=True,
            from_email="alerts@test.com",
            to_emails=["admin@test.com", "ops@test.com"]
        )
    
    @pytest.fixture
    def email_handler(self, email_config):
        """Create email alert handler for testing."""
        return EmailAlertHandler(email_config)
    
    @pytest.mark.asyncio
    async def test_email_handler_missing_config(self):
        """Test email handler with missing configuration."""
        incomplete_config = AlertConfig()  # No email settings
        handler = EmailAlertHandler(incomplete_config)
        
        alert = Alert(AlertType.TASK_FAILURE, AlertSeverity.HIGH, "Test alert", {})
        result = await handler.send_alert(alert)
        
        assert result is False
    
    @pytest.mark.asyncio
    @patch('smtplib.SMTP')
    async def test_email_handler_successful_send(self, mock_smtp_class, email_handler):
        """Test successful email sending."""
        # Mock SMTP server
        mock_server = Mock()
        mock_smtp_class.return_value = mock_server
        
        alert = Alert(
            AlertType.DATABASE_CONNECTION_FAILED,
            AlertSeverity.CRITICAL,
            "Database connection failed",
            {"host": "db.test.com"},
            correlation_id="db-error-123",
            service_name="database"
        )
        
        result = await email_handler.send_alert(alert)
        
        assert result is True
        
        # Verify SMTP interactions
        mock_smtp_class.assert_called_once_with("smtp.test.com", 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("alerts@test.com", "password123")
        mock_server.send_message.assert_called_once()
        mock_server.quit.assert_called_once()
        
        # Check email message content
        call_args = mock_server.send_message.call_args[0][0]
        assert call_args['Subject'].startswith("[CRITICAL] database_connection_failed")
        assert "Database connection failed" in str(call_args)
        assert "db.test.com" in str(call_args)
        assert "db-error-123" in str(call_args)
    
    @pytest.mark.asyncio
    @patch('smtplib.SMTP')
    async def test_email_handler_smtp_error(self, mock_smtp_class, email_handler):
        """Test email handler with SMTP error."""
        mock_smtp_class.side_effect = Exception("SMTP connection failed")
        
        alert = Alert(AlertType.TASK_FAILURE, AlertSeverity.HIGH, "Test alert", {})
        result = await email_handler.send_alert(alert)
        
        assert result is False


class TestWebhookAlertHandler:
    """Tests for WebhookAlertHandler."""
    
    @pytest.fixture
    def webhook_config(self):
        """Create webhook configuration for testing."""
        return AlertConfig(
            webhook_urls=[
                "https://webhook1.test.com/alerts",
                "https://webhook2.test.com/notifications"
            ],
            webhook_timeout=30
        )
    
    @pytest.fixture
    def webhook_handler(self, webhook_config):
        """Create webhook alert handler for testing."""
        return WebhookAlertHandler(webhook_config)
    
    @pytest.mark.asyncio
    async def test_webhook_handler_no_urls(self):
        """Test webhook handler with no configured URLs."""
        empty_config = AlertConfig()
        handler = WebhookAlertHandler(empty_config)
        
        alert = Alert(AlertType.TASK_FAILURE, AlertSeverity.HIGH, "Test alert", {})
        result = await handler.send_alert(alert)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_webhook_handler_successful_send(self, webhook_handler):
        """Test successful webhook sending."""
        alert = Alert(
            AlertType.RATE_LIMIT_EXCEEDED,
            AlertSeverity.MEDIUM,
            "Rate limit exceeded",
            {"limit": 1000, "current": 1500},
            correlation_id="rate-limit-456"
        )
        
        # Mock aiohttp session and responses
        mock_response1 = AsyncMock()
        mock_response1.status = 200
        
        mock_response2 = AsyncMock()
        mock_response2.status = 201
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            mock_session.post.side_effect = [
                AsyncMock(__aenter__=AsyncMock(return_value=mock_response1)),
                AsyncMock(__aenter__=AsyncMock(return_value=mock_response2))
            ]
            
            result = await webhook_handler.send_alert(alert)
        
        assert result is True
        assert mock_session.post.call_count == 2
        
        # Verify webhook payloads
        call_args_list = mock_session.post.call_args_list
        
        for call_args in call_args_list:
            url = call_args[0][0]
            assert url in webhook_handler.config.webhook_urls
            
            payload = call_args[1]['json']
            assert payload['text'] == "[MEDIUM] Rate limit exceeded"
            assert payload['alert']['alert_type'] == "rate_limit_exceeded"
            assert payload['alert']['details']['limit'] == 1000
    
    @pytest.mark.asyncio
    async def test_webhook_handler_partial_failure(self, webhook_handler):
        """Test webhook handler with partial failures."""
        alert = Alert(AlertType.TASK_FAILURE, AlertSeverity.HIGH, "Test alert", {})
        
        # Mock one success, one failure
        mock_response1 = AsyncMock()
        mock_response1.status = 200
        
        mock_response2 = AsyncMock()
        mock_response2.status = 500
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            mock_session.post.side_effect = [
                AsyncMock(__aenter__=AsyncMock(return_value=mock_response1)),
                AsyncMock(__aenter__=AsyncMock(return_value=mock_response2))
            ]
            
            result = await webhook_handler.send_alert(alert)
        
        # Should return True if at least one webhook succeeded
        assert result is True
    
    @pytest.mark.asyncio
    async def test_webhook_handler_all_failures(self, webhook_handler):
        """Test webhook handler when all webhooks fail."""
        alert = Alert(AlertType.TASK_FAILURE, AlertSeverity.HIGH, "Test alert", {})
        
        with patch('aiohttp.ClientSession') as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            
            # Both webhooks fail
            mock_session.post.side_effect = Exception("Network error")
            
            result = await webhook_handler.send_alert(alert)
        
        assert result is False


class TestAlertManager:
    """Tests for AlertManager class."""
    
    @pytest.fixture
    def alert_manager(self):
        """Create alert manager for testing."""
        config = AlertConfig(max_alerts_per_hour=5)
        manager = AlertManager(config)
        
        # Add a test rule
        test_rule = AlertRule(
            alert_type=AlertType.TASK_FAILURE,
            severity=AlertSeverity.HIGH,
            channels=[AlertChannel.LOG_ONLY],
            cooldown_period=10  # Short cooldown for testing
        )
        manager.add_alert_rule(test_rule)
        
        return manager
    
    def test_alert_manager_initialization(self):
        """Test alert manager initialization."""
        config = AlertConfig(max_alerts_per_hour=15)
        manager = AlertManager(config)
        
        assert manager.config.max_alerts_per_hour == 15
        assert AlertChannel.LOG_ONLY in manager.handlers
        assert len(manager.rules) == 0
        assert len(manager.alert_history) == 0
    
    def test_alert_manager_add_remove_rules(self, alert_manager):
        """Test adding and removing alert rules."""
        # Rule should already be added in fixture
        assert AlertType.TASK_FAILURE in alert_manager.rules
        
        # Add another rule
        new_rule = AlertRule(
            alert_type=AlertType.CIRCUIT_BREAKER_OPENED,
            severity=AlertSeverity.CRITICAL,
            channels=[AlertChannel.LOG_ONLY]
        )
        alert_manager.add_alert_rule(new_rule)
        
        assert AlertType.CIRCUIT_BREAKER_OPENED in alert_manager.rules
        assert len(alert_manager.rules) == 2
        
        # Remove rule
        alert_manager.remove_alert_rule(AlertType.CIRCUIT_BREAKER_OPENED)
        assert AlertType.CIRCUIT_BREAKER_OPENED not in alert_manager.rules
        assert len(alert_manager.rules) == 1
    
    @pytest.mark.asyncio
    async def test_alert_manager_send_alert_success(self, alert_manager):
        """Test successful alert sending."""
        result = await alert_manager.send_alert(
            alert_type=AlertType.TASK_FAILURE,
            severity=AlertSeverity.HIGH,
            message="Task failed",
            details={"task_id": "123"},
            correlation_id="test-correlation",
            service_name="test_service"
        )
        
        assert result is True
        assert len(alert_manager.alert_history) == 1
        
        history_entry = alert_manager.alert_history[0]
        assert history_entry["alert_type"] == "task_failure"
        assert history_entry["message"] == "Task failed"
        assert history_entry["details"]["task_id"] == "123"
    
    @pytest.mark.asyncio
    async def test_alert_manager_no_matching_rule(self, alert_manager):
        """Test alert manager with no matching rule."""
        result = await alert_manager.send_alert(
            alert_type=AlertType.CIRCUIT_BREAKER_OPENED,  # No rule for this
            severity=AlertSeverity.HIGH,
            message="Circuit breaker opened"
        )
        
        assert result is False
        assert len(alert_manager.alert_history) == 0
    
    @pytest.mark.asyncio
    async def test_alert_manager_disabled_rule(self, alert_manager):
        """Test alert manager with disabled rule."""
        # Disable the rule
        alert_manager.rules[AlertType.TASK_FAILURE].enabled = False
        
        result = await alert_manager.send_alert(
            alert_type=AlertType.TASK_FAILURE,
            severity=AlertSeverity.HIGH,
            message="Task failed"
        )
        
        assert result is False
        assert len(alert_manager.alert_history) == 0
    
    @pytest.mark.asyncio
    async def test_alert_manager_rate_limiting(self, alert_manager):
        """Test alert manager rate limiting."""
        # Send alerts up to the limit
        for i in range(5):  # max_alerts_per_hour = 5
            result = await alert_manager.send_alert(
                alert_type=AlertType.TASK_FAILURE,
                severity=AlertSeverity.HIGH,
                message=f"Task failed {i}",
                service_name="test_service"
            )
            assert result is True
        
        # Next alert should be rate limited
        result = await alert_manager.send_alert(
            alert_type=AlertType.TASK_FAILURE,
            severity=AlertSeverity.HIGH,
            message="Task failed - should be rate limited",
            service_name="test_service"
        )
        
        assert result is False
        assert len(alert_manager.alert_history) == 5
    
    @pytest.mark.asyncio
    async def test_alert_manager_cooldown_period(self, alert_manager):
        """Test alert manager cooldown period."""
        # Send first alert
        result1 = await alert_manager.send_alert(
            alert_type=AlertType.TASK_FAILURE,
            severity=AlertSeverity.HIGH,
            message="First alert",
            service_name="test_service"
        )
        assert result1 is True
        
        # Send second alert immediately - should be in cooldown
        result2 = await alert_manager.send_alert(
            alert_type=AlertType.TASK_FAILURE,
            severity=AlertSeverity.HIGH,
            message="Second alert",
            service_name="test_service"
        )
        assert result2 is False
        
        # Only first alert should be in history
        assert len(alert_manager.alert_history) == 1
    
    def test_alert_manager_get_alert_history(self, alert_manager):
        """Test getting alert history."""
        # Add some mock history
        alert_manager.alert_history = [
            {"alert_type": "task_failure", "timestamp": time.time()},
            {"alert_type": "rate_limit_exceeded", "timestamp": time.time()}
        ]
        
        # Test default limit
        history = alert_manager.get_alert_history()
        assert len(history) == 2
        
        # Test custom limit
        history_limited = alert_manager.get_alert_history(limit=1)
        assert len(history_limited) == 1
        assert history_limited[0]["alert_type"] == "rate_limit_exceeded"  # Most recent
    
    def test_alert_manager_rate_limit_status(self, alert_manager):
        """Test getting rate limit status."""
        # Add some mock rate limit data
        current_time = time.time()
        alert_manager.rate_limit_counters = {
            "task_failure:test_service": [current_time - 1800, current_time - 900, current_time],
            "circuit_breaker_opened:another_service": [current_time - 3000]
        }
        
        status = alert_manager.get_rate_limit_status()
        
        assert "task_failure:test_service" in status
        assert "circuit_breaker_opened:another_service" in status
        
        task_failure_status = status["task_failure:test_service"]
        assert task_failure_status["alerts_in_last_hour"] == 3
        assert task_failure_status["rate_limit"] == 5
        assert task_failure_status["remaining"] == 2
    
    def test_alert_manager_email_configuration_detection(self):
        """Test email configuration detection."""
        # Manager without email config
        manager1 = AlertManager(AlertConfig())
        assert AlertChannel.EMAIL not in manager1.handlers
        
        # Manager with complete email config
        email_config = AlertConfig(
            smtp_host="smtp.test.com",
            smtp_username="user@test.com",
            smtp_password="password",
            from_email="alerts@test.com",
            to_emails=["admin@test.com"]
        )
        manager2 = AlertManager(email_config)
        assert AlertChannel.EMAIL in manager2.handlers
    
    def test_alert_manager_webhook_configuration_detection(self):
        """Test webhook configuration detection."""
        # Manager without webhook config
        manager1 = AlertManager(AlertConfig())
        assert AlertChannel.WEBHOOK not in manager1.handlers
        
        # Manager with webhook config
        webhook_config = AlertConfig(
            webhook_urls=["https://webhook.test.com"]
        )
        manager2 = AlertManager(webhook_config)
        assert AlertChannel.WEBHOOK in manager2.handlers


class TestDefaultAlertRules:
    """Tests for default alert rules."""
    
    def test_default_alert_rules_exist(self):
        """Test that default alert rules are defined."""
        assert len(DEFAULT_ALERT_RULES) > 0
        
        # Check for expected rule types
        rule_types = {rule.alert_type for rule in DEFAULT_ALERT_RULES}
        expected_types = {
            AlertType.CIRCUIT_BREAKER_OPENED,
            AlertType.TASK_FAILURE,
            AlertType.DATABASE_CONNECTION_FAILED,
            AlertType.EXTERNAL_SERVICE_UNAVAILABLE
        }
        
        assert expected_types.issubset(rule_types)
    
    def test_setup_default_alert_rules(self):
        """Test setup_default_alert_rules function."""
        manager = AlertManager()
        assert len(manager.rules) == 0
        
        setup_default_alert_rules(manager)
        
        assert len(manager.rules) == len(DEFAULT_ALERT_RULES)
        
        # Verify specific rules
        assert AlertType.CIRCUIT_BREAKER_OPENED in manager.rules
        assert AlertType.DATABASE_CONNECTION_FAILED in manager.rules
        
        # Check critical alerts have appropriate channels
        db_rule = manager.rules[AlertType.DATABASE_CONNECTION_FAILED]
        assert db_rule.severity == AlertSeverity.CRITICAL
        assert AlertChannel.LOG_ONLY in db_rule.channels
    
    def test_default_rule_severities(self):
        """Test that default rules have appropriate severities."""
        severity_map = {rule.alert_type: rule.severity for rule in DEFAULT_ALERT_RULES}
        
        # Critical alerts
        assert severity_map[AlertType.DATABASE_CONNECTION_FAILED] == AlertSeverity.CRITICAL
        
        # High severity alerts
        assert severity_map[AlertType.CIRCUIT_BREAKER_OPENED] == AlertSeverity.HIGH
        assert severity_map[AlertType.EXTERNAL_SERVICE_UNAVAILABLE] == AlertSeverity.HIGH
        
        # Medium severity alerts
        assert severity_map[AlertType.TASK_FAILURE] == AlertSeverity.MEDIUM
        assert severity_map[AlertType.RATE_LIMIT_EXCEEDED] == AlertSeverity.MEDIUM


class TestGlobalAlertManager:
    """Tests for global alert manager functionality."""
    
    def test_get_alert_manager_singleton(self):
        """Test that get_alert_manager returns same instance."""
        manager1 = get_alert_manager()
        manager2 = get_alert_manager()
        
        assert manager1 is manager2
        assert isinstance(manager1, AlertManager)
    
    def test_get_alert_manager_with_custom_config(self):
        """Test get_alert_manager with custom configuration."""
        custom_config = AlertConfig(max_alerts_per_hour=20)
        
        # Clear any existing global instance
        import src.core.error_handling.alert_manager as am
        am._alert_manager = None
        
        manager = get_alert_manager(custom_config)
        
        assert manager.config.max_alerts_per_hour == 20
        assert len(manager.rules) > 0  # Should have default rules


class TestAlertIntegration:
    """Integration tests for alert system."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_alert_flow(self):
        """Test complete alert flow from creation to logging."""
        # Setup manager with email and webhook handlers
        config = AlertConfig(
            smtp_host="smtp.test.com",
            smtp_username="test@test.com",
            smtp_password="password",
            from_email="alerts@test.com",
            to_emails=["admin@test.com"],
            webhook_urls=["https://webhook.test.com"]
        )
        
        manager = AlertManager(config)
        
        # Add rule for multiple channels
        rule = AlertRule(
            alert_type=AlertType.EXTERNAL_SERVICE_UNAVAILABLE,
            severity=AlertSeverity.HIGH,
            channels=[AlertChannel.LOG_ONLY, AlertChannel.EMAIL, AlertChannel.WEBHOOK]
        )
        manager.add_alert_rule(rule)
        
        # Mock handlers to avoid actual email/webhook sends
        manager.handlers[AlertChannel.EMAIL] = AsyncMock(return_value=True)
        manager.handlers[AlertChannel.WEBHOOK] = AsyncMock(return_value=True)
        
        result = await manager.send_alert(
            alert_type=AlertType.EXTERNAL_SERVICE_UNAVAILABLE,
            severity=AlertSeverity.HIGH,
            message="Google News service is down",
            details={"service": "google_news", "error_code": "503"},
            correlation_id="service-down-123",
            service_name="google_news"
        )
        
        assert result is True
        
        # Verify all handlers were called
        manager.handlers[AlertChannel.EMAIL].send_alert.assert_called_once()
        manager.handlers[AlertChannel.WEBHOOK].send_alert.assert_called_once()
        
        # Verify history was updated
        assert len(manager.alert_history) == 1
        history_entry = manager.alert_history[0]
        assert history_entry["alert_type"] == "external_service_unavailable"
        assert history_entry["correlation_id"] == "service-down-123"
    
    @pytest.mark.asyncio
    async def test_alert_system_resilience(self):
        """Test alert system handles handler failures gracefully."""
        manager = AlertManager()
        
        # Add rule
        rule = AlertRule(
            alert_type=AlertType.TASK_FAILURE,
            severity=AlertSeverity.MEDIUM,
            channels=[AlertChannel.LOG_ONLY, AlertChannel.EMAIL]
        )
        manager.add_alert_rule(rule)
        
        # Mock email handler to fail
        failing_email_handler = AsyncMock(side_effect=Exception("Email server down"))
        manager.handlers[AlertChannel.EMAIL] = failing_email_handler
        
        # Should still succeed because log handler works
        result = await manager.send_alert(
            alert_type=AlertType.TASK_FAILURE,
            severity=AlertSeverity.MEDIUM,
            message="Task failed but email is down"
        )
        
        assert result is True  # Log handler succeeded
        assert len(manager.alert_history) == 1
    
    def test_alert_serialization_json_compatibility(self):
        """Test that alerts can be serialized to JSON."""
        alert = Alert(
            alert_type=AlertType.CIRCUIT_BREAKER_OPENED,
            severity=AlertSeverity.CRITICAL,
            message="Circuit breaker opened for service",
            details={
                "service": "google_news",
                "failure_count": 5,
                "timestamp": datetime.now().isoformat()
            },
            correlation_id="cb-789",
            service_name="news_crawler"
        )
        
        alert_dict = alert.to_dict()
        
        # Should be JSON serializable
        json_str = json.dumps(alert_dict)
        assert isinstance(json_str, str)
        
        # Should deserialize back correctly
        deserialized = json.loads(json_str)
        assert deserialized["alert_type"] == "circuit_breaker_opened"
        assert deserialized["details"]["service"] == "google_news"