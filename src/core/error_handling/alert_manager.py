"""Alert system for critical failures and monitoring."""

import asyncio
import time
import json
import aiohttp
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Callable
from dataclasses import dataclass, field
import logging
from abc import ABC, abstractmethod

from src.shared.exceptions import ErrorCode

logger = logging.getLogger(__name__)


class AlertType(Enum):
    """Types of alerts that can be sent."""
    ERROR_THRESHOLD = "error_threshold"
    CIRCUIT_BREAKER_OPENED = "circuit_breaker_opened"
    CIRCUIT_BREAKER_CLOSED = "circuit_breaker_closed"
    SERVICE_DEGRADED = "service_degraded"
    SERVICE_RECOVERED = "service_recovered"
    TASK_FAILURE = "task_failure"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    DATABASE_CONNECTION_FAILED = "database_connection_failed"
    EXTERNAL_SERVICE_UNAVAILABLE = "external_service_unavailable"


class AlertSeverity(Enum):
    """Alert severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertChannel(Enum):
    """Available alert channels."""
    EMAIL = "email"
    WEBHOOK = "webhook"
    LOG_ONLY = "log_only"


@dataclass
class AlertRule:
    """Configuration for when to trigger alerts."""
    alert_type: AlertType
    severity: AlertSeverity
    channels: List[AlertChannel]
    error_codes: Optional[Set[ErrorCode]] = None
    circuit_breaker_states: Optional[Set[str]] = None
    threshold_count: Optional[int] = None
    threshold_window: Optional[int] = None  # seconds
    cooldown_period: int = 3600  # 1 hour default
    enabled: bool = True


@dataclass
class AlertConfig:
    """Configuration for alert system."""
    max_alerts_per_hour: int = 10
    default_cooldown_period: int = 3600
    
    # Email configuration
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_use_tls: bool = True
    from_email: Optional[str] = None
    to_emails: List[str] = field(default_factory=list)
    
    # Webhook configuration
    webhook_urls: List[str] = field(default_factory=list)
    webhook_timeout: int = 30


@dataclass
class Alert:
    """Represents an alert to be sent."""
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    details: Dict[str, Any]
    correlation_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    service_name: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary for serialization."""
        return {
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "details": self.details,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp,
            "service_name": self.service_name,
            "readable_time": time.ctime(self.timestamp)
        }


class AlertHandler(ABC):
    """Abstract base class for alert handlers."""
    
    @abstractmethod
    async def send_alert(self, alert: Alert) -> bool:
        """Send an alert through this handler.
        
        Returns:
            True if alert was sent successfully, False otherwise
        """
        pass


class LogAlertHandler(AlertHandler):
    """Handler that logs alerts."""
    
    async def send_alert(self, alert: Alert) -> bool:
        """Log the alert."""
        log_level = {
            AlertSeverity.LOW: logging.INFO,
            AlertSeverity.MEDIUM: logging.WARNING,
            AlertSeverity.HIGH: logging.ERROR,
            AlertSeverity.CRITICAL: logging.CRITICAL
        }.get(alert.severity, logging.WARNING)
        
        logger.log(
            log_level,
            f"ALERT [{alert.severity.value.upper()}] {alert.alert_type.value}: {alert.message}",
            extra={
                "alert_type": alert.alert_type.value,
                "severity": alert.severity.value,
                "correlation_id": alert.correlation_id,
                "service_name": alert.service_name,
                "alert_details": alert.details
            }
        )
        return True


