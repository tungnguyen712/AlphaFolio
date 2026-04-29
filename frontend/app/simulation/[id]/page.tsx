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
      <main className="mx-auto max-w-5xl px-6 py-12">
        <div className="flex flex-col items-center gap-4 py-20 text-center">
          <Spinner />
          <p className="text-sm text-zinc-500 dark:text-zinc-400">Loading simulation…</p>
        </div>
      </main>
    );
  }

  if (error || !data) {
    return (
      <main className="mx-auto max-w-5xl px-6 py-12">
        <div className="rounded-xl border border-red-200 bg-red-50 px-6 py-4 dark:border-red-900 dark:bg-red-950/30">
          <p className="text-sm font-medium text-red-700 dark:text-red-400">
            {error ?? "Simulation not found"}
          </p>
        </div>
        <button
          onClick={() => router.push("/simulation")}
          className="mt-4 text-sm text-zinc-500 underline hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200"
        >
          ← New simulation
        </button>
      </main>
    );
  }

  const hasSeries = data.series && Object.keys(data.series).length > 0;
  const hasMetrics = data.metrics && Object.keys(data.metrics).length > 0;

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold text-zinc-900 dark:text-zinc-100">Simulation result</h1>
          <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">
            {data.start_date} → {data.end_date} · benchmark:{" "}
            <span className="font-mono">{data.benchmark}</span>
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {data.positions.map((p) => (
            <span
              key={p.ticker}
              className="rounded-full border border-zinc-200 bg-zinc-50 px-2.5 py-0.5 font-mono text-xs text-zinc-600 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400"
            >
              {p.ticker} {(p.weight * 100).toFixed(0)}%
            </span>
          ))}
        </div>
      </div>

      {/* Chart */}
      {hasSeries ? (
        <div className="mb-6 rounded-xl border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <p className="mb-3 text-xs font-medium text-zinc-500 dark:text-zinc-400">
            Cumulative % return from start date
          </p>
          <MultiLineReturnChart
            series={data.series!}
            benchmark={data.benchmark}
            portfolioSeries={data.portfolio_series}
          />
        </div>
      ) : (
        <div className="mb-6 rounded-xl border border-zinc-200 bg-zinc-50 px-6 py-8 text-center text-sm text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
          No price data available for the selected date range.
        </div>
      )}

      {/* Metrics table */}
      {hasMetrics && (
        <div className="mb-6">
          <h2 className="mb-3 text-sm font-semibold text-zinc-700 dark:text-zinc-300">
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
      <div className="rounded-xl border border-zinc-200 bg-zinc-50 p-4 dark:border-zinc-800 dark:bg-zinc-900">
        <p className="mb-3 text-xs font-medium text-zinc-600 dark:text-zinc-400">
          Research these tickers historically (as of {data.start_date})
        </p>
        <div className="flex flex-wrap gap-2">
          {data.positions.map((p) => (
            <Link
              key={p.ticker}
              href={`/research?ticker=${p.ticker}&as_of_date=${data.start_date}`}
              className="rounded-lg border border-zinc-300 bg-white px-3 py-1.5 text-xs font-medium text-zinc-700 hover:border-sky-400 hover:text-sky-700 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-300 dark:hover:border-sky-600 dark:hover:text-sky-400"
            >
              Research {p.ticker} →
            </Link>
          ))}
        </div>
      </div>

      <div className="mt-6">
        <Link
          href="/simulation"
          className="text-sm text-zinc-500 underline hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200"
        >
          ← New simulation
        </Link>
      </div>
    </main>
  );
}
