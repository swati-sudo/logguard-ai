"""Incident Agent - detects, correlates, and escalates incidents."""

import os
import uuid
from datetime import datetime, timedelta
from typing import Optional, List
from dataclasses import asdict

from agents.base_agent import BaseAgent, AgentConfig
from agents.event_bus import Event, EventType, get_event_bus
from models import (
    Incident, IncidentSeverity, IncidentStatus, EscalationChannel,
    AlertCorrelation, IncidentDetectionRule, IncidentTimeline
)


class IncidentAgent(BaseAgent):
    """
    Detects, correlates, and escalates incidents from alerts and log patterns.
    
    Responsibilities:
    - Group related alerts into incidents
    - Detect critical patterns (error spikes, cascading failures)
    - Assign severity levels
    - Manage incident lifecycle (OPEN → RESOLVED)
    - Escalate to appropriate channels (PagerDuty, Slack, etc.)
    """
    
    # Detection thresholds
    ERROR_RATE_THRESHOLD = 0.50  # 50% error rate triggers incident
    ERROR_COUNT_THRESHOLD = 10  # At least 10 errors
    ALERT_CORRELATION_WINDOW = 60  # seconds
    ALERT_CORRELATION_COUNT = 3  # At least 3 alerts to correlate
    CASCADING_FAILURE_WINDOW = 60  # seconds
    SERVICE_CORRELATION_TIMEOUT = 300  # 5 minutes
    
    def __init__(self, config: Optional[AgentConfig] = None):
        """Initialize incident agent."""
        super().__init__(config)
        self.incidents: dict[str, Incident] = {}
        self.incident_queue: list[AlertCorrelation] = []
        self.event_bus = get_event_bus()
        self.detection_rules = self._load_detection_rules()
        
    def _load_detection_rules(self) -> list[IncidentDetectionRule]:
        """Load predefined incident detection rules."""
        return [
            IncidentDetectionRule(
                name="HIGH_ERROR_RATE",
                description="Error rate exceeds 50%",
                condition="error_rate > 0.5",
                severity=IncidentSeverity.CRITICAL,
                affected_services=["*"],
                auto_escalate=True,
                escalation_channel=EscalationChannel.PAGERDUTY
            ),
            IncidentDetectionRule(
                name="PII_BREACH",
                description="PII credentials detected in logs",
                condition="pii_involved == true",
                severity=IncidentSeverity.CRITICAL,
                affected_services=["*"],
                auto_escalate=True,
                escalation_channel=EscalationChannel.PAGERDUTY
            ),
            IncidentDetectionRule(
                name="CASCADING_FAILURE",
                description="Multiple services failing simultaneously",
                condition="service_count > 3 and error_rate > 0.2",
                severity=IncidentSeverity.HIGH,
                affected_services=["*"],
                auto_escalate=True,
                escalation_channel=EscalationChannel.SLACK
            ),
            IncidentDetectionRule(
                name="DATABASE_OVERLOAD",
                description="Database connection pool exhaustion",
                condition="db_pool_utilization > 90",
                severity=IncidentSeverity.HIGH,
                affected_services=["*"],
                auto_escalate=True,
                escalation_channel=EscalationChannel.SLACK
            ),
            IncidentDetectionRule(
                name="MEMORY_LEAK",
                description="Memory utilization spike",
                condition="memory_utilization > 85",
                severity=IncidentSeverity.MEDIUM,
                affected_services=["*"],
                auto_escalate=False,
                escalation_channel=EscalationChannel.SLACK
            ),
        ]
    
    def process(self, data: dict) -> dict:
        """
        Process alerts and detect incidents.
        
        Expected data structure:
        {
            "alerts": [
                {
                    "id": "alert-001",
                    "severity": "HIGH",
                    "timestamp": "2026-07-22T14:30:00Z",
                    "message": "PII detected: password",
                    "service": "auth-service",
                    "category": "pii"  # pii, error, timeout, resource
                }
            ],
            "metrics": {
                "error_rate": 0.55,
                "error_count": 45,
                "affected_services": ["auth-service", "payments-api"]
            }
        }
        """
        self.validate_input(data, ["alerts", "metrics"])
        
        alerts = data.get("alerts", [])
        metrics = data.get("metrics", {})
        
        # Add alerts to queue
        for alert in alerts:
            correlation = AlertCorrelation(
                alert_id=alert["id"],
                severity=alert.get("severity", "MEDIUM"),
                timestamp=datetime.fromisoformat(alert["timestamp"].replace("Z", "+00:00")),
                message=alert["message"],
                service=alert.get("service", "unknown"),
                category=alert.get("category", "error")
            )
            self.incident_queue.append(correlation)
        
        # Detect incidents
        detected_incidents = self._detect_incidents(metrics)
        
        # Correlate alerts
        correlated_incidents = self._correlate_alerts()
        
        # Merge and deduplicate
        all_incidents = detected_incidents + correlated_incidents
        merged_incidents = self._merge_incidents(all_incidents)
        
        # Update incident registry
        for incident in merged_incidents:
            self.incidents[incident.id] = incident
            
            # Publish event
            self.event_bus.publish(Event(
                event_type=EventType.INCIDENT_CREATED,
                source_agent=self.name,
                timestamp=datetime.utcnow(),
                data=asdict(incident),
                severity=incident.severity.value
            ))
            
            # Auto-escalate if needed
            if incident.escalation_channel:
                self._escalate_incident(incident)
        
        return {
            "incident_count": len(merged_incidents),
            "incidents": [asdict(i) for i in merged_incidents],
            "queue_size": len(self.incident_queue)
        }
    
    def _detect_incidents(self, metrics: dict) -> list[Incident]:
        """Detect incidents based on metrics."""
        incidents = []
        
        error_rate = metrics.get("error_rate", 0)
        error_count = metrics.get("error_count", 0)
        affected_services = metrics.get("affected_services", [])
        
        # Rule 1: High error rate
        if error_rate > self.ERROR_RATE_THRESHOLD and error_count >= self.ERROR_COUNT_THRESHOLD:
            incident = self._create_incident(
                title="High Error Rate Detected",
                description=f"Error rate {error_rate*100:.1f}% exceeds threshold ({self.ERROR_RATE_THRESHOLD*100}%)",
                severity=IncidentSeverity.CRITICAL,
                affected_services=affected_services,
                alert_ids=[],
                pii_involved=metrics.get("pii_involved", False)
            )
            incidents.append(incident)
        
        # Rule 2: PII involved
        if metrics.get("pii_involved"):
            incident = self._create_incident(
                title="PII/Credential Leak Detected",
                description=f"Sensitive credentials detected in {len(affected_services)} services",
                severity=IncidentSeverity.CRITICAL,
                affected_services=affected_services,
                alert_ids=[],
                pii_involved=True,
                pii_category=metrics.get("pii_category")
            )
            incidents.append(incident)
        
        # Rule 3: Cascading failure
        if len(affected_services) > 3 and error_rate > 0.2:
            incident = self._create_incident(
                title="Cascading Failure Detected",
                description=f"Multiple services failing: {', '.join(affected_services)}",
                severity=IncidentSeverity.HIGH,
                affected_services=affected_services,
                alert_ids=[]
            )
            incidents.append(incident)
        
        # Rule 4: Database overload
        if metrics.get("db_pool_utilization", 0) > 90:
            incident = self._create_incident(
                title="Database Connection Pool Exhaustion",
                description="Database connection pool utilization >90%",
                severity=IncidentSeverity.HIGH,
                affected_services=affected_services,
                alert_ids=[]
            )
            incidents.append(incident)
        
        return incidents
    
    def _correlate_alerts(self) -> list[Incident]:
        """Group related alerts into incidents."""
        incidents = []
        now = datetime.utcnow()
        
        # Remove old alerts from queue (older than correlation window)
        self.incident_queue = [
            a for a in self.incident_queue
            if (now - a.timestamp).total_seconds() < self.SERVICE_CORRELATION_TIMEOUT
        ]
        
        if len(self.incident_queue) < self.ALERT_CORRELATION_COUNT:
            return incidents
        
        # Group alerts by category and service
        alert_groups: dict[tuple, list[AlertCorrelation]] = {}
        for alert in self.incident_queue:
            key = (alert.category, alert.service)
            if key not in alert_groups:
                alert_groups[key] = []
            alert_groups[key].append(alert)
        
        # Create incidents from alert groups
        for (category, service), alerts in alert_groups.items():
            if len(alerts) >= self.ALERT_CORRELATION_COUNT:
                # Check if alerts are within correlation window
                time_span = (alerts[-1].timestamp - alerts[0].timestamp).total_seconds()
                if time_span < self.ALERT_CORRELATION_WINDOW:
                    incident = self._create_incident(
                        title=f"Alert Aggregation: {category.upper()} in {service}",
                        description=f"{len(alerts)} {category} alerts detected in {service}",
                        severity=self._infer_severity(alerts),
                        affected_services=[service],
                        alert_ids=[a.alert_id for a in alerts],
                        pii_involved=category == "pii"
                    )
                    incidents.append(incident)
                    
                    # Publish event
                    self.event_bus.publish(Event(
                        event_type=EventType.ALERT_AGGREGATED,
                        source_agent=self.name,
                        timestamp=datetime.utcnow(),
                        data={
                            "alert_count": len(alerts),
                            "category": category,
                            "service": service,
                            "time_span_seconds": time_span
                        }
                    ))
        
        return incidents
    
    def _create_incident(
        self,
        title: str,
        description: str,
        severity: IncidentSeverity,
        affected_services: list[str],
        alert_ids: list[str],
        pii_involved: bool = False,
        pii_category: Optional[str] = None
    ) -> Incident:
        """Create a new incident."""
        incident_id = f"incident-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8]}"
        now = datetime.utcnow()
        
        # Determine escalation
        escalation_channel = None
        if severity in [IncidentSeverity.CRITICAL, IncidentSeverity.HIGH]:
            escalation_channel = EscalationChannel.PAGERDUTY if severity == IncidentSeverity.CRITICAL else EscalationChannel.SLACK
        
        incident = Incident(
            id=incident_id,
            created_at=now,
            updated_at=now,
            severity=severity,
            status=IncidentStatus.OPEN,
            title=title,
            description=description,
            affected_services=affected_services,
            alert_ids=alert_ids,
            alert_count=len(alert_ids),
            pii_involved=pii_involved,
            pii_category=pii_category,
            escalation_channel=escalation_channel,
            events=[
                {
                    "timestamp": now.isoformat(),
                    "event_type": "CREATED",
                    "description": "Incident created by Incident Agent"
                }
            ]
        )
        
        return incident
    
    def _infer_severity(self, alerts: list[AlertCorrelation]) -> IncidentSeverity:
        """Infer incident severity from alerts."""
        severities = [a.severity for a in alerts]
        
        if "CRITICAL" in severities:
            return IncidentSeverity.CRITICAL
        elif "HIGH" in severities:
            return IncidentSeverity.HIGH
        elif "MEDIUM" in severities:
            return IncidentSeverity.MEDIUM
        else:
            return IncidentSeverity.LOW
    
    def _merge_incidents(self, incidents: list[Incident]) -> list[Incident]:
        """Deduplicate and merge related incidents."""
        if not incidents:
            return []
        
        # For now, return as-is (advanced deduplication can be added later)
        # In production: merge incidents with same affected services within time window
        return incidents
    
    def _escalate_incident(self, incident: Incident) -> None:
        """Escalate incident to appropriate channel."""
        if not incident.escalation_channel:
            return
        
        incident.escalated_at = datetime.utcnow()
        
        # In production, integrate with actual services
        channel_names = {
            EscalationChannel.PAGERDUTY: "@pagerduty-oncall",
            EscalationChannel.SLACK: "@incident-channel",
            EscalationChannel.EMAIL: "incident-alert@company.com",
            EscalationChannel.SMS: "emergency-team"
        }
        
        incident.escalated_to = [channel_names.get(incident.escalation_channel, "unknown")]
        
        # Publish escalation event
        self.event_bus.publish(Event(
            event_type=EventType.INCIDENT_ESCALATED,
            source_agent=self.name,
            timestamp=datetime.utcnow(),
            data={
                "incident_id": incident.id,
                "channel": incident.escalation_channel.value,
                "escalated_to": incident.escalated_to
            },
            severity=incident.severity.value
        ))
    
    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Get incident by ID."""
        return self.incidents.get(incident_id)
    
    def get_open_incidents(self) -> list[Incident]:
        """Get all open incidents."""
        return [i for i in self.incidents.values() if i.status == IncidentStatus.OPEN]
    
    def get_incidents_by_severity(self, severity: IncidentSeverity) -> list[Incident]:
        """Get incidents by severity level."""
        return [i for i in self.incidents.values() if i.severity == severity]
    
    def acknowledge_incident(self, incident_id: str, actor: str = "system") -> Optional[Incident]:
        """Acknowledge an incident."""
        incident = self.get_incident(incident_id)
        if incident:
            incident.status = IncidentStatus.ACKNOWLEDGED
            incident.updated_at = datetime.utcnow()
            incident.events.append({
                "timestamp": datetime.utcnow().isoformat(),
                "event_type": "ACKNOWLEDGED",
                "actor": actor,
                "description": f"Incident acknowledged by {actor}"
            })
            
            # Publish event
            self.event_bus.publish(Event(
                event_type=EventType.INCIDENT_UPDATED,
                source_agent=self.name,
                timestamp=datetime.utcnow(),
                data={"incident_id": incident_id, "status": "ACKNOWLEDGED"}
            ))
        
        return incident
    
    def resolve_incident(self, incident_id: str, resolution_notes: str = "", actor: str = "system") -> Optional[Incident]:
        """Resolve an incident."""
        incident = self.get_incident(incident_id)
        if incident:
            incident.status = IncidentStatus.RESOLVED
            incident.resolution_notes = resolution_notes
            incident.updated_at = datetime.utcnow()
            incident.resolved_at = datetime.utcnow()
            incident.events.append({
                "timestamp": datetime.utcnow().isoformat(),
                "event_type": "RESOLVED",
                "actor": actor,
                "description": f"Incident resolved by {actor}"
            })
            
            # Publish event
            self.event_bus.publish(Event(
                event_type=EventType.INCIDENT_RESOLVED,
                source_agent=self.name,
                timestamp=datetime.utcnow(),
                data={
                    "incident_id": incident_id,
                    "resolution_notes": resolution_notes
                }
            ))
        
        return incident
