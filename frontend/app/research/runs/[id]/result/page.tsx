"use client";

import Link from "next/link";
import { useRun, useRunSteps } from "@/hooks/useRuns";
import { useReports } from "@/hooks/useResearch";
import { VerdictCard } from "@/components/ui/VerdictCard";
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
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-neutral-400">News</p>
          <ol className="space-y-2">
            {news.map((src, i) => (
              <li key={i} className="flex gap-2 text-sm">
                <span className="mt-0.5 shrink-0 text-xs font-medium text-neutral-400">[{i + 1}]</span>
                {src.url ? (
                  <a href={src.url} target="_blank" rel="noopener noreferrer"
                     className="text-blue-600 hover:underline leading-snug">
                    {src.label}
                  </a>
                ) : (
                  <span className="text-neutral-600 leading-snug">{src.label}</span>
                )}
              </li>
            ))}
          </ol>
        </div>
      )}
      {filings.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-neutral-400">SEC Filings</p>
          <ol className="space-y-2">
            {filings.map((src, i) => (
              <li key={i} className="flex gap-2 text-sm">
                <span className="mt-0.5 shrink-0 text-xs font-medium text-neutral-400">F{i + 1}</span>
                {src.url ? (
                  <a href={src.url} target="_blank" rel="noopener noreferrer"
                     className="text-blue-600 hover:underline leading-snug">
                    {src.label}
                  </a>
                ) : (
                  <span className="text-neutral-600 leading-snug">{src.label}</span>
                )}
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}

export default function ResearchRunResultPage({ params }: { params: { id: string } }) {
  const { data: run, loading, error } = useRun(params.id);
  const { data: steps } = useRunSteps(params.id);
  const ticker = run?.ticker ?? null;
  const { data: reports } = useReports(ticker ? { ticker, limit: 1 } : {});
  const savedReportId = reports[0]?.id;

  if (loading) {
    return (
      <div className="flex items-center gap-3 py-12">
        <Spinner />
        <span className="text-neutral-500">Loading result…</span>
      </div>
    );
  }

  if (error) return <p className="text-red-600">{error}</p>;
  if (!run) return null;

  if (run.status === "queued" || run.status === "running") {
    return (
      <div className="flex items-center gap-3 py-12">
        <Spinner />
        <span className="text-neutral-500">Run still in progress…</span>
        <Link href={`/research/runs/${params.id}`} className="text-neutral-500 underline">
          Back to progress view
        </Link>
      </div>
    );
  }

  if (run.status === "failed") {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 p-4 text-red-700">
        Run failed: {run.error ?? "unknown error"}
      </div>
    );
  }

  if (!run.report) return <p className="text-neutral-500">No report generated.</p>;

  const sources: ResearchSource[] = run.report.sources ?? [];
  const newsSources = sources.filter((s) => s.kind === "news");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-neutral-800">
          Research result — {run.ticker}
        </h2>
        <div className="flex items-center gap-4">
          {savedReportId && (
            <Link href={`/research/reports/${savedReportId}`}
              className="text-neutral-500 underline hover:text-neutral-800">
              View full report →
            </Link>
          )}
          <Link href="/research" className="text-neutral-400 hover:text-neutral-700">← Back</Link>
        </div>
      </div>

      <VerdictCard layers={run.report.layers} signal={run.report.signal} ticker={run.ticker ?? undefined} />

      <SignalsList steps={steps} />

      <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
        {/* Rationale */}
        <div className="rounded-xl border border-neutral-200 bg-white p-6">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="font-semibold text-neutral-800">Rationale</h3>
            {newsSources.length > 0 && (
              <span className="text-xs text-neutral-400">{newsSources.length} source{newsSources.length !== 1 ? "s" : ""} cited →</span>
            )}
          </div>
          <RationaleText text={run.report.rationale} sources={sources} />
        </div>

        {/* Sticky sources sidebar */}
        {sources.length > 0 && (
          <div className="lg:sticky lg:top-6 lg:self-start rounded-xl border border-neutral-200 bg-white p-5">
            <h3 className="mb-4 font-semibold text-neutral-800">Sources</h3>
            <SourcesSidebar sources={sources} />
          </div>
        )}
      </div>
    </div>
  );
}

