"use client";

import { useState } from "react";

interface CapitalBarProps {
  invested: number;
  cash: number;
  onCashSave?: (newCash: number) => Promise<void>;
}

function fmt(n: number) {
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });
}

export function CapitalBar({ invested, cash, onCashSave }: CapitalBarProps) {
  const [editing, setEditing] = useState(false);
  const [inputVal, setInputVal] = useState(cash.toFixed(2));
  const [saving, setSaving] = useState(false);

  const available = Math.max(0, cash - invested);
  const investedPct = cash > 0 ? Math.min((invested / cash) * 100, 100) : 0;
  const availablePct = cash > 0 ? (available / cash) * 100 : 100;

  const handleSave = async () => {
    const parsed = parseFloat(inputVal.replace(/[^0-9.]/g, ""));
    if (isNaN(parsed) || parsed < 0 || !onCashSave) return;
    setSaving(true);
    try {
      await onCashSave(parsed);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setInputVal(cash.toFixed(2));
    setEditing(false);
  };

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-base">
        <span className="text-muted">
          Deployed{" "}
          <span className="font-semibold tabular-nums text-ink">{fmt(invested)}</span>
          <span className="ml-1 tabular-nums">({investedPct.toFixed(0)}%)</span>
        </span>

        <span className="flex items-center gap-2 text-muted">
          {editing ? (
            <>
              <span className="font-semibold text-ink">$</span>
              <input
                type="text"
                inputMode="decimal"
                aria-label="Cash balance"
                value={inputVal}
                onChange={(e) => setInputVal(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") void handleSave(); if (e.key === "Escape") handleCancel(); }}
                className="w-32 rounded border border-action bg-surface px-2 py-1 text-base tabular-nums text-ink"
                autoFocus
              />
              <button
                onClick={() => void handleSave()}
                disabled={saving}
                className="rounded bg-action px-3 py-1 text-sm font-medium text-action-ink hover:opacity-90 disabled:opacity-50"
              >
                {saving ? "Saving" : "Save"}
              </button>
              <button onClick={handleCancel} className="text-sm text-muted hover:text-ink">
                Cancel
              </button>
            </>
          ) : (
            <>
              <span>
                Buying power{" "}
                <span className="font-semibold tabular-nums text-ink">{fmt(available)}</span>
                <span className="ml-1 tabular-nums">({availablePct.toFixed(0)}%)</span>
              </span>
              {onCashSave && (
                <button
                  onClick={() => { setInputVal(cash.toFixed(2)); setEditing(true); }}
                  className="text-sm text-action hover:underline"
                >
                  Edit cash
                </button>
              )}
            </>
          )}
        </span>
      </div>

      <div className="h-2 w-full overflow-hidden rounded-sm bg-rule">
        {investedPct > 0 && <div className="h-full bg-action" style={{ width: `${investedPct}%` }} />}
      </div>
    </div>
  );
}
