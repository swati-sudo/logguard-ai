"""Incident Agent - detects, correlates, and escalates incidents."""

import os
import re # For template rendering
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
    ALERT_DELIVERY_RETRY_ATTEMPTS = 3
    ALERT_DELIVERY_BACKOFF_FACTOR = 0.5 # Start with 0.5s, 1s, 2s
    
    def __init__(self, config: Optional[AgentConfig] = None):
        """Initialize incident agent."""
        super().__init__(config)
        self.incidents: dict[str, Incident] = {}
        self.incident_queue: list[AlertCorrelation] = []
        self.event_bus = get_event_bus()
        self.detection_rules = self._load_detection_rules()
        self.service_alert_routes = self._load_service_alert_routes()
        self.remediation_templates = self._load_remediation_templates()
        
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
    
    def _load_service_alert_routes(self) -> dict[str, list[dict]]:
        """
        Mock loading per-service alert routing configurations from a DB.
        In a real system, this would query the `service_alert_routing` table.
        """
        # Using dictionaries to represent the `service_alert_routing` table structure
        return {
            "auth-service": [
                {"type": "slack", "destination_meta": "#auth-alerts", "min_severity": IncidentSeverity.MEDIUM},
                {"type": "pagerduty", "destination_meta": "auth_pd_key", "min_severity": IncidentSeverity.HIGH},
                {"type": "email", "destination_meta": "security@example.com", "min_severity": IncidentSeverity.CRITICAL}
            ],
            "payments-api": [
                {"type": "slack", "destination_meta": "#payments-alerts", "min_severity": IncidentSeverity.LOW},
                {"type": "pagerduty", "destination_meta": "payments_pd_key", "min_severity": IncidentSeverity.MEDIUM},
                {"type": "webhook", "destination_meta": "https://example.com/payments-alert-hook", "min_severity": IncidentSeverity.HIGH}
            ],
            "notification-service": [
                {"type": "slack", "destination_meta": "#notifications-alerts", "min_severity": IncidentSeverity.LOW}
            ],
            "default": [ # Fallback for services not explicitly configured
                {"type": "slack", "destination_meta": "#general-alerts", "min_severity": IncidentSeverity.MEDIUM},
                {"type": "pagerduty", "destination_meta": "default_pd_key", "min_severity": IncidentSeverity.CRITICAL}
            ]
        }

    def _load_remediation_templates(self) -> list[dict]:
        """
        Mock loading remediation templates from a DB.
        In a real system, this would query the `remediation_templates` table.
        """
        # Using dictionaries to represent the `remediation_templates` table structure
        return [
            {
                "id": "pii_critical_alert",
                "name": "Critical PII Breach Alert",
                "template_text": """
                🚨 **CRITICAL ALERT: PII/Credential Breach Detected** 🚨
                **Service:** `{service}`
                **Severity:** `{severity}`
                **Trace ID:** `{trace_id}`
                **Description:** `{incident_description}`
                
                **Redacted Snippet:**
                ```
                {redacted_snippet}
                ```
                
                **Suggested Remediation:**
                {if severity in ["CRITICAL", "HIGH"] and suggested_patch_url and suggested_patch_url != "No automated patch available."}
                A potential code fix has been generated: {suggested_patch_url}
                Please review and approve the PR immediately.
                {else}
                Immediately investigate service logs for `{trace_id}` and rotate affected credentials.
                {endif}
                """,
                "conditions_json": {"category": "pii", "min_severity": IncidentSeverity.CRITICAL}
            },
            {
                "id": "default_incident_alert",
                "name": "Default Incident Alert",
                "template_text": """**ALERT: Incident Detected**\n**Service:** `{service}`\n**Severity:** `{severity}`\n**Description:** `{incident_description}`\n**Trace ID:** `{trace_id}`""",
                "conditions_json": {"min_severity": IncidentSeverity.LOW}
            }
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
                    "redacted_snippet": "logger.warn(password)", # Added
                    "service": "auth-service",
                    "trace_id": "abc-123-xyz", # Added
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
                redacted_snippet=alert.get("redacted_snippet"), # New
                service=alert.get("service", "unknown"),
                trace_id=alert.get("trace_id"), # New
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
            
            # Auto-escalate if needed (now includes routing and templating)
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
                pii_involved=metrics.get("pii_involved", False),
                trace_id=metrics.get("trace_id") # Pass trace_id from metrics
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
                pii_category=metrics.get("pii_category"),
                trace_id=metrics.get("trace_id")
            )
            incidents.append(incident)
        
        # Rule 3: Cascading failure
        if len(affected_services) > 3 and error_rate > 0.2:
            incident = self._create_incident(
                title="Cascading Failure Detected",
                description=f"Multiple services failing: {', '.join(affected_services)}",
                severity=IncidentSeverity.HIGH,
                affected_services=affected_services,
                alert_ids=[],
                trace_id=metrics.get("trace_id")
            )
            incidents.append(incident)
        
        # Rule 4: Database overload
        if metrics.get("db_pool_utilization", 0) > 90:
            incident = self._create_incident(
                title="Database Connection Pool Exhaustion",
                description="Database connection pool utilization >90%",
                severity=IncidentSeverity.HIGH,
                affected_services=affected_services,
                alert_ids=[],
                trace_id=metrics.get("trace_id")
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
                        pii_involved=category == "pii",
                        redacted_snippet=alerts[0].redacted_snippet, # Take from first alert
                        trace_id=alerts[0].trace_id # Take from first alert
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
        pii_category: Optional[str] = None,
        redacted_snippet: Optional[str] = None, # New
        trace_id: Optional[str] = None, # New
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
            redacted_snippet=redacted_snippet, # New
            trace_id=trace_id, # New
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
        """
        Escalate incident to appropriate channel(s) using configured routing
        and templated remediation text.
        """
        # Use a dummy suggested_patch_url if a real one isn't available.
        # In a real scenario, RemediationAgent would update the incident with this.
        # For now, let's mock it if the incident doesn't have it.
        if not hasattr(incident, 'suggested_patch_url') or incident.suggested_patch_url is None:
            incident.suggested_patch_url = "https://github.com/org/repo/pull/123" # Mock for template demo

        # Render the remediation template
        alert_message = self._render_remediation_template(incident)

        # Determine routing destinations
        service_id = incident.affected_services[0] if incident.affected_services else "default"
        destinations = self._get_routing_destinations(service_id, incident.severity)

        incident.escalated_at = datetime.utcnow()
        incident.escalated_to = [] # Reset, as routing is dynamic

        for dest in destinations:
            success = self._send_alert(incident, dest, alert_message)
            if success:
                incident.escalated_to.append(f"{dest['type']}:{dest['destination_meta']}")
            else:
                # Log failure
                self.event_bus.publish(Event(
                    event_type=EventType.ALERT_DELIVERY_FAILED,
                    source_agent=self.name,
                    timestamp=datetime.utcnow(),
                    data={
                        "incident_id": incident.id,
                        "destination_type": dest['type'],
                        "destination_meta": dest['destination_meta'],
                        "severity": incident.severity.value
                    }
                ))
                # Specific fallback for PagerDuty critical alerts
                if dest['type'] == "pagerduty" and dest['min_severity'] == IncidentSeverity.CRITICAL and not success:
                    fallback_dest = {"type": "webhook", "destination_meta": "https://example.com/fallback-webhook", "min_severity": IncidentSeverity.CRITICAL}
                    self._send_alert(incident, fallback_dest, f"FALLBACK: PagerDuty critical alert failed for {incident.id}. Original message:\n{alert_message}")
                    incident.escalated_to.append(f"fallback_webhook:{fallback_dest['destination_meta']}")

        if not incident.escalated_to:
            print(f"[{self.name}] No successful escalations for incident {incident.id}")

        # Publish escalation event (only if actual escalations happened)
        if incident.escalated_to:
            self.event_bus.publish(Event(
                event_type=EventType.INCIDENT_ESCALATED,
                source_agent=self.name,
                timestamp=datetime.utcnow(),
                data={
                    "incident_id": incident.id,
                    "channels": incident.escalated_to
                },
                severity=incident.severity.value
            ))

    def _render_remediation_template(self, incident: Incident) -> str:
        """
        Renders the highest-priority applicable remediation template for an incident.
        """
        # Ensure Incident has necessary attributes for templating
        # This assumes Incident class (from models.py) was extended to include these.
        # If not, we'd need to fall back or make assumptions using getattr.
        _redacted_snippet = getattr(incident, 'redacted_snippet', "N/A")
        _trace_id = getattr(incident, 'trace_id', "N/A")
        _suggested_patch_url = getattr(incident, 'suggested_patch_url', "No automated patch available.")

        context = {
            "service": incident.affected_services[0] if incident.affected_services else "Unknown Service",
            "severity": incident.severity.value,
            "redacted_snippet": _redacted_snippet,
            "trace_id": _trace_id,
            "incident_description": incident.description,
            "suggested_patch_url": _suggested_patch_url
        }

        best_template: Optional[dict] = None
        # Simple priority: critical > high > medium > low, then specific category match
        # Sort by min_severity value (higher value = higher priority)
        sorted_templates = sorted(
            self.remediation_templates,
            key=lambda t: t["conditions_json"].get("min_severity", IncidentSeverity.LOW).value,
            reverse=True
        )

        for template in sorted_templates:
            conditions = template["conditions_json"]
            # Check severity condition
            min_severity_ok = incident.severity.value >= conditions.get("min_severity", IncidentSeverity.LOW).value
            
            # Check category condition
            category_ok = True
            if conditions.get("category"):
                # This is a crude check. A more robust solution would pass incident.category explicitly.
                if conditions["category"] == "pii":
                    category_ok = incident.pii_involved

            if min_severity_ok and category_ok:
                best_template = template
                break # Found the highest priority applicable template

        if not best_template:
            # Fallback to default if no specific template matches
            best_template = next((t for t in self.remediation_templates if t["id"] == "default_incident_alert"), None)
            if not best_template:
                return f"[{context['severity']}][{context['service']}] Incident: {context['incident_description']}. Trace: {context['trace_id']}"

        # Basic placeholder replacement and conditional blocks
        rendered_text = best_template["template_text"]
        for key, value in context.items():
            rendered_text = rendered_text.replace(f"{{{key}}}", str(value))

        # Simple conditional block processing (e.g., {if condition} ... {else} ... {endif})
        # This is a very basic implementation; a proper template engine would be better.
        # Re-parse to handle nested replacements or complex logic
        while "{if" in rendered_text:
            if_match = re.search(r"{if\s+(.*?)\s*}(.*?)(?:{else}(.*?))?{endif}", rendered_text, re.DOTALL)
            if not if_match:
                break # No more valid if blocks
            
            condition_str = if_match.group(1)
            true_block = if_match.group(2)
            false_block = if_match.group(3) or "" # Group 3 is optional for {else}
            
            # Evaluate condition string. WARNING: Direct eval is dangerous.
            # Using a safer, limited context for eval.
            try:
                _locals = {k: v for k, v in context.items()}
                # Ensure IncidentSeverity enum is available for comparison
                _locals['IncidentSeverity'] = IncidentSeverity 
                if eval(condition_str, {"__builtins__": None, "IncidentSeverity": IncidentSeverity}, _locals): # Safely evaluate
                    rendered_text = rendered_text.replace(if_match.group(0), true_block)
                else:
                    rendered_text = rendered_text.replace(if_match.group(0), false_block)
            except Exception as e:
                print(f"Error evaluating condition '{condition_str}': {e}")
                rendered_text = rendered_text.replace(if_match.group(0), true_block) # Fallback if eval fails

        return rendered_text

    def _get_routing_destinations(self, service_id: str, severity: IncidentSeverity) -> list[dict]:
        """Get configured alert destinations for a service and severity."""
        routes = self.service_alert_routes.get(service_id, [])
        if not routes:
            routes = self.service_alert_routes.get("default", [])

        applicable_destinations = [
            dest for dest in routes
            if severity.value >= dest["min_severity"].value
        ]
        # Sort by severity (highest priority first) or by type if custom preference
        return sorted(applicable_destinations, key=lambda x: x["min_severity"].value, reverse=True)

    def _send_alert(self, incident: Incident, destination: dict, message: str) -> bool:
        """
        Simulates sending an alert to a destination with retry logic.
        Generates metrics: alerts.sent, alerts.failed, alerts.latency_ms.
        """
        start_time = datetime.utcnow()
        
        for attempt in range(self.ALERT_DELIVERY_RETRY_ATTEMPTS):
            try:
                # Simulate HTTP POST
                # In production, use requests library for webhooks,
                # PagerDuty/Slack SDKs, SMTP for email.
                print(f"[{self.name}] Sending alert (attempt {attempt+1}/{self.ALERT_DELIVERY_RETRY_ATTEMPTS}) to {destination['type']}:{destination['destination_meta']} for incident {incident.id}")
                print(f"Message:\n{message[:200]}...") # Print first 200 chars

                # Simulate network latency and potential failure
                import random, time
                time.sleep(random.uniform(0.05, 0.2)) # Simulate latency
                if random.random() < 0.1 and attempt < self.ALERT_DELIVERY_RETRY_ATTEMPTS - 1: # 10% failure rate
                    raise Exception("Simulated network error") # Changed from requests.exceptions.RequestException
                
                # Simulate success
                self.event_bus.publish(Event(
                    event_type=EventType.METRIC_GENERATED,
                    source_agent=self.name,
                    timestamp=datetime.utcnow(),
                    data={"metric_name": "alerts.sent", "value": 1, "tags": {"service": incident.affected_services[0] if incident.affected_services else "unknown", "destination_type": destination['type'], "severity": incident.severity.value}},
                ))
                latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                self.event_bus.publish(Event(
                    event_type=EventType.METRIC_GENERATED,
                    source_agent=self.name,
                    timestamp=datetime.utcnow(),
                    data={"metric_name": "alerts.latency_ms", "value": latency_ms, "tags": {"service": incident.affected_services[0] if incident.affected_services else "unknown", "destination_type": destination['type'], "severity": incident.severity.value}},
                ))
                print(f"[{self.name}] Alert sent successfully to {destination['type']}:{destination['destination_meta']}")
                return True
            except Exception as e:
                print(f"[{self.name}] Failed to send alert to {destination['type']}:{destination['destination_meta']} (attempt {attempt+1}): {e}")
                if attempt < self.ALERT_DELIVERY_RETRY_ATTEMPTS - 1:
                    time.sleep(self.ALERT_DELIVERY_BACKOFF_FACTOR * (2 ** attempt)) # Exponential backoff
                else:
                    # Last attempt failed
                    self.event_bus.publish(Event(
                        event_type=EventType.METRIC_GENERATED,
                        source_agent=self.name,
                        timestamp=datetime.utcnow(),
                        data={"metric_name": "alerts.failed", "value": 1, "tags": {"service": incident.affected_services[0] if incident.affected_services else "unknown", "destination_type": destination['type'], "severity": incident.severity.value}},
                    ))
        return False
    
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
