# LogGuard AI — Extended Agent Architecture Plan

## Overview

Current 3-Agent Pipeline:
```
Privacy Agent → Noise Agent → Remediation Agent
```

**New 6-Agent Extension:**
```
[Raw Logs] 
    ↓
[Privacy Agent] ────→ PII Detection & Redaction
    ↓
[Noise Agent] ───────→ Redundancy Grouping & ROI
    ↓
[Incident Agent] ────→ Incident Detection & Aggregation
    ↓
[Dependency Agent] ──→ Service Dependency Mapping
    ↓
[Impact Agent] ──────→ Business Impact Analysis
    ↓
[Control Agent] ─────→ Remediation & Control Enforcement
    ↓
[Recovery Agent] ────→ Recovery Orchestration
    ↓
[Report Agent] ──────→ Compliance & Audit Reporting
```

---

## 1. Incident Agent

### Purpose
Detect, correlate, and escalate incidents from log streams and security alerts.

### Responsibilities
- **Incident Detection**: Identify critical patterns (repeated errors, cascading failures)
- **Alert Aggregation**: Group related alerts into incidents (e.g., 5 alerts from same service → 1 incident)
- **Severity Classification**: Calculate incident severity (LOW, MEDIUM, HIGH, CRITICAL)
- **Escalation**: Trigger PagerDuty, Slack, email based on severity
- **Duplicate Prevention**: Deduplicate similar incidents (same root cause within time window)

### Inputs
- PII alerts from Privacy Agent
- Noise patterns from Noise Agent
- Real-time log stream

### Outputs
```python
@dataclass
class Incident:
    id: str                          # incident-20260722-001
    created_at: datetime
    severity: str                    # LOW, MEDIUM, HIGH, CRITICAL
    status: str                      # OPEN, ACKNOWLEDGED, RESOLVED
    title: str                       # "Database connection failures in payments-api"
    description: str
    affected_services: list[str]     # ["payments-api", "ledger-service"]
    alert_count: int                 # 23 correlated alerts
    pii_involved: bool               # Does incident involve PII leak?
    related_alerts: list[str]        # ["alert-0001", "alert-0002", ...]
    root_logs: list[str]             # Last 10 root cause logs
    escalation_channel: str          # "pagerduty" | "slack" | "email"
    escalated_to: list[str]          # ["@oncall", "@security-team"]
```

### Detection Patterns
```python
ERROR_RATE_THRESHOLD = 50          # errors/minute
RESPONSE_TIME_THRESHOLD = 5000     # ms (P99)
CASCADING_FAILURE_WINDOW = 60      # seconds
PII_BREACH_ESCALATION = "CRITICAL"
```

### API Endpoints
```
POST /api/incidents
GET /api/incidents/{id}
GET /api/incidents?status=OPEN&severity=HIGH
PATCH /api/incidents/{id} (acknowledge/resolve)
POST /api/incidents/{id}/escalate
```

### Example Flow
```
[100 error logs in 30 seconds from payments-api] 
  → Incident Agent creates Incident(severity=CRITICAL)
  → Sends to Slack: "🚨 CRITICAL: payments-api down (100 errors/30s)"
  → Creates PagerDuty alert
  → Triggers on-call rotation
```

---

## 2. Dependency Agent

### Purpose
Map microservice dependencies and predict cascade failure impacts.

### Responsibilities
- **Service Graph Construction**: Build dependency tree from logs
- **Criticality Scoring**: Rank services by importance (upstream count, revenue impact)
- **Failure Impact Prediction**: If service X fails, which services are affected?
- **Critical Path Analysis**: Identify longest dependency chains
- **Bottleneck Detection**: Find services with highest fan-in

### Inputs
- Service names from logs
- Service-to-service call traces
- Historical failure data

### Outputs
```python
@dataclass
class ServiceDependency:
    service_name: str
    depends_on: list[str]            # Direct dependencies
    transitively_depends_on: list[str] # Transitive dependencies
    depended_on_by: list[str]        # Services that depend on this one
    criticality_score: float         # 0-100 (higher = more critical)
    failure_impact: list[str]        # Services affected if this fails
    avg_call_latency_ms: float
    error_rate: float               # 0-1
    
@dataclass
class ServiceGraph:
    services: dict[str, ServiceDependency]
    critical_paths: list[list[str]]  # ["auth" → "ledger" → "audit"]
    bottlenecks: list[str]           # Services with high fan-in
    last_updated: datetime
```

