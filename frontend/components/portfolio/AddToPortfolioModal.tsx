"use client";

import { useState } from "react";
import { usePortfolios } from "@/hooks/usePortfolios";
import { useCreatePendingPosition } from "@/hooks/usePortfolios";
import { Spinner } from "@/components/ui/Spinner";

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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-sm rounded-xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold text-neutral-900">Add {ticker} to Portfolio</h2>
          <button
            onClick={onClose}
            className="text-neutral-400 hover:text-neutral-700"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {success ? (
          <p className="text-sm font-medium text-green-700">
            Added as pending position. Review it in the Pending tab.
          </p>
        ) : (
          <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-neutral-600">
                Portfolio
              </label>
              {portfoliosLoading ? (
                <Spinner size="sm" />
              ) : (
                <select
                  value={selectedPortfolioId}
                  onChange={(e) => setSelectedPortfolioId(e.target.value)}
                  required
                  className="w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm focus:border-neutral-500 focus:outline-none"
                >
                  <option value="">Select a portfolio…</option>
                  {portfolios.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              )}
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium text-neutral-600">
                Target allocation %
              </label>
              <input
                type="text"
                value={targetPct}
                onChange={(e) => setTargetPct(e.target.value)}
                className="w-full rounded-md border border-neutral-300 px-3 py-2 text-sm focus:border-neutral-500 focus:outline-none"
                placeholder="5"
              />
            </div>

            {createPending.error && (
              <p className="text-xs text-red-600">{createPending.error}</p>
            )}

            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={onClose}
                className="rounded-md px-4 py-2 text-sm text-neutral-600 hover:bg-neutral-100"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={createPending.loading || !selectedPortfolioId}
                className="flex items-center gap-2 rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-700 disabled:opacity-50"
              >
                {createPending.loading && <Spinner size="sm" />}
                Add to portfolio
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
