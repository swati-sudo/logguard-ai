# LogGuard AI — 5-Minute Judge Demo Script

## Setup (before judges arrive)

1. Start backend: `cd backend && source .venv/bin/activate && uvicorn main:app --port 8000`
2. Start frontend: `cd frontend && npm run dev`
3. Open http://localhost:5173 on a large display

---

## Demo Flow (~5 minutes)

### 1. Introduction (30 sec)

> "Deutsche Bank generates terabytes of logs daily. Two problems: **log pollution** — millions of useless warnings masking real crashes — and **data leakage** — IBANs, passwords, and tokens printed into unencrypted logs.
>
> LogGuard AI is a 3-agent system that acts as an automated, real-time code reviewer and log cleaner."

Point to the **3-Agent Pipeline** header.

---

### 2. Start Live Ingestion (60 sec)

Click **Start Ingestion**.

> "Raw logs flow in from auth-service, payments-api, and kyc-worker. Watch the Privacy Agent — it scans every line in real time."

When a **red PII row** appears:

> "There — IBAN and credentials detected. The raw line is struck through; the redacted version is what gets stored. A PagerDuty alert fires in under a second."

Point to the **Security Alerts** panel showing containment time in ms.

---

### 3. ROI Dashboard (60 sec)

Point to **Storage ROI Calculator**:

> "The Noise Agent groups redundant patterns — connection retries, deprecated API warnings, cache misses. Over 24 hours, 42% of log volume is suppressible noise.
>
> That's €14,000 per month saved in Splunk/Datadog ingestion costs. And 99.9% reduction in alert fatigue — no more 3 AM wake-ups for harmless retry warnings."

Show the before/after bar chart.

---

### 4. Remediation PR (60 sec)

Click **View PR →** on a flagged log row.

> "The Remediation Agent traces the log back to the exact microservice and line of code. It auto-generates a fix — downgrading log level from warn to debug, or applying masking functions — and opens a pull request for the team to merge."

Show the GitHub-style diff with **Demo Mode** badge.

---

### 5. Zero-Leak Code Playground (60 sec)

Scroll to **Zero-Leak Code Playground** (pre-loaded with vulnerable code):

```java
logger.info("User login: iban=" + user.getIban() + ", password=" + password);
```

Click **Analyze Code**:

> "A developer pastes code during review. LogGuard flags the PII and credential leak instantly, blocks it, and generates a secure patch — password removed, IBAN masked with maskIban()."

Show the secure patch and embedded PR preview.

---

### 6. Close (30 sec)

> "Three agents, one pipeline:
> - **99.9%** alert fatigue reduction
> - **Sub-second** PII containment
> - **Self-healing codebase** — logging hygiene improves automatically via PRs
>
> LogGuard AI — agentic observability and privacy for modern banking."

---

## Backup Talking Points

- Agents use NER-style pattern matching today; production roadmap includes on-prem models
- Integrations ready for GitHub, PagerDuty, Slack, Splunk (demo uses mocks for reliability)
- Top noisy patterns table shows actionable CHATTY_RETRY and DEPRECATED_WARN classifications