### Detection Method
```
1. Parse logs for service identifiers: [service-name]
2. Track call chains: service-a calls service-b (extract from traces)
3. Build directed graph
4. Run centrality algorithms (PageRank, betweenness centrality)
5. Identify critical paths using topological sort
6. Detect cycles (circular dependencies)
```

### API Endpoints
```
GET /api/dependencies/graph
GET /api/dependencies/service/{name}
GET /api/dependencies/impact/{service}?depth=2
GET /api/dependencies/critical-paths
POST /api/dependencies/refresh
```

### Example Output
```json
{
  "services": {
    "payments-api": {
      "criticality_score": 95,
      "depends_on": ["auth-service", "ledger-service"],
      "depended_on_by": ["notification-hub", "kyc-worker"],
      "failure_impact": ["notification-hub", "kyc-worker", "reporting-service"]
    }
  },
  "critical_paths": [
    ["auth-service", "payments-api", "ledger-service", "audit-service"]
  ]
}
```

---

## 3. Impact Agent

### Purpose
Quantify business impact of incidents and log anomalies.

### Responsibilities
- **Transaction Impact**: How many transactions are affected?
- **Revenue Impact**: Estimated €/$ loss per minute of downtime
- **Customer Impact**: How many customers are affected?
- **SLA Violation Detection**: Are we breaching SLAs?
- **Risk Scoring**: Assign risk level to incidents

### Inputs
- Incident data from Incident Agent
- Transaction metadata from logs
- Customer metadata (customer tier: premium/standard/free)
- SLA thresholds

### Outputs
```python
@dataclass
class Impact:
    incident_id: str
    affected_transactions: int       # 5,234 transactions blocked
    affected_customers: int          # 1,203 customers
    premium_customers: int           # 45 (high-value)
    estimated_revenue_impact: float  # €8,500/hour
    sla_violation: bool
    sla_breach_percentage: float    # How much over SLA threshold
    customer_communication_needed: bool
    incident_priority: int          # 1 (highest) to 5
    recovery_urgency: str           # IMMEDIATE, HIGH, MEDIUM, LOW
```

### Calculation Model
```python
# Revenue Impact
transactions_per_hour_normal = 100,000
revenue_per_transaction = €0.85
downtime_minutes = 30
revenue_impact = (transactions_per_hour_normal / 60 * downtime_minutes) * revenue_per_transaction

# SLA Violation
normal_error_rate = 0.1%  # 0.1% errors acceptable
current_error_rate = 2.5%
sla_violation = current_error_rate > normal_error_rate

# Customer Impact
premium_customers_affected = 45
standard_customers_affected = 1,158
weight = (premium_customers_affected * 100) + (standard_customers_affected * 10)
```

### API Endpoints
```
GET /api/impact/incident/{incident_id}
GET /api/impact/current
POST /api/impact/calculate (manual analysis)
GET /api/impact/history?period=24h
```

### Example
```json
{
  "incident_id": "incident-20260722-001",
  "affected_transactions": 5234,
  "affected_customers": 1203,
  "premium_customers": 45,
  "estimated_revenue_impact": 8500,
  "sla_violation": true,
  "recovery_urgency": "IMMEDIATE",
  "customer_communication_needed": true
}
```

---

## 4. Control Agent

### Purpose
Apply controls, enforce compliance, and manage remediation execution.

### Responsibilities
- **Control Execution**: Apply predefined controls (rate limiting, circuit breaker, etc.)
- **Compliance Enforcement**: Ensure compliance rules are followed
- **Configuration Management**: Update service configs for remediation
- **Feature Toggle Management**: Enable/disable features based on incidents
- **Access Control**: Manage emergency access during incidents

### Inputs
- Incident from Incident Agent
- Impact assessment from Impact Agent
- Control policies (database)

### Outputs
```python
@dataclass
class Control:
    id: str                          # control-20260722-001
    incident_id: str
    control_type: str               # "RATE_LIMIT" | "CIRCUIT_BREAK" | "DISABLE_FEATURE" | "ROLLBACK"
    service: str
    status: str                     # PENDING, APPLIED, FAILED, ROLLED_BACK
    applied_at: datetime
    config_change: dict             # {"rate_limit": 100, "timeout": 5000}
    reason: str
    auto_rollback_in_seconds: int   # Automatic rollback after N seconds if unsuccessful
```

