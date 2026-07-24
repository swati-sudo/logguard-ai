import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useCallback } from "react";
import type { ROIMetrics } from "../types";
 
interface Props {
  metrics: ROIMetrics | null;
}

export default function ROIDashboard({ metrics }: Props) {
  if (!metrics) {
    return (
      <div className="rounded-xl border border-bank-border bg-bank-panel p-4">
        <p className="text-sm text-slate-500">Loading ROI metrics…</p>
      </div>
    );
  }

  const chartData = [
    { name: "Before", gb: metrics.baseline_gb_per_day },
    { name: "After", gb: metrics.current_gb_per_day },
  ];

  // Function to handle CSV export
  const handleExport = useCallback(() => {
    if (!metrics) return;

    const headers = [
      "Metric",
      "Value",
    ].join(",");

    // Construct data rows from available metrics. Date range is not explicitly available in current metrics object.
    const dataRows = [
      `Noise Suppressed,${metrics.noise_percent}%`,
      `Monthly Savings EUR,€${metrics.monthly_savings_eur.toLocaleString()}`,
      `Alert Fatigue Reduction,${metrics.alert_fatigue_reduction}%`,
      `PII Containment (ms),<${metrics.pii_containment_ms}ms`,
      `Baseline GB per day,${metrics.baseline_gb_per_day} GB`,
      `Current GB per day,${metrics.current_gb_per_day} GB`,
    ].join("\n");

    const csvContent = `${headers}\n${dataRows}`;
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", "roi_dashboard_export.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }, [metrics]);

  return (
    <div className="rounded-xl border border-bank-border bg-bank-panel p-4">
      <div className="flex justify-between items-center mb-1">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
          Storage ROI Calculator
        </h2>
        <button onClick={handleExport} className="px-3 py-1 text-xs rounded-md bg-bank-accent text-white hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50">
          Export CSV
        </button>
      </div>
      <p className="mb-4 text-xs text-slate-500">Before &amp; after ingestion cost</p>

      <div className="mb-4 grid grid-cols-2 gap-3">
        <StatCard
          label="Noise Suppressed"
          value={`${metrics.noise_percent}%`}
          accent="text-emerald-400"
        />
        <StatCard
          label="Monthly Savings"
          value={`€${metrics.monthly_savings_eur.toLocaleString()}`}
          accent="text-blue-400"
        />
        <StatCard
          label="Alert Fatigue ↓"
          value={`${metrics.alert_fatigue_reduction}%`}
          accent="text-amber-400"
        />
        <StatCard
          label="PII Containment"
          value={`<${metrics.pii_containment_ms}ms`}
          accent="text-red-400"
        />
      </div>

      <div className="h-36">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData}>
            <XAxis dataKey="name" stroke="#64748b" fontSize={12} />
            <YAxis stroke="#64748b" fontSize={12} unit=" GB" />
            <Tooltip
              contentStyle={{
                background: "#121826",
                border: "1px solid #1e293b",
                borderRadius: 8,
              }}
            />
            <Bar dataKey="gb" fill="#3b82f6" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <p className="mt-2 text-center text-xs text-slate-500">
        AI suppressed {metrics.noise_percent}% of redundant log noise, saving €
        {metrics.monthly_savings_eur.toLocaleString()}/month in Splunk/Datadog ingestion
      </p>
    </div>
  );
}

function StatCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent: string;
}) {
  return (
    <div className="rounded-lg border border-bank-border bg-bank-bg p-3">
      <div className="text-[10px] uppercase tracking-wider text-slate-500">{label}</div>
      <div className={`text-lg font-bold ${accent}`}>{value}</div>
    </div>
  );
}
