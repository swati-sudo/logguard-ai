"""Pydantic models for incident data structures."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from enum import Enum


class IncidentSeverity(str, Enum):
    """Incident severity levels."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentStatus(str, Enum):
    """Incident lifecycle status."""
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class EscalationChannel(str, Enum):
    """Incident escalation channels."""
    SLACK = "slack"
    PAGERDUTY = "pagerduty"
    EMAIL = "email"
    SMS = "sms"


@dataclass
class AlertCorrelation:
    """Represents correlation between alerts for incident."""
    alert_id: str
    severity: str
    timestamp: datetime
    message: str
    service: str
    category: str  # "pii", "error", "timeout", "resource"


@dataclass
class Incident:
    """Core incident data structure."""
    id: str
    created_at: datetime
    updated_at: datetime
    severity: IncidentSeverity
    status: IncidentStatus
    title: str
    description: str
    
    # Services involved
    affected_services: list[str] = field(default_factory=list)
    
    # Related alerts
    alert_ids: list[str] = field(default_factory=list)
    alert_count: int = 0
    
    # PII involvement
    pii_involved: bool = False
    pii_category: Optional[str] = None
    
    # Escalation
    escalation_channel: Optional[EscalationChannel] = None
    escalated_to: list[str] = field(default_factory=list)
    escalated_at: Optional[datetime] = None
    
    # Root cause
    root_cause: Optional[str] = None
    root_logs: list[str] = field(default_factory=list)
    
    # Timeline events
    events: list[dict] = field(default_factory=list)
    
    # Resolution
    resolution_notes: Optional[str] = None
    resolved_at: Optional[datetime] = None
    
    # Metadata
    tags: list[str] = field(default_factory=list)
    custom_fields: dict = field(default_factory=dict)


@dataclass
class IncidentDetectionRule:
    """Rule for detecting incidents."""
    name: str
    description: str
    condition: str  # e.g., "error_rate > 50 and duration > 60"
    severity: IncidentSeverity
    affected_services: list[str]
    enabled: bool = True
    auto_escalate: bool = False
    escalation_channel: Optional[EscalationChannel] = None


@dataclass
class IncidentMetrics:
    """Metrics for incident analysis."""
    incident_id: str
    error_rate: float  # 0-1
    error_count: int
    affected_transactions: int = 0
    affected_customers: int = 0
    duration_seconds: int = 0
    p99_latency_ms: float = 0
    p95_latency_ms: float = 0
    cpu_utilization_percent: float = 0
    memory_utilization_percent: float = 0
    database_connection_pool_percent: float = 0


@dataclass
class IncidentTimeline:
    """Timeline event for incident."""
    timestamp: datetime
    event_type: str  # "CREATED", "ACKNOWLEDGED", "ALERT_ADDED", "ESCALATED", "RESOLVED"
    description: str
    actor: Optional[str] = None  # User or system component
    metadata: dict = field(default_factory=dict)


@dataclass
class IncidentResponse:
    """Incident response/remediation."""
    incident_id: str
    action_type: str  # "RATE_LIMIT", "CIRCUIT_BREAK", "ROLLBACK", "SCALE"
    service: str
    applied_at: Optional[datetime] = None
    status: str = "PENDING"  # PENDING, APPLIED, FAILED, ROLLED_BACK
    config_change: dict = field(default_factory=dict)
    reason: str = ""
