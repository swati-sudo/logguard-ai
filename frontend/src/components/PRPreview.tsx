import type { PullRequest } from "../types";

interface Props {
  pr: PullRequest | null;
  compact?: boolean;
}

export default function PRPreview({ pr, compact = false }: Props) {
  if (!pr) {
    return (
      <div className="rounded-xl border border-bank-border bg-bank-panel p-4">
        <p className="text-sm text-slate-500">Select a flagged log to preview the auto-generated PR</p>
      </div>
    );
  }

  return (
    <div className={`rounded-xl border border-bank-border bg-bank-panel ${compact ? "p-3" : "p-4"}`}>
      {!compact && (
        <>
          <h2 className="mb-1 text-sm font-semibold uppercase tracking-wider text-slate-400">
            Remediation PR Preview
          </h2>
          <p className="mb-3 text-xs text-slate-500">Mock GitHub pull request — Demo Mode</p>
        </>
      )}

      <div className="rounded-lg border border-bank-border bg-[#0d1117]">
        <div className="flex items-center justify-between border-b border-bank-border px-4 py-2">
          <div>
            <p className="text-sm font-medium text-slate-200">{pr.title}</p>
            <p className="text-xs text-slate-500">
              {pr.branch} → main · {pr.service}
            </p>
          </div>
          <span className="rounded-full bg-amber-500/20 px-2 py-0.5 text-[10px] font-bold text-amber-400">
            DEMO MODE
          </span>
        </div>

        <div className="border-b border-bank-border px-4 py-2 text-xs text-slate-500">
          <span className="text-blue-400">{pr.file_path}</span>
          <span className="ml-2">Line {pr.line_number}</span>
          <span className="ml-2">Reviewer: {pr.reviewer}</span>
        </div>

        <pre className="overflow-x-auto p-4 font-mono text-xs leading-relaxed">
          {pr.diff.split("\n").map((line, i) => (
            <div
              key={i}
              className={
                line.startsWith("+")
                  ? "bg-emerald-500/10 text-emerald-300"
                  : line.startsWith("-")
                    ? "bg-red-500/10 text-red-300"
                    : "text-slate-400"
              }
            >
              {line}
            </div>
          ))}
        </pre>

        <div className="border-t border-bank-border px-4 py-2">
          <button
            disabled
            className="cursor-not-allowed rounded-md bg-emerald-600/40 px-3 py-1 text-xs font-medium text-emerald-200/50"
          >
            Merge pull request
          </button>
        </div>
      </div>
    </div>
  );
}
