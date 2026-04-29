"use client";

import type { SimMetrics } from "@/lib/types";

interface Props {
  metrics: Record<string, SimMetrics>;
  portfolioMetrics: SimMetrics | null;
  benchmark: string;
}

function pctCell(value: number) {
  const cls = value >= 0 ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400";
  return (
    <span className={cls}>
      {value >= 0 ? "+" : ""}
      {value.toFixed(2)}%
    </span>
  );
}

function numCell(value: number, decimals = 2) {
  return <span>{value.toFixed(decimals)}</span>;
}

const COLS = [
  { label: "Ticker", key: "ticker" as const },
  { label: "Total Return", key: "total_return" as const },
  { label: "CAGR", key: "cagr" as const },
  { label: "Sharpe", key: "sharpe" as const },
  { label: "Max Drawdown", key: "max_drawdown" as const },
];

export function SimMetricsTable({ metrics, portfolioMetrics, benchmark }: Props) {
  const rows: (SimMetrics & { isPortfolio?: boolean; isBenchmark?: boolean })[] = [];

  if (portfolioMetrics) {
    rows.push({ ...portfolioMetrics, isPortfolio: true });
  }

  const benchmarkMetrics = metrics[benchmark];
  if (benchmarkMetrics) {
    rows.push({ ...benchmarkMetrics, isBenchmark: true });
  }

  for (const [ticker, m] of Object.entries(metrics)) {
    if (ticker !== benchmark) {
      rows.push(m);
    }
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-zinc-200 dark:border-zinc-800">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-zinc-200 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900/50">
            {COLS.map((c) => (
              <th
                key={c.key}
                className="px-4 py-3 text-left text-xs font-medium text-zinc-500 dark:text-zinc-400"
              >
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
          {rows.map((row) => (
            <tr
              key={row.ticker + (row.isPortfolio ? "-portfolio" : "")}
              className={`${row.isPortfolio ? "bg-blue-50/50 dark:bg-blue-950/20 font-medium" : "bg-white dark:bg-zinc-950"}`}
            >
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-zinc-900 dark:text-zinc-100">{row.ticker}</span>
                  {row.isPortfolio && (
                    <span className="rounded-full bg-blue-100 px-1.5 py-0.5 text-[10px] font-medium text-blue-700 dark:bg-blue-900 dark:text-blue-300">
                      portfolio
                    </span>
                  )}
                  {row.isBenchmark && (
                    <span className="rounded-full bg-zinc-100 px-1.5 py-0.5 text-[10px] font-medium text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400">
                      benchmark
                    </span>
                  )}
                </div>
              </td>
              <td className="px-4 py-3">{pctCell(row.total_return)}</td>
              <td className="px-4 py-3">{pctCell(row.cagr)}</td>
              <td className="px-4 py-3">{numCell(row.sharpe, 3)}</td>
              <td className="px-4 py-3">{pctCell(row.max_drawdown)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
