# Incident Agent — Implementation Guide

## Overview

The **Incident Agent** is the fourth component in the LogGuard AI pipeline, sitting between the Noise Agent and Remediation Agent. It detects, correlates, and escalates incidents from alerts and log patterns.

```
Privacy Agent → Noise Agent → [Incident Agent] → Remediation Agent
```

## Architecture

### Core Responsibilities

1. **Incident Detection** — Identify critical patterns:
   - High error rates (>50% errors)
   - PII/credential leaks
   - Cascading failures (multiple services down)
   - Database connection pool exhaustion
   - Memory leaks

2. **Alert Aggregation** — Group related alerts:
   - 5+ alerts from same service in 60s → 1 incident
   - Deduplication (prevent alert fatigue)
   - Correlation by service, category, time window

3. **Severity Classification**:
   - `CRITICAL`: PII leak, error rate >50%
   - `HIGH`: Cascading failure, DB overload
   - `MEDIUM`: Memory spike, timeouts
   - `LOW`: Informational alerts

4. **Escalation** — Auto-notify on-call teams:
   - PagerDuty (CRITICAL)
   - Slack (HIGH/MEDIUM)
   - Email (LOW)
   - SMS (custom rules)

5. **Lifecycle Management**:
   - OPEN → ACKNOWLEDGED → RESOLVED
   - Track timeline of all events
   - Support root cause analysis

## Files Created

### 1. `backend/agents/base_agent.py`
Abstract base class for all agents to inherit from.

**Key Classes:**
- `BaseAgent` — Abstract base with common functionality
- `AgentConfig` — Configuration dataclass (enabled, timeout, retry_count)

**Key Methods:**
```python
execute(data) → dict      # Main entry point with error handling
process(data) → Any       # To be implemented by subclasses
validate_input(data) → bool
get_agent_info() → dict
```

### 2. `backend/agents/event_bus.py`
In-memory pub/sub system for inter-agent communication.

**Key Classes:**
- `Event` — Represents a system event
- `EventType` — Enum of all event types
- `EventBus` — Central event broker

**Events:**
```
incident.created
incident.updated
incident.escalated
incident.resolved
alert.generated
alert.aggregated
```

**Usage:**
```python
bus = get_event_bus()
bus.subscribe(EventType.INCIDENT_CREATED, callback)
bus.publish(Event(...))
```

### 3. `backend/models/__init__.py`
Pydantic dataclasses for incident data structures.

**Key Classes:**
- `Incident` — Core incident data
- `AlertCorrelation` — Alert metadata
- `IncidentMetrics` — Metrics for analysis
- `IncidentTimeline` — Event timeline
- `IncidentDetectionRule` — Detection rules

### 4. `backend/agents/incident_agent.py`
Main incident detection and management agent.

**Key Methods:**
```python
process(data) → dict               # Main processing
_detect_incidents(metrics) → list  # Pattern-based detection
_correlate_alerts() → list         # Alert grouping
_create_incident(...) → Incident   # Incident factory
_escalate_incident(incident) → None
get_open_incidents() → list
acknowledge_incident(id) → Incident
resolve_incident(id, notes) → Incident
```

**Detection Thresholds:**
```python
ERROR_RATE_THRESHOLD = 0.50        # 50% error rate
ERROR_COUNT_THRESHOLD = 10         # Minimum 10 errors
ALERT_CORRELATION_WINDOW = 60      # seconds
ALERT_CORRELATION_COUNT = 3        # Minimum 3 alerts
CASCADING_FAILURE_WINDOW = 60      # seconds
```

## Data Flow

### Input Format
```python
{
    "alerts": [
        {
            "id": "alert-0001",
            "severity": "CRITICAL",
            "timestamp": "2026-07-22T14:30:00Z",
            "message": "PII detected: password",
            "service": "auth-service",
            "category": "pii"  # pii, error, timeout, resource
        }
    ],
    "metrics": {
        "error_rate": 0.55,
        "error_count": 45,
        "affected_services": ["auth-service", "payments-api"],
        "pii_involved": True,
        "pii_category": "credential",
        "db_pool_utilization": 85
    }
}
```

### Output Format
```python
{
    "incident_count": 1,
    "incidents": [
        {
            "id": "incident-20260722-a1b2c3d4",
            "created_at": "2026-07-22T14:31:00Z",
            "severity": "CRITICAL",
            "status": "OPEN",
            "title": "PII/Credential Leak Detected",
            "description": "Sensitive credentials detected in auth-service",
            "affected_services": ["auth-service"],
            "alert_ids": ["alert-0001", "alert-0002"],
            "alert_count": 2,
            "pii_involved": True,
            "escalation_channel": "pagerduty",
            "escalated_to": ["@pagerduty-oncall"]
        }
    ],
    "queue_size": 0
}
```

## API Endpoints

### Incident Detection
```
POST /api/incidents/detect
    Trigger incident detection from current alerts
    
GET /api/incidents
    Get all open incidents
    
GET /api/incidents/{id}
    Get specific incident
```

### Incident Management
```
POST /api/incidents/{id}/acknowledge
    Mark incident as acknowledged
    Body: {"actor": "user@company.com"}
    
POST /api/incidents/{id}/resolve
    Resolve incident
    Body: {"resolution_notes": "...", "actor": "..."}
```

### Event History
```
GET /api/events?limit=100
    Get event bus history
```

## Integration with Pipeline

The incident agent is integrated into `LogPipeline`:

```python
# In pipeline.py
from agents.incident_agent import IncidentAgent

class LogPipeline:
    def __init__(self):
        self.incident = IncidentAgent()
    
    def detect_incidents(self) -> dict:
        # Prepare data from current alerts
        incident_data = {
            "alerts": self.alerts[-10:],
            "metrics": {...}
        }
        # Process incidents
        return self.incident.execute(incident_data)
```

