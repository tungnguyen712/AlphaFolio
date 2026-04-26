"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useReports } from "@/hooks/useResearch";
import { useStartResearchRun } from "@/hooks/useResearch";
import { useRuns } from "@/hooks/useRuns";
import { EmptyState } from "@/components/ui/EmptyState";
import { Spinner } from "@/components/ui/Spinner";

const signalBadge: Record<string, string> = {
  buy: "bg-green-100 text-green-800",
  hold: "bg-yellow-100 text-yellow-800",
  sell: "bg-red-100 text-red-800",
};

const statusBadge: Record<string, string> = {
  queued: "bg-neutral-100 text-neutral-600",
  running: "bg-blue-100 text-blue-700",
  complete: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
};

function ResearchForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [ticker, setTicker] = useState(searchParams.get("ticker") ?? "");
  const [mode, setMode] = useState<"public" | "pre_ipo">("public");
  const [lookback, setLookback] = useState("90");
  const { mutate, loading, error } = useStartResearchRun();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ticker.trim()) return;
    const result = await mutate({
      ticker: ticker.trim().toUpperCase(),
      mode,
      lookback_days: parseInt(lookback, 10),
    });
    if (result) router.push(`/research/runs/${result.run_id}`);
  };

  return (
    <form
      onSubmit={(e) => void handleSubmit(e)}
      className="rounded-xl border border-neutral-200 bg-white p-6 shadow-sm"
    >
      <h2 className="mb-4 text-base font-semibold text-neutral-800">Run research</h2>
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="sm:col-span-1">
          <label className="mb-1 block text-xs font-medium text-neutral-600">Ticker</label>
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="e.g. AAPL"
            required
            className="w-full rounded-md border border-neutral-300 px-3 py-2 text-sm uppercase focus:border-neutral-500 focus:outline-none"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-neutral-600">Mode</label>
          <select
            value={mode}
            onChange={(e) => setMode(e.target.value as "public" | "pre_ipo")}
            className="w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm focus:border-neutral-500 focus:outline-none"
          >
            <option value="public">Public</option>
            <option value="pre_ipo">Pre-IPO</option>
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-neutral-600">
            Lookback (days): {lookback}
          </label>
          <input
            type="range"
            min="7"
            max="365"
            value={lookback}
            onChange={(e) => setLookback(e.target.value)}
            className="mt-2 w-full"
          />
        </div>
      </div>

      {error && <p className="mt-3 text-xs text-red-600">{error}</p>}

      <button
        type="submit"
        disabled={loading}
        className="mt-4 flex items-center gap-2 rounded-md bg-neutral-900 px-5 py-2 text-sm font-medium text-white hover:bg-neutral-700 disabled:opacity-50"
      >
        {loading && <Spinner size="sm" />}
        Start research
      </button>
    </form>
  );
}

function RecentRuns() {
  const { data: runs, loading } = useRuns({ flow: "research", limit: 5 });
  if (loading) return <Spinner />;
  if (runs.length === 0) return null;

  return (
    <div className="mt-8">
      <h2 className="mb-3 text-sm font-semibold text-neutral-700">Recent runs</h2>
      <ul className="space-y-2">
        {runs.map((run) => (
          <li key={run.id}>
            <Link
              href={`/research/runs/${run.id}`}
              className="flex items-center justify-between rounded-lg border border-neutral-200 bg-white px-4 py-3 hover:bg-neutral-50"
            >
              <div className="flex items-center gap-3">
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusBadge[run.status] ?? "bg-neutral-100 text-neutral-600"}`}
                >
                  {run.status}
                </span>
                <span className="text-sm font-medium text-neutral-800">
                  {run.ticker ?? "—"}
                </span>
              </div>
              <span className="text-xs text-neutral-400">
                {run.started_at ? new Date(run.started_at).toLocaleString() : "—"}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

function RecentReports() {
  const { data: reports, loading } = useReports({ limit: 10 });
  if (loading) return <Spinner />;

  return (
    <div className="mt-8">
      <h2 className="mb-3 text-sm font-semibold text-neutral-700">Research reports</h2>
      {reports.length === 0 ? (
        <EmptyState
          title="No reports yet"
          description="Run research on a ticker to see reports here."
        />
      ) : (
        <ul className="space-y-2">
          {reports.map((r) => (
            <li key={r.id}>
              <Link
                href={`/research/reports/${r.id}`}
                className="flex items-center justify-between rounded-lg border border-neutral-200 bg-white px-4 py-3 hover:bg-neutral-50"
              >
                <div className="flex items-center gap-3">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-semibold ${signalBadge[r.signal] ?? ""}`}
                  >
                    {r.signal.toUpperCase()}
                  </span>
                  <span className="text-sm font-medium text-neutral-800">{r.ticker}</span>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-xs text-neutral-500">
                    {Math.round(r.confidence * 100)}% confidence
                  </span>
                  <span className="text-xs text-neutral-400">
                    {new Date(r.created_at).toLocaleDateString()}
                  </span>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function ResearchPage() {
  return (
    <div>
      <Suspense>
        <ResearchForm />
      </Suspense>
      <RecentRuns />
      <RecentReports />
    </div>
  );
}
