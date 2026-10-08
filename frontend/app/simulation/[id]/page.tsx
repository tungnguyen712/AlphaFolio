"use client";

import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useSimulation } from "@/hooks/useSimulation";
import { MultiLineReturnChart } from "@/components/simulation/MultiLineReturnChart";
import { SimMetricsTable } from "@/components/simulation/SimMetricsTable";
import { Spinner } from "@/components/ui/Spinner";

export default function SimulationResultPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const { data, loading, error } = useSimulation(id);

  if (loading) {
    return (
      <div>
        <div className="flex flex-col items-center gap-4 py-20 text-center">
          <Spinner />
          <p className="text-base text-muted">Loading simulation</p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div>
        <div className="rounded-lg border border-sell/40 bg-sell-soft px-6 py-4">
          <p className="text-sm font-medium text-sell">
            {error ?? "Simulation not found"}
          </p>
        </div>
        <button
          onClick={() => router.push("/simulation")}
          className="mt-4 text-base text-action hover:underline"
        >
          New simulation
        </button>
      </div>
    );
  }

  const hasSeries = data.series && Object.keys(data.series).length > 0;
  const hasMetrics = data.metrics && Object.keys(data.metrics).length > 0;

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-ink">Simulation result</h1>
          <p className="mt-0.5 text-base text-muted">
            {data.start_date} to {data.end_date}, benchmark:{" "}
            <span className="tabular-nums">{data.benchmark}</span>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {data.positions.map((p) => (
            <span
              key={p.ticker}
              className="rounded bg-rule/60 px-2.5 py-0.5 tabular-nums text-sm text-ink"
            >
              {p.ticker} {(p.weight * 100).toFixed(0)}%
            </span>
          ))}
        </div>
      </div>

      {/* Chart */}
      {hasSeries ? (
        <div className="mb-10">
          <p className="mb-3 text-base font-medium text-muted">
            Cumulative % return from start date
          </p>
          <MultiLineReturnChart
            series={data.series!}
            benchmark={data.benchmark}
            portfolioSeries={data.portfolio_series}
          />
        </div>
      ) : (
        <div className="mb-10 rounded-lg border border-dashed border-rule px-6 py-10 text-base text-muted">
          No price data is available for this date range. Try a later start date.
        </div>
      )}

      {/* Metrics table */}
      {hasMetrics && (
        <div className="mb-10">
          <h2 className="mb-3 text-xl font-semibold text-ink">
            Performance metrics
          </h2>
          <SimMetricsTable
            metrics={data.metrics!}
            portfolioMetrics={data.portfolio_metrics}
            benchmark={data.benchmark}
          />
        </div>
      )}

      {/* Cross-links: Research each ticker as of start_date */}
      <div className="border-t border-rule pt-6">
        <p className="mb-3 text-lg font-semibold text-ink">
          Research these tickers historically (as of {data.start_date})
        </p>
        <div className="flex flex-wrap gap-2">
          {data.positions.map((p) => (
            <Link
              key={p.ticker}
              href={`/research?ticker=${p.ticker}&as_of_date=${data.start_date}`}
              className="rounded border border-rule bg-surface px-3 py-1.5 text-sm font-medium text-ink hover:border-action hover:text-action"
            >
              Research {p.ticker}
            </Link>
          ))}
        </div>
      </div>

      <div className="mt-6">
        <Link
          href="/simulation"
          className="text-base text-action hover:underline"
        >
          New simulation
        </Link>
      </div>
    </div>
  );
}
