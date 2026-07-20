import os
import re
import hashlib
import json
from dataclasses import dataclass, field
from typing import Optional
import requests
from pathlib import Path

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


@dataclass
class PrivacyFinding:
    severity: str  # CRITICAL, HIGH, MEDIUM
    category: str
    matched_text: str
    redacted_value: str
    breached: bool = False
    breach_severity: Optional[str] = None


@dataclass
class PrivacyResult:
    raw: str
    redacted: str
    has_pii: bool
    findings: list[PrivacyFinding] = field(default_factory=list)
    alert_channel: Optional[str] = None
    llm_analysis: Optional[dict] = None


class PrivacyAgent:
    """Detects and redacts PII/credentials in logs and source code."""
    
    def __init__(self):
        self.enable_llm = os.getenv("ENABLE_LLM_DETECTION", "false").lower() == "true"
        self.enable_breach_check = os.getenv("ENABLE_BREACH_CHECK", "false").lower() == "true"
        self.client = None
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
        
        if self.enable_llm and GEMINI_AVAILABLE:
            try:
                service_account_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
                if service_account_path and Path(service_account_path).exists():
                    # Configure Gemini with service account
                    with open(service_account_path) as f:
                        service_account_info = json.load(f)
                    genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))
                    self.client = genai.GenerativeModel(self.model_name)
                elif os.getenv("GEMINI_API_KEY"):
                    # Fallback to API key if service account not configured
                    genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))
                    self.client = genai.GenerativeModel(self.model_name)
            except Exception as e:
                print(f"Failed to initialize Gemini client: {e}")
                self.client = None

    PATTERNS: list[tuple[str, str, str, str]] = [
        (r"\bpassword\s*[=:]\s*[^\s,;\"']+", "CRITICAL", "credential", "[REDACTED_PASSWORD]"),
        (r"\bpasswd\s*[=:]\s*[^\s,;\"']+", "CRITICAL", "credential", "[REDACTED_PASSWORD]"),
        (r"password\s*\+\s*\w+", "CRITICAL", "credential", "[REDACTED_PASSWORD]"),
        (r"Bearer\s+[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+", "CRITICAL", "jwt", "[REDACTED_JWT]"),
        (r"\bsk_live_[A-Za-z0-9]{16,}", "CRITICAL", "api_key", "[REDACTED_API_KEY]"),
        (r"\bapi[_-]?key\s*[=:]\s*[A-Za-z0-9_\-]{16,}", "CRITICAL", "api_key", "[REDACTED_API_KEY]"),
        (r"\bDE\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{2}\b", "HIGH", "iban", "DE** **** **** **** **** **"),
        (r"\biban\s*[=:]\s*[A-Z]{2}\d{2}[A-Z0-9\s]{10,30}", "HIGH", "iban", "iban=[REDACTED_IBAN]"),
        (r"iban\s*\+\s*\w+", "HIGH", "iban", "iban=[REDACTED_IBAN]"),
        (r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b", "HIGH", "credit_card", "****-****-****-****"),
        (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "MEDIUM", "email", "[REDACTED_EMAIL]"),
        (r"\bpassport\s*[=:]\s*[A-Z0-9]{6,12}", "HIGH", "passport", "[REDACTED_PASSPORT]"),
        (r"clientName\s*[=:]\s*[\"'][^\"']+[\"']", "MEDIUM", "name", "clientName=[REDACTED_NAME]"),
    ]

    CODE_PATTERNS: list[tuple[str, str, str]] = [
        (r"password", "CRITICAL", "logging_password"),
        (r"iban", "HIGH", "logging_iban_concat"),
        (r'System\.out\.print[^)]*(password|iban|ssn)[^)]*\)', "CRITICAL", "stdout_leak"),
    ]

    def check_breach_database(self, credential: str) -> dict:
        """Check if password/credential is in known breaches (HaveIBeenPwned-style)"""
        if not self.enable_breach_check:
            return {"breached": False}
        
        try:
            # Simple hash-based check (in production, use actual HIBP API)
            sha1_hash = hashlib.sha1(credential.encode()).hexdigest().upper()
            prefix = sha1_hash[:5]
            suffix = sha1_hash[5:]
            
            response = requests.get(
                f"https://api.pwnedpasswords.com/range/{prefix}",
                headers={"User-Agent": "LogGuard-AI"},
                timeout=2
            )
            
            if suffix in response.text:
                return {
                    "breached": True,
                    "severity": "CRITICAL",
                    "action": "ROTATE_IMMEDIATELY",
                    "message": "Credential found in known breach database"
                }
        except Exception as e:
            # Fail safely — if breach check fails, don't block
            pass
        
        return {"breached": False}

    def _redact_with_llm(self, text: str) -> tuple[str, dict]:
        """Use LLM for context-aware redaction"""
        if not self.client:
            return text, {}
        
        try:
            prompt = f"""Redact all PII from this log while preserving structure and meaning.
Replace PII with [REDACTED_TYPE]. Keep everything else identical.

Log: {text[:500]}

Respond with ONLY the redacted text, no explanation."""
            
            response = self.client.generate_content(prompt)
            redacted = response.text.strip()
            return redacted, {"llm_model": self.model_name, "method": "context_aware"}
        except Exception as e:
            return text, {"error": str(e), "method": "fallback"}

    def scan(self, text: str, *, is_code: bool = False) -> PrivacyResult:
        findings: list[PrivacyFinding] = []
        redacted = text
        llm_analysis = None

        # Phase 1: Regex-based detection (fast)
        for pattern, severity, category, replacement in self.PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                matched_val = match.group(0)[:80]
                finding = PrivacyFinding(
                    severity=severity,
                    category=category,
                    matched_text=matched_val,
                    redacted_value=replacement,
                )
                
                # Check if credential is breached
                if category in ("credential", "api_key", "jwt"):
                    breach_check = self.check_breach_database(matched_val)
                    if breach_check.get("breached"):
                        finding.breached = True
                        finding.breach_severity = breach_check.get("severity")
                
                findings.append(finding)
                redacted = re.sub(re.escape(match.group(0)), replacement, redacted, count=1)

        # Phase 2: Code pattern detection
        if is_code:
            for pattern, severity, category in self.CODE_PATTERNS:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    findings.append(
                        PrivacyFinding(
                            severity=severity,
                            category=category,
                            matched_text=match.group(0)[:120],
                            redacted_value="[SECURE_LOGGING_REQUIRED]",
                        )
                    )

        # Phase 3: LLM-based detection for edge cases (slow, only if enabled)
        if self.enable_llm and not findings and len(text) < 1000:
            try:
                prompt = f"""Does this log/code contain PII (names, IDs, passwords, secrets, API keys)?
Be conservative — only flag if clearly PII.

Text: {text[:300]}

Respond: YES or NO only."""
                
                response = self.client.generate_content(prompt)
                llm_response = response.text.strip().upper()
                if "YES" in llm_response:
                    # Use LLM to redact
                    llm_redacted, llm_info = self._redact_with_llm(text)
                    redacted = llm_redacted
                    llm_analysis = llm_info
                    findings.append(
                        PrivacyFinding(
                            severity="MEDIUM",
                            category="llm_detected_pii",
                            matched_text="[LLM detected potential PII]",
                            redacted_value="[REDACTED_BY_LLM]",
                        )
                    )
            except Exception as e:
                # LLM detection failed, continue with regex findings
                llm_analysis = {"error": str(e)}

        has_pii = len(findings) > 0
        alert_channel = None
        if has_pii:
            severities = {f.severity for f in findings}
            if "CRITICAL" in severities:
                alert_channel = "pagerduty"
            elif "HIGH" in severities:
                alert_channel = "slack"
            
            # Upgrade alert channel if breach detected
            if any(f.breached for f in findings):
                alert_channel = "pagerduty"

        return PrivacyResult(
            raw=text,
            redacted=redacted,
            has_pii=has_pii,
            findings=findings,
            alert_channel=alert_channel,
            llm_analysis=llm_analysis,
        )
