"use client";

import { useState } from "react";
import Link from "next/link";
import { usePortfolios, useCreatePortfolio } from "@/hooks/usePortfolios";
import type { RiskProfile } from "@/lib/types";
import { EmptyState } from "@/components/ui/EmptyState";
import { Spinner } from "@/components/ui/Spinner";

const riskColors: Record<RiskProfile, string> = {
  conservative: "bg-blue-100 text-blue-700",
  moderate: "bg-yellow-100 text-yellow-700",
  aggressive: "bg-red-100 text-red-700",
};

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
        <h2 className="text-base font-semibold text-neutral-800">Your portfolios</h2>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-700"
        >
          {showForm ? "Cancel" : "+ Create portfolio"}
        </button>
      </div>

      {showForm && (
        <form
          onSubmit={(e) => void handleCreate(e)}
          className="mb-6 rounded-xl border border-neutral-200 bg-white p-6 shadow-sm"
        >
          <h3 className="mb-4 text-sm font-semibold text-neutral-800">New portfolio</h3>
          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-neutral-600">Name</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                className="w-full rounded-md border border-neutral-300 px-3 py-2 text-sm focus:border-neutral-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-neutral-600">
                Cash balance ($)
              </label>
              <input
                type="text"
                value={cashBalance}
                onChange={(e) => setCashBalance(e.target.value)}
                required
                className="w-full rounded-md border border-neutral-300 px-3 py-2 text-sm focus:border-neutral-500 focus:outline-none"
                placeholder="10000.00"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-neutral-600">
                Risk profile
              </label>
              <select
                value={riskProfile}
                onChange={(e) => setRiskProfile(e.target.value as RiskProfile)}
                className="w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm focus:border-neutral-500 focus:outline-none"
              >
                <option value="conservative">Conservative</option>
                <option value="moderate">Moderate</option>
                <option value="aggressive">Aggressive</option>
              </select>
            </div>
          </div>
          {createError && <p className="mt-2 text-xs text-red-600">{createError}</p>}
          <button
            type="submit"
            disabled={creating}
            className="mt-4 flex items-center gap-2 rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-700 disabled:opacity-50"
          >
            {creating && <Spinner size="sm" />}
            Create
          </button>
        </form>
      )}

      {loading ? (
        <Spinner />
      ) : error ? (
        <p className="text-sm text-red-600">{error}</p>
      ) : portfolios.length === 0 ? (
        <EmptyState
          title="No portfolios yet"
          description="Create your first portfolio to start building."
          action={
            <button
              onClick={() => setShowForm(true)}
              className="rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-700"
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
              className="rounded-xl border border-neutral-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md"
            >
              <div className="mb-3 flex items-center justify-between">
                <span className="text-base font-semibold text-neutral-900">{p.name}</span>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs font-medium ${riskColors[p.risk_profile]}`}
                >
                  {p.risk_profile}
                </span>
              </div>
              <p className="text-sm text-neutral-500">
                Cash:{" "}
                <strong className="text-neutral-800">
                  ${parseFloat(p.cash_balance).toLocaleString("en-US", { minimumFractionDigits: 2 })}
                </strong>
              </p>
              <p className="mt-1 text-xs text-neutral-400">
                {new Date(p.created_at).toLocaleDateString()}
              </p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
