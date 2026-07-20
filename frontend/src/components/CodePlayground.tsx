import { useState } from "react";
import { analyzeCode } from "../hooks/useLogStream";
import type { CodeAnalysisResult } from "../types";
import PRPreview from "./PRPreview";

const DEFAULT_CODE = `logger.info("User login: iban=" + user.getIban() + ", password=" + password);`;

export default function CodePlayground() {
  const [code, setCode] = useState(DEFAULT_CODE);
  const [result, setResult] = useState<CodeAnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);

  const handleAnalyze = async () => {
    setLoading(true);
    try {
      const data = await analyzeCode(code);
      setResult(data);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-xl border border-bank-border bg-bank-panel p-4">
      <h2 className="mb-1 text-sm font-semibold uppercase tracking-wider text-slate-400">
        Zero-Leak Code Playground
      </h2>
      <p className="mb-3 text-xs text-slate-500">
        Paste vulnerable Java/Spring Boot code — AI flags &amp; patches instantly
      </p>

      <textarea
        value={code}
        onChange={(e) => setCode(e.target.value)}
        className="mb-3 h-28 w-full resize-none rounded-lg border border-bank-border bg-bank-bg p-3 font-mono text-xs text-slate-300 focus:border-bank-accent focus:outline-none"
        spellCheck={false}
      />

      <button
        onClick={handleAnalyze}
        disabled={loading}
        className="rounded-lg bg-bank-accent px-4 py-2 text-sm font-semibold text-white hover:bg-blue-600 disabled:opacity-50"
      >
        {loading ? "Analyzing…" : "Analyze Code"}
      </button>

      {result && (
        <div className="mt-4 space-y-3">
          {result.has_pii ? (
            <div className="rounded-lg border border-red-500/50 bg-red-500/10 p-3">
              <p className="text-sm font-bold text-red-400">
                ⚠ {result.severity} — PII/Credential leak detected
              </p>
              <ul className="mt-2 space-y-1">
                {result.findings.map((f, i) => (
                  <li key={i} className="text-xs text-slate-400">
                    <span className="text-red-300">{f.severity}</span> · {f.category}:{" "}
                    <code className="text-slate-500">{f.matched_text}</code>
                  </li>
                ))}
              </ul>
              {result.alert_channel && (
                <p className="mt-2 text-xs text-amber-400">
                  Alert dispatched to {result.alert_channel === "pagerduty" ? "PagerDuty" : "Slack"}
                </p>
              )}
            </div>
          ) : (
            <div className="rounded-lg border border-emerald-500/50 bg-emerald-500/10 p-3 text-sm text-emerald-400">
              ✓ No PII detected in this snippet
            </div>
          )}

          <div>
            <p className="mb-1 text-xs font-semibold uppercase text-slate-500">Secure Patch</p>
            <pre className="overflow-x-auto rounded-lg border border-emerald-500/30 bg-bank-bg p-3 font-mono text-xs text-emerald-300">
              {result.secure_patch}
            </pre>
          </div>

          <PRPreview pr={result.pull_request} compact />
        </div>
      )}
    </div>
  );
}
