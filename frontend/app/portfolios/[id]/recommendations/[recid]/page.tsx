"use client";

import Link from "next/link";
import { usePortfolioRecommendations } from "@/hooks/usePortfolios";
import { VerdictCard } from "@/components/ui/VerdictCard";
import { Spinner } from "@/components/ui/Spinner";

export default function RecommendationDetailPage({
  params,
}: {
  params: { id: string; recid: string };
}) {
  const { data: recs, loading, error } = usePortfolioRecommendations(params.id);
  const rec = recs.find((r) => r.id === params.recid);

  if (loading) return <Spinner />;
  if (error) return <p className="text-sm text-red-600">{error}</p>;
  if (!rec) return <p className="text-sm text-neutral-500">Recommendation not found.</p>;

  return (
    <div className="max-w-2xl space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold text-neutral-800">Recommendation</h3>
        <Link
          href={`/portfolios/${params.id}/recommendations`}
          className="text-sm text-neutral-400 hover:text-neutral-700"
        >
          ← All recommendations
        </Link>
      </div>

      <VerdictCard layers={rec.recommendation.layers} />

      <div className="rounded-xl border border-neutral-200 bg-white p-6">
        <h4 className="mb-3 text-sm font-semibold text-neutral-700">Rationale</h4>
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-neutral-700">
          {rec.recommendation.rationale}
        </p>
      </div>

      {rec.recommendation.proposed_trades.length > 0 && (
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
              {rec.recommendation.proposed_trades.map((trade, i) => (
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

      {Object.keys(rec.recommendation.target_allocations).length > 0 && (
        <div className="rounded-xl border border-neutral-200 bg-white p-6">
          <h4 className="mb-3 text-sm font-semibold text-neutral-700">Target allocations</h4>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {Object.entries(rec.recommendation.target_allocations).map(([ticker, pct]) => (
              <div
                key={ticker}
                className="flex items-center justify-between rounded bg-neutral-50 px-3 py-2"
              >
                <span className="text-sm font-semibold text-neutral-800">{ticker}</span>
                <span className="text-sm text-neutral-600">{Math.round(pct * 100)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <p className="text-xs text-neutral-400">
        Generated {new Date(rec.created_at).toLocaleString()}
      </p>
    </div>
  );
}
