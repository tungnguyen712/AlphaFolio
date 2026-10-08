"use client";

import type { SimMetrics } from "@/lib/types";

interface Props {
  metrics: Record<string, SimMetrics>;
  portfolioMetrics: SimMetrics | null;
  benchmark: string;
}

function pctCell(value: number) {
  const cls = value >= 0 ? "text-buy" : "text-sell";
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
    <div className="overflow-x-auto rounded-lg border border-rule">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-rule bg-rule/30">
            {COLS.map((c) => (
              <th
                key={c.key}
                className="px-4 py-3 text-left text-sm font-medium text-muted"
              >
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-rule ">
          {rows.map((row) => (
            <tr
              key={row.ticker + (row.isPortfolio ? "-portfolio" : "")}
              className={`${row.isPortfolio ? "bg-action/10 font-medium" : "bg-surface "}`}
            >
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  <span className="tabular-nums text-ink">{row.ticker}</span>
                  {row.isPortfolio && (
                    <span className="rounded-full bg-action/10 px-1.5 py-0.5 text-sm font-medium text-action">
                      portfolio
                    </span>
                  )}
                  {row.isBenchmark && (
                    <span className="rounded-full bg-rule/60 px-1.5 py-0.5 text-sm font-medium text-muted">
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
