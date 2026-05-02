"use client";

import { useState } from "react";
import { useTriggers, useCreateTrigger, useDeleteTrigger } from "@/hooks/usePortfolios";
import type { RebalanceTriggerKind } from "@/lib/types";
import { EmptyState } from "@/components/ui/EmptyState";
import { Spinner } from "@/components/ui/Spinner";

const kindMeta: Record<RebalanceTriggerKind, { label: string; color: string; description: string }> = {
  drift_threshold: {
    label: "Drift threshold",
    color: "bg-yellow-100 text-yellow-700",
    description: "Notify when a holding drifts beyond a target allocation percentage",
  },
  earnings_date: {
    label: "Earnings date",
    color: "bg-orange-100 text-orange-700",
    description: "Notify on a scheduled earnings date",
  },
  lockup_expiry: {
    label: "Lock-up expiry",
    color: "bg-purple-100 text-purple-700",
    description: "Notify when a lock-up period expires",
  },
  macro_event: {
    label: "Macro event",
    color: "bg-blue-100 text-blue-700",
    description: "Notify on a scheduled macro event (e.g. Fed rate decision, CPI release)",
  },
  custom: {
    label: "Custom",
    color: "bg-neutral-100 text-neutral-700 dark:bg-zinc-800 dark:text-zinc-300",
    description: "Custom reminder with a date and note",
  },
};

function formatCondition(kind: RebalanceTriggerKind, cond: Record<string, unknown>): string {
  if (kind === "drift_threshold") {
    const parts: string[] = [];
    if (cond.ticker) parts.push(`Ticker: ${String(cond.ticker).toUpperCase()}`);
    if (cond.threshold != null) parts.push(`Drift > ${Math.round(Number(cond.threshold) * 100)}%`);
    return parts.join(" · ") || "No condition set";
  }
  if (kind === "earnings_date" || kind === "lockup_expiry") {
    const parts: string[] = [];
    if (cond.ticker) parts.push(`Ticker: ${String(cond.ticker).toUpperCase()}`);
    if (cond.notes) parts.push(String(cond.notes));
    return parts.join(" · ") || "No details";
  }
  if (kind === "macro_event") {
    return String(cond.event ?? cond.notes ?? "No details");
  }
  return String(cond.notes ?? "No details");
}

function ConditionFields({
  kind,
  values,
  onChange,
}: {
  kind: RebalanceTriggerKind;
  values: Record<string, string>;
  onChange: (key: string, val: string) => void;
}) {
  const inputClass =
    "w-full rounded-md border border-neutral-300 px-3 py-2 text-sm text-zinc-900 focus:outline-none focus:ring-2 focus:ring-neutral-400 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100";

  if (kind === "drift_threshold") {
    return (
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-xs font-medium text-neutral-600 dark:text-zinc-400">Ticker</label>
          <input
            type="text"
            placeholder="e.g. AAPL"
            value={values.ticker ?? ""}
            onChange={(e) => onChange("ticker", e.target.value.toUpperCase())}
            className={inputClass}
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-neutral-600 dark:text-zinc-400">
            Drift threshold (%)
          </label>
          <input
            type="number"
            min={1}
            max={50}
            step={0.5}
            placeholder="e.g. 5"
            value={values.threshold_pct ?? ""}
            onChange={(e) => onChange("threshold_pct", e.target.value)}
            className={inputClass}
          />
          <p className="mt-1 text-xs text-neutral-400 dark:text-zinc-500">
            Fire when this holding drifts more than this % from its target weight
          </p>
        </div>
      </div>
    );
  }

  if (kind === "earnings_date" || kind === "lockup_expiry") {
    return (
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-xs font-medium text-neutral-600 dark:text-zinc-400">Ticker</label>
          <input
            type="text"
            placeholder="e.g. AAPL"
            value={values.ticker ?? ""}
            onChange={(e) => onChange("ticker", e.target.value.toUpperCase())}
            className={inputClass}
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-neutral-600 dark:text-zinc-400">
            Notes (optional)
          </label>
          <input
            type="text"
            placeholder="Any extra context"
            value={values.notes ?? ""}
            onChange={(e) => onChange("notes", e.target.value)}
            className={inputClass}
          />
        </div>
      </div>
    );
  }

  if (kind === "macro_event") {
    return (
      <div>
        <label className="mb-1 block text-xs font-medium text-neutral-600 dark:text-zinc-400">Event description</label>
        <input
          type="text"
          placeholder="e.g. Fed rate decision, CPI release"
          value={values.event ?? ""}
          onChange={(e) => onChange("event", e.target.value)}
          className={inputClass}
        />
      </div>
    );
  }

  // custom
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-neutral-600 dark:text-zinc-400">Note</label>
      <input
        type="text"
        placeholder="Describe this reminder"
        value={values.notes ?? ""}
        onChange={(e) => onChange("notes", e.target.value)}
        className={inputClass}
      />
    </div>
  );
}

