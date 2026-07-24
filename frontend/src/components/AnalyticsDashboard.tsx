import { useEffect, useState } from "react";
import { fetchAccuracy, fetchTrends, fetchRootCause } from "../hooks/useLogStream";
import type { AccuracyMetrics, TrendAnalysis, RootCauseAnalysis } from "../types";

export default function AnalyticsDashboard() {
  const [accuracy, setAccuracy] = useState<AccuracyMetrics | null>(null);
  const [trends, setTrends] = useState<TrendAnalysis | null>(null);
  const [rootCause, setRootCause] = useState<RootCauseAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        const [accData, trendData, rcData] = await Promise.all([
          fetchAccuracy().catch(() => null),
          fetchTrends().catch(() => null),
          fetchRootCause().catch(() => null),
        ]);
        if (accData && !("error" in accData)) setAccuracy(accData);
        if (trendData && !("error" in trendData)) setTrends(trendData);
        if (rcData && !("error" in rcData)) setRootCause(rcData);
      } catch (err) {
        console.error("Failed to load analytics:", err);
        setError("Failed to load analytics");
      }
    };

    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      {/* Accuracy Metrics */}
      <div className="rounded-xl border border-bank-border bg-bank-panel p-4">
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wider text-slate-400">
          System Accuracy
        </h3>
        {accuracy ? (
          <div className="space-y-2">
            {accuracy.accuracy !== null ? (
              <>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-slate-500">Detection Accuracy</span>
                  <span className="text-sm font-bold text-emerald-400">
                    {accuracy.accuracy}%
                  </span>
                </div>
                <div className="h-2 rounded-full bg-slate-700">
                  <div
                    className="h-full rounded-full bg-emerald-500"
                    style={{ width: `${accuracy.accuracy}%` }}
                  ></div>
                </div>
              </>
            ) : (
              <p className="text-xs text-slate-500">No feedback yet</p>
            )}
            <div className="mt-3 space-y-1 text-xs text-slate-500">
              <p>False Positives: {accuracy.false_positives}</p>
              <p>Total Feedback: {accuracy.total_feedback}</p>
            </div>
          </div>
        ) : (
          <p className="text-xs text-slate-500">Loading...</p>
        )}
      </div>

      {/* Trend Analysis */}
      <div className="rounded-xl border border-bank-border bg-bank-panel p-4">
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wider text-slate-400">
          Trend Analysis
        </h3>
        {trends && trends.noise_trend ? (
          <div className="space-y-2 text-xs">
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Noise Trend</span>
              <span
                className={`font-bold ${
                  trends.noise_trend === "decreasing"
                    ? "text-emerald-400"
                    : trends.noise_trend === "increasing"
                      ? "text-red-400"
                      : "text-slate-400"
                }`}
              >
                {trends.noise_trend?.toUpperCase() || "N/A"} ({trends.noise_change_percent > 0 ? "+" : ""}{trends.noise_change_percent?.toFixed(1) || "0"}%)
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Alert Trend</span>
              <span
                className={`font-bold ${
                  trends.alert_trend === "decreasing" ? "text-emerald-400" : "text-amber-400"
                }`}
              > 
                {trends.alert_trend?.toUpperCase() || "N/A"}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Total Alerts</span>
              <span className="font-bold text-blue-400">{trends.total_alerts || 0}</span>
            </div>
            {trends.recent_pii_breaches && trends.recent_pii_breaches > 0 && (
              <div className="flex items-center justify-between rounded-lg bg-red-500/10 p-2">
                <span className="text-red-400">Breached Credentials</span>
                <span className="font-bold text-red-400">{trends.recent_pii_breaches}</span>
              </div>
            )}
          </div>
        ) : (
          <p className="text-xs text-slate-500">Loading...</p>
        )}
      </div>

      {/* Root Cause Analysis */}
      <div className="rounded-xl border border-bank-border bg-bank-panel p-4 md:col-span-2">
        <h3 className="mb-2 text-sm font-semibold uppercase tracking-wider text-slate-400">
          Root Cause Analysis
        </h3>
        {rootCause && rootCause.root_cause ? (
          <div className="space-y-2">
            <div className="rounded-lg bg-slate-800/50 p-3">
              <p className="mb-2 text-xs font-semibold text-slate-300">Root Cause</p>
              <p className="text-sm text-slate-200">{rootCause.root_cause || "Unable to determine"}</p>
            </div>
            <div className="flex items-center gap-4">
              <div>
                <p className="text-xs text-slate-500">Severity</p>
                <p
                  className={`text-sm font-bold ${
                    rootCause.severity === "HIGH"
                      ? "text-red-400"
                      : rootCause.severity === "MEDIUM"
                        ? "text-amber-400"
                        : "text-emerald-400"
                  }`}
                >
                  {rootCause.severity || "UNKNOWN"}
                </p>
              </div>
              <div>
                <p className="text-xs text-slate-500">Recommended Action</p>
                <p className="text-sm text-blue-400">{rootCause.action || "No action"}</p>
              </div>
            </div>
          </div>
        ) : (
          <p className="text-xs text-slate-500">Loading...</p>
        )}
      </div>
    </div>
  );
}