class EmailAlertHandler(AlertHandler):
    """Handler that sends alerts via email."""
    
    def __init__(self, config: AlertConfig):
        self.config = config
    
    async def send_alert(self, alert: Alert) -> bool:
        """Send alert via email."""
        if not all([
            self.config.smtp_host,
            self.config.smtp_username,
            self.config.smtp_password,
            self.config.from_email,
            self.config.to_emails
        ]):
            logger.warning("Email alert handler not configured properly")
            return False
        
        try:
            # Create email message
            msg = MIMEMultipart()
            msg['From'] = self.config.from_email
            msg['To'] = ', '.join(self.config.to_emails)
            msg['Subject'] = f"[{alert.severity.value.upper()}] {alert.alert_type.value} - {alert.service_name or 'Google News Scraper'}"
            
            # Create email body
            body = f"""
Alert Details:
- Type: {alert.alert_type.value}
- Severity: {alert.severity.value}
- Service: {alert.service_name or 'Unknown'}
- Time: {time.ctime(alert.timestamp)}
- Correlation ID: {alert.correlation_id or 'N/A'}

Message:
{alert.message}

Details:
{json.dumps(alert.details, indent=2)}
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            server = smtplib.SMTP(self.config.smtp_host, self.config.smtp_port)
            if self.config.smtp_use_tls:
                server.starttls()
            server.login(self.config.smtp_username, self.config.smtp_password)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email alert sent for {alert.alert_type.value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False


class WebhookAlertHandler(AlertHandler):
    """Handler that sends alerts to webhooks."""
    
    def __init__(self, config: AlertConfig):
        self.config = config
    
    async def send_alert(self, alert: Alert) -> bool:
        """Send alert to configured webhooks."""
        if not self.config.webhook_urls:
            logger.warning("No webhook URLs configured")
            return False
        
        success_count = 0
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.config.webhook_timeout)) as session:
            for webhook_url in self.config.webhook_urls:
                try:
                    payload = {
                        "text": f"[{alert.severity.value.upper()}] {alert.message}",
                        "alert": alert.to_dict()
                    }
                    
                    async with session.post(webhook_url, json=payload) as response:
                        if response.status < 400:
                            success_count += 1
                            logger.info(f"Webhook alert sent to {webhook_url}")
                        else:
                            logger.error(f"Webhook alert failed for {webhook_url}: HTTP {response.status}")
                
                except Exception as e:
                    logger.error(f"Failed to send webhook alert to {webhook_url}: {e}")
        
        return success_count > 0


class AlertManager:
    """Manages alert rules, rate limiting, and delivery."""
    
    def __init__(self, config: Optional[AlertConfig] = None):
        self.config = config or AlertConfig()
        self.rules: Dict[AlertType, AlertRule] = {}
        self.handlers: Dict[AlertChannel, AlertHandler] = {}
        self.alert_history: List[Dict[str, Any]] = []
        self.rate_limit_counters: Dict[str, List[float]] = {}  # key -> list of timestamps
        
        # Initialize default handlers
        self._setup_default_handlers()
    
    def _setup_default_handlers(self):
        """Set up default alert handlers."""
        self.handlers[AlertChannel.LOG_ONLY] = LogAlertHandler()
        
        if self._is_email_configured():
            self.handlers[AlertChannel.EMAIL] = EmailAlertHandler(self.config)
        
        if self.config.webhook_urls:
            self.handlers[AlertChannel.WEBHOOK] = WebhookAlertHandler(self.config)
    
    def _is_email_configured(self) -> bool:
        """Check if email is properly configured."""
        return all([
            self.config.smtp_host,
            self.config.smtp_username,
            self.config.smtp_password,
            self.config.from_email,
            self.config.to_emails
        ])
    
    def add_alert_rule(self, rule: AlertRule):
        """Add an alert rule."""
        self.rules[rule.alert_type] = rule
        logger.info(f"Added alert rule for {rule.alert_type.value}")
    
    def remove_alert_rule(self, alert_type: AlertType):
        """Remove an alert rule."""
        if alert_type in self.rules:
            del self.rules[alert_type]
            logger.info(f"Removed alert rule for {alert_type.value}")
    
    def _should_send_alert(self, alert: Alert) -> bool:
        """Check if alert should be sent based on rules and rate limiting."""
        # Check if rule exists and is enabled
        rule = self.rules.get(alert.alert_type)
        if not rule or not rule.enabled:
            return False
        
        # Check rate limiting
        current_time = time.time()
        rate_limit_key = f"{alert.alert_type.value}:{alert.service_name or 'global'}"
        
        # Clean old timestamps
        hour_ago = current_time - 3600
        if rate_limit_key in self.rate_limit_counters:
            self.rate_limit_counters[rate_limit_key] = [
                ts for ts in self.rate_limit_counters[rate_limit_key] 
                if ts > hour_ago
            ]
        else:
            self.rate_limit_counters[rate_limit_key] = []
        
        # Check if we've hit the rate limit
        if len(self.rate_limit_counters[rate_limit_key]) >= self.config.max_alerts_per_hour:
            logger.warning(f"Rate limit exceeded for alert {alert.alert_type.value}")
            return False
        
        # Check cooldown period
        cooldown_key = f"{alert.alert_type.value}:{alert.service_name or 'global'}:cooldown"
        last_alert_time = None
        
        for history_entry in reversed(self.alert_history):
            if (history_entry.get('alert_type') == alert.alert_type.value and
                history_entry.get('service_name') == alert.service_name):
                last_alert_time = history_entry.get('timestamp')
                break
        
        if last_alert_time and (current_time - last_alert_time) < rule.cooldown_period:
            logger.debug(f"Alert {alert.alert_type.value} still in cooldown period")
            return False
        
        return True
    
    async def send_alert(
        self,
        alert_type: AlertType,
        severity: AlertSeverity,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        service_name: Optional[str] = None
    ) -> bool:
        """Send an alert if it passes all checks.
        
        Args:
            alert_type: Type of alert
            severity: Severity level
            message: Alert message
            details: Additional details dictionary
            correlation_id: Correlation ID for tracking
            service_name: Name of the service triggering the alert
            
        Returns:
            True if alert was sent successfully
        """
        alert = Alert(
            alert_type=alert_type,
            severity=severity,
            message=message,
            details=details or {},
            correlation_id=correlation_id,
            service_name=service_name
        )
        
        # Check if we should send this alert
        if not self._should_send_alert(alert):
            return False
        
        # Get the rule for channel configuration
        rule = self.rules.get(alert_type)
        if not rule:
            logger.warning(f"No rule found for alert type {alert_type.value}")
            return False
        
        # Send to all configured channels
        success_count = 0
        for channel in rule.channels:
            handler = self.handlers.get(channel)
            if handler:
                try:
                    if await handler.send_alert(alert):
                        success_count += 1
                except Exception as e:
                    logger.error(f"Failed to send alert via {channel.value}: {e}")
            else:
                logger.warning(f"No handler configured for channel {channel.value}")
        
        # Record in history and rate limiting if at least one channel succeeded
        if success_count > 0:
            current_time = time.time()
            
            # Add to history
            self.alert_history.append(alert.to_dict())
            
            # Keep history limited
            if len(self.alert_history) > 1000:
                self.alert_history = self.alert_history[-500:]
            
            # Update rate limiting counter
            rate_limit_key = f"{alert.alert_type.value}:{alert.service_name or 'global'}"
            if rate_limit_key not in self.rate_limit_counters:
                self.rate_limit_counters[rate_limit_key] = []
            self.rate_limit_counters[rate_limit_key].append(current_time)
            
            logger.info(
                f"Alert sent successfully: {alert_type.value}",
                extra={
                    "alert_type": alert_type.value,
                    "severity": severity.value,
                    "correlation_id": correlation_id,
                    "service_name": service_name,
                    "channels_succeeded": success_count
                }
            )
            return True
        
        logger.error(f"Failed to send alert {alert_type.value} to any channel")
        return False
    
    def get_alert_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent alert history."""
        return self.alert_history[-limit:]
    
    def get_rate_limit_status(self) -> Dict[str, Dict[str, Any]]:
        """Get current rate limiting status."""
        current_time = time.time()
        hour_ago = current_time - 3600
        
        status = {}
        for key, timestamps in self.rate_limit_counters.items():
            recent_alerts = [ts for ts in timestamps if ts > hour_ago]
            status[key] = {
                "alerts_in_last_hour": len(recent_alerts),
                "rate_limit": self.config.max_alerts_per_hour,
                "remaining": max(0, self.config.max_alerts_per_hour - len(recent_alerts)),
                "next_reset_time": max(recent_alerts) + 3600 if recent_alerts else None
            }
        
        return status


