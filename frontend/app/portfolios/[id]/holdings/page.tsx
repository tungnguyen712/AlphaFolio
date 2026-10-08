"use client";

import { useState } from "react";
import {
  usePortfolio,
  useAddHolding,
  useUpdateHolding,
  useDeleteHolding,
} from "@/hooks/usePortfolios";
import type { AssetClass, HoldingOut } from "@/lib/types";
import { Spinner } from "@/components/ui/Spinner";
import { EmptyState } from "@/components/ui/EmptyState";

interface EditState {
  shares: string;
  avg_cost: string;
  asset_class: AssetClass;
}

const assetClasses: AssetClass[] = ["established", "ipo", "private"];

export default function HoldingsPage({ params }: { params: { id: string } }) {
  const { data: portfolio, loading, error, refetch } = usePortfolio(params.id);
  const addHolding = useAddHolding(params.id);
  const updateHolding = useUpdateHolding(params.id);
  const deleteHolding = useDeleteHolding(params.id);

  const [editId, setEditId] = useState<string | null>(null);
  const [editState, setEditState] = useState<EditState>({ shares: "", avg_cost: "", asset_class: "established" });
  const [newTicker, setNewTicker] = useState("");
  const [newShares, setNewShares] = useState("");
  const [newAvgCost, setNewAvgCost] = useState("");
  const [newAssetClass, setNewAssetClass] = useState<AssetClass>("established");
  const [showAddForm, setShowAddForm] = useState(false);

  if (loading) return <Spinner />;
  if (error) return <p className="text-sm text-sell">{error}</p>;
  if (!portfolio) return null;

  const startEdit = (h: HoldingOut) => {
    setEditId(h.id);
    setEditState({ shares: h.shares, avg_cost: h.avg_cost, asset_class: h.asset_class });
  };

  const handleUpdate = async (holdingId: string) => {
    if (!editState.shares || isNaN(parseFloat(editState.shares))) return;
    if (!editState.avg_cost || isNaN(parseFloat(editState.avg_cost))) return;
    const result = await updateHolding.mutate(holdingId, editState);
    if (result) {
      setEditId(null);
      void refetch();
    }
  };

  const handleDelete = async (holdingId: string) => {
    if (!confirm("Delete this holding?")) return;
    await deleteHolding.mutate(holdingId);
    void refetch();
  };

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTicker || isNaN(parseFloat(newShares)) || isNaN(parseFloat(newAvgCost))) return;
    const result = await addHolding.mutate({
      ticker: newTicker,
      shares: newShares,
      avg_cost: newAvgCost,
      asset_class: newAssetClass,
    });
    if (result) {
      setNewTicker("");
      setNewShares("");
      setNewAvgCost("");
      setShowAddForm(false);
      void refetch();
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-xl font-semibold text-ink">Holdings</h3>
        <button
          onClick={() => setShowAddForm((v) => !v)}
          className="rounded bg-action px-3 py-1.5 text-sm font-medium text-action-ink hover:opacity-90"
        >
          {showAddForm ? "Cancel" : "+ Add holding"}
        </button>
      </div>

      {showAddForm && (
        <form
          onSubmit={(e) => void handleAdd(e)}
          className="rounded-lg border border-rule bg-surface p-5"
        >
          <div className="grid gap-4 sm:grid-cols-4">
            <div>
              <label className="mb-1 block text-sm font-medium text-ink">Ticker</label>
              <input
                type="text"
                value={newTicker}
                onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
                required
                className="w-full rounded border border-rule px-3 py-2 text-sm text-ink focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-ink">Shares</label>
              <input
                type="text"
                value={newShares}
                onChange={(e) => setNewShares(e.target.value)}
                required
                className="w-full rounded border border-rule px-3 py-2 text-sm text-ink focus:outline-none"
                placeholder="100"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-ink">Avg cost</label>
              <input
                type="text"
                value={newAvgCost}
                onChange={(e) => setNewAvgCost(e.target.value)}
                required
                className="w-full rounded border border-rule px-3 py-2 text-sm text-ink focus:outline-none"
                placeholder="150.00"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-ink">Class</label>
              <select
                value={newAssetClass}
                onChange={(e) => setNewAssetClass(e.target.value as AssetClass)}
                className="w-full rounded border border-rule bg-surface px-3 py-2 text-sm text-ink focus:outline-none"
              >
                {assetClasses.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
          </div>
          {addHolding.error && <p className="mt-2 text-sm text-sell">{addHolding.error}</p>}
          <button
            type="submit"
            disabled={addHolding.loading}
            className="mt-4 flex items-center gap-2 rounded bg-action px-4 py-2 text-sm font-medium text-action-ink hover:opacity-90 disabled:opacity-50"
          >
            {addHolding.loading && <Spinner size="sm" />}
            Add
          </button>
        </form>
      )}

      {portfolio.holdings.length === 0 ? (
        <EmptyState title="No holdings" description="Add your first holding above." />
      ) : (
        <div className="rounded-lg border border-rule bg-surface">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-rule text-sm text-muted">
                <th className="px-6 py-3 text-left font-medium">Ticker</th>
                <th className="px-6 py-3 text-right font-medium">Shares</th>
                <th className="px-6 py-3 text-right font-medium">Avg cost</th>
                <th className="px-6 py-3 text-left font-medium">Class</th>
                <th className="px-6 py-3" />
              </tr>
            </thead>
            <tbody className="divide-y divide-rule ">
              {portfolio.holdings.map((h) =>
                editId === h.id ? (
                  <tr key={h.id} className="bg-rule/30">
                    <td className="px-6 py-3 font-semibold text-ink">{h.ticker}</td>
                    <td className="px-6 py-3">
                      <input
                        type="text"
                        value={editState.shares}
                        onChange={(e) => setEditState((s) => ({ ...s, shares: e.target.value }))}
                        className="w-24 rounded border border-rule px-2 py-1 text-right text-sm text-ink focus:outline-none"
                      />
                    </td>
                    <td className="px-6 py-3">
                      <input
                        type="text"
                        value={editState.avg_cost}
                        onChange={(e) => setEditState((s) => ({ ...s, avg_cost: e.target.value }))}
                        className="w-28 rounded border border-rule px-2 py-1 text-right text-sm text-ink focus:outline-none"
                      />
                    </td>
                    <td className="px-6 py-3">
                      <select
                        value={editState.asset_class}
                        onChange={(e) =>
                          setEditState((s) => ({ ...s, asset_class: e.target.value as AssetClass }))
                        }
                        className="rounded border border-rule bg-surface px-2 py-1 text-sm text-ink focus:outline-none"
                      >
                        {assetClasses.map((c) => (
                          <option key={c} value={c}>{c}</option>
                        ))}
                      </select>
                    </td>
                    <td className="px-6 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => void handleUpdate(h.id)}
                          disabled={updateHolding.loading}
                          className="text-sm font-medium text-buy hover:underline"
                        >
                          Save
                        </button>
                        <button
                          onClick={() => setEditId(null)}
                          className="text-sm text-muted hover:underline"
                        >
                          Cancel
                        </button>
                      </div>
                    </td>
                  </tr>
                ) : (
                  <tr key={h.id} className="hover:bg-rule/30">
                    <td className="px-6 py-3 font-semibold text-ink">{h.ticker}</td>
                    <td className="px-6 py-3 text-right text-ink">{parseFloat(h.shares).toLocaleString()}</td>
                    <td className="px-6 py-3 text-right text-ink">${parseFloat(h.avg_cost).toFixed(2)}</td>
                    <td className="px-6 py-3 text-sm text-ink">{h.asset_class}</td>
                    <td className="px-6 py-3 text-right">
                      <div className="flex items-center justify-end gap-3">
                        <button
                          onClick={() => startEdit(h)}
                          className="text-sm text-muted hover:underline"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => void handleDelete(h.id)}
                          disabled={deleteHolding.loading}
                          className="text-sm text-sell hover:underline"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
