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
    <div className="rounded-xl border border-zinc-200 bg-white px-5 py-4 dark:border-zinc-800 dark:bg-zinc-900">
      <div className="mb-3 flex items-center justify-between text-xs font-medium">
        <span className="text-zinc-500 dark:text-zinc-400">
          Deployed{" "}
          <span className="font-mono font-semibold text-zinc-800 dark:text-zinc-200">{fmt(invested)}</span>
          <span className="ml-1 font-mono text-zinc-400 dark:text-zinc-500">({investedPct.toFixed(0)}%)</span>
        </span>

        <span className="flex items-center gap-1.5 text-zinc-500 dark:text-zinc-400">
          <span className="font-mono text-zinc-400 dark:text-zinc-500">({availablePct.toFixed(0)}%)</span>
          {editing ? (
            <>
              <span className="font-mono font-semibold text-zinc-800 dark:text-zinc-200">$</span>
              <input
                type="text"
                value={inputVal}
                onChange={(e) => setInputVal(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") void handleSave(); if (e.key === "Escape") handleCancel(); }}
                className="w-28 rounded border border-sky-400 bg-white px-1.5 py-0.5 font-mono text-xs text-zinc-900 focus:outline-none focus:ring-1 focus:ring-sky-500 dark:border-sky-600 dark:bg-zinc-800 dark:text-zinc-100"
                autoFocus
              />
              <button
                onClick={() => void handleSave()}
                disabled={saving}
                className="rounded bg-sky-600 px-2 py-0.5 text-white hover:bg-sky-500 disabled:opacity-50"
              >
                {saving ? "…" : "Save"}
              </button>
              <button onClick={handleCancel} className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200">
                Cancel
              </button>
            </>
          ) : (
            <>
              <span className="font-mono font-semibold text-zinc-800 dark:text-zinc-200">{fmt(available)}</span>
              {" "}Buying Power
              {onCashSave && (
                <button
                  onClick={() => { setInputVal(cash.toFixed(2)); setEditing(true); }}
                  aria-label="Edit cash balance"
                  className="ml-1 text-zinc-400 hover:text-sky-500 dark:hover:text-sky-400"
                >
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125" />
                  </svg>
                </button>
              )}
            </>
          )}
        </span>
      </div>

      <div className="h-3 w-full overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
        {investedPct > 0 && (
          <div
            className="h-full rounded-l-full bg-sky-500"
            style={{
              width: `${investedPct}%`,
              borderRadius: investedPct >= 100 ? "9999px" : undefined,
            }}
          />
        )}
      </div>
    </div>
  );
}
