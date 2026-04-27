"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function SupplyChainHome() {
  const router = useRouter();
  const [ticker, setTicker] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const t = ticker.trim().toUpperCase();
    if (!t) return;
    router.push(`/supply-chain/${t}`);
  };

  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <div className="mb-8 text-center">
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">
          Supply Chain
        </h1>
        <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
          Explore supplier, customer, manufacturer, and corporate relationships
          for any publicly traded company.
        </p>
      </div>
      <form
        onSubmit={handleSubmit}
        className="rounded-xl border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900"
      >
        <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
          Ticker symbol
        </label>
        <div className="flex gap-3">
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            placeholder="NVDA"
            className="flex-1 rounded-lg border border-zinc-300 bg-white px-3 py-2 font-mono text-sm uppercase text-zinc-900 placeholder-zinc-400 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100 dark:placeholder-zinc-600"
            maxLength={10}
          />
          <button
            type="submit"
            disabled={!ticker.trim()}
            className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-700 disabled:opacity-40"
          >
            Explore
          </button>
        </div>
        <p className="mt-3 text-xs text-zinc-400 dark:text-zinc-500">
          Data sources: SEC 10-K filings, Wikidata corporate structure.
          Results cached 24h.
        </p>
      </form>
    </main>
  );
}
