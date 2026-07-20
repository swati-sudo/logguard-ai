import os
import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

try:
    from github import Github
    GITHUB_AVAILABLE = True
except ImportError:
    GITHUB_AVAILABLE = False


@dataclass
class PullRequest:
    id: str
    title: str
    branch: str
    service: str
    file_path: str
    line_number: int
    reviewer: str
    before: str
    after: str
    diff: str
    fix_type: str
    github_url: Optional[str] = None
    created_at: Optional[str] = None


class RemediationAgent:
    """Traces noisy/leaking logs to source code and generates patches."""

    def __init__(self) -> None:
        map_path = Path(__file__).parent.parent / "samples" / "log_source_map.json"
        if map_path.exists():
            self.source_map: dict = json.loads(map_path.read_text())
        else:
            self.source_map = {}
        
        self.enable_llm = os.getenv("ENABLE_LLM_DETECTION", "false").lower() == "true"
        self.enable_github = os.getenv("ENABLE_GITHUB_INTEGRATION", "false").lower() == "true"
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
        self.client = None
        
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
        
        if self.enable_github and GITHUB_AVAILABLE:
            try:
                self.github = Github(os.getenv("GITHUB_TOKEN", ""))
            except Exception:
                self.github = None
        else:
            self.github = None

    def _make_diff(self, before: str, after: str) -> str:
        lines = []
        lines.append(f"- {before.strip()}")
        lines.append(f"+ {after.strip()}")
        return "\n".join(lines)

    def _fix_code_with_llm(self, code: str, findings: list) -> str:
        """Use LLM to generate context-aware fix"""
        if not self.client:
            return self._fix_code_template(code, findings)
        
        try:
            finding_summary = "\n".join([f"- {f.get('category', 'unknown')}: {f.get('matched_text', '')}" for f in findings])
            
            prompt = f"""Fix this code to remove PII/credential leakage. 
Respond with ONLY the fixed code, no explanation.

Original:
{code}

Issues:
{finding_summary}

Guidelines:
- Remove all credentials and sensitive data
- Use masking functions like maskIban(), maskPassword()
- Add comments explaining the fix
- Keep the functionality intact"""
            
            response = self.client.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            return self._fix_code_template(code, findings)

    def _fix_code_template(self, code: str, findings: list) -> str:
        """Fallback template-based code fixing"""
        fixed = code.strip()
        
        if re.search(r"iban", code, re.I) and re.search(r"password", code, re.I):
            fixed = (
                'logger.debug("User login: iban={}", maskIban(user.getIban()));\n'
                "// password removed — never log credentials"
            )
        elif re.search(r"password", code, re.I):
            fixed = re.sub(
                r"logger\.(info|warn)\([^)]*password[^)]*\)",
                'logger.debug("Auth event processed"); // password removed — never log credentials',
                fixed,
                flags=re.I,
            )
        elif re.search(r"iban", code, re.I):
            fixed = 'logger.debug("User login: iban={}", maskIban(user.getIban()));'
        
        if fixed == code.strip() and re.search(r"logger\.(warn|info)", code):
            fixed = re.sub(r"logger\.warn", "logger.debug", code)
        
        return fixed

    def remediate_code(self, code: str, findings: list) -> PullRequest:
        """Generate PR to fix PII leakage in code"""
        
        # Use LLM if available, fallback to template
        fixed = self._fix_code_with_llm(code, findings) if self.client else self._fix_code_template(code, findings)
        
        pr_id = f"pr-{str(uuid.uuid4())[:8]}"
        
        pr = PullRequest(
            id=pr_id,
            title="fix(security): remove PII/credential leakage detected by LogGuard",
            branch=f"logguard/fix-pii-{pr_id}",
            service="detected-service",
            file_path="src/main/java/com/db/auth/Controller.java",
            line_number=42,
            reviewer="@security-team",
            before=code.strip(),
            after=fixed.strip(),
            diff=self._make_diff(code, fixed),
            fix_type="secure_logging",
        )
        
        # Try to create real GitHub PR if enabled
        if self.enable_github and self.github:
            pr = self._create_github_pr(pr)
        
        return pr

    def remediate_log(
        self,
        fingerprint: str,
        sample: str,
        classification: str,
        service: str,
    ) -> PullRequest:
        """Generate PR to fix noisy logging pattern"""
        mapping = self.source_map.get(fingerprint) or self._default_mapping(service, classification)

        before = mapping.get("before", sample[:120])
        after = mapping.get("after", self._template_fix(before, classification))
        pr_id = f"pr-{service}-{str(uuid.uuid4())[:6]}"

        pr = PullRequest(
            id=pr_id,
            title=mapping.get("title", f"fix(logging): reduce {classification} noise in {service}"),
            branch=mapping.get("branch", f"logguard/fix-noise-{service}"),
            service=service,
            file_path=mapping.get("file", f"src/main/java/com/db/{service}/Handler.java"),
            line_number=mapping.get("line", 42),
            reviewer=mapping.get("reviewer", "@platform-eng"),
            before=before,
            after=after,
            diff=self._make_diff(before, after),
            fix_type=mapping.get("fix_type", classification.lower()),
        )
        
        # Try to create real GitHub PR if enabled
        if self.enable_github and self.github:
            pr = self._create_github_pr(pr)
        
        return pr

    def _create_github_pr(self, pr: PullRequest) -> PullRequest:
        """Create actual GitHub pull request"""
        if not self.github:
            return pr
        
        try:
            repo_name = os.getenv("GITHUB_REPO", "")
            if not repo_name:
                return pr
            
            repo = self.github.get_repo(repo_name)
            main_branch = repo.get_branch("main")
            
            # Create feature branch
            try:
                repo.create_git_ref(
                    ref=f"refs/heads/{pr.branch}",
                    sha=main_branch.commit.sha
                )
            except Exception:
                # Branch already exists, that's ok
                pass
            
            # Get current file content
            try:
                file_content = repo.get_contents(pr.file_path)
                sha = file_content.sha
            except Exception:
                # File doesn't exist, create it
                sha = None
            
            # Update/create file
            if sha:
                repo.update_file(
                    path=pr.file_path,
                    message=pr.title,
                    content=pr.after,
                    branch=pr.branch,
                    sha=sha
                )
            else:
                repo.create_file(
                    path=pr.file_path,
                    message=pr.title,
                    content=pr.after,
                    branch=pr.branch
                )
            
            # Create pull request
            github_pr = repo.create_pull(
                title=pr.title,
                body=f"**LogGuard AI Auto-Generated Fix**\n\n{pr.fix_type.upper()}\n\n```diff\n{pr.diff}\n```",
                head=pr.branch,
                base="main"
            )
            
            pr.github_url = github_pr.html_url
            return pr
        except Exception as e:
            # GitHub PR creation failed, return mock PR
            return pr

    def analyze_root_cause(self, logs: list[str]) -> dict:
        """Use LLM to find root cause from log sequence"""
        if not self.client or len(logs) == 0:
            return {"root_cause": "Unable to analyze", "severity": "UNKNOWN", "action": "Check logs manually"}
        
        try:
            log_summary = "\n".join(logs[-10:])
            
            prompt = f"""Analyze these logs from a banking microservice. What's the likely root cause?

{log_summary}

Respond in JSON: {{"root_cause": "...", "severity": "HIGH|MEDIUM|LOW", "action": "..."}}"""
            
            response = self.client.generate_content(prompt)
            response_text = response.text.strip()
            # Extract JSON from response
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(response_text[start:end])
        except Exception as e:
            pass
        
        return {"root_cause": "Unable to determine", "severity": "MEDIUM", "action": "Investigate logs manually"}

    def _template_fix(self, before: str, classification: str) -> str:
        """Template-based fix for noisy patterns"""
        if classification == "CHATTY_RETRY":
            return re.sub(r"logger\.warn", "logger.debug", before)
        if classification == "DEPRECATED_WARN":
            return before.replace("logger.warn", "logger.debug") + " // scheduled for removal"
        if "password" in before.lower() or "iban" in before.lower():
            return 'logger.debug("Event processed with masked payload={}", maskSensitive(payload));'
        return re.sub(r"logger\.(warn|info)", "logger.debug", before)

    def _default_mapping(self, service: str, classification: str) -> dict:
        """Default template mapping for common patterns"""
        return {
            "before": f'logger.warn("[{service}] Connection retry attempt {{}}", attempt);',
            "after": f'logger.debug("[{service}] Connection retry attempt {{}}", attempt);',
            "title": f"fix(logging): downgrade {classification} in {service}",
            "branch": f"logguard/fix-noise-{service}",
            "file": f"src/main/java/com/db/{service.replace('-', '/')}/ConnectionPool.java",
            "line": 88,
            "fix_type": "log_level_downgrade",
        }
