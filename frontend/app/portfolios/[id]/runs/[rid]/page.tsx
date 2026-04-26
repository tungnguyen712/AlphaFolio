"use client";

import { useCallback } from "react";
import { useRouter } from "next/navigation";
import { RunProgressPanel } from "@/components/ui/RunProgressPanel";
import { useRun } from "@/hooks/useRuns";
import { VerdictCard } from "@/components/ui/VerdictCard";
import { Spinner } from "@/components/ui/Spinner";
import type { RunStatusOut } from "@/lib/types";

export default function PortfolioRunPage({
  params,
}: {
  params: { id: string; rid: string };
}) {
  const router = useRouter();
  const { data: run, loading } = useRun(params.rid);

  const handleComplete = useCallback(
    (_run: RunStatusOut) => {
      // Re-render will pick up the completed state via useRun polling
      void router.replace(`/portfolios/${params.id}/runs/${params.rid}`);
    },
    [params.id, params.rid, router],
  );

  if (loading && !run) return <Spinner />;

  // If run is complete and has a recommendation, show results inline
  if (run?.status === "complete" && run.recommendation) {
    return (
      <div className="max-w-2xl space-y-6">
        <h3 className="text-base font-semibold text-neutral-800">Portfolio analysis complete</h3>

        <VerdictCard layers={run.recommendation.layers} />

        <div className="rounded-xl border border-neutral-200 bg-white p-6">
          <h4 className="mb-3 text-sm font-semibold text-neutral-700">Rationale</h4>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-neutral-700">
            {run.recommendation.rationale}
          </p>
        </div>

        {run.recommendation.proposed_trades.length > 0 && (
          <div className="rounded-xl border border-neutral-200 bg-white shadow-sm">
            <div className="border-b border-neutral-100 px-6 py-4">
              <h4 className="text-sm font-semibold text-neutral-800">Proposed trades</h4>
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-100 text-xs text-neutral-500">
                  <th className="px-6 py-3 text-left font-medium">Ticker</th>
                  <th className="px-6 py-3 text-left font-medium">Action</th>
                  <th className="px-6 py-3 text-right font-medium">Target weight</th>
                  <th className="px-6 py-3 text-left font-medium">Rationale</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-50">
                {run.recommendation.proposed_trades.map((trade, i) => (
                  <tr key={i} className="hover:bg-neutral-50">
                    <td className="px-6 py-3 font-semibold text-neutral-900">{trade.ticker}</td>
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
                    <td className="px-6 py-3 text-right text-neutral-700">
                      {Math.round(trade.target_weight_pct * 100)}%
                    </td>
                    <td className="px-6 py-3 text-xs text-neutral-600">{trade.rationale}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {Object.keys(run.recommendation.target_allocations).length > 0 && (
          <div className="rounded-xl border border-neutral-200 bg-white p-6">
            <h4 className="mb-3 text-sm font-semibold text-neutral-700">Target allocations</h4>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {Object.entries(run.recommendation.target_allocations).map(([ticker, pct]) => (
                <div key={ticker} className="flex items-center justify-between rounded bg-neutral-50 px-3 py-2">
                  <span className="text-sm font-semibold text-neutral-800">{ticker}</span>
                  <span className="text-sm text-neutral-600">{Math.round(pct * 100)}%</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="max-w-2xl">
      <h3 className="mb-4 text-base font-semibold text-neutral-800">Portfolio analysis in progress</h3>
      <RunProgressPanel runId={params.rid} onComplete={handleComplete} />
    </div>
  );
}
