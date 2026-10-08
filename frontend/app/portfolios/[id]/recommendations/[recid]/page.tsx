"use client";

import Link from "next/link";
import { usePortfolioRecommendations } from "@/hooks/usePortfolios";
import { VerdictCard } from "@/components/ui/VerdictCard";
import { Spinner } from "@/components/ui/Spinner";
import { noEmDash } from "@/lib/text";

export default function RecommendationDetailPage({
  params,
}: {
  params: { id: string; recid: string };
}) {
  const { data: recs, loading, error } = usePortfolioRecommendations(params.id);
  const rec = recs.find((r) => r.id === params.recid);

  if (loading) return <Spinner />;
  if (error) return <p className="text-sm text-sell">{error}</p>;
  if (!rec) return <p className="text-sm text-muted">Recommendation not found.</p>;

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-xl font-semibold text-ink">Recommendation</h3>
        <Link
          href={`/portfolios/${params.id}/recommendations`}
          className="text-sm text-muted hover:text-ink"
        >
          ← All recommendations
        </Link>
      </div>

      <VerdictCard layers={rec.recommendation.layers} />

      <div className="rounded-lg border border-rule bg-surface p-6">
        <h4 className="mb-3 text-xl font-semibold text-ink">Rationale</h4>
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-ink">
          {noEmDash(rec.recommendation.rationale)}
        </p>
      </div>

      {rec.recommendation.proposed_trades.length > 0 && (
        <div className="rounded-lg border border-rule bg-surface">
          <div className="border-b border-rule px-6 py-4">
            <h4 className="text-xl font-semibold text-ink">Proposed trades</h4>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-rule text-sm text-muted">
                <th className="px-6 py-3 text-left font-medium">Ticker</th>
                <th className="px-6 py-3 text-left font-medium">Action</th>
                <th className="px-6 py-3 text-right font-medium">Target weight</th>
                <th className="px-6 py-3 text-left font-medium">Rationale</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {rec.recommendation.proposed_trades.map((trade, i) => (
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
      )}

      {Object.keys(rec.recommendation.target_allocations).length > 0 && (
        <div className="rounded-lg border border-rule bg-surface p-6">
          <h4 className="mb-3 text-xl font-semibold text-ink">Target allocations</h4>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {Object.entries(rec.recommendation.target_allocations).map(([ticker, pct]) => (
              <div
                key={ticker}
                className="flex items-center justify-between rounded bg-rule/30 px-3 py-2"
              >
                <span className="text-sm font-semibold text-ink">{ticker}</span>
                <span className="text-sm text-ink">{Math.round(pct * 100)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <p className="text-sm text-muted">
        Generated {new Date(rec.created_at).toLocaleString()}
      </p>
    </div>
  );
}
