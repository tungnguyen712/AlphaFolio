"use client";

import { useState } from "react";
import { usePortfolios } from "@/hooks/usePortfolios";
import { useCreatePendingPosition } from "@/hooks/usePortfolios";
import { Spinner } from "@/components/ui/Spinner";
import { Button } from "@/components/ui/Button";
import { Field, inputClass } from "@/components/ui/Field";

interface AddToPortfolioModalProps {
  reportId: string;
  ticker: string;
  isOpen: boolean;
  onClose: () => void;
}

export function AddToPortfolioModal({
  reportId,
  ticker,
  isOpen,
  onClose,
}: AddToPortfolioModalProps) {
  const { data: portfolios, loading: portfoliosLoading } = usePortfolios();
  const [selectedPortfolioId, setSelectedPortfolioId] = useState("");
  const [targetPct, setTargetPct] = useState("5");
  const [success, setSuccess] = useState(false);

  const createPending = useCreatePendingPosition(selectedPortfolioId || "placeholder");

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPortfolioId) return;

    const pctDecimal = (parseFloat(targetPct) / 100).toFixed(4);
    const result = await createPending.mutate({
      ticker,
      target_pct: pctDecimal,
      source_report_id: reportId,
    });

    if (result) {
      setSuccess(true);
      setTimeout(() => {
        setSuccess(false);
        onClose();
      }, 1500);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-to-portfolio-title"
        className="w-full max-w-sm rounded-lg border border-rule bg-surface p-6 shadow-xl"
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 id="add-to-portfolio-title" className="text-xl font-semibold text-ink">
            Add {ticker} to a portfolio
          </h2>
          <button onClick={onClose} className="rounded p-1 text-muted hover:text-ink" aria-label="Close">
            ✕
          </button>
        </div>

        {success ? (
          <p className="text-base font-medium text-buy">
            Added as a pending position. Review it on the Pending tab of that portfolio.
          </p>
        ) : (
          <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
            {portfoliosLoading ? (
              <Spinner size="sm" />
            ) : (
              <Field label="Portfolio">
                <select
                  value={selectedPortfolioId}
                  onChange={(e) => setSelectedPortfolioId(e.target.value)}
                  required
                  className={inputClass}
                >
                  <option value="">Select a portfolio</option>
                  {portfolios.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </Field>
            )}

            <Field label="Target allocation (%)">
              <input
                type="text"
                inputMode="decimal"
                value={targetPct}
                onChange={(e) => setTargetPct(e.target.value)}
                className={inputClass}
                placeholder="5"
              />
            </Field>

            {createPending.error && (
              <p role="alert" className="text-sm text-sell">
                {createPending.error}
              </p>
            )}

            <div className="flex justify-end gap-3">
              <Button type="button" variant="quiet" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" disabled={createPending.loading || !selectedPortfolioId}>
                {createPending.loading && <Spinner size="sm" />}
                Add to portfolio
              </Button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
