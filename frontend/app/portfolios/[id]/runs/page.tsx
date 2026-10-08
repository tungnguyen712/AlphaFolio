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
  queued: "bg-rule/60 text-ink",
  running: "bg-action/10 text-action",
  complete: "bg-buy-soft text-buy",
  failed: "bg-sell-soft text-sell",
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
        className="rounded-lg border border-rule bg-surface p-6"
      >
        <h3 className="mb-4 text-xl font-semibold text-ink">Run portfolio analysis</h3>

        <div className="space-y-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-ink">
              Objective (optional)
            </label>
            <textarea
              value={objective}
              onChange={(e) => setObjective(e.target.value)}
              rows={2}
              maxLength={500}
              className="w-full rounded border border-rule px-3 py-2 text-sm text-ink focus:border-rule focus:outline-none"
              placeholder="e.g. Reduce tech concentration, target 15% cash"
            />
          </div>

          {reports.length > 0 && (
            <div>
              <label className="mb-2 block text-sm font-medium text-ink">
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
                    <span className="text-sm text-ink">
                      {r.ticker}: {r.signal.toUpperCase()} ({Math.round(r.confidence * 100)}%)
                    </span>
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>

        {startError && <p className="mt-2 text-sm text-sell">{startError}</p>}

        <button
          type="submit"
          disabled={starting || navigating}
          className="mt-4 flex items-center gap-2 rounded bg-action px-5 py-2 text-sm font-medium text-action-ink hover:opacity-90 disabled:opacity-50"
        >
          {(starting || navigating) && <Spinner size="sm" />}
          {navigating ? "Starting…" : "Start rebalance analysis"}
        </button>
      </form>

      <div>
        <h3 className="mb-3 text-xl font-semibold text-ink">Run history</h3>
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
                  className="flex items-center justify-between rounded-lg border border-rule bg-surface px-4 py-3 hover:bg-rule/30"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`rounded-full px-2 py-0.5 text-sm font-medium ${statusBadge[run.status] ?? ""}`}
                    >
                      {run.status}
                    </span>
                    <span className="text-sm text-ink">Portfolio run</span>
                  </div>
                  <span className="text-sm text-muted">
                    {run.started_at ? new Date(run.started_at).toLocaleString() : "n/a"}
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
