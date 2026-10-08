"use client";

import Link from "next/link";
import { useRun, useRunSteps } from "@/hooks/useRuns";
import { useReports } from "@/hooks/useResearch";
import { VerdictCard } from "@/components/ui/VerdictCard";
import { Spinner } from "@/components/ui/Spinner";
import { RationaleText } from "@/components/ui/RationaleText";
import { ReportSections } from "@/components/research/ReportSections";
import { SignalsList } from "@/components/ui/SignalsList";
import { ButtonLink } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { ErrorState } from "@/components/ui/Panel";
import { SourcesRail } from "@/components/research/SourcesRail";
import type { SourceRef } from "@/lib/types";

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
        <span className="text-muted">Loading result</span>
      </div>
    );
  }

  if (error) return <ErrorState title="Couldn't load this result" message={error} />;
  if (!run) return null;

  if (run.status === "queued" || run.status === "running") {
    return (
      <div className="flex items-center gap-3 py-12">
        <Spinner />
        <span className="text-muted">This run is still in progress.</span>
        <Link href={`/research/runs/${params.id}`} className="text-action hover:underline">
          Back to progress
        </Link>
      </div>
    );
  }

  if (run.status === "failed") {
    return <ErrorState title="Run failed" message={run.error ?? "No error was recorded for this run."} />;
  }

  if (!run.report) return <p className="text-muted">This run finished without a report.</p>;

  const sources: SourceRef[] = run.report.sources ?? [];
  const newsSources = sources.filter((s) => s.kind === "news");

  const isHistorical = run.flow === "backtest" && run.as_of_date;

  return (
    <div className="space-y-10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Link href="/research" className="text-base text-muted hover:text-ink">
            ← Research
          </Link>
          {isHistorical && (
            <Chip tone="hold">Historical, as of {run.as_of_date?.split("-").reverse().join("/")}</Chip>
          )}
        </div>
        <div className="flex items-center gap-3">
          {isHistorical && run.ticker && (
            <ButtonLink variant="secondary" href={`/simulation?ticker=${run.ticker}&start_date=${run.as_of_date}`}>
              Add to simulation
            </ButtonLink>
          )}
          {savedReportId && <ButtonLink href={`/research/reports/${savedReportId}`}>Open full report</ButtonLink>}
        </div>
      </div>

      <h1 className="text-headline font-semibold">
        Is {run.ticker} <span className="italic">worth holding?</span>
      </h1>

      <VerdictCard layers={run.report.layers} signal={run.report.signal} ticker={run.ticker ?? undefined} />

      <SignalsList steps={steps} />

      <div className="grid gap-10 lg:grid-cols-[minmax(0,45rem)_1fr]">
        <section>
          <h2 className="mb-1 text-xl font-semibold text-ink">Rationale</h2>
          {newsSources.length > 0 && (
            <p className="mb-4 text-base text-muted">
              Cites {newsSources.length} news source{newsSources.length !== 1 ? "s" : ""}; numbers in brackets match the list.
            </p>
          )}
          <div className="font-serif">
            {run.report.report_sections && Object.keys(run.report.report_sections).length > 0 ? (
              <ReportSections sections={run.report.report_sections} sources={sources} />
            ) : (
              <RationaleText text={run.report.rationale} sources={sources} />
            )}
          </div>
        </section>

        <SourcesRail sources={sources} />
      </div>
    </div>
  );
}
