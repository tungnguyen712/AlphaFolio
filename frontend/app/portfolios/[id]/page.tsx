"use client";

import Link from "next/link";
import { usePortfolio, useUpdatePortfolio } from "@/hooks/usePortfolios";
import { usePortfolioMarketData } from "@/hooks/usePortfolioMarketData";
import { EmptyState } from "@/components/ui/EmptyState";
import { Spinner } from "@/components/ui/Spinner";
import { StatCard } from "@/components/ui/StatCard";
import { CapitalBar } from "@/components/ui/CapitalBar";
import { AllocationDonut } from "@/components/charts/AllocationDonut";
import { AssetClassBar } from "@/components/charts/AssetClassBar";
import { SectorBar } from "@/components/charts/SectorBar";
import type { AssetClass, RiskProfile } from "@/lib/types";

const riskColors: Record<RiskProfile, string> = {
  conservative: "bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300",
  moderate: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  aggressive: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
};

const ipoStyle = "bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300";

const assetClassColors: Record<AssetClass, string> = {
  ipo: ipoStyle,
  established: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  private: ipoStyle,
};

function fmtCompact(n: number) {
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

export default function PortfolioOverviewPage({ params }: { params: { id: string } }) {
  const { data: portfolio, loading, error, refetch } = usePortfolio(params.id);
  const { data: marketData, loading: mktLoading } = usePortfolioMarketData(params.id);
  const { mutate: updatePortfolio } = useUpdatePortfolio(params.id);

  if (loading) return <div className="flex justify-center pt-16"><Spinner /></div>;
  if (error) return (
    <div className="rounded-xl border border-red-200 bg-red-50 p-5 dark:border-red-900 dark:bg-red-950/40">
      <p className="text-sm font-semibold text-red-800 dark:text-red-300">Failed to load portfolio</p>
      <p className="mt-0.5 text-sm text-red-700 dark:text-red-400">{error}</p>
    </div>
  );
  if (!portfolio) return null;

  const cash = parseFloat(portfolio.cash_balance);
  const holdings = portfolio.holdings;

  const totalInvested = holdings.reduce(
    (s, h) => s + parseFloat(h.shares) * parseFloat(h.avg_cost),
    0
  );

  const prices = marketData?.prices ?? {};
  const hasPrices = Object.values(prices).some((p) => p.prev_close !== null);

  const currentValue = hasPrices
    ? holdings.reduce((s, h) => {
        const p = prices[h.ticker]?.prev_close;
        return s + (p !== null && p !== undefined ? parseFloat(h.shares) * p : parseFloat(h.shares) * parseFloat(h.avg_cost));
      }, 0)
    : null;

  const totalValue = currentValue !== null ? currentValue + cash : null;
  const gainAbs = totalValue !== null ? totalValue - (totalInvested + cash) : null;
  const gainPct = gainAbs !== null && totalInvested > 0 ? (gainAbs / totalInvested) * 100 : null;

  const allocationData = holdings.map((h) => ({
    name: h.ticker,
    value:
      hasPrices && prices[h.ticker]?.prev_close != null
        ? parseFloat(h.shares) * prices[h.ticker]!.prev_close!
        : parseFloat(h.shares) * parseFloat(h.avg_cost),
  }));

  const assetClassMap: Record<string, number> = {};
  for (const h of holdings) {
    const key = h.asset_class === "private" ? "ipo" : h.asset_class;
    const val = parseFloat(h.shares) * parseFloat(h.avg_cost);
    assetClassMap[key] = (assetClassMap[key] ?? 0) + val;
  }
  const assetClassData = Object.entries(assetClassMap).map(([name, value]) => ({ name, value }));

  const sectorMap: Record<string, number> = {};
  for (const h of holdings) {
    const sector = prices[h.ticker]?.sector;
    if (sector) {
      const val = parseFloat(h.shares) * parseFloat(h.avg_cost);
      sectorMap[sector] = (sectorMap[sector] ?? 0) + val;
    }
  }
  const sectorData = Object.entries(sectorMap)
    .sort((a, b) => b[1] - a[1])
    .map(([name, value]) => ({ name, value }));

  return (
    <div className="space-y-6">
      {/* Stat row */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard label="Total Inputs" value={fmtCompact(totalInvested)} />
        <StatCard
          label="Money Gained"
          value={gainAbs !== null ? fmtCompact(gainAbs) : "—"}
          loading={mktLoading}
        />
        <StatCard
          label="% Gained"
          value={
            gainPct !== null
              ? `${gainPct >= 0 ? "+" : ""}${gainPct.toFixed(2)}%`
              : "—"
          }
          delta={
            gainPct !== null
              ? { value: `${Math.abs(gainPct).toFixed(2)}%`, positive: gainPct >= 0 }
              : undefined
          }
          loading={mktLoading}
        />
        <StatCard
          label="Total Value"
          value={totalValue !== null ? fmtCompact(totalValue) : "—"}
          loading={mktLoading}
        />
      </div>

      {/* Capital bar */}
      <CapitalBar
        invested={totalInvested}
        cash={cash}
        onCashSave={async (newCash) => {
          await updatePortfolio({ cash_balance: newCash.toFixed(2) });
          await refetch();
        }}
      />

      {/* Charts row */}
      {holdings.length > 0 && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
            <div className="mb-3 flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                Allocation
              </p>
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${riskColors[portfolio.risk_profile]}`}>
                {portfolio.risk_profile}
              </span>
            </div>
            <AllocationDonut
              data={allocationData}
              totalLabel={totalValue !== null ? fmtCompact(totalValue) : undefined}
            />
          </div>

          <div className="space-y-4">
            <div className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
              <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                By asset class
              </p>
              <AssetClassBar data={assetClassData} />
            </div>

            <div className="rounded-xl border border-zinc-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
              <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
                By sector
              </p>
              <SectorBar data={sectorData} />
            </div>
          </div>
        </div>
      )}

      {/* Holdings table */}
      <div className="rounded-xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
        <div className="flex items-center justify-between border-b border-zinc-100 px-6 py-4 dark:border-zinc-800">
          <h3 className="text-sm font-semibold text-zinc-800 dark:text-zinc-200">Holdings</h3>
          <Link
            href={`/portfolios/${params.id}/holdings`}
            className="text-xs text-zinc-400 underline hover:text-zinc-700 dark:text-zinc-500 dark:hover:text-zinc-300"
          >
            Manage
          </Link>
        </div>
        {holdings.length === 0 ? (
          <div className="p-6">
            <EmptyState
              title="No holdings yet"
              description="Add holdings in the Holdings tab."
              icon={
                <svg className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" />
                </svg>
              }
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-100 text-xs text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
                  <th className="px-6 py-3 text-left font-medium">Ticker</th>
                  <th className="px-6 py-3 text-right font-medium">Shares</th>
                  <th className="px-6 py-3 text-right font-medium">Avg cost</th>
                  <th className="px-6 py-3 text-right font-medium">Cur. price</th>
                  <th className="px-6 py-3 text-right font-medium">Value</th>
                  <th className="px-6 py-3 text-right font-medium">Alloc %</th>
                  <th className="px-6 py-3 text-left font-medium">Class</th>
                  <th className="px-6 py-3 text-left font-medium">Research</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-50 dark:divide-zinc-800/60">
                {holdings.map((h) => {
                  const shares = parseFloat(h.shares);
                  const avgCost = parseFloat(h.avg_cost);
                  const curPrice = prices[h.ticker]?.prev_close ?? null;
                  const holdingValue = curPrice !== null ? shares * curPrice : shares * avgCost;
                  const totalPortValue = totalValue ?? totalInvested + cash;
                  const allocPct = totalPortValue > 0 ? (holdingValue / totalPortValue) * 100 : 0;
                  const gainOnHolding =
                    curPrice !== null ? ((curPrice - avgCost) / avgCost) * 100 : null;

                  return (
                    <tr key={h.id} className="hover:bg-zinc-50 dark:hover:bg-zinc-800/40">
                      <td className="px-6 py-3 font-mono font-semibold text-zinc-900 dark:text-zinc-100">
                        {h.ticker}
                      </td>
                      <td className="px-6 py-3 text-right font-mono text-zinc-700 dark:text-zinc-300">
                        {shares.toLocaleString()}
                      </td>
                      <td className="px-6 py-3 text-right font-mono text-zinc-700 dark:text-zinc-300">
                        ${avgCost.toFixed(2)}
                      </td>
                      <td className="px-6 py-3 text-right font-mono text-zinc-700 dark:text-zinc-300">
                        {mktLoading ? (
                          <span className="inline-block h-4 w-14 animate-pulse rounded bg-zinc-100 dark:bg-zinc-800" />
                        ) : curPrice !== null ? (
                          <span>
                            ${curPrice.toFixed(2)}
                            {gainOnHolding !== null && (
                              <span
                                className={`ml-1.5 text-xs ${gainOnHolding >= 0 ? "text-emerald-500" : "text-red-500"}`}
                              >
                                {gainOnHolding >= 0 ? "▲" : "▼"}
                                {Math.abs(gainOnHolding).toFixed(1)}%
                              </span>
                            )}
                          </span>
                        ) : (
                          <span className="text-zinc-400">—</span>
                        )}
                      </td>
                      <td className="px-6 py-3 text-right font-mono text-zinc-900 dark:text-zinc-100">
                        {fmtCompact(holdingValue)}
                      </td>
                      <td className="px-6 py-3 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <div className="h-1.5 w-16 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
                            <div
                              className="h-full rounded-full bg-sky-500"
                              style={{ width: `${Math.min(allocPct, 100)}%` }}
                            />
                          </div>
                          <span className="font-mono text-xs text-zinc-500 dark:text-zinc-400">
                            {allocPct.toFixed(1)}%
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-3">
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs font-medium ${assetClassColors[h.asset_class]}`}
                        >
                          {h.asset_class}
                        </span>
                      </td>
                      <td className="px-6 py-3">
                        <Link
                          href={`/research?ticker=${h.ticker}`}
                          className="text-xs text-sky-500 underline hover:text-sky-600 dark:text-sky-400 dark:hover:text-sky-300"
                        >
                          Research
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
