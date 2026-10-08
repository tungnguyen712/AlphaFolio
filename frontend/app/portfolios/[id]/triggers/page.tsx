"use client";

import { useState } from "react";
import { useTriggers, useCreateTrigger, useDeleteTrigger } from "@/hooks/usePortfolios";
import type { RebalanceTriggerKind } from "@/lib/types";
import { EmptyState } from "@/components/ui/EmptyState";
import { Spinner } from "@/components/ui/Spinner";

const kindMeta: Record<RebalanceTriggerKind, { label: string; color: string; description: string }> = {
  drift_threshold: {
    label: "Drift threshold",
    color: "bg-hold-soft text-hold",
    description: "Notify when a holding drifts beyond a target allocation percentage",
  },
  earnings_date: {
    label: "Earnings date",
    color: "bg-hold-soft text-hold",
    description: "Notify on a scheduled earnings date",
  },
  lockup_expiry: {
    label: "Lock-up expiry",
    color: "bg-purple-100 text-purple-700",
    description: "Notify when a lock-up period expires",
  },
  macro_event: {
    label: "Macro event",
    color: "bg-action/10 text-action",
    description: "Notify on a scheduled macro event (e.g. Fed rate decision, CPI release)",
  },
  custom: {
    label: "Custom",
    color: "bg-rule/60 text-ink",
    description: "Custom reminder with a date and note",
  },
  price_below: {
    label: "Price below",
    color: "bg-sell-soft text-sell",
    description: "Notify when the price falls below a target level",
  },
  price_above: {
    label: "Price above",
    color: "bg-buy-soft text-buy",
    description: "Notify when the price rises above a target level",
  },
  earnings_beat_check: {
    label: "Earnings beat",
    color: "bg-action/10 text-action",
    description: "Notify after earnings with EPS beat/miss result",
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
  if (kind === "price_below" || kind === "price_above") {
    const ticker = cond.ticker ? String(cond.ticker).toUpperCase() : "";
    const price = cond.price_target != null ? `$${Number(cond.price_target).toFixed(2)}` : "";
    const label = kind === "price_below" ? "below" : "above";
    return ticker && price ? `${ticker} ${label} ${price}` : ticker || "No condition set";
  }
  if (kind === "earnings_beat_check") {
    return cond.ticker ? `EPS beat check: ${String(cond.ticker).toUpperCase()}` : "No ticker set";
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
    "w-full rounded border border-rule px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-rule";

  if (kind === "drift_threshold") {
    return (
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-sm font-medium text-ink">Ticker</label>
          <input
            type="text"
            placeholder="e.g. AAPL"
            value={values.ticker ?? ""}
            onChange={(e) => onChange("ticker", e.target.value.toUpperCase())}
            className={inputClass}
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-ink">
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
          <p className="mt-1 text-sm text-muted">
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
          <label className="mb-1 block text-sm font-medium text-ink">Ticker</label>
          <input
            type="text"
            placeholder="e.g. AAPL"
            value={values.ticker ?? ""}
            onChange={(e) => onChange("ticker", e.target.value.toUpperCase())}
            className={inputClass}
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-ink">
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

  if (kind === "price_below" || kind === "price_above") {
    return (
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-sm font-medium text-ink">Ticker</label>
          <input
            type="text"
            placeholder="e.g. NVDA"
            value={values.ticker ?? ""}
            onChange={(e) => onChange("ticker", e.target.value.toUpperCase())}
            className={inputClass}
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-ink">
            Price target ($)
          </label>
          <input
            type="number"
            min={0}
            step={0.01}
            placeholder={kind === "price_below" ? "e.g. 200" : "e.g. 300"}
            value={values.price_target ?? ""}
            onChange={(e) => onChange("price_target", e.target.value)}
            className={inputClass}
          />
          <p className="mt-1 text-sm text-muted">
            Checked every minute during market hours (9:30–16:00 ET)
          </p>
        </div>
      </div>
    );
  }

  if (kind === "earnings_beat_check") {
    return (
      <div>
        <label className="mb-1 block text-sm font-medium text-ink">Ticker</label>
        <input
          type="text"
          placeholder="e.g. AAPL"
          value={values.ticker ?? ""}
          onChange={(e) => onChange("ticker", e.target.value.toUpperCase())}
          className={inputClass}
        />
        <p className="mt-1 text-sm text-muted">
          Fires after earnings. Reports whether EPS beat or missed estimates
        </p>
      </div>
    );
  }

  if (kind === "macro_event") {
    return (
      <div>
        <label className="mb-1 block text-sm font-medium text-ink">Event description</label>
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
      <label className="mb-1 block text-sm font-medium text-ink">Reminder note</label>
      <input
        type="text"
        placeholder="e.g. Review TSLA position after lockup"
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
    if (kind === "price_below" || kind === "price_above") {
      const out: Record<string, unknown> = {};
      if (condFields.ticker) out.ticker = condFields.ticker;
      if (condFields.price_target) out.price_target = parseFloat(condFields.price_target);
      return out;
    }
    if (kind === "earnings_beat_check") {
      return condFields.ticker ? { ticker: condFields.ticker } : {};
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
  if (error) return <p className="text-sm text-sell">{error}</p>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-xl font-semibold text-ink">Rebalance triggers</h3>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="rounded bg-action px-3 py-1.5 text-sm font-medium text-action-ink hover:opacity-90"
        >
          {showForm ? "Cancel" : "+ Add trigger"}
        </button>
      </div>

      {showForm && (
        <form
          onSubmit={(e) => void handleCreate(e)}
          className="rounded-lg border border-rule bg-surface p-5"
        >
          {/* Kind selector */}
          <div className="mb-4">
            <label className="mb-2 block text-sm font-medium text-ink">Trigger type</label>
            <div className="flex flex-wrap gap-2">
              {(Object.keys(kindMeta) as RebalanceTriggerKind[]).map((k) => (
                <button
                  key={k}
                  type="button"
                  onClick={() => handleKindChange(k)}
                  className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                    kind === k
                      ? "border-action bg-action text-action-ink"
                      : "border-rule bg-surface text-ink hover:border-rule"
                  }`}
                >
                  {kindMeta[k].label}
                </button>
              ))}
            </div>
            <p className="mt-2 text-sm text-muted">{kindMeta[kind].description}</p>
          </div>

          {/* Kind-specific condition fields */}
          <div className="mb-4">
            <ConditionFields kind={kind} values={condFields} onChange={handleFieldChange} />
          </div>

          {/* Fires at — not used for price-based triggers */}
          {kind !== "price_below" && kind !== "price_above" && kind !== "earnings_beat_check" && (
            <div className="mb-4">
              <label className="mb-1 block text-sm font-medium text-ink">
                Fire at date/time{kind === "custom" || kind === "macro_event" ? "" : " (optional)"}
              </label>
              <input
                type="datetime-local"
                value={firesAt}
                onChange={(e) => setFiresAt(e.target.value)}
                className="w-full rounded border border-rule px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-rule sm:max-w-xs"
              />
              <p className="mt-1 text-sm text-muted">
                Celery Beat checks every minute and fires a notification when this time is reached.
              </p>
            </div>
          )}

          {createError && <p className="mb-3 text-sm text-sell">{createError}</p>}

          <button
            type="submit"
            disabled={creating}
            className="flex items-center gap-2 rounded bg-action px-4 py-2 text-sm font-medium text-action-ink hover:opacity-90 disabled:opacity-50"
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
              className="flex items-start justify-between rounded-lg border border-rule bg-surface p-4"
            >
              <div className="space-y-1.5">
                <span className={`inline-block rounded-full px-2 py-0.5 text-sm font-medium ${kindMeta[t.kind].color}`}>
                  {kindMeta[t.kind].label}
                </span>
                <p className="text-sm text-ink">
                  {formatCondition(t.kind, t.condition_json as Record<string, unknown>)}
                </p>
                {t.fires_at && (
                  <p className="text-sm text-muted">
                    Fires {new Date(t.fires_at).toLocaleString()}
                  </p>
                )}
              </div>
              <button
                onClick={() => void handleDelete(t.id)}
                disabled={deletingId === t.id}
                className="ml-4 shrink-0 rounded px-2 py-1 text-sm text-sell hover:bg-sell-soft hover:text-sell disabled:cursor-not-allowed disabled:opacity-50"
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

