"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { inputClass } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";

const EXAMPLES = ["NVDA", "AAPL", "TSLA", "AMZN"];

export default function SupplyChainHome() {
  const router = useRouter();
  const [ticker, setTicker] = useState("");

  const go = (value: string) => {
    const t = value.trim().toUpperCase();
    if (!t) return;
    router.push(`/supply-chain/${t}`);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    go(ticker);
  };

  return (
    <div>
      <PageHeader
        title="Supply chain"
        description="See who a company buys from, sells to, and is owned by. This maps relationships; it doesn't recommend anything."
      />
      <form onSubmit={handleSubmit} className="max-w-3xl">
        <label htmlFor="sc-ticker" className="mb-2 block text-lg font-medium text-ink">
          Which company do you want to map?
        </label>
        <div className="flex gap-3">
          <input
            id="sc-ticker"
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            placeholder="NVDA"
            autoComplete="off"
            className={`${inputClass} h-14 flex-1 text-2xl font-semibold tracking-wide`}
            maxLength={10}
          />
          <Button type="submit" size="lg" className="h-14" disabled={!ticker.trim()}>
            Map supply chain
          </Button>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="text-sm text-muted">Try</span>
          {EXAMPLES.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => go(t)}
              className="rounded border border-rule bg-surface px-3 py-1 text-sm font-medium text-ink hover:border-action hover:text-action"
            >
              {t}
            </button>
          ))}
        </div>
        <p className="mt-6 max-w-reading text-sm text-muted">
          Built from SEC 10-K filings, Wikidata, GLEIF, and news. Results are cached for 24 hours.
        </p>
      </form>
    </div>
  );
}
