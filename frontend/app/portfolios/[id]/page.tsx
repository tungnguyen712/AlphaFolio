"use client";

import Link from "next/link";
import { usePortfolio, useUpdatePortfolio } from "@/hooks/usePortfolios";
import { usePortfolioMarketData } from "@/hooks/usePortfolioMarketData";
import { EmptyState } from "@/components/ui/EmptyState";
import { Spinner } from "@/components/ui/Spinner";
import { StatCard } from "@/components/ui/StatCard";
import { Chip } from "@/components/ui/Chip";
import { ErrorState } from "@/components/ui/Panel";
import { CapitalBar } from "@/components/ui/CapitalBar";
import { AllocationDonut } from "@/components/charts/AllocationDonut";
import { AssetClassBar } from "@/components/charts/AssetClassBar";
import { SectorBar } from "@/components/charts/SectorBar";
import type { AssetClass, RiskProfile } from "@/lib/types";

const riskTone: Record<RiskProfile, "action" | "hold" | "sell"> = {
  conservative: "action",
  moderate: "hold",
  aggressive: "sell",
};

const assetTone: Record<AssetClass, "action" | "buy"> = {
  ipo: "action",
  established: "buy",
  private: "action",
};

function fmtCompact(n: number) {
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

export default function PortfolioOverviewPage({ params }: { params: { id: string } }) {
  const { data: portfolio, loading, error, refetch } = usePortfolio(params.id);
  const { data: marketData, loading: mktLoading } = usePortfolioMarketData(params.id);
  const { mutate: updatePortfolio } = useUpdatePortfolio(params.id);

  if (loading) return <div className="flex justify-center pt-16"><Spinner /></div>;
  if (error) return <ErrorState title="Couldn't load this portfolio" message={error} onRetry={() => void refetch()} />;
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

  const gainTone = gainAbs === null ? "text-ink" : gainAbs >= 0 ? "text-buy" : "text-sell";

  return (
    <div className="space-y-10">
      {/* Header strip: total value first, the rest supports it */}
      <div className="grid gap-6 sm:grid-cols-[minmax(0,1.4fr)_repeat(3,minmax(0,1fr))]">
        <div>
          <p className="text-base text-muted">Total value</p>
          {mktLoading ? (
            <div className="mt-2 h-12 w-48 animate-pulse rounded bg-rule/60" />
          ) : (
            <p className="font-serif text-3xl font-semibold text-ink">{fmtCompact(totalValue ?? totalInvested + cash)}</p>
          )}
          {totalValue === null && !mktLoading && (
            <p className="mt-1 max-w-[16rem] text-base text-muted">Based on what you paid. Live prices are unavailable right now.</p>
          )}
          {gainPct !== null && (
            <p className={`text-lg font-medium ${gainTone}`}>
              {gainPct >= 0 ? "▲" : "▼"} {Math.abs(gainPct).toFixed(2)}% overall
            </p>
          )}
        </div>
        <StatCard label="Invested" value={fmtCompact(totalInvested)} />
        <StatCard label="Gain or loss" value={gainAbs !== null ? fmtCompact(gainAbs) : null} emptyText="Shown once live prices load" loading={mktLoading} />
        <StatCard label="Cash" value={fmtCompact(cash)} />
      </div>

      <CapitalBar
        invested={totalInvested}
        cash={cash}
        onCashSave={async (newCash) => {
          await updatePortfolio({ cash_balance: newCash.toFixed(2) });
          await refetch();
        }}
      />

      {holdings.length > 0 && (
        <div className="grid grid-cols-1 gap-10 lg:grid-cols-2">
          <section>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-xl font-semibold text-ink">Allocation</h2>
              <Chip tone={riskTone[portfolio.risk_profile]}>{portfolio.risk_profile}</Chip>
            </div>
            <AllocationDonut
              data={allocationData}
              totalLabel={totalValue !== null ? fmtCompact(totalValue) : undefined}
            />
          </section>

          <div className="space-y-8">
            <section>
              <h2 className="mb-2 text-xl font-semibold text-ink">By asset class</h2>
              <AssetClassBar data={assetClassData} />
            </section>
            <section>
              <h2 className="mb-2 text-xl font-semibold text-ink">By sector</h2>
              <SectorBar data={sectorData} />
            </section>
          </div>
        </div>
      )}

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-xl font-semibold text-ink">Holdings</h2>
          <Link href={`/portfolios/${params.id}/holdings`} className="text-base text-action hover:underline">
            Manage holdings
          </Link>
        </div>
        {holdings.length === 0 ? (
          <EmptyState
            title="No holdings yet"
            description="Add holdings on the Holdings tab, or research a stock and add it from its report."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-base">
              <thead>
                <tr className="border-b border-ink/30 text-sm text-muted">
                  <th className="py-2 pr-4 text-left font-medium">Ticker</th>
                  <th className="px-4 py-2 text-right font-medium">Shares</th>
                  <th className="px-4 py-2 text-right font-medium">Avg cost</th>
                  <th className="px-4 py-2 text-right font-medium">Price</th>
                  <th className="px-4 py-2 text-right font-medium">Value</th>
                  <th className="px-4 py-2 text-right font-medium">Weight</th>
                  <th className="px-4 py-2 text-left font-medium">Class</th>
                  <th className="py-2 pl-4 text-right font-medium">
                    <span className="sr-only">Research</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
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
                    <tr key={h.id} className="hover:bg-rule/30">
                      <td className="py-3 pr-4 font-semibold text-ink">{h.ticker}</td>
                      <td className="px-4 py-3 text-right tabular-nums text-ink">{shares.toLocaleString()}</td>
                      <td className="px-4 py-3 text-right tabular-nums text-ink">${avgCost.toFixed(2)}</td>
                      <td className="px-4 py-3 text-right tabular-nums text-ink">
                        {mktLoading ? (
                          <span className="inline-block h-4 w-14 animate-pulse rounded bg-rule/60" />
                        ) : curPrice !== null ? (
                          <span>
                            ${curPrice.toFixed(2)}
                            {gainOnHolding !== null && (
                              <span className={`ml-2 text-sm ${gainOnHolding >= 0 ? "text-buy" : "text-sell"}`}>
                                {gainOnHolding >= 0 ? "▲" : "▼"}
                                {Math.abs(gainOnHolding).toFixed(1)}%
                              </span>
                            )}
                          </span>
                        ) : (
                          <span className="text-sm text-muted" title="The price provider returned no price for this ticker">No live price</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right font-medium tabular-nums text-ink">
                        {fmtCompact(holdingValue)}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-2">
                          <div className="h-1.5 w-16 overflow-hidden rounded-sm bg-rule">
                            <div className="h-full bg-action" style={{ width: `${Math.min(allocPct, 100)}%` }} />
                          </div>
                          <span className="w-12 text-right text-sm tabular-nums text-muted">{allocPct.toFixed(1)}%</span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <Chip tone={assetTone[h.asset_class]}>{h.asset_class}</Chip>
                      </td>
                      <td className="py-3 pl-4 text-right">
                        <Link
                          href={`/research?ticker=${h.ticker}`}
                          className="whitespace-nowrap text-action hover:underline"
                        >
                          Research {h.ticker}
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