### Predefined Controls
```python
CONTROLS = {
    "DATABASE_OVERLOAD": {
        "type": "RATE_LIMIT",
        "action": {"service": "payments-api", "rate_limit_rps": 100}
    },
    "MEMORY_LEAK": {
        "type": "CIRCUIT_BREAK",
        "action": {"service": "cache-service", "enabled": False}
    },
    "CASCADING_FAILURE": {
        "type": "DISABLE_FEATURE",
        "action": {"service": "auth-service", "feature": "2fa", "enabled": False}
    },
    "CORRUPTED_DATA": {
        "type": "ROLLBACK",
        "action": {"service": "ledger-service", "rollback_to": "last_good_version"}
    }
}
```

### API Endpoints
```
GET /api/controls/policies
POST /api/controls/apply (manual trigger)
PATCH /api/controls/{id} (update status)
POST /api/controls/{id}/rollback
GET /api/controls/history?incident_id={id}
```

### Example Flow
```
Incident: Database overloaded (error_rate > 50%)
  → Impact: 5,000 transactions blocked
  → Control Agent activates RATE_LIMIT control
  → Config: {"payments-api": {"rate_limit_rps": 100}}
  → Auto-rollback in 300 seconds if error rate doesn't drop
```

---

## 5. Recovery Agent

### Purpose
Orchestrate service recovery and health monitoring.

### Responsibilities
- **Health Checks**: Monitor service recovery progress
- **Staged Recovery**: Gradually increase traffic (canary → 10% → 50% → 100%)
- **Rollback Management**: Automatic rollback if recovery fails
- **Resource Scaling**: Trigger auto-scaling if needed
- **Service Restart**: Orchestrate graceful restarts

### Inputs
- Applied controls from Control Agent
- Real-time metrics (error rate, latency, throughput)
- Service status

### Outputs
```python
@dataclass
class RecoveryPlan:
    incident_id: str
    service: str
    status: str                    # IN_PROGRESS, RECOVERED, FAILED
    current_stage: int             # 1: 0% traffic, 2: 10%, 3: 50%, 4: 100%
    max_stages: int = 4
    stage_start_time: datetime
    traffic_percentage: int
    metrics: dict                  # {error_rate: 0.05, latency_p99: 450}
    health_check_status: str       # HEALTHY, DEGRADED, UNHEALTHY
    estimated_recovery_time: str   # "5 minutes remaining"
    last_check: datetime
```

### Recovery Stages
```
Stage 1 (0% traffic):   [Service offline] → Health checks only
Stage 2 (10% traffic):  [Canary] → Monitor error rate
Stage 3 (50% traffic):  [Ramp up] → Gradual traffic increase
Stage 4 (100% traffic): [Fully recovered] → Normal operations
```

### Health Check Criteria
```python
HEALTH_CRITERIA = {
    "error_rate": 0.1,           # < 0.1% errors
    "p99_latency_ms": 500,       # < 500ms
    "cpu_utilization": 70,       # < 70%
    "memory_utilization": 75,    # < 75%
    "db_connection_pool": 80     # < 80% utilized
}
```

### API Endpoints
```
GET /api/recovery/status/{incident_id}
POST /api/recovery/start
POST /api/recovery/next-stage
POST /api/recovery/rollback
GET /api/recovery/history?service={name}&period=24h
```

### Example Flow
```
Incident resolved, but service is recovering
Stage 1: Health check passes → Error rate 0.05%, Latency 200ms ✓
Stage 2: Route 10% traffic → Monitor for 60s
  - Error rate: 0.08% ✓
  - Latency P99: 450ms ✓
Stage 3: Route 50% traffic → Monitor for 120s
Stage 4: Route 100% traffic → Recovery complete
```

---

## 6. Report Agent

### Purpose
Generate compliance, audit, and operational reports.

### Responsibilities
- **Incident Reports**: Detailed post-incident analysis (RCA - Root Cause Analysis)
- **Compliance Reports**: SOC 2, GDPR, PCI-DSS compliance tracking
- **Audit Logs**: Immutable records of all system actions
- **Metrics Reporting**: KPIs, SLA metrics, reliability statistics
- **Trend Analysis**: Month-over-month improvements/regressions

