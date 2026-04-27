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
  buy: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-300",
  hold: "bg-yellow-100 text-yellow-800 dark:bg-yellow-950 dark:text-yellow-300",
  sell: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
};

const statusBadge: Record<string, string> = {
  queued: "bg-neutral-100 text-neutral-600 dark:bg-zinc-800 dark:text-zinc-300",
  running: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  complete: "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300",
  failed: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
};

function ResearchForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [ticker, setTicker] = useState(searchParams.get("ticker") ?? "");
  const [mode, setMode] = useState<"public" | "pre_ipo">("public");
  const [lookback, setLookback] = useState("90");
  const [navigating, setNavigating] = useState(false);
  const { mutate, loading, error } = useStartResearchRun();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ticker.trim()) return;
    const result = await mutate({
      ticker: ticker.trim().toUpperCase(),
      mode,
      lookback_days: parseInt(lookback, 10),
    });
    if (result) {
      setNavigating(true);
      router.push(`/research/runs/${result.run_id}`);
    }
  };

  return (
    <form
      onSubmit={(e) => void handleSubmit(e)}
      className="rounded-xl border border-neutral-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900"
    >
      <h2 className="mb-4 text-base font-semibold text-neutral-800 dark:text-zinc-100">Run research</h2>
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="sm:col-span-1">
          <label className="mb-1 block text-xs font-medium text-neutral-600 dark:text-zinc-400">Ticker</label>
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="e.g. AAPL"
            required
            className="w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm uppercase text-zinc-900 focus:border-neutral-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-neutral-600 dark:text-zinc-400">Mode</label>
          <select
            value={mode}
            onChange={(e) => setMode(e.target.value as "public" | "pre_ipo")}
            className="w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm text-zinc-900 focus:border-neutral-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
          >
            <option value="public">Public</option>
            <option value="pre_ipo">Pre-IPO</option>
          </select>
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-neutral-600 dark:text-zinc-400">
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
        disabled={loading || navigating}
        className="mt-4 flex items-center gap-2 rounded-md bg-neutral-900 px-5 py-2 text-sm font-medium text-white hover:bg-neutral-700 disabled:opacity-50"
      >
        {(loading || navigating) && <Spinner size="sm" />}
        {navigating ? "Starting…" : "Start research"}
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
      <h2 className="mb-3 text-sm font-semibold text-neutral-700 dark:text-zinc-300">Recent runs</h2>
      <ul className="space-y-2">
        {runs.map((run) => (
          <li key={run.id}>
            <Link
              href={`/research/runs/${run.id}`}
              className="flex items-center justify-between rounded-lg border border-neutral-200 bg-white px-4 py-3 hover:bg-neutral-50 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:bg-zinc-800/60"
            >
              <div className="flex items-center gap-3">
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusBadge[run.status] ?? "bg-neutral-100 text-neutral-600 dark:bg-zinc-800 dark:text-zinc-300"}`}
                >
                  {run.status}
                </span>
                <span className="text-sm font-medium text-neutral-800 dark:text-zinc-100">
                  {run.ticker ?? "—"}
                </span>
              </div>
              <span className="text-xs text-neutral-400 dark:text-zinc-500">
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
      <h2 className="mb-3 text-sm font-semibold text-neutral-700 dark:text-zinc-300">Research reports</h2>
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
                className="flex items-center justify-between rounded-lg border border-neutral-200 bg-white px-4 py-3 hover:bg-neutral-50 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:bg-zinc-800/60"
              >
                <div className="flex items-center gap-3">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-semibold ${signalBadge[r.signal] ?? ""}`}
                  >
                    {r.signal.toUpperCase()}
                  </span>
                  <span className="text-sm font-medium text-neutral-800 dark:text-zinc-100">{r.ticker}</span>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-xs text-neutral-500 dark:text-zinc-400">
                    {Math.round(r.confidence * 100)}% confidence
                  </span>
                  <span className="text-xs text-neutral-400 dark:text-zinc-500">
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
