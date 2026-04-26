"use client";

import Link from "next/link";
import { usePortfolio } from "@/hooks/usePortfolios";
import { EmptyState } from "@/components/ui/EmptyState";
import { Spinner } from "@/components/ui/Spinner";
import type { RiskProfile } from "@/lib/types";

const riskColors: Record<RiskProfile, string> = {
  conservative: "bg-blue-100 text-blue-700",
  moderate: "bg-yellow-100 text-yellow-700",
  aggressive: "bg-red-100 text-red-700",
};

const assetClassColors: Record<string, string> = {
  ipo: "bg-purple-100 text-purple-700",
  established: "bg-green-100 text-green-700",
  private: "bg-neutral-100 text-neutral-600",
};

export default function PortfolioOverviewPage({ params }: { params: { id: string } }) {
  const { data: portfolio, loading, error } = usePortfolio(params.id);

  if (loading) return <Spinner />;
  if (error) return <p className="text-sm text-red-600">{error}</p>;
  if (!portfolio) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="grid grid-cols-3 gap-4">
        <div className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-medium text-neutral-500">Cash balance</p>
          <p className="mt-1 text-xl font-bold text-neutral-900">
            ${parseFloat(portfolio.cash_balance).toLocaleString("en-US", { minimumFractionDigits: 2 })}
          </p>
        </div>
        <div className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-medium text-neutral-500">Risk profile</p>
          <p className="mt-2">
            <span className={`rounded-full px-3 py-1 text-sm font-semibold ${riskColors[portfolio.risk_profile]}`}>
              {portfolio.risk_profile}
            </span>
          </p>
        </div>
        <div className="rounded-xl border border-neutral-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-medium text-neutral-500">Holdings</p>
          <p className="mt-1 text-xl font-bold text-neutral-900">{portfolio.holdings.length}</p>
        </div>
      </div>

      {/* Holdings table */}
      <div className="rounded-xl border border-neutral-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-neutral-100 px-6 py-4">
          <h3 className="text-sm font-semibold text-neutral-800">Holdings</h3>
          <Link
            href={`/portfolios/${params.id}/holdings`}
            className="text-xs text-neutral-500 underline hover:text-neutral-800"
          >
            Manage
          </Link>
        </div>
        {portfolio.holdings.length === 0 ? (
          <div className="p-6">
            <EmptyState
              title="No holdings yet"
              description="Add holdings in the Holdings tab."
            />
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-neutral-100 text-xs text-neutral-500">
                <th className="px-6 py-3 text-left font-medium">Ticker</th>
                <th className="px-6 py-3 text-right font-medium">Shares</th>
                <th className="px-6 py-3 text-right font-medium">Avg cost</th>
                <th className="px-6 py-3 text-left font-medium">Class</th>
                <th className="px-6 py-3 text-left font-medium">Research</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-50">
              {portfolio.holdings.map((h) => (
                <tr key={h.id} className="hover:bg-neutral-50">
                  <td className="px-6 py-3 font-semibold text-neutral-900">{h.ticker}</td>
                  <td className="px-6 py-3 text-right text-neutral-700">{parseFloat(h.shares).toLocaleString()}</td>
                  <td className="px-6 py-3 text-right text-neutral-700">${parseFloat(h.avg_cost).toFixed(2)}</td>
                  <td className="px-6 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${assetClassColors[h.asset_class] ?? ""}`}>
                      {h.asset_class}
                    </span>
                  </td>
                  <td className="px-6 py-3">
                    <Link
                      href={`/research?ticker=${h.ticker}`}
                      className="text-xs text-neutral-400 underline hover:text-neutral-700"
                    >
                      Research {h.ticker}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