### Inputs
- All incident data
- Control actions
- Recovery metrics
- User feedback
- System metrics history

### Outputs
```python
@dataclass
class IncidentReport:
    incident_id: str
    created_at: datetime
    report_type: str               # "POST_MORTEM" | "COMPLIANCE" | "AUDIT" | "METRICS"
    title: str
    summary: str
    root_cause: str
    timeline: list[dict]           # Chronological events
    contributing_factors: list[str]
    preventive_measures: list[str]
    lessons_learned: str
    action_items: list[str]
    severity_distribution: dict    # {LOW: 10, MEDIUM: 5, HIGH: 2, CRITICAL: 1}

@dataclass
class ComplianceReport:
    period: str                    # "2026-07" (July 2026)
    pii_incidents: int
    breaches: int
    controls_applied: int
    failed_controls: int
    avg_resolution_time_hours: float
    sla_compliance_percentage: float
    audit_trail_count: int
    recommendations: list[str]

@dataclass
class AuditLog:
    timestamp: datetime
    action: str                    # "INCIDENT_CREATED", "CONTROL_APPLIED", "DATA_ACCESSED"
    actor: str                     # User or system component
    resource: str                  # incident-001, service-name, etc.
    status: str                    # SUCCESS, FAILURE
    details: dict                  # Contextual details
    change_diff: dict              # Before/after state
```

### Report Types
```
1. POST_MORTEM
   - What happened?
   - Why did it happen?
   - What controls failed?
   - How to prevent?

2. COMPLIANCE
   - PII incidents: 0
   - Confirmed breaches: 0
   - Control effectiveness: 98%
   - Audit trail completeness: 100%

3. AUDIT
   - 1,234 actions logged
   - All actions authenticated
   - No data access anomalies
   - Immutable audit trail maintained

4. METRICS
   - MTTR: 15 minutes (down from 45 min)
   - MTBF: 720 hours (up from 480 hours)
   - Error rate: 0.05% (SLA: 0.1%)
   - Incident prevention: 89% (prevented via controls)
```

### API Endpoints
```
GET /api/reports/incident/{incident_id}
GET /api/reports/compliance?period=2026-07
GET /api/reports/audit?start_date=2026-07-01&end_date=2026-07-31
GET /api/reports/metrics?period=30d
POST /api/reports/generate (trigger report generation)
GET /api/reports/history
```

### Example Report
```json
{
  "incident_id": "incident-20260722-001",
  "report_type": "POST_MORTEM",
  "title": "payments-api Database Connection Exhaustion",
  "root_cause": "Connection pool not returned after query timeout (bug in v2.1.5)",
  "timeline": [
    {"time": "2026-07-22T14:30:00Z", "event": "Error rate spike detected"},
    {"time": "2026-07-22T14:31:00Z", "event": "Incident created, severity=CRITICAL"},
    {"time": "2026-07-22T14:32:00Z", "event": "Rate limiting control applied"},
    {"time": "2026-07-22T14:35:00Z", "event": "Service recovered"}
  ],
  "preventive_measures": [
    "Upgrade to v2.1.6 (contains fix)",
    "Add connection pool monitoring alerts",
    "Implement automated rollback for high error rates"
  ]
}
```

---

## Integration Architecture

### Data Flow
```
[Raw Logs]
    ↓
[Privacy Agent] → Redacts PII, flags sensitive data
    ↓
[Noise Agent] → Groups redundant logs, calculates ROI
    ↓
[Incident Agent] → Detects incidents, aggregates alerts
    ↓
[Dependency Agent] → Maps service dependencies
    ↓
[Impact Agent] → Quantifies business impact
    ↓
[Control Agent] → Applies remediation controls
    ↓
[Recovery Agent] → Monitors and orchestrates recovery
    ↓
[Report Agent] → Generates compliance & audit reports
    ↓
[Remediation Agent] → Creates GitHub PRs for code fixes
```

### Cross-Agent Communication
```python
# Shared State/Database
class AgentState:
    incidents: dict[str, Incident]
    dependencies: ServiceGraph
    controls_applied: dict[str, Control]
    recovery_plans: dict[str, RecoveryPlan]
    audit_logs: list[AuditLog]
    metrics_history: list[dict]
```

