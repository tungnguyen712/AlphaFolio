"use client";

import { useParams, useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import Link from "next/link";
import { useSupplyChain } from "@/hooks/useSupplyChain";
import { RelationshipGroup } from "@/components/supply-chain/RelationshipGroup";
import { SupplyChainGraph } from "@/components/supply-chain/SupplyChainGraph";
import { Spinner } from "@/components/ui/Spinner";
import type { RelatedCompany, RelationshipKind } from "@/lib/types";

const GROUP_CONFIG: { kind: RelationshipKind; title: string; empty: string }[] = [
  { kind: "supplier",     title: "Suppliers",     empty: "No suppliers found in filings" },
  { kind: "customer",     title: "Customers",     empty: "No customers found in filings" },
  { kind: "manufacturer", title: "Manufacturers", empty: "No contract manufacturers found" },
  { kind: "competitor",   title: "Competitors",   empty: "No competitors identified in filings" },
  { kind: "parent",       title: "Parent Company",empty: "No parent organization found" },
  { kind: "subsidiary",   title: "Subsidiaries",  empty: "No subsidiaries found" },
];

function groupBy(rels: RelatedCompany[]): Record<RelationshipKind, RelatedCompany[]> {
  const result = {} as Record<RelationshipKind, RelatedCompany[]>;
  for (const { kind } of GROUP_CONFIG) result[kind] = [];
  for (const rel of rels ?? []) {
    if (result[rel.relationship]) result[rel.relationship].push(rel);
  }
  return result;
}

const sourceLabel: Record<string, string> = {
  gleif: "GLEIF",
  wikidata: "Wikidata",
  wikipedia: "Wikipedia",
  "10k": "SEC 10-K",
  sec_efts: "SEC EFTS",
  tavily: "News",
};

type ViewMode = "card" | "graph";

const VIEW_KEY = "sc-view";

export default function SupplyChainTicker() {
  const params = useParams();
  const router = useRouter();
  const ticker = (params.ticker as string).toUpperCase();
  const { data, loading, error, notFound } = useSupplyChain(ticker);

  const [viewMode, setViewMode] = useState<ViewMode>("card");

  // Initialise from localStorage after hydration
  useEffect(() => {
    const stored = localStorage.getItem(VIEW_KEY);
    if (stored === "card" || stored === "graph") setViewMode(stored);
  }, []);

  function switchView(mode: ViewMode) {
    setViewMode(mode);
    localStorage.setItem(VIEW_KEY, mode);
  }

  if (loading) {
    return (
      <main className="mx-auto max-w-5xl px-6 py-12">
        <div className="flex flex-col items-center gap-4 py-20 text-center">
          <Spinner />
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            Building supply chain map for {ticker}&hellip; this may take a few seconds.
          </p>
        </div>
      </main>
    );
  }

  if (notFound) {
    return (
      <main className="mx-auto max-w-5xl px-6 py-12">
        <div className="py-20 text-center">
          <p className="text-base font-medium text-zinc-900 dark:text-zinc-100">
            No supply chain data found for {ticker}
          </p>
          <p className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
            The ticker may not be SEC-listed or have insufficient public filings.
          </p>
          <button
            onClick={() => router.push("/supply-chain")}
            className="mt-4 rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
          >
            Try another ticker
          </button>
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="mx-auto max-w-5xl px-6 py-12">
        <div className="rounded-xl border border-red-200 bg-red-50 px-6 py-4 dark:border-red-900 dark:bg-red-950/30">
          <p className="text-sm font-medium text-red-700 dark:text-red-400">{error}</p>
        </div>
      </main>
    );
  }

  if (!data) return null;

  const relationships = data.relationships ?? [];
  const dataSources = data.data_sources_used ?? [];
  const grouped = groupBy(relationships);

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-zinc-900 dark:text-zinc-100">
              {data.company_name}
            </h1>
            <span className="rounded bg-zinc-100 px-2 py-0.5 font-mono text-xs font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
              {data.ticker}
            </span>
          </div>
          <div className="mt-1 flex items-center gap-3 text-xs text-zinc-400 dark:text-zinc-500">
            <span>{relationships.length} relationships found</span>
            {data.filed_at && <span>10-K filed {data.filed_at}</span>}
            {data.filing_url && (
              <a
                href={data.filing_url}
                target="_blank"
                rel="noopener noreferrer"
                className="underline hover:text-zinc-600 dark:hover:text-zinc-300"
              >
                View filing
              </a>
            )}
          </div>
        </div>
        <div className="flex flex-wrap gap-1">
          {dataSources.map((s) => (
            <span
              key={s}
              className="rounded-full border border-zinc-200 bg-zinc-50 px-2 py-0.5 text-xs text-zinc-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400"
            >
              {sourceLabel[s] ?? s}
            </span>
          ))}
        </div>
      </div>

      {/* View toggle */}
      <div className="mb-4 flex items-center gap-2">
        <div className="inline-flex rounded-lg border border-zinc-200 bg-zinc-50 p-0.5 dark:border-zinc-700 dark:bg-zinc-900">
          {(["card", "graph"] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => switchView(mode)}
              className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                viewMode === mode
                  ? "bg-white text-zinc-900 shadow-sm dark:bg-zinc-800 dark:text-zinc-100"
                  : "text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
              }`}
            >
              {mode === "card" ? "Cards" : "Graph"}
            </button>
          ))}
        </div>
      </div>

      {/* Relationship view */}
      {viewMode === "graph" ? (
        <SupplyChainGraph report={data} />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {GROUP_CONFIG.map(({ kind, title, empty }) => (
            <RelationshipGroup
              key={kind}
              title={title}
              relationships={grouped[kind]}
              emptyMessage={empty}
            />
          ))}
        </div>
      )}

      {/* Confidence legend — card view only */}
      {viewMode === "card" && (
        <div className="mt-6 flex items-center gap-4 text-xs text-zinc-400 dark:text-zinc-500">
          <span className="font-medium">Confidence:</span>
          {(["high", "medium", "low"] as const).map((c) => (
            <span key={c} className="flex items-center gap-1">
              <span
                className={`h-2 w-2 rounded-full ${
                  c === "high" ? "bg-green-500" : c === "medium" ? "bg-yellow-400" : "bg-zinc-400"
                }`}
              />
              {c.charAt(0).toUpperCase() + c.slice(1)}
            </span>
          ))}
        </div>
      )}

      {data.notes && (
        <p className="mt-4 text-xs text-zinc-400 dark:text-zinc-500">{data.notes}</p>
      )}

      <div className="mt-8">
        <Link
          href="/supply-chain"
          className="text-sm text-zinc-500 underline hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-200"
        >
          ← Search another ticker
        </Link>
      </div>
    </main>
  );
}
