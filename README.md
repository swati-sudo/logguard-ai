# LogGuard AI

**Agentic Observability & Privacy Engine** — a hackathon demo for Deutsche Bank showing real-time PII containment, log noise reduction, and automated code remediation.

## Architecture

```
[Raw Log Stream]
       │
       ▼
┌───────────────┐
│ Privacy Agent │ ──► PII/Credentials → Redact → Alert (PagerDuty/Slack)
└───────────────┘
       │
       ▼
┌───────────────┐
│  Noise Agent  │ ──► Group redundant logs → Calculate storage ROI
└───────────────┘
       │
       ▼
┌───────────────┐
│ Remediation   │ ──► Trace to source → Generate PR patch
│    Agent      │
└───────────────┘
```

## Pitch Metrics

| Metric | Value |
|--------|-------|
| Alert fatigue reduction | **99.9%** |
| PII containment | **Sub-second** (<420ms) |
| Log noise suppressed | **42%** |
| Monthly savings | **€14,000** (Splunk/Datadog ingestion) |

## Quick Start

### 1. Backend

```bash
cd logguard-ai/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 2. Frontend

```bash
cd logguard-ai/frontend
npm install
npm run dev
```

Open **http://localhost:5173**

## Demo Features

- **Live Log Stream** — SSE-fed banking microservice logs with real-time redaction
- **3-Agent Pipeline** — animated Privacy → Noise → Remediation workflow
- **ROI Dashboard** — before/after storage cost chart with € savings
- **Security Alerts** — mock PagerDuty/Slack PII containment events
- **Zero-Leak Code Playground** — paste vulnerable Java, get instant secure patch
- **Mock PR Preview** — GitHub-style diff with auto-generated fix

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/stream/logs` | GET (SSE) | Live log stream |
| `/api/analyze/code` | POST | Analyze pasted source code |
| `/api/metrics/roi` | GET | Noise & cost metrics |
| `/api/alerts` | GET | Recent PII alerts |
| `/api/noise/top` | GET | Top noisy log patterns |
| `/api/remediation/pr/{id}` | GET | Mock PR diff |

## Production Roadmap

- Real GitHub/GitLab PR creation via API
- PagerDuty & Slack webhook integrations
- Live Splunk/Datadog log ingestion
- On-prem NER models for advanced PII detection
- Optional LLM agent layer for complex contextual analysis

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, SSE
- **Frontend:** React, TypeScript, Vite, Tailwind CSS, Recharts
- **LLM/AI:** Google Gemini API (with service account support)
- **Agents:** Deterministic regex/rules + LLM enhancement (optional)
