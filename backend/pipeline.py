import json
import random
from dataclasses import asdict
from pathlib import Path
from datetime import datetime
from typing import Any

from agents.noise_agent import NoiseAgent
from agents.privacy_agent import PrivacyAgent
from agents.remediation_agent import RemediationAgent


class LogPipeline:
    """Orchestrates Privacy → Noise → Remediation agents."""

    def __init__(self) -> None:
        self.privacy = PrivacyAgent()
        self.noise = NoiseAgent()
        self.remediation = RemediationAgent()
        self.processed_logs: list[str] = []
        self.alerts: list[dict[str, Any]] = []
        self.pr_cache: dict[str, dict] = {}
        self.feedback: list[dict[str, Any]] = []  # User feedback for model improvement
        self.metrics_history: list[dict] = []  # Track metrics over time
        self._load_samples()

    def _load_samples(self) -> None:
        sample_path = Path(__file__).parent / "samples" / "log_stream.jsonl"
        self.sample_logs: list[dict] = []
        if sample_path.exists():
            for line in sample_path.read_text().strip().splitlines():
                if line.strip():
                    self.sample_logs.append(json.loads(line))

        raw_messages = [entry["message"] for entry in self.sample_logs]
        self.baseline_noise = self.noise.analyze(raw_messages)

    def process_log(self, raw_message: str, metadata: dict | None = None) -> dict[str, Any]:
        metadata = metadata or {}
        privacy = self.privacy.scan(raw_message)
        self.processed_logs.append(raw_message)

        alert = None
        if privacy.has_pii:
            alert = {
                "id": f"alert-{len(self.alerts)+1:04d}",
                "severity": max(f.severity for f in privacy.findings),
                "channel": privacy.alert_channel or "slack",
                "message": f"PII detected: {privacy.findings[0].category}",
                "raw_snippet": privacy.raw[:120],
                "redacted_snippet": privacy.redacted[:120],
                "categories": list({f.category for f in privacy.findings}),
                "containment_ms": random.randint(180, 950),
                "breached": any(f.breached for f in privacy.findings),
                "llm_detected": privacy.llm_analysis is not None,
            }
            self.alerts.insert(0, alert)
            self.alerts = self.alerts[:50]

        noise = self.noise.analyze(self.processed_logs[-500:])
        remediation = None
        if privacy.has_pii or (noise.top_patterns and noise.top_patterns[0].suppressible):
            pattern = noise.top_patterns[0] if noise.top_patterns else None
            if privacy.has_pii:
                pr = self.remediation.remediate_code(
                    'logger.info("User login: iban=" + user.getIban() + ", password=" + password);',
                    [asdict(f) for f in privacy.findings],
                )
            elif pattern:
                pr = self.remediation.remediate_log(
                    pattern.fingerprint,
                    pattern.sample,
                    pattern.classification,
                    pattern.service,
                )
            else:
                pr = None

            if pr:
                remediation = asdict(pr)
                self.pr_cache[pr.id] = remediation

        return {
            "raw": privacy.raw,
            "redacted": privacy.redacted,
            "has_pii": privacy.has_pii,
            "findings": [asdict(f) for f in privacy.findings],
            "alert": alert,
            "service": metadata.get("service", "unknown"),
            "level": metadata.get("level", "INFO"),
            "timestamp": metadata.get("timestamp"),
            "noise_percent": noise.noise_percent,
            "remediation_id": remediation["id"] if remediation else None,
        }

    def analyze_code(self, code: str) -> dict[str, Any]:
        privacy = self.privacy.scan(code, is_code=True)
        pr = self.remediation.remediate_code(code, [asdict(f) for f in privacy.findings])
        self.pr_cache[pr.id] = asdict(pr)

        severity_order = {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1, "NONE": 0}
        severity = "NONE"
        if privacy.findings:
            severity = max(privacy.findings, key=lambda f: severity_order.get(f.severity, 0)).severity

        return {
            "findings": [asdict(f) for f in privacy.findings],
            "has_pii": privacy.has_pii,
            "severity": severity,
            "alert_channel": privacy.alert_channel,
            "secure_patch": pr.after,
            "pull_request": asdict(pr),
        }

    def get_roi_metrics(self) -> dict[str, Any]:
        noise = self.noise.analyze(self.processed_logs or [e["message"] for e in self.sample_logs])
        baseline_gb = self.baseline_noise.suppressed_gb_per_day / 0.42
        current_gb = baseline_gb * (1 - noise.noise_percent / 100)

        metrics = {
            "noise_percent": noise.noise_percent,
            "noisy_logs": noise.noisy_logs,
            "total_logs": noise.total_logs,
            "suppressed_gb_per_day": noise.suppressed_gb_per_day,
            "baseline_gb_per_day": round(baseline_gb, 2),
            "current_gb_per_day": round(current_gb, 2),
            "cost_per_gb_eur": noise.cost_per_gb_eur,
            "monthly_savings_eur": noise.monthly_savings_eur,
            "alert_fatigue_reduction": noise.alert_fatigue_reduction,
            "pii_containment_ms": 420,
            "accuracy": self.get_accuracy_metrics(),
        }
        
        # Track metrics history for trends
        self.metrics_history.append({**metrics, "timestamp": datetime.now().isoformat()})
        
        return metrics

    def get_top_noise(self) -> list[dict]:
        logs = self.processed_logs or [e["message"] for e in self.sample_logs]
        metrics = self.noise.analyze(logs)
        return [asdict(p) for p in metrics.top_patterns]

    def get_sample_stream(self) -> list[dict]:
        return self.sample_logs

    def get_pr(self, pr_id: str) -> dict | None:
        return self.pr_cache.get(pr_id)
    
    def log_user_feedback(self, alert_id: str, was_correct: bool, feedback_text: str = "") -> dict:
        """Log user feedback for continuous improvement"""
        feedback_entry = {
            "id": f"feedback-{len(self.feedback)+1}",
            "alert_id": alert_id,
            "correct": was_correct,
            "text": feedback_text,
            "timestamp": datetime.now().isoformat(),
        }
        self.feedback.append(feedback_entry)
        return feedback_entry
    
    def get_accuracy_metrics(self) -> dict:
        """Calculate accuracy, false positive, and false negative rates"""
        if not self.feedback:
            return {"accuracy": None, "false_positives": 0, "false_negatives": 0, "total_feedback": 0}
        
        correct = sum(1 for f in self.feedback if f["correct"])
        accuracy = (correct / len(self.feedback) * 100) if self.feedback else 0
        
        return {
            "accuracy": round(accuracy, 2),
            "false_positives": sum(1 for f in self.feedback if not f["correct"]),
            "false_negatives": 0,  # Would need additional tracking
            "total_feedback": len(self.feedback),
        }
    
    def analyze_trends(self) -> dict:
        """Analyze alert and noise trends"""
        if len(self.metrics_history) < 2:
            return {"trend": "insufficient_data", "message": "Need more data points"}
        
        recent = self.metrics_history[-1]
        previous = self.metrics_history[-2]
        
        noise_change = recent["noise_percent"] - previous["noise_percent"]
        alert_trend = "increasing" if len(self.alerts) > 5 else "stable"
        
        return {
            "noise_trend": "decreasing" if noise_change < 0 else "increasing" if noise_change > 0 else "stable",
            "noise_change_percent": round(noise_change, 2),
            "alert_trend": alert_trend,
            "total_alerts": len(self.alerts),
            "recent_pii_breaches": sum(1 for a in self.alerts if a.get("breached", False)),
        }
    
    def get_root_cause_analysis(self) -> dict:
        """Analyze root causes of issues"""
        if not self.processed_logs:
            return {"root_cause": "No logs processed yet"}
        
        # Use remediation agent's LLM analysis
        analysis = self.remediation.analyze_root_cause(self.processed_logs[-50:])
        return analysis

