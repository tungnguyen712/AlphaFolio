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
    <div className="rounded-xl border border-neutral-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-base font-bold text-neutral-900 dark:text-zinc-100">{pending.ticker}</p>
          <p className="mt-0.5 text-xs text-neutral-500 dark:text-zinc-400">
            Target {Math.round(parseFloat(pending.target_pct) * 100)}% allocation
          </p>
          <p className="mt-0.5 text-xs text-neutral-400 dark:text-zinc-500">
            Added {new Date(pending.created_at).toLocaleDateString()}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setAcceptOpen((v) => !v)}
            className="rounded-md bg-green-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-600"
          >
            Accept
          </button>
          <button
            onClick={() => void handleReject()}
            disabled={rejecting}
            className="rounded-md border border-red-300 px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
          >
            Reject
          </button>
        </div>
      </div>

      {acceptOpen && (
        <form
          onSubmit={(e) => void handleAccept(e)}
          className="mt-4 border-t border-neutral-100 pt-4 dark:border-zinc-800"
        >
          <div className="grid gap-3 sm:grid-cols-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-neutral-600 dark:text-zinc-400">Shares</label>
              <input
                type="text"
                value={form.shares}
                onChange={(e) => setForm((s) => ({ ...s, shares: e.target.value }))}
                required
                className="w-full rounded-md border border-neutral-300 px-3 py-2 text-sm text-zinc-900 focus:outline-none dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
                placeholder="100"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-neutral-600 dark:text-zinc-400">Avg cost</label>
              <input
                type="text"
                value={form.avg_cost}
                onChange={(e) => setForm((s) => ({ ...s, avg_cost: e.target.value }))}
                required
                className="w-full rounded-md border border-neutral-300 px-3 py-2 text-sm text-zinc-900 focus:outline-none dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
                placeholder="150.00"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-neutral-600 dark:text-zinc-400">Class</label>
              <select
                value={form.asset_class}
                onChange={(e) => setForm((s) => ({ ...s, asset_class: e.target.value as AssetClass }))}
                className="w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm text-zinc-900 focus:outline-none dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
              >
                {assetClasses.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
          </div>
          {acceptError && <p className="mt-2 text-xs text-red-600">{acceptError}</p>}
          <div className="mt-3 flex items-center gap-2">
            <button
              type="submit"
              disabled={accepting}
              className="flex items-center gap-1 rounded-md bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-neutral-700 disabled:opacity-50 dark:bg-zinc-700 dark:hover:bg-zinc-600"
            >
              {accepting && <Spinner size="sm" />}
              Confirm
            </button>
            <button
              type="button"
              onClick={() => setAcceptOpen(false)}
              className="text-xs text-neutral-400 hover:underline dark:text-zinc-500"
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
  if (error) return <p className="text-sm text-red-600">{error}</p>;

  return (
    <div>
      <h3 className="mb-4 text-sm font-semibold text-neutral-800 dark:text-zinc-100">Pending positions</h3>
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
