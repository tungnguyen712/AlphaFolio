"use client";

import Link from "next/link";
import { usePortfolioRecommendations } from "@/hooks/usePortfolios";
import { EmptyState } from "@/components/ui/EmptyState";
import { Spinner } from "@/components/ui/Spinner";

function verdictSignal(verdict: string): string {
  const w = verdict.split(" ")[0]?.toUpperCase() ?? "";
  if (w === "BUY") return "bg-buy-soft text-buy";
  if (w === "SELL") return "bg-sell-soft text-sell";
  return "bg-hold-soft text-hold";
}

export default function RecommendationsPage({ params }: { params: { id: string } }) {
  const { data: recs, loading, error } = usePortfolioRecommendations(params.id);

  if (loading) return <Spinner />;
  if (error) return <p className="text-sm text-sell">{error}</p>;

  return (
    <div>
      <h3 className="mb-4 text-xl font-semibold text-ink">Recommendations</h3>
      {recs.length === 0 ? (
        <EmptyState
          title="No recommendations yet"
          description="Run a portfolio analysis to generate recommendations."
          action={
            <Link
              href={`/portfolios/${params.id}/runs`}
              className="rounded bg-action px-4 py-2 text-sm font-medium text-action-ink hover:opacity-90"
            >
              Run analysis
            </Link>
          }
        />
      ) : (
        <ul className="space-y-2">
          {recs.map((rec) => (
            <li key={rec.id}>
              <Link
                href={`/portfolios/${params.id}/recommendations/${rec.id}`}
                className="flex items-center justify-between rounded-lg border border-rule bg-surface px-4 py-3 hover:bg-rule/30"
              >
                <div className="flex items-center gap-3">
                  <span
                    className={`rounded-full px-2 py-0.5 text-sm font-semibold ${verdictSignal(rec.recommendation.layers.verdict)}`}
                  >
                    {rec.recommendation.layers.verdict.split(" ")[0]?.toUpperCase()}
                  </span>
                  <span className="text-sm text-ink line-clamp-1">
                    {rec.recommendation.layers.verdict}
                  </span>
                </div>
                <span className="text-sm text-muted">
                  {new Date(rec.created_at).toLocaleDateString()}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