# Default alert rules
DEFAULT_ALERT_RULES = [
    AlertRule(
        alert_type=AlertType.CIRCUIT_BREAKER_OPENED,
        severity=AlertSeverity.HIGH,
        channels=[AlertChannel.LOG_ONLY, AlertChannel.EMAIL],
        cooldown_period=1800  # 30 minutes
    ),
    AlertRule(
        alert_type=AlertType.CIRCUIT_BREAKER_CLOSED,
        severity=AlertSeverity.MEDIUM,
        channels=[AlertChannel.LOG_ONLY],
        cooldown_period=300  # 5 minutes
    ),
    AlertRule(
        alert_type=AlertType.TASK_FAILURE,
        severity=AlertSeverity.MEDIUM,
        channels=[AlertChannel.LOG_ONLY, AlertChannel.EMAIL],
        cooldown_period=3600  # 1 hour
    ),
    AlertRule(
        alert_type=AlertType.RATE_LIMIT_EXCEEDED,
        severity=AlertSeverity.MEDIUM,
        channels=[AlertChannel.LOG_ONLY],
        cooldown_period=1800  # 30 minutes
    ),
    AlertRule(
        alert_type=AlertType.DATABASE_CONNECTION_FAILED,
        severity=AlertSeverity.CRITICAL,
        channels=[AlertChannel.LOG_ONLY, AlertChannel.EMAIL, AlertChannel.WEBHOOK],
        cooldown_period=600  # 10 minutes
    ),
    AlertRule(
        alert_type=AlertType.EXTERNAL_SERVICE_UNAVAILABLE,
        severity=AlertSeverity.HIGH,
        channels=[AlertChannel.LOG_ONLY, AlertChannel.EMAIL],
        cooldown_period=1800  # 30 minutes
    )
]


def setup_default_alert_rules(alert_manager: AlertManager):
    """Set up default alert rules."""
    for rule in DEFAULT_ALERT_RULES:
        alert_manager.add_alert_rule(rule)


# Global alert manager instance
_alert_manager: Optional[AlertManager] = None


def get_alert_manager(config: Optional[AlertConfig] = None) -> AlertManager:
    """Get the global alert manager instance."""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager(config)
        setup_default_alert_rules(_alert_manager)
    return _alert_manager