export default function TriggersPage({ params }: { params: { id: string } }) {
  const { data: triggers, loading, error, refetch } = useTriggers(params.id);
  const { mutate: createTrigger, loading: creating, error: createError } = useCreateTrigger(params.id);
  const { mutate: deleteTrigger } = useDeleteTrigger(params.id);

  const [showForm, setShowForm] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [kind, setKind] = useState<RebalanceTriggerKind>("drift_threshold");
  const [firesAt, setFiresAt] = useState("");
  const [condFields, setCondFields] = useState<Record<string, string>>({});

  const handleKindChange = (k: RebalanceTriggerKind) => {
    setKind(k);
    setCondFields({});
  };

  const handleFieldChange = (key: string, val: string) => {
    setCondFields((prev) => ({ ...prev, [key]: val }));
  };

  const buildConditionJson = (): Record<string, unknown> => {
    if (kind === "drift_threshold") {
      const out: Record<string, unknown> = {};
      if (condFields.ticker) out.ticker = condFields.ticker;
      if (condFields.threshold_pct) out.threshold = parseFloat(condFields.threshold_pct) / 100;
      return out;
    }
    if (kind === "earnings_date" || kind === "lockup_expiry") {
      const out: Record<string, unknown> = {};
      if (condFields.ticker) out.ticker = condFields.ticker;
      if (condFields.notes) out.notes = condFields.notes;
      return out;
    }
    if (kind === "macro_event") {
      return condFields.event ? { event: condFields.event } : {};
    }
    return condFields.notes ? { notes: condFields.notes } : {};
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const result = await createTrigger({
      kind,
      condition_json: buildConditionJson(),
      fires_at: firesAt || undefined,
    });
    if (result) {
      setShowForm(false);
      setCondFields({});
      setFiresAt("");
      void refetch();
    }
  };

  const handleDelete = async (triggerId: string) => {
    if (deletingId) return;
    if (!confirm("Deactivate this trigger? It will no longer fire notifications.")) return;
    setDeletingId(triggerId);
    await deleteTrigger(triggerId);
    setDeletingId(null);
    void refetch();
  };

  if (loading) return <Spinner />;
  if (error) return <p className="text-sm text-red-600">{error}</p>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-neutral-800 dark:text-zinc-100">Rebalance triggers</h3>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="rounded-md bg-neutral-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-neutral-700 dark:bg-zinc-700 dark:hover:bg-zinc-600"
        >
          {showForm ? "Cancel" : "+ Add trigger"}
        </button>
      </div>

      {showForm && (
        <form
          onSubmit={(e) => void handleCreate(e)}
          className="rounded-xl border border-neutral-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900"
        >
          {/* Kind selector */}
          <div className="mb-4">
            <label className="mb-2 block text-xs font-medium text-neutral-600 dark:text-zinc-400">Trigger type</label>
            <div className="flex flex-wrap gap-2">
              {(Object.keys(kindMeta) as RebalanceTriggerKind[]).map((k) => (
                <button
                  key={k}
                  type="button"
                  onClick={() => handleKindChange(k)}
                  className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                    kind === k
                      ? "border-neutral-900 bg-neutral-900 text-white dark:border-zinc-500 dark:bg-zinc-700"
                      : "border-neutral-200 bg-white text-neutral-600 hover:border-neutral-400 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:border-zinc-500"
                  }`}
                >
                  {kindMeta[k].label}
                </button>
              ))}
            </div>
            <p className="mt-2 text-xs text-neutral-400 dark:text-zinc-500">{kindMeta[kind].description}</p>
          </div>

          {/* Kind-specific condition fields */}
          <div className="mb-4">
            <ConditionFields kind={kind} values={condFields} onChange={handleFieldChange} />
          </div>

          {/* Fires at */}
          <div className="mb-4">
            <label className="mb-1 block text-xs font-medium text-neutral-600 dark:text-zinc-400">
              Fire at date/time{kind === "custom" || kind === "macro_event" ? "" : " (optional)"}
            </label>
            <input
              type="datetime-local"
              value={firesAt}
              onChange={(e) => setFiresAt(e.target.value)}
              className="w-full rounded-md border border-neutral-300 px-3 py-2 text-sm text-zinc-900 focus:outline-none focus:ring-2 focus:ring-neutral-400 sm:max-w-xs dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
            />
            <p className="mt-1 text-xs text-neutral-400 dark:text-zinc-500">
              Celery Beat checks every minute and fires a notification when this time is reached.
            </p>
          </div>

          {createError && <p className="mb-3 text-xs text-red-600">{createError}</p>}

          <button
            type="submit"
            disabled={creating}
            className="flex items-center gap-2 rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-700 disabled:opacity-50 dark:bg-zinc-700 dark:hover:bg-zinc-600"
          >
            {creating && <Spinner size="sm" />}
            Create trigger
          </button>
        </form>
      )}

      {triggers.length === 0 ? (
        <EmptyState
          title="No triggers"
          description="Create a trigger to be notified when rebalancing conditions are met."
        />
      ) : (
        <ul className="space-y-2">
          {triggers.map((t) => (
            <li
              key={t.id}
              className="flex items-start justify-between rounded-xl border border-neutral-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900"
            >
              <div className="space-y-1.5">
                <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${kindMeta[t.kind].color}`}>
                  {kindMeta[t.kind].label}
                </span>
                <p className="text-sm text-neutral-700 dark:text-zinc-300">
                  {formatCondition(t.kind, t.condition_json as Record<string, unknown>)}
                </p>
                {t.fires_at && (
                  <p className="text-xs text-neutral-400 dark:text-zinc-500">
                    Fires {new Date(t.fires_at).toLocaleString()}
                  </p>
                )}
              </div>
              <button
                onClick={() => void handleDelete(t.id)}
                disabled={deletingId === t.id}
                className="ml-4 shrink-0 rounded px-2 py-1 text-xs text-red-500 hover:bg-red-50 hover:text-red-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {deletingId === t.id ? "Deactivating…" : "Deactivate"}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

