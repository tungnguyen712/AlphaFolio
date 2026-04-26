"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useStartPortfolioRun } from "@/hooks/usePortfolios";
import { useRuns } from "@/hooks/useRuns";
import { useReports } from "@/hooks/useResearch";
import { Spinner } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";

const statusBadge: Record<string, string> = {
  queued: "bg-neutral-100 text-neutral-600",
  running: "bg-blue-100 text-blue-700",
  complete: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
};

export default function PortfolioRunsPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { mutate: startRun, loading: starting, error: startError } = useStartPortfolioRun(params.id);
  const { data: runs, loading: runsLoading } = useRuns({ flow: "portfolio", limit: 20 });
  const { data: reports } = useReports({ limit: 20 });

  const [objective, setObjective] = useState("");
  const [selectedReportIds, setSelectedReportIds] = useState<string[]>([]);
  const [navigating, setNavigating] = useState(false);

  const portfolioRuns = runs.filter((r) => r.recommendation !== null || r.flow === "portfolio");

  const handleStart = async (e: React.FormEvent) => {
    e.preventDefault();
    const result = await startRun({
      candidate_report_ids: selectedReportIds.length > 0 ? selectedReportIds : undefined,
      objective: objective.trim() || undefined,
    });
    if (result) {
      setNavigating(true);
      router.push(`/portfolios/${params.id}/runs/${result.run_id}`);
    }
  };

  const toggleReport = (id: string) => {
    setSelectedReportIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  };

  return (
    <div className="space-y-6">
      <form
        onSubmit={(e) => void handleStart(e)}
        className="rounded-xl border border-neutral-200 bg-white p-6 shadow-sm"
      >
        <h3 className="mb-4 text-sm font-semibold text-neutral-800">Run portfolio analysis</h3>

        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-neutral-600">
              Objective (optional)
            </label>
            <textarea
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
              rows={2}
              maxLength={500}
              className="w-full rounded-md border border-neutral-300 px-3 py-2 text-sm focus:border-neutral-500 focus:outline-none"
              placeholder="e.g. Reduce tech concentration, target 15% cash"
            />
          </div>

          {reports.length > 0 && (
            <div>
              <label className="mb-2 block text-xs font-medium text-neutral-600">
                Include research reports (optional)
              </label>
              <div className="grid gap-2 sm:grid-cols-2">
                {reports.slice(0, 10).map((r) => (
                  <label key={r.id} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selectedReportIds.includes(r.id)}
                      onChange={() => toggleReport(r.id)}
                      className="rounded"
                    />
                    <span className="text-sm text-neutral-700">
                      {r.ticker} — {r.signal.toUpperCase()} ({Math.round(r.confidence * 100)}%)
                    </span>
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>

        {startError && <p className="mt-2 text-xs text-red-600">{startError}</p>}

        <button
          type="submit"
          disabled={starting || navigating}
          className="mt-4 flex items-center gap-2 rounded-md bg-neutral-900 px-5 py-2 text-sm font-medium text-white hover:bg-neutral-700 disabled:opacity-50"
        >
          {(starting || navigating) && <Spinner size="sm" />}
          {navigating ? "Starting…" : "Start rebalance analysis"}
        </button>
      </form>

      <div>
        <h3 className="mb-3 text-sm font-semibold text-neutral-800">Run history</h3>
        {runsLoading ? (
          <Spinner />
        ) : portfolioRuns.length === 0 ? (
          <EmptyState title="No portfolio runs yet" description="Start a run above." />
        ) : (
          <ul className="space-y-2">
            {portfolioRuns.map((run) => (
              <li key={run.id}>
                <Link
                  href={`/portfolios/${params.id}/runs/${run.id}`}
                  className="flex items-center justify-between rounded-lg border border-neutral-200 bg-white px-4 py-3 hover:bg-neutral-50"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusBadge[run.status] ?? ""}`}
                    >
                      {run.status}
                    </span>
                    <span className="text-sm text-neutral-700">Portfolio run</span>
                  </div>
                  <span className="text-xs text-neutral-400">
                    {run.started_at ? new Date(run.started_at).toLocaleString() : "—"}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
