"use client";

import Link from "next/link";
import { usePortfolioRecommendations } from "@/hooks/usePortfolios";
import { EmptyState } from "@/components/ui/EmptyState";
import { Spinner } from "@/components/ui/Spinner";

function verdictSignal(verdict: string): string {
  const w = verdict.split(" ")[0]?.toUpperCase() ?? "";
  if (w === "BUY") return "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-300";
  if (w === "SELL") return "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300";
  return "bg-yellow-100 text-yellow-800 dark:bg-yellow-950 dark:text-yellow-300";
}

export default function RecommendationsPage({ params }: { params: { id: string } }) {
  const { data: recs, loading, error } = usePortfolioRecommendations(params.id);

  if (loading) return <Spinner />;
  if (error) return <p className="text-sm text-red-600">{error}</p>;

  return (
    <div>
      <h3 className="mb-4 text-sm font-semibold text-neutral-800 dark:text-zinc-100">Recommendations</h3>
      {recs.length === 0 ? (
        <EmptyState
          title="No recommendations yet"
          description="Run a portfolio analysis to generate recommendations."
          action={
            <Link
              href={`/portfolios/${params.id}/runs`}
              className="rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-700 dark:bg-zinc-700 dark:hover:bg-zinc-600"
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
                className="flex items-center justify-between rounded-lg border border-neutral-200 bg-white px-4 py-3 hover:bg-neutral-50 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:bg-zinc-800/60"
              >
                <div className="flex items-center gap-3">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-semibold ${verdictSignal(rec.recommendation.layers.verdict)}`}
                  >
                    {rec.recommendation.layers.verdict.split(" ")[0]?.toUpperCase() ?? "—"}
                  </span>
                  <span className="text-sm text-neutral-700 line-clamp-1 dark:text-zinc-200">
                    {rec.recommendation.layers.verdict}
                  </span>
                </div>
                <span className="text-xs text-neutral-400 dark:text-zinc-500">
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