### Usage in Main.py

```python
# In main.py
@app.post("/api/incidents/detect")
def detect_incidents():
    return pipeline.detect_incidents()
```

## Event-Driven Architecture

### Event Publishing
When an incident is created, the agent publishes an event:

```python
event = Event(
    event_type=EventType.INCIDENT_CREATED,
    source_agent="IncidentAgent",
    timestamp=datetime.utcnow(),
    data=asdict(incident),
    severity=incident.severity.value
)
event_bus.publish(event)
```

### Event Subscription
Other agents can subscribe to incidents:

```python
bus = get_event_bus()
bus.subscribe(EventType.INCIDENT_CREATED, handle_incident)

def handle_incident(event: Event):
    incident_id = event.data["id"]
    # Dependency Agent, Impact Agent, etc. can react
```

## Detection Rules

### Rule 1: High Error Rate
```
Condition: error_rate > 50% AND error_count >= 10
Severity: CRITICAL
Escalation: PagerDuty
```

### Rule 2: PII Leak
```
Condition: pii_involved == True
Severity: CRITICAL
Escalation: PagerDuty
```

### Rule 3: Cascading Failure
```
Condition: affected_services > 3 AND error_rate > 20%
Severity: HIGH
Escalation: Slack
```

### Rule 4: Database Overload
```
Condition: db_pool_utilization > 90%
Severity: HIGH
Escalation: Slack
```

### Rule 5: Memory Leak
```
Condition: memory_utilization > 85%
Severity: MEDIUM
Escalation: Slack
```

## Alert Correlation Algorithm

### Step 1: Queue Alerts
```
alert = AlertCorrelation(
    alert_id="alert-001",
    service="auth-service",
    category="pii",
    timestamp=now
)
self.incident_queue.append(alert)
```

### Step 2: Group by (category, service)
```
alert_groups = {
    ("pii", "auth-service"): [alert1, alert2, alert3],
    ("error", "payments-api"): [alert4, alert5]
}
```

### Step 3: Create Incident if Threshold Met
```
if len(alerts) >= MIN_CORRELATION_COUNT (3):
    if time_span < CORRELATION_WINDOW (60s):
        create_incident()
```

## Example Scenarios

### Scenario 1: Single PII Alert → Incident
```
Input:
  - Alert: "password detected in auth-service"
  
Detection:
  - Rule: PII_LEAK matches
  - Severity: CRITICAL
  
Output:
  - Incident created
  - Escalated to PagerDuty
  - On-call notified immediately
```

### Scenario 2: 10 Errors in 30s → Incident
```
Input:
  - 10 error alerts from payments-api in 30 seconds
  - error_rate: 55%
  
Detection:
  - Rule: HIGH_ERROR_RATE matches
  - Severity: CRITICAL
  
Output:
  - Incident created
  - 10 alerts aggregated into 1 incident
  - Escalated to PagerDuty
```

### Scenario 3: Multiple Services Failing → Incident
```
Input:
  - Alerts from: auth-service, payments-api, ledger-service
  - error_rate: 35%
  
Detection:
  - Rule: CASCADING_FAILURE matches
  - Severity: HIGH
  
Output:
  - Incident created with all 3 services
  - Escalated to Slack
```

## Testing

### Unit Tests
```python
def test_incident_creation():
    agent = IncidentAgent()
    result = agent.process({
        "alerts": [...],
        "metrics": {...}
    })
    assert result["incident_count"] > 0

def test_alert_correlation():
    agent = IncidentAgent()
    # Add 3+ alerts within time window
    result = agent._correlate_alerts()
    assert len(result) == 1  # Should correlate into 1 incident

def test_escalation():
    agent = IncidentAgent()
    incident = agent._create_incident(
        title="Test",
        severity=IncidentSeverity.CRITICAL,
        ...
    )
    assert incident.escalation_channel == EscalationChannel.PAGERDUTY
```

### Integration Tests
```python
# Start streaming logs
# Generate alerts
# Detect incidents
# Verify escalation events published
```

## Future Enhancements

1. **ML-Based Detection**
   - Anomaly detection using historical baselines
   - Predictive incident forecasting

2. **Advanced Correlation**
   - Trace dependency chains across services
   - Temporal correlation patterns

3. **Smart Escalation**
   - Route based on time of day (24/7 oncall)
   - Escalate based on service criticality
   - Route to oncall schedules

4. **Incident History**
   - Persistent storage (PostgreSQL, MongoDB)
   - Duplicate detection (same root cause)
   - Pattern learning

5. **Integration**
   - PagerDuty API (create/update incidents)
   - Slack webhooks (formatted messages)
   - JIRA integration (create tickets)
   - Datadog/Splunk (send incidents)

## Configuration

### Environment Variables
```env
# Incident detection thresholds
INCIDENT_ERROR_RATE_THRESHOLD=0.50
INCIDENT_ERROR_COUNT_THRESHOLD=10
INCIDENT_ALERT_CORRELATION_WINDOW=60
INCIDENT_ALERT_CORRELATION_COUNT=3

# Escalation settings
ENABLE_PAGERDUTY_ESCALATION=true
PAGERDUTY_API_KEY=your_key_here
ENABLE_SLACK_ESCALATION=true
SLACK_WEBHOOK_URL=your_webhook_here
```

## Next Steps

1. **Dependency Agent** — Map service dependencies and predict impact
2. **Impact Agent** — Quantify business impact (€/customer/hour)
3. **Control Agent** — Apply automatic remediation controls
4. **Recovery Agent** — Orchestrate staged recovery
5. **Report Agent** — Generate post-mortems and compliance reports

