import { useCallback, useEffect, useRef, useState } from "react";
import type { AgentStatus, LogEntry, StreamEvent, AccuracyMetrics, TrendAnalysis, RootCauseAnalysis } from "../types";

export function useLogStream() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [agentStatus, setAgentStatus] = useState<AgentStatus>({
    privacy: "idle",
    noise: "idle",
    remediation: "idle",
  });
  const sourceRef = useRef<EventSource | null>(null);

  const start = useCallback(() => {
    if (sourceRef.current) return;

    const source = new EventSource("/api/stream/logs");
    sourceRef.current = source;
    setStreaming(true);

    source.onmessage = (event) => {
      const payload: StreamEvent = JSON.parse(event.data);
      setLogs((prev) => [payload.data, ...prev].slice(0, 80));
      setAgentStatus(payload.agent_status);
    };

    source.onerror = () => {
      source.close();
      sourceRef.current = null;
      setStreaming(false);
    };
  }, []);

  const stop = useCallback(() => {
    sourceRef.current?.close();
    sourceRef.current = null;
    setStreaming(false);
    fetch("/api/stream/stop", { method: "POST" }).catch(() => {});
  }, []);

  useEffect(() => {
    return () => {
      sourceRef.current?.close();
    };
  }, []);

  return { logs, streaming, agentStatus, start, stop };
}

export async function fetchROI() {
  const res = await fetch("/api/metrics/roi");
  return res.json();
}

export async function fetchAlerts() {
  const res = await fetch("/api/alerts");
  return res.json();
}

export async function fetchTopNoise() {
  const res = await fetch("/api/noise/top");
  return res.json();
}

export async function analyzeCode(code: string) {
  const res = await fetch("/api/analyze/code", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });
  return res.json();
}

export async function fetchPR(id: string) {
  const res = await fetch(`/api/remediation/pr/${id}`);
  return res.json();
}

export async function submitFeedback(alertId: string, wasCorrect: boolean, text: string = "") {
  const res = await fetch("/api/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ alert_id: alertId, was_correct: wasCorrect, feedback_text: text }),
  });
  return res.json();
}

export async function fetchAccuracy(): Promise<AccuracyMetrics> {
  const res = await fetch("/api/metrics/accuracy");
  return res.json();
}

export async function fetchTrends(): Promise<TrendAnalysis> {
  const res = await fetch("/api/analytics/trends");
  return res.json();
}

export async function fetchRootCause(): Promise<RootCauseAnalysis> {
  const res = await fetch("/api/analytics/root-cause");
  return res.json();
}
