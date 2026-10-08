"use client";

import { useState } from "react";
import {
  usePendingPositions,
  useAcceptPending,
  useRejectPending,
} from "@/hooks/usePortfolios";
import type { AssetClass, PendingPositionOut } from "@/lib/types";
import { EmptyState } from "@/components/ui/EmptyState";
import { Spinner } from "@/components/ui/Spinner";

interface AcceptFormState {
  shares: string;
  avg_cost: string;
  asset_class: AssetClass;
}

const assetClasses: AssetClass[] = ["established", "ipo", "private"];

function PendingCard({
  pending,
  portfolioId,
  onResolved,
}: {
  pending: PendingPositionOut;
  portfolioId: string;
  onResolved: () => void;
}) {
  const [acceptOpen, setAcceptOpen] = useState(false);
  const [form, setForm] = useState<AcceptFormState>({
    shares: "",
    avg_cost: "",
    asset_class: "established",
  });
  const { mutate: accept, loading: accepting, error: acceptError } = useAcceptPending(portfolioId);
  const { mutate: reject, loading: rejecting } = useRejectPending(portfolioId);

  const handleAccept = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isNaN(parseFloat(form.shares)) || isNaN(parseFloat(form.avg_cost))) return;
    const result = await accept(pending.id, form);
    if (result) onResolved();
  };

  const handleReject = async () => {
    if (!confirm(`Reject ${pending.ticker}?`)) return;
    await reject(pending.id);
    onResolved();
  };

  return (
    <div className="rounded-lg border border-rule bg-surface p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-base font-bold text-ink">{pending.ticker}</p>
          <p className="mt-0.5 text-sm text-muted">
            Target {Math.round(parseFloat(pending.target_pct) * 100)}% allocation
          </p>
          <p className="mt-0.5 text-sm text-muted">
            Added {new Date(pending.created_at).toLocaleDateString()}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setAcceptOpen((v) => !v)}
            className="rounded bg-buy px-3 py-1.5 text-sm font-medium text-action-ink hover:opacity-90"
          >
            Accept
          </button>
          <button
            onClick={() => void handleReject()}
            disabled={rejecting}
            className="rounded border border-sell/40 px-3 py-1.5 text-sm font-medium text-sell hover:bg-sell-soft disabled:opacity-50"
          >
            Reject
          </button>
        </div>
      </div>

      {acceptOpen && (
        <form
          onSubmit={(e) => void handleAccept(e)}
          className="mt-4 border-t border-rule pt-4"
        >
          <div className="grid gap-3 sm:grid-cols-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-ink">Shares</label>
              <input
                type="text"
                value={form.shares}
                onChange={(e) => setForm((s) => ({ ...s, shares: e.target.value }))}
                required
                className="w-full rounded border border-rule px-3 py-2 text-sm text-ink focus:outline-none"
                placeholder="100"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-ink">Avg cost</label>
              <input
                type="text"
                value={form.avg_cost}
                onChange={(e) => setForm((s) => ({ ...s, avg_cost: e.target.value }))}
                required
                className="w-full rounded border border-rule px-3 py-2 text-sm text-ink focus:outline-none"
                placeholder="150.00"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-ink">Class</label>
              <select
                value={form.asset_class}
                onChange={(e) => setForm((s) => ({ ...s, asset_class: e.target.value as AssetClass }))}
                className="w-full rounded border border-rule bg-surface px-3 py-2 text-sm text-ink focus:outline-none"
              >
                {assetClasses.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
          </div>
          {acceptError && <p className="mt-2 text-sm text-sell">{acceptError}</p>}
          <div className="mt-3 flex items-center gap-2">
            <button
              type="submit"
              disabled={accepting}
              className="flex items-center gap-1 rounded bg-action px-3 py-1.5 text-sm font-medium text-action-ink hover:opacity-90 disabled:opacity-50"
            >
              {accepting && <Spinner size="sm" />}
              Confirm
            </button>
            <button
              type="button"
              onClick={() => setAcceptOpen(false)}
              className="text-sm text-muted hover:underline"
            >
              Cancel
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

export default function PendingPage({ params }: { params: { id: string } }) {
  const { data: pending, loading, error, refetch } = usePendingPositions(params.id);

  if (loading) return <Spinner />;
  if (error) return <p className="text-sm text-sell">{error}</p>;

  return (
    <div>
      <h3 className="mb-4 text-xl font-semibold text-ink">Pending positions</h3>
      {pending.length === 0 ? (
        <EmptyState
          title="No pending positions"
          description="Research a ticker with a portfolio context to add pending positions."
        />
      ) : (
        <div className="space-y-3">
          {pending.map((p) => (
            <PendingCard
              key={p.id}
              pending={p}
              portfolioId={params.id}
              onResolved={() => void refetch()}
            />
          ))}
        </div>
      )}
    </div>
  );
}
