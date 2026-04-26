"use client";

import { useState } from "react";
import Link from "next/link";
import { usePortfolios, useCreatePortfolio } from "@/hooks/usePortfolios";
import type { RiskProfile } from "@/lib/types";
import { EmptyState } from "@/components/ui/EmptyState";
import { Spinner } from "@/components/ui/Spinner";

const riskColors: Record<RiskProfile, string> = {
  conservative: "bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300",
  moderate: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  aggressive: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
};

const inputCls =
  "w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100 dark:focus:border-sky-500";

export default function PortfoliosPage() {
  const { data: portfolios, loading, error, refetch } = usePortfolios();
  const { mutate: createPortfolio, loading: creating, error: createError } = useCreatePortfolio();
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [cashBalance, setCashBalance] = useState("");
  const [riskProfile, setRiskProfile] = useState<RiskProfile>("moderate");

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const result = await createPortfolio({ name, cash_balance: cashBalance, risk_profile: riskProfile });
    if (result) {
      setShowForm(false);
      setName("");
      setCashBalance("");
      void refetch();
    }
  };

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-base font-semibold text-zinc-800 dark:text-zinc-200">Your portfolios</h2>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 dark:bg-sky-500 dark:hover:bg-sky-400"
        >
          {showForm ? "Cancel" : "+ Create portfolio"}
        </button>
      </div>

      {showForm && (
        <form
          onSubmit={(e) => void handleCreate(e)}
          className="mb-6 rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900"
        >
          <h3 className="mb-4 text-sm font-semibold text-zinc-800 dark:text-zinc-200">New portfolio</h3>
          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                className={inputCls}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
                Cash balance ($)
              </label>
              <input
                type="text"
                value={cashBalance}
                onChange={(e) => setCashBalance(e.target.value)}
                required
                className={inputCls}
                placeholder="10000.00"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
                Risk profile
              </label>
              <select
                value={riskProfile}
                onChange={(e) => setRiskProfile(e.target.value as RiskProfile)}
                className={inputCls}
              >
                <option value="conservative">Conservative</option>
                <option value="moderate">Moderate</option>
                <option value="aggressive">Aggressive</option>
              </select>
            </div>
          </div>
          {createError && (
            <p className="mt-2 text-xs text-red-600 dark:text-red-400">{createError}</p>
          )}
          <button
            type="submit"
            disabled={creating}
            className="mt-4 flex items-center gap-2 rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50 dark:bg-sky-500 dark:hover:bg-sky-400"
          >
            {creating && <Spinner size="sm" />}
            Create
          </button>
        </form>
      )}

      {loading ? (
        <div className="flex justify-center pt-16"><Spinner /></div>
      ) : error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-5 dark:border-red-900 dark:bg-red-950/40">
          <p className="text-sm font-semibold text-red-800 dark:text-red-300">Failed to load portfolios</p>
          <p className="mt-0.5 text-sm text-red-700 dark:text-red-400">{error}</p>
        </div>
      ) : portfolios.length === 0 ? (
        <EmptyState
          title="No portfolios yet"
          description="Create your first portfolio to start building."
          icon={
            <svg className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 18.75a60.07 60.07 0 0 1 15.797 2.101c.727.198 1.453-.342 1.453-1.096V18.75M3.75 4.5v.75A.75.75 0 0 1 3 6h-.75m0 0v-.375c0-.621.504-1.125 1.125-1.125H20.25M2.25 6v9m18-10.5v.75c0 .414.336.75.75.75h.75m-1.5-1.5h.375c.621 0 1.125.504 1.125 1.125v9.75c0 .621-.504 1.125-1.125 1.125h-.375m1.5-1.5H21a.75.75 0 0 0-.75.75v.75m0 0H3.75m0 0h-.375a1.125 1.125 0 0 1-1.125-1.125V15m1.5 1.5v-.75A.75.75 0 0 0 3 15h-.75M15 10.5a3 3 0 1 1-6 0 3 3 0 0 1 6 0Zm3 0h.008v.008H18V10.5Zm-12 0h.008v.008H6V10.5Z" />
            </svg>
          }
          action={
            <button
              onClick={() => setShowForm(true)}
              className="rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 dark:bg-sky-500 dark:hover:bg-sky-400"
            >
              + Create portfolio
            </button>
          }
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {portfolios.map((p) => (
            <Link
              key={p.id}
              href={`/portfolios/${p.id}`}
              className="rounded-xl border border-zinc-200 bg-white p-5 transition-colors hover:border-zinc-300 hover:bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-zinc-700 dark:hover:bg-zinc-800/60"
            >
              <div className="mb-3 flex items-center justify-between">
                <span className="text-base font-semibold text-zinc-900 dark:text-zinc-100">{p.name}</span>
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${riskColors[p.risk_profile]}`}>
                  {p.risk_profile}
                </span>
              </div>
              <p className="font-mono text-sm text-zinc-500 dark:text-zinc-400">
                Cash:{" "}
                <strong className="text-zinc-800 dark:text-zinc-200">
                  ${parseFloat(p.cash_balance).toLocaleString("en-US", { minimumFractionDigits: 2 })}
                </strong>
              </p>
              <p className="mt-1 font-mono text-xs text-zinc-400 dark:text-zinc-500">
                {new Date(p.created_at).toLocaleDateString()}
              </p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
