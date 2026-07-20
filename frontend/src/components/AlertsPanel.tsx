import { useState } from "react";
import { submitFeedback } from "../hooks/useLogStream";
import type { Alert } from "../types";

interface Props {
  alerts: Alert[];
}

const severityStyles: Record<string, string> = {
  CRITICAL: "border-red-500 bg-red-500/10",
  HIGH: "border-orange-500 bg-orange-500/10",
  MEDIUM: "border-amber-500 bg-amber-500/10",
};

const channelIcons: Record<string, string> = {
  pagerduty: "🚨 PagerDuty",
  slack: "💬 Slack",
};

export default function AlertsPanel({ alerts }: Props) {
  const [feedbackGiven, setFeedbackGiven] = useState<Set<string>>(new Set());

  const handleFeedback = async (alertId: string, wasCorrect: boolean) => {
    try {
      await submitFeedback(alertId, wasCorrect, "");
      setFeedbackGiven((prev) => new Set([...prev, alertId]));
    } catch (error) {
      console.error("Feedback submission failed:", error);
    }
  };

  return (
    <div className="rounded-xl border border-bank-border bg-bank-panel p-4">
      <h2 className="mb-1 text-sm font-semibold uppercase tracking-wider text-slate-400">
        Security Alerts
      </h2>
      <p className="mb-3 text-xs text-slate-500">Real-time PII containment events</p>

      <div className="max-h-64 space-y-2 overflow-y-auto">
        {alerts.length === 0 && (
          <p className="text-xs text-slate-500">No alerts yet — start ingestion</p>
        )}
        {alerts.map((alert) => (
          <div
            key={alert.id}
            className={`rounded-lg border p-3 ${severityStyles[alert.severity] || severityStyles.MEDIUM}`}
          >
            <div className="mb-1 flex items-center justify-between">
              <span className="text-xs font-bold text-red-300">{alert.severity}</span>
              <div className="flex items-center gap-2">
                {alert.breached && (
                  <span className="rounded-full bg-red-600 px-2 py-0.5 text-[10px] font-bold text-white">
                    BREACHED
                  </span>
                )}
                {alert.llm_detected && (
                  <span className="rounded-full bg-blue-600 px-2 py-0.5 text-[10px] font-bold text-white">
                    LLM
                  </span>
                )}
                <span className="text-[10px] text-slate-400">
                  {channelIcons[alert.channel] || alert.channel}
                </span>
              </div>
            </div>
            <p className="text-xs font-medium">{alert.message}</p>
            <p className="mt-1 truncate text-[10px] text-slate-500">{alert.raw_snippet}</p>
            <p className="truncate text-[10px] text-emerald-400">→ {alert.redacted_snippet}</p>
            <p className="mt-1 text-[10px] text-slate-500">
              Contained in {alert.containment_ms}ms
            </p>
            {!feedbackGiven.has(alert.id) && (
              <div className="mt-2 flex gap-2">
                <button
                  onClick={() => handleFeedback(alert.id, true)}
                  className="text-[10px] rounded bg-emerald-500/30 px-2 py-0.5 text-emerald-400 hover:bg-emerald-500/50"
                >
                  ✓ Correct
                </button>
                <button
                  onClick={() => handleFeedback(alert.id, false)}
                  className="text-[10px] rounded bg-red-500/30 px-2 py-0.5 text-red-400 hover:bg-red-500/50"
                >
                  ✗ False Positive
                </button>
              </div>
            )}
            {feedbackGiven.has(alert.id) && (
              <p className="mt-2 text-[10px] text-slate-400">Feedback recorded</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
