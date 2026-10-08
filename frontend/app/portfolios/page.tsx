"use client";

import { useState } from "react";
import Link from "next/link";
import { usePortfolios, useCreatePortfolio } from "@/hooks/usePortfolios";
import type { RiskProfile } from "@/lib/types";
import { EmptyState } from "@/components/ui/EmptyState";
import { Spinner } from "@/components/ui/Spinner";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { Field, inputClass } from "@/components/ui/Field";
import { ErrorState } from "@/components/ui/Panel";
import { PageHeader } from "@/components/ui/PageHeader";

const riskTone: Record<RiskProfile, "action" | "hold" | "sell"> = {
  conservative: "action",
  moderate: "hold",
  aggressive: "sell",
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
      <PageHeader
        title="Portfolios"
        description="Hold your positions, review the allocation, and get rebalance recommendations."
        action={
          <Button variant={showForm ? "secondary" : "primary"} onClick={() => setShowForm((v) => !v)}>
            {showForm ? "Cancel" : "Create portfolio"}
          </Button>
        }
      />

      {showForm && (
        <form
          onSubmit={(e) => void handleCreate(e)}
          className="mb-8 max-w-form rounded-lg border border-rule bg-surface p-6"
        >
          <h2 className="mb-4 text-xl font-semibold text-ink">New portfolio</h2>
          <div className="space-y-4">
            <Field label="Name">
              <input type="text" value={name} onChange={(e) => setName(e.target.value)} required className={inputClass} />
            </Field>
            <Field label="Cash balance ($)">
              <input
                type="text"
                inputMode="decimal"
                value={cashBalance}
                onChange={(e) => setCashBalance(e.target.value)}
                required
                className={inputClass}
                placeholder="10000.00"
              />
            </Field>
            <Field label="Risk profile" hint="Sets the maximum size of any single position when the optimizer builds an allocation.">
              <select
                value={riskProfile}
                onChange={(e) => setRiskProfile(e.target.value as RiskProfile)}
                className={inputClass}
              >
                <option value="conservative">Conservative</option>
                <option value="moderate">Moderate</option>
                <option value="aggressive">Aggressive</option>
              </select>
            </Field>
          </div>
          {createError && (
            <p role="alert" className="mt-3 text-sm text-sell">
              {createError}
            </p>
          )}
          <Button type="submit" disabled={creating} className="mt-5">
            {creating && <Spinner size="sm" />}
            Create portfolio
          </Button>
        </form>
      )}

      {loading ? (
        <div className="flex justify-center pt-16">
          <Spinner />
        </div>
      ) : error ? (
        <ErrorState title="Couldn't load your portfolios" message={error} onRetry={() => void refetch()} />
      ) : portfolios.length === 0 ? (
        <EmptyState
          title="No portfolios yet"
          description="Create a portfolio to track holdings, or research a stock and add it from its report."
          action={<Button onClick={() => setShowForm(true)}>Create portfolio</Button>}
        />
      ) : (
        <ul>
          {portfolios.map((p) => (
            <li key={p.id}>
              <Link
                href={`/portfolios/${p.id}`}
                className="flex flex-wrap items-baseline gap-y-1 border-b border-rule px-1 py-4 hover:bg-highlight/30"
              >
                <span className="font-serif text-2xl font-semibold tracking-tight">{p.name}</span>
                <span className="mx-3 hidden min-w-4 flex-1 border-b-2 border-dotted border-ink/40 sm:block" aria-hidden />
                <span className="mr-6">
                  <Chip tone={riskTone[p.risk_profile]}>{p.risk_profile}</Chip>
                </span>
                <span className="text-base text-muted">
                  Cash{" "}
                  <span className="font-serif text-xl font-semibold text-ink">
                    ${parseFloat(p.cash_balance).toLocaleString("en-US", { minimumFractionDigits: 2 })}
                  </span>
                </span>
                <span className="ml-6 w-20 text-right text-sm text-muted">
                  {new Date(p.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
