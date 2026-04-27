"use client";

import { useState } from "react";
import Link from "next/link";
import { useReport } from "@/hooks/useResearch";
import { useRunSteps } from "@/hooks/useRuns";
import { VerdictCard } from "@/components/ui/VerdictCard";
import { AddToPortfolioModal } from "@/components/portfolio/AddToPortfolioModal";
import { Spinner } from "@/components/ui/Spinner";
import { RationaleText } from "@/components/ui/RationaleText";
import { SignalsList } from "@/components/ui/SignalsList";
import type { SourceRef } from "@/lib/types";

function SourcesSidebar({ sources }: { sources: SourceRef[] }) {
  if (!sources.length) return null;
  const news = sources.filter((s) => s.kind === "news");
  const filings = sources.filter((s) => s.kind === "sec_filing");

  return (
    <div className="space-y-4">
      {news.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-neutral-400 dark:text-zinc-500">News</p>
          <ol className="space-y-2">
            {news.map((src, i) => (
              <li key={i} className="flex gap-2 text-sm">
                <span className="mt-0.5 shrink-0 text-xs font-medium text-neutral-400 dark:text-zinc-500">[{i + 1}]</span>
                {src.url ? (
                  <a href={src.url} target="_blank" rel="noopener noreferrer"
                     className="text-blue-600 hover:underline leading-snug dark:text-sky-400">
                    {src.label}
                  </a>
                ) : (
                  <span className="text-neutral-600 leading-snug dark:text-zinc-300">{src.label}</span>
                )}
              </li>
            ))}
          </ol>
        </div>
      )}
      {filings.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-neutral-400 dark:text-zinc-500">SEC Filings</p>
          <ol className="space-y-2">
            {filings.map((src, i) => (
              <li key={i} className="flex gap-2 text-sm">
                <span className="mt-0.5 shrink-0 text-xs font-medium text-neutral-400 dark:text-zinc-500">F{i + 1}</span>
                {src.url ? (
                  <a href={src.url} target="_blank" rel="noopener noreferrer"
                     className="text-blue-600 hover:underline leading-snug dark:text-sky-400">
                    {src.label}
                  </a>
                ) : (
                  <span className="text-neutral-600 leading-snug dark:text-zinc-300">{src.label}</span>
                )}
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}

export default function ResearchReportPage({ params }: { params: { id: string } }) {
  const { data: report, loading, error } = useReport(params.id);
  const { data: steps } = useRunSteps(report?.run_id ?? null);
  const [modalOpen, setModalOpen] = useState(false);

  if (loading) {
    return (
      <div className="flex items-center gap-3 py-12">
        <Spinner />
        <span className="text-neutral-500 dark:text-zinc-400">Loading report…</span>
      </div>
    );
  }

  if (error) return <p className="text-red-600 dark:text-red-400">{error}</p>;
  if (!report) return null;

  const sources: SourceRef[] = report.report.sources ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-neutral-400 dark:text-zinc-500">{new Date(report.created_at).toLocaleString()}</p>
          <h2 className="text-2xl font-bold text-neutral-900 dark:text-zinc-100">{report.ticker}</h2>
        </div>
        <div className="flex items-center gap-3">
          {report.signal === "buy" && (
            <button
              onClick={() => setModalOpen(true)}
              className="rounded-md bg-green-700 px-4 py-2 text-sm font-medium text-white hover:bg-green-600 dark:bg-green-800 dark:hover:bg-green-700"
            >
              + Add to portfolio
            </button>
          )}
          <Link href="/research" className="text-sm text-neutral-400 hover:text-neutral-700 dark:text-zinc-500 dark:hover:text-zinc-200">
            ← All Research
          </Link>
        </div>
      </div>

      <VerdictCard layers={report.report.layers} signal={report.signal} ticker={report.ticker} />

      <SignalsList steps={steps} />

      {report.report.recommended_position_pct != null && (
        <div className="rounded-xl border border-neutral-200 bg-white px-6 py-4 dark:border-zinc-800 dark:bg-zinc-900">
          <p className="text-base text-neutral-600 dark:text-zinc-300">
            Recommended position:{" "}
            <strong className="text-neutral-900 dark:text-zinc-100">{Math.round(report.report.recommended_position_pct * 100)}%</strong>{" "}
            of portfolio
          </p>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
        {/* Rationale */}
        <div className="rounded-xl border border-neutral-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="font-semibold text-neutral-800 dark:text-zinc-100">Rationale</h3>
            {sources.filter((s) => s.kind === "news").length > 0 && (
              <span className="text-xs text-neutral-400 dark:text-zinc-500">
                {sources.filter((s) => s.kind === "news").length} source{sources.filter((s) => s.kind === "news").length !== 1 ? "s" : ""} →
              </span>
            )}
          </div>
          <RationaleText text={report.report.rationale} sources={sources} />
        </div>

        {/* Sticky sources sidebar */}
        {sources.length > 0 && (
          <div className="lg:sticky lg:top-6 lg:self-start rounded-xl border border-neutral-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
            <h3 className="mb-4 font-semibold text-neutral-800 dark:text-zinc-100">Sources</h3>
            <SourcesSidebar sources={sources} />
          </div>
        )}
      </div>

      <AddToPortfolioModal
        reportId={params.id}
        ticker={report.ticker}
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
      />
    </div>
  );
}
