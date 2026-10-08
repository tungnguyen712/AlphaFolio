"use client";

import { useParams, useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import Link from "next/link";
import { useSupplyChain } from "@/hooks/useSupplyChain";
import { RelationshipGroup } from "@/components/supply-chain/RelationshipGroup";
import { SupplyChainGraph } from "@/components/supply-chain/SupplyChainGraph";
import { Spinner } from "@/components/ui/Spinner";
import { ButtonLink } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { ErrorState } from "@/components/ui/Panel";
import { ConfidenceDot } from "@/components/supply-chain/CompanyChip";
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
      <div className="flex items-center gap-3 py-12">
        <Spinner />
        <p className="text-base text-muted">
          Building the supply chain map for {ticker}. This can take a few seconds.
        </p>
      </div>
    );
  }

  if (notFound) {
    return (
      <div className="max-w-form py-8">
        <h1 className="text-2xl font-semibold tracking-tight text-ink">No supply chain data for {ticker}</h1>
        <p className="mb-5 mt-2 text-base text-muted">
          The ticker may not be SEC-listed, or it may not have enough public filings. Check the symbol or try
          another company.
        </p>
        <ButtonLink href="/supply-chain">Try another company</ButtonLink>
      </div>
    );
  }

  if (error) {
    return <ErrorState title={`Couldn't map ${ticker}`} message={error} />;
  }

  if (!data) return null;

  const relationships = data.relationships ?? [];
  const dataSources = data.data_sources_used ?? [];
  const grouped = groupBy(relationships);

  return (
    <div>
      <div className="mb-8">
        <Link href="/supply-chain" className="text-base text-muted hover:text-ink">
          ← Supply chain
        </Link>
        <div className="mt-1 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold tracking-tight text-ink">{data.company_name}</h1>
          <Chip>{data.ticker}</Chip>
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-base text-muted">
          <span>{relationships.length} relationships found</span>
          {data.filed_at && <span>10-K filed {data.filed_at}</span>}
          {data.filing_url && (
            <a
              href={data.filing_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-action hover:underline"
            >
              View filing
            </a>
          )}
        </div>
        {dataSources.length > 0 && (
          <p className="mt-1 text-sm text-muted">
            Sources: {dataSources.map((src) => sourceLabel[src] ?? src).join(", ")}
          </p>
        )}
      </div>

      <div role="group" aria-label="View" className="mb-8 inline-flex rounded border border-rule bg-surface p-0.5">
        {(["card", "graph"] as const).map((mode) => (
          <button
            key={mode}
            aria-pressed={viewMode === mode}
            onClick={() => switchView(mode)}
            className={`rounded px-3 py-1 text-sm font-medium ${
              viewMode === mode ? "bg-action text-action-ink" : "text-muted hover:text-ink"
            }`}
          >
            {mode === "card" ? "List" : "Graph"}
          </button>
        ))}
      </div>

      {/* Relationship view */}
      {viewMode === "graph" ? (
        <SupplyChainGraph report={data} />
      ) : (
        <div className="grid gap-x-12 gap-y-10 lg:grid-cols-2">
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

      {viewMode === "card" && (
        <div className="mt-10 flex flex-wrap items-center gap-x-5 gap-y-1 text-sm text-muted">
          <span className="font-medium text-ink">Confidence</span>
          {(["high", "medium", "low"] as const).map((c) => (
            <span key={c} className="flex items-center gap-1.5">
              <ConfidenceDot level={c} />
              {c.charAt(0).toUpperCase() + c.slice(1)}
            </span>
          ))}
        </div>
      )}

      {data.notes && (
        <p className="mt-4 max-w-reading text-sm text-muted">{data.notes}</p>
      )}

    </div>
  );
}