### Event-Driven Triggers
```
Incident created → Trigger Dependency Agent (map impact)
Impact assessed → Trigger Control Agent (apply remedies)
Control applied → Trigger Recovery Agent (monitor health)
Recovery complete → Trigger Report Agent (generate RCA)
Report generated → Log to audit trail
```

---

## Implementation Roadmap

### Phase 1 (Weeks 1-2): Core Infrastructure
- [ ] Design unified agent interface (all agents inherit from `BaseAgent`)
- [ ] Build event bus for inter-agent communication
- [ ] Create shared state management (incident registry, audit logs)
- [ ] Implement Incident Agent (MVP)

### Phase 2 (Weeks 3-4): Dependency & Impact
- [ ] Implement Dependency Agent (service graph)
- [ ] Implement Impact Agent (business metrics)
- [ ] Build visualization dashboard (service graph, impact metrics)

### Phase 3 (Weeks 5-6): Control & Recovery
- [ ] Implement Control Agent (policy enforcement)
- [ ] Implement Recovery Agent (staged recovery)
- [ ] Build control policy DSL/UI

### Phase 4 (Weeks 7-8): Reporting & Testing
- [ ] Implement Report Agent (post-mortem, compliance)
- [ ] Build reporting dashboard
- [ ] End-to-end testing & integration
- [ ] Performance optimization

### Phase 5 (Ongoing): Enhancements
- [ ] ML-based incident prediction
- [ ] Advanced dependency analysis (ML clustering)
- [ ] Automated chaos engineering for resilience testing
- [ ] Integration with PagerDuty/Slack/Datadog

---

## Technology Stack

### New Dependencies
```
# Event Bus
confluent-kafka==2.3.0  # or: aio-pika (RabbitMQ), redis (pub/sub)

# Time Series DB (for metrics history)
influxdb-client==1.18.0  # or: prometheus-client, clickhouse-driver

# Distributed Tracing (optional)
opentelemetry-api==1.18.0
opentelemetry-sdk==1.18.0
opentelemetry-exporter-jaeger==1.18.0

# Graphing (dependency visualization)
networkx==3.1

# Advanced ML (optional, for predictions)
scikit-learn==1.5.1  # Already have this
xgboost==2.0.0      # For incident prediction
```

### Updated `requirements.txt`
```
# Existing
fastapi==0.115.6
uvicorn[standard]==0.34.0
pydantic==2.10.4
google-generativeai==0.3.0
sentence-transformers==3.0.1
scikit-learn==1.5.1
PyGithub==2.4.0

# New for agents
confluent-kafka==2.3.0
influxdb-client==1.18.0
networkx==3.1
```

---

## File Structure

```
backend/agents/
  ├── __init__.py
  ├── base_agent.py                 # NEW: Abstract base class
  ├── privacy_agent.py              # Existing
  ├── noise_agent.py                # Existing
  ├── remediation_agent.py          # Existing
  ├── incident_agent.py             # NEW
  ├── dependency_agent.py           # NEW
  ├── impact_agent.py               # NEW
  ├── control_agent.py              # NEW
  ├── recovery_agent.py             # NEW
  ├── report_agent.py               # NEW
  └── event_bus.py                  # NEW: Inter-agent communication

backend/
  ├── pipeline.py                   # Existing (refactor to use event bus)
  ├── main.py                       # Existing (add new endpoints)
  ├── models/
  │   ├── __init__.py               # NEW: Pydantic models for all agents
  │   ├── incidents.py
  │   ├── dependencies.py
  │   ├── impact.py
  │   ├── controls.py
  │   ├── recovery.py
  │   └── reports.py
  └── storage/
      ├── __init__.py               # NEW: Persistence layer
      ├── audit_log.py
      ├── incident_store.py
      ├── metrics_store.py
      └── state_store.py
```

---

## Success Metrics

- **Incident Detection**: < 30s from event to incident creation
- **Control Execution**: < 5s from incident to control application
- **Recovery Time**: Automated recovery reduces MTTR from 45min → 5min
- **False Positive Rate**: < 5% (measured via user feedback)
- **Audit Compliance**: 100% of actions logged immutably
- **SLA Compliance**: 99.95% (from current 98%)

---

## Next Steps

1. Review this plan with team
2. Prioritize agents (recommend: Incident → Dependency → Impact → Control)
3. Design base agent interface
4. Build event bus prototype
5. Implement Incident Agent as MVP
6. Iterate based on feedback

