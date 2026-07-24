"""Incident Agent - detects, correlates, and escalates incidents."""

import os
import uuid
from datetime import datetime, timedelta
from typing import Optional, List
from dataclasses import asdict

# New imports for templating and config handling
import json
import textwrap

from agents.base_agent import BaseAgent, AgentConfig
from agents.event_bus import Event, EventType, get_event_bus
from models import (
    # Assuming these dataclasses/enums are defined in models.py
    # For this diff, we assume the Incident dataclass can dynamically
    # accept 'redacted_snippet', 'trace_id', 'suggested_patch_url' attributes
    # or that they are fields in the actual models.Incident.
    # The 'escalated_to' list is also assumed to be an attribute for tracking.
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

        # Define severity ranking for comparison
        self.SEVERITY_RANK = {
            IncidentSeverity.LOW.value: 1,
            IncidentSeverity.MEDIUM.value: 2,
            IncidentSeverity.HIGH.value: 3,
            IncidentSeverity.CRITICAL.value: 4
        }
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
    
    # New: Mock configurable alert routing and remediation templates
    # In a real system, these would be loaded from a database or config service
    # based on the schema: service_alert_routing(service_id, destination_type, destination_meta, min_severity)
    self.service_alert_routing_config: Dict[str, List[Dict[str, Any]]] = {
        "auth-service": [
            {"type": "slack", "channel": "#auth-alerts", "priority": "warning", "min_severity": IncidentSeverity.MEDIUM.value},
            {"type": "pagerduty", "service_key": "pd_auth_critical", "priority": "critical", "min_severity": IncidentSeverity.CRITICAL.value}
        ],
        "payments-api": [
            {"type": "slack", "channel": "#payments-alerts", "priority": "warning", "min_severity": IncidentSeverity.MEDIUM.value},
            {"type": "email", "list": "payments-devs@example.com", "priority": "high", "min_severity": IncidentSeverity.HIGH.value},
            {"type": "pagerduty", "service_key": "pd_payments_critical", "priority": "critical", "min_severity": IncidentSeverity.CRITICAL.value}
        ],
        "default": [ # Fallback routing if no service-specific config found
            {"type": "slack", "channel": "#general-alerts", "priority": "info", "min_severity": IncidentSeverity.LOW.value},
            {"type": "pagerduty", "service_key": "pd_general_high", "priority": "high", "min_severity": IncidentSeverity.HIGH.value}
        ]
    }

    # New: Mock remediation templates config
    # Based on schema: remediation_templates(id, name, template_text, conditions_json)
    self.remediation_templates_config: List[Dict[str, Any]] = [
        {
            "id": "pii_critical_breach",
            "name": "PII Critical Breach Template",
            "template_text": textwrap.dedent("""
                🚨 CRITICAL PII BREACH DETECTED in {service}! 🚨
                Severity: {severity}
                Details: {redacted_snippet}
                Trace ID: {trace_id}
                Suggested Remediation: Investigate immediately. Suggested patch URL: {suggested_patch_url}
                Team: @security-oncall
                {% if pii_category == 'credential' %}
                ACTION REQUIRED: Rotate affected credentials.
                {% endif %}
            """).strip(),
            "conditions_json": {"min_severity": IncidentSeverity.CRITICAL.value, "pii_involved": True}
        },
        {
            "id": "high_error_rate",
            "name": "High Error Rate Template",
            "template_text": textwrap.dedent("""
                🔥 HIGH ERROR RATE in {service} ({severity}) 🔥
                Description: {description}
                Affected Services: {service}
                Trace ID: {trace_id}
                Suggested Remediation: Check recent deployments or service dependencies.
                Dashboard: [Link to {service} Dashboard]
            """).strip(),
            "conditions_json": {"min_severity": IncidentSeverity.HIGH.value, "category_keyword": "error rate"}
        },
        {
            "id": "default_incident",
            "name": "Default Incident Template",
            "template_text": textwrap.dedent("""
                ⚠️ New Incident in {service} ({severity}) ⚠️
                Title: {title}
                Description: {description}
                Trace ID: {trace_id}
                Suggested Remediation: Review logs and recent changes for {service}.
            """).strip(),
            "conditions_json": {"min_severity": IncidentSeverity.LOW.value} # Default, lowest priority
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
        
        incident = Incident(
            # Note: `models.py` is not provided. We assume `Incident` dataclass
            # can accept additional attributes or they are defined in models.py.
            # For this change, we dynamically add 'redacted_snippet', 'trace_id',
            # 'suggested_patch_url', and 'escalated_to' for templating and routing purposes.
            # In a real system, these would be explicitly defined fields in models.py.
            # The `escalation_channel` field will be set to the highest priority
            # channel from the dynamically determined destinations, or left None if no destinations.
            # The full list of destinations will be stored in `incident.escalated_to`.

            # Existing fields
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
            escalation_channel=None, # This will be set dynamically during escalation based on selected route

            # Dynamically added attributes (assume models.py supports these or they are added as runtime attributes)
            redacted_snippet=self._get_redacted_snippet(alert_ids),
            trace_id=self._get_trace_id(alert_ids), # Mocked or derived from alert data
            suggested_patch_url=None, # This would come from RemediationAgent if a fix PR was generated
            escalated_to=[], # To store all channels alert is sent to
            events=[
                {
                    "timestamp": now.isoformat(),
                    "event_type": "CREATED",
                    "description": "Incident created by Incident Agent"
                }
            ]
        )
        return incident
    
    def _get_redacted_snippet(self, alert_ids: List[str]) -> str:
        """Retrieves a redacted snippet from the alerts in the incident queue."""
        if not alert_ids:
            return "No specific snippet available."
        
        # Find the first alert message from the queue that matches an alert_id
        for alert_id in alert_ids:
            for correlation in self.incident_queue:
                if correlation.alert_id == alert_id:
                    # Assume correlation.message is already redacted by PrivacyAgent
                    return correlation.message[:200].replace('\n', ' ') # Take first 200 chars as snippet, clean newlines
        return "No specific snippet available."

    def _get_trace_id(self, alert_ids: List[str]) -> Optional[str]:
        """Mocks retrieving a trace ID from associated alerts."""
        # In a real system, this would extract trace_id from alert metadata
        if alert_ids:
            # Example: return a pseudo trace ID derived from the first alert_id
            return f"trace-{alert_ids[0][:8]}"
        return None

    def _select_and_render_template(self, incident: Incident) -> str:
        """Selects the highest-priority applicable template and populates placeholders."""
        
        applicable_templates = []
        for template_conf in self.remediation_templates_config:
            conditions = template_conf.get("conditions_json", {})
            is_applicable = True
            
            # Check severity condition
            min_severity_str = conditions.get("min_severity")
            if min_severity_str and self.SEVERITY_RANK[incident.severity.value] < self.SEVERITY_RANK[min_severity_str]:
                is_applicable = False

            # Check pii_involved condition
            if "pii_involved" in conditions and conditions["pii_involved"] != incident.pii_involved:
                is_applicable = False
            
            # Check category keyword condition (simplified, could be more robust)
            category_keyword = conditions.get("category_keyword")
            if category_keyword and category_keyword.lower() not in incident.title.lower() and category_keyword.lower() not in incident.description.lower():
                is_applicable = False

            if is_applicable:
                applicable_templates.append(template_conf)
        
        # Sort by implied priority (higher severity conditions first, or order in config)
        # For simplicity, assume order in self.remediation_templates_config defines priority.
        # The first applicable template found is the "highest priority".
        if not applicable_templates:
            return "No remediation template found for this incident. Please check configuration."
        
        selected_template = applicable_templates[0] # Take the first one as highest priority by config order

        # Prepare context for template rendering
        template_context = {
            "service": ", ".join(incident.affected_services) if incident.affected_services else "unknown-service",
            "severity": incident.severity.value,
            "title": incident.title,
            "description": incident.description,
            "redacted_snippet": getattr(incident, 'redacted_snippet', 'N/A'),
            "trace_id": getattr(incident, 'trace_id', 'N/A'),
            "suggested_patch_url": getattr(incident, 'suggested_patch_url', 'N/A'),
            "pii_involved": incident.pii_involved,
            "pii_category": incident.pii_category if incident.pii_category else 'N/A',
            # Add other relevant incident fields as needed
        }

        # Render template, handling conditional blocks (simplified for f-string capability)
        rendered_text = selected_template["template_text"]
        
        # Simple conditional block processing (for demonstration, a full templating engine like Jinja2 is better)
        # This example handles {% if condition %}...{% endif %} for `pii_category == 'credential'`
        if "{% if pii_category == 'credential' %}" in rendered_text:
            if template_context.get("pii_category") == "credential":
                rendered_text = rendered_text.replace("{% if pii_category == 'credential' %}", "").replace("{% endif %}", "")
            else:
                # Remove the block if condition not met
                rendered_text = re.sub(r"{% if pii_category == 'credential' %}.*?{% endif %}", "", rendered_text, flags=re.DOTALL)

        try:
            return rendered_text.format(**template_context)
        except KeyError as e:
            return f"Error rendering template '{selected_template.get('name', selected_template['id'])}': Missing placeholder {e}."
        except Exception as e:
            return f"Unexpected error rendering template '{selected_template.get('name', selected_template['id'])}': {e}."

    def _get_service_routing_config(self, service_name: str, severity: IncidentSeverity) -> List[Dict[str, Any]]:
        """
        Retrieves alert routing destinations for a given service and severity.
        Prioritizes service-specific configurations, then falls back to default.
        """
        
        applicable_routes = []
        
        # Check service-specific config, then fall back to default
        service_routes = self.service_alert_routing_config.get(service_name, [])
        if not service_routes:
            service_routes = self.service_alert_routing_config.get("default", [])

        # Filter by minimum severity
        current_severity_rank = self.SEVERITY_RANK[severity.value]
        for route in service_routes:
            min_severity_str = route.get("min_severity", IncidentSeverity.LOW.value)
            if current_severity_rank >= self.SEVERITY_RANK[min_severity_str]:
                applicable_routes.append(route)
        
        # Sort by priority (e.g., critical > high > warning > info)
        # Assuming "min_severity" reflects priority in descending order
        applicable_routes.sort(key=lambda r: self.SEVERITY_RANK[r.get("min_severity", IncidentSeverity.LOW.value)], reverse=True)

        return applicable_routes
    
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
    
    def _simulate_delivery(self, destination: Dict[str, Any], message: str) -> bool:
        """Simulates sending an alert to a destination."""
        # print(f"  Attempting delivery to {destination['type']} ({destination.get('channel') or destination.get('list') or destination.get('service_key')})...")
        
        # Simulate failure for PagerDuty critical alerts 10% of the time
        if destination["type"] == "pagerduty" and destination.get("min_severity") == IncidentSeverity.CRITICAL.value and uuid.uuid4().int % 10 == 0:
            print(f"  Simulated PagerDuty CRITICAL delivery FAILURE for {destination['service_key']}")
            return False
        
        # Simulate failure for other types 5% of the time
        if uuid.uuid4().int % 20 == 0:
            print(f"  Simulated {destination['type']} delivery FAILURE.")
            return False
        
        # print(f"  Delivered to {destination['type']} successfully.")
        return True

    def _escalate_incident(self, incident: Incident) -> None:
        """Escalate incident to appropriate channels based on per-service config and templates."""
        
        # Render remediation text for the incident using the highest priority template
        remediation_message = self._select_and_render_template(incident)

        # Get routing configuration for the primary affected service
        primary_service = incident.affected_services[0] if incident.affected_services else "default"
        destinations = self._get_service_routing_config(primary_service, incident.severity)
        
        if not destinations:
            print(f"No escalation routes configured for service '{primary_service}' with severity '{incident.severity.value}'.")
            return
        
        incident.escalated_to = [] # Clear previous, if any, and prepare to track all attempts
        
        # Iterate through all applicable destinations and attempt delivery
        delivery_successful_to_any = False
        for dest in destinations:
            destination_identifier = f"{dest['type']}:{dest.get('channel') or dest.get('list') or dest.get('service_key')}"
            incident.escalated_to.append(destination_identifier)
            
            delivery_successful = False
            for attempt in range(3): # Retry 3 times with exponential backoff
                print(f"  Attempting delivery to {destination_identifier} (Attempt {attempt+1})...")
                if self._simulate_delivery(dest, remediation_message):
                    print(f"  Delivered to {destination_identifier} successfully.")
                    delivery_successful = True
                    delivery_successful_to_any = True
                    break
                else:
                    backoff_time = 0.2 * (2 ** attempt) # Exponential backoff: 200ms, 400ms, 800ms
                    print(f"  Delivery failed to {destination_identifier}. Retrying in {backoff_time:.1f}s...")
                    # In a real system, you'd use time.sleep(backoff_time)
            
            if not delivery_successful:
                print(f"  Final delivery failure for {destination_identifier}. Logging to alerts_failures table (mocked).")
                # Log failure to a persistent store (e.g., 'alerts_failures' table)
                self.event_bus.publish(Event(
                    event_type=EventType.ALERT_DELIVERY_FAILED,
                    source_agent=self.name,
                    timestamp=datetime.utcnow(),
                    data={
                        "incident_id": incident.id,
                        "destination": dest,
                        "reason": "Max retries exceeded",
                        "message": remediation_message
                    },
                    severity=incident.severity.value
                ))
                
                # Check for PagerDuty critical fallback to a webhook
                if dest["type"] == "pagerduty" and dest.get("min_severity") == IncidentSeverity.CRITICAL.value:
                    print("  PagerDuty CRITICAL alert failed, escalating to fallback webhook (mocked).")
                    # Send to a fallback webhook
                    # requests.post("https://fallback.webhook.example.com/critical", json={"incident_id": incident.id, "message": remediation_message})

        # Update incident object's escalation status
        incident.escalated_at = datetime.utcnow()
        incident.escalation_channel = EscalationChannel[destinations[0]["type"].upper()] if delivery_successful_to_any else None # Set to highest priority type if any delivery was successful
        incident.description = f"{incident.description}\n\n--- Remediation Guidance ---\n{remediation_message}" # Append templated remediation to description
        
        # Publish escalation event
        self.event_bus.publish(Event(
            event_type=EventType.INCIDENT_ESCALATED,
            source_agent=self.name,
            timestamp=datetime.utcnow(),
            data={
                "incident_id": incident.id,
                "escalation_details": incident.escalated_to,
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
