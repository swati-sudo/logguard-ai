export interface PrivacyFinding {
  severity: string;
  category: string;
  matched_text: string;
  redacted_value: string;
  breached?: boolean;
  breach_severity?: string;
}

export interface LogEntry {
  raw: string;
  redacted: string;
  has_pii: boolean;
  findings: PrivacyFinding[];
  alert: Alert | null;
  service: string;
  level: string;
  timestamp?: string;
  noise_percent: number;
  remediation_id: string | null;
}

export interface Alert {
  id: string;
  severity: string;
  channel: string;
  message: string;
  raw_snippet: string;
  redacted_snippet: string;
  categories: string[];
  containment_ms: number;
  breached?: boolean;
  llm_detected?: boolean;
}

export interface ROIMetrics {
  noise_percent: number;
  noisy_logs: number;
  total_logs: number;
  suppressed_gb_per_day: number;
  baseline_gb_per_day: number;
  current_gb_per_day: number;
  cost_per_gb_eur: number;
  monthly_savings_eur: number;
  alert_fatigue_reduction: number;
  pii_containment_ms: number;
  accuracy?: { accuracy: number | null; false_positives: number; total_feedback: number };
}

export interface NoisyPattern {
  fingerprint: string;
  sample: string;
  count: number;
  classification: string;
  service: string;
  suppressible: boolean;
}

export interface PullRequest {
  id: string;
  title: string;
  branch: string;
  service: string;
  file_path: string;
  line_number: number;
  reviewer: string;
  before: string;
  after: string;
  diff: string;
  fix_type: string;
  github_url?: string;
}

export interface AgentStatus {
  privacy: string;
  noise: string;
  remediation: string;
}

export interface StreamEvent {
  type: string;
  data: LogEntry;
  agent_status: AgentStatus;
}

export interface CodeAnalysisResult {
  findings: PrivacyFinding[];
  has_pii: boolean;
  severity: string;
  alert_channel: string | null;
  secure_patch: string;
  pull_request: PullRequest;
}

export interface AccuracyMetrics {
  accuracy: number | null;
  false_positives: number;
  false_negatives: number;
  total_feedback: number;
}

export interface TrendAnalysis {
  noise_trend: string;
  noise_change_percent: number;
  alert_trend: string;
  total_alerts: number;
  recent_pii_breaches: number;
}

export interface RootCauseAnalysis {
  root_cause: string;
  severity: string;
  action: string;
}
