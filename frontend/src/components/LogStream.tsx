import type { LogEntry } from "../types";

interface Props {
  logs: LogEntry[];
  onSelectPR: (id: string) => void;
}

const levelColors: Record<string, string> = {
  INFO: "text-blue-400",
  WARN: "text-amber-400",
  ERROR: "text-orange-400",
  CRITICAL: "text-red-400",
};

export default function LogStream({ logs, onSelectPR }: Props) {
  return (
    <div className="flex h-full flex-col rounded-xl border border-bank-border bg-bank-panel">
      <div className="border-b border-bank-border px-4 py-3">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
          Live Log Stream
        </h2>
        <p className="text-xs text-slate-500">Raw vs redacted — critical rows highlighted</p>
      </div>
      <div className="flex-1 overflow-y-auto p-2 font-mono text-xs">
        {logs.length === 0 && (
          <p className="p-4 text-center text-slate-500">
            Click &quot;Start Ingestion&quot; to begin the log stream
          </p>
        )}
        {logs.map((log, i) => (
          <div
            key={`${log.timestamp}-${i}`}
            className={`mb-2 rounded-lg border p-2 ${
              log.has_pii
                ? "border-red-500/50 bg-red-500/10"
                : "border-bank-border bg-bank-bg/50"
            }`}
          >
            <div className="mb-1 flex items-center gap-2">
              <span className={`font-bold ${levelColors[log.level] || "text-slate-400"}`}>
                {log.level}
              </span>
              <span className="text-slate-500">{log.service}</span>
              {log.has_pii && (
                <span className="rounded bg-red-500/30 px-1.5 py-0.5 text-[10px] font-bold text-red-300">
                  PII BLOCKED
                </span>
              )}
              {log.remediation_id && (
                <button
                  onClick={() => onSelectPR(log.remediation_id!)}
                  className="ml-auto rounded bg-bank-accent/20 px-2 py-0.5 text-[10px] text-blue-300 hover:bg-bank-accent/30"
                >
                  View PR →
                </button>
              )}
            </div>
            <div className="text-slate-500 line-through opacity-60">{log.raw}</div>
            <div className="text-emerald-300">{log.redacted}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
