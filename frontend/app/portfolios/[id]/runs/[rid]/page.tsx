"use client";

import { useRun } from "@/hooks/useRuns";
import { RunProgressPanel } from "@/components/ui/RunProgressPanel";
import { VerdictCard } from "@/components/ui/VerdictCard";
import { Spinner } from "@/components/ui/Spinner";

export default function PortfolioRunPage({
  params,
}: {
  params: { id: string; rid: string };
}) {
  const { data: run, loading } = useRun(params.rid);

  if (loading && !run) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-24">
        <Spinner />
        <p className="text-sm text-neutral-500 dark:text-zinc-400">Loading run…</p>
      </div>
    );
  }

  // If run is complete and has a recommendation, show results inline
  if (run?.status === "complete" && run.recommendation) {
    return (
      <div className="space-y-6">
        <h3 className="text-base font-semibold text-neutral-800 dark:text-zinc-100">Portfolio analysis complete</h3>

        <VerdictCard layers={run.recommendation.layers} />

          <div className="rounded-xl border border-neutral-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
          <h4 className="mb-3 text-sm font-semibold text-neutral-700 dark:text-zinc-300">Rationale</h4>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-neutral-700 dark:text-zinc-300">
            {run.recommendation.rationale}
          </p>
        </div>

        {run.recommendation.proposed_trades.length > 0 && (
          <div className="rounded-xl border border-neutral-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <div className="border-b border-neutral-100 px-6 py-4 dark:border-zinc-800">
              <h4 className="text-sm font-semibold text-neutral-800 dark:text-zinc-100">Proposed trades</h4>
            </div>
            <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-100 text-xs text-neutral-500 dark:border-zinc-800 dark:text-zinc-400">
                  <th className="px-6 py-3 text-left font-medium">Ticker</th>
                  <th className="px-6 py-3 text-left font-medium">Action</th>
                  <th className="px-6 py-3 text-right font-medium">Target weight</th>
                  <th className="px-6 py-3 text-left font-medium">Rationale</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-50 dark:divide-zinc-800">
                {run.recommendation.proposed_trades.map((trade, i) => (
                  <tr key={i} className="hover:bg-neutral-50 dark:hover:bg-zinc-800/40">
                    <td className="px-6 py-3 font-semibold text-neutral-900 dark:text-zinc-100">{trade.ticker}</td>
                    <td className="px-6 py-3">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          trade.action === "buy" || trade.action === "add"
                            ? "bg-green-100 text-green-700"
                            : "bg-red-100 text-red-700"
                        }`}
                      >
                        {trade.action.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-6 py-3 text-right text-neutral-700 dark:text-zinc-300">
                      {Math.round(trade.target_weight_pct * 100)}%
                    </td>
                    <td className="px-6 py-3 text-xs text-neutral-600 dark:text-zinc-400">{trade.rationale}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          </div>
        )}

        {Object.keys(run.recommendation.target_allocations).length > 0 && (
          <div className="rounded-xl border border-neutral-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
            <h4 className="mb-3 text-sm font-semibold text-neutral-700 dark:text-zinc-300">Target allocations</h4>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
              {Object.entries(run.recommendation.target_allocations).map(([ticker, pct]) => (
                <div key={ticker} className="flex items-center justify-between rounded bg-neutral-50 px-3 py-2 dark:bg-zinc-800">
                  <span className="text-sm font-semibold text-neutral-800 dark:text-zinc-100">{ticker}</span>
                  <span className="text-sm text-neutral-600 dark:text-zinc-400">{Math.round(pct * 100)}%</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div>
      <h3 className="mb-4 text-base font-semibold text-neutral-800 dark:text-zinc-100">Portfolio analysis in progress</h3>
      <RunProgressPanel runId={params.rid} />
    </div>
  );
}
