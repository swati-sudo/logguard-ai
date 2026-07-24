import { useCallback, useEffect, useState } from "react";
import AgentPipeline from "./components/AgentPipeline";
import AlertsPanel from "./components/AlertsPanel";
import AnalyticsDashboard from "./components/AnalyticsDashboard";
import CodePlayground from "./components/CodePlayground";
import LogStream from "./components/LogStream";
import PRPreview from "./components/PRPreview";
import ROIDashboard from "./components/ROIDashboard";
import {
  fetchAlerts,
  fetchPR,
  fetchROI,
  fetchTopNoise,
  useLogStream,
} from "./hooks/useLogStream";
import type { Alert, NoisyPattern, PullRequest, ROIMetrics } from "./types";

export default function App() {
  const { logs, streaming, agentStatus, start, stop } = useLogStream();
  const [metrics, setMetrics] = useState<ROIMetrics | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [noisePatterns, setNoisePatterns] = useState<NoisyPattern[]>([]);
  const [selectedPR, setSelectedPR] = useState<PullRequest | null>(null);

  const refreshMetrics = useCallback(async () => {
    const [roi, alertData, noise] = await Promise.all([
      fetchROI(),
      fetchAlerts(),
      fetchTopNoise(),
    ]);
    setMetrics(roi);
    setAlerts(alertData.alerts || []);
    setNoisePatterns(noise.patterns || []);
  }, []);

  useEffect(() => {
    refreshMetrics();
    const interval = setInterval(refreshMetrics, 3000);
    return () => clearInterval(interval);
  }, [refreshMetrics, logs.length]);

  const handleSelectPR = async (id: string) => {
    const pr = await fetchPR(id);
    if (!pr.error) setSelectedPR(pr);
  };

  return (
    <div className="min-h-screen">
      <header className="border-b border-bank-border bg-bank-panel px-6 py-4">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold tracking-tight">
              LogGuard AI
              <span className="ml-2 text-sm font-normal text-slate-500">
                Agentic Observability &amp; Privacy Engine
              </span>
            </h1>
            <p className="text-xs text-slate-500">XYZ Bank Hackathon Demo</p>
          </div>
          <div className="flex gap-2">
            {!streaming ? (
              <button
                onClick={start}
                className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500"
              >
                Start Ingestion
              </button>
            ) : (
              <button
                onClick={stop}
                className="rounded-lg bg-red-600/80 px-4 py-2 text-sm font-semibold text-white hover:bg-red-500"
              >
                Stop Stream
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-4 p-4">
        <AgentPipeline status={agentStatus} logCount={logs.length} />

        <div className="grid gap-4 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <div className="h-[420px]">
              <LogStream logs={logs} onSelectPR={handleSelectPR} />
            </div>
          </div>
          <div className="space-y-4">
            <ROIDashboard metrics={metrics} />
            <AlertsPanel alerts={alerts} />
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <CodePlayground />
          <PRPreview pr={selectedPR} />
        </div>

        <AnalyticsDashboard />

        {noisePatterns.length > 0 && (
          <div className="rounded-xl border border-bank-border bg-bank-panel p-4">
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
              Top Noisy Patterns (24h)
            </h2>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-bank-border text-slate-500">
                    <th className="pb-2 pr-4">Service</th>
                    <th className="pb-2 pr-4">Classification</th>
                    <th className="pb-2 pr-4">Count</th>
                    <th className="pb-2">Sample</th>
                  </tr>
                </thead>
                <tbody>
                  {noisePatterns.map((p, i) => (
                    <tr key={i} className="border-b border-bank-border/50">
                      <td className="py-2 pr-4 text-blue-400">{p.service}</td>
                      <td className="py-2 pr-4 text-amber-400">{p.classification}</td>
                      <td className="py-2 pr-4">{p.count.toLocaleString()}</td>
                      <td className="max-w-md truncate py-2 text-slate-500">{p.sample}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
