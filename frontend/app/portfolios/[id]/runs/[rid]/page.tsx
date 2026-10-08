"use client";

import { useRun } from "@/hooks/useRuns";
import { RunProgressPanel } from "@/components/ui/RunProgressPanel";
import { VerdictCard } from "@/components/ui/VerdictCard";
import { Spinner } from "@/components/ui/Spinner";
import { noEmDash } from "@/lib/text";

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
        <p className="text-sm text-muted">Loading run…</p>
      </div>
    );
  }

  // If run is complete and has a recommendation, show results inline
  if (run?.status === "complete" && run.recommendation) {
    return (
      <div className="space-y-6">
        <h3 className="text-xl font-semibold text-ink">Portfolio analysis complete</h3>

        <VerdictCard layers={run.recommendation.layers} />

          <div className="rounded-lg border border-rule bg-surface p-6">
          <h4 className="mb-3 text-xl font-semibold text-ink">Rationale</h4>
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink">
            {noEmDash(run.recommendation.rationale)}
          </p>
        </div>

        {run.recommendation.proposed_trades.length > 0 && (
          <div className="rounded-lg border border-rule bg-surface">
            <div className="border-b border-rule px-6 py-4">
              <h4 className="text-xl font-semibold text-ink">Proposed trades</h4>
            </div>
            <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-rule text-sm text-muted">
                  <th className="px-6 py-3 text-left font-medium">Ticker</th>
                  <th className="px-6 py-3 text-left font-medium">Action</th>
                  <th className="px-6 py-3 text-right font-medium">Target weight</th>
                  <th className="px-6 py-3 text-left font-medium">Rationale</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule ">
                {run.recommendation.proposed_trades.map((trade, i) => (
                  <tr key={i} className="hover:bg-rule/30">
                    <td className="px-6 py-3 font-semibold text-ink">{trade.ticker}</td>
                    <td className="px-6 py-3">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          trade.action === "buy" || trade.action === "add"
                            ? "bg-buy-soft text-buy"
                            : "bg-sell-soft text-sell"
                        }`}
                      >
                        {trade.action.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-6 py-3 text-right text-ink">
                      {Math.round(trade.target_weight_pct * 100)}%
                    </td>
                    <td className="px-6 py-3 text-sm text-ink">{noEmDash(trade.rationale)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          </div>
        )}

        {Object.keys(run.recommendation.target_allocations).length > 0 && (
          <div className="rounded-lg border border-rule bg-surface p-6">
            <h4 className="mb-3 text-xl font-semibold text-ink">Target allocations</h4>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
              {Object.entries(run.recommendation.target_allocations).map(([ticker, pct]) => (
                <div key={ticker} className="flex items-center justify-between rounded bg-rule/30 px-3 py-2">
                  <span className="text-sm font-semibold text-ink">{ticker}</span>
                  <span className="text-sm text-ink">{Math.round(pct * 100)}%</span>
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
      <h3 className="mb-4 text-xl font-semibold text-ink">Portfolio analysis in progress</h3>
      <RunProgressPanel runId={params.rid} />
    </div>
  );
}
