import type { AgentStatus } from "../types";

interface Props {
  status: AgentStatus;
  logCount: number;
}

const agents = [
  {
    key: "privacy" as const,
    name: "Privacy Agent",
    desc: "PII / credential detection & redaction",
    icon: "🛡️",
  },
  {
    key: "noise" as const,
    name: "Noise Agent",
    desc: "Redundant log grouping & ROI",
    icon: "📉",
  },
  {
    key: "remediation" as const,
    name: "Remediation Agent",
    desc: "Source trace & auto PR generation",
    icon: "🔧",
  },
];

const statusStyles: Record<string, string> = {
  idle: "bg-slate-700 text-slate-300",
  active: "bg-emerald-500/20 text-emerald-400 border-emerald-500/40",
  processing: "bg-blue-500/20 text-blue-400 border-blue-500/40",
  alert: "bg-red-500/20 text-red-400 border-red-500/40 animate-pulse",
  ready: "bg-amber-500/20 text-amber-400 border-amber-500/40",
};

export default function AgentPipeline({ status, logCount }: Props) {
  return (
    <div className="rounded-xl border border-bank-border bg-bank-panel p-4">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
          3-Agent Pipeline
        </h2>
        <span className="text-xs text-slate-500">{logCount} logs processed</span>
      </div>
      <div className="flex flex-col gap-3 md:flex-row md:items-stretch">
        {agents.map((agent, i) => (
          <div key={agent.key} className="flex flex-1 items-center gap-2">
            <div className="flex-1 rounded-lg border border-bank-border bg-bank-bg p-3">
              <div className="mb-1 flex items-center gap-2">
                <span>{agent.icon}</span>
                <span className="text-sm font-medium">{agent.name}</span>
              </div>
              <p className="mb-2 text-xs text-slate-500">{agent.desc}</p>
              <span 
                className={`inline-block rounded-full border px-2 py-0.5 text-xs font-medium uppercase ${statusStyles[status[agent.key]] || statusStyles.idle}`}
              >
                {status[agent.key]}
              </span>
            </div>
            {i < agents.length - 1 && (
              <span className="hidden text-slate-600 md:block">→</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
