"use client";

import Link from "next/link";
import { useRun } from "@/hooks/useRuns";
import { useReports } from "@/hooks/useResearch";
import { ReportView } from "@/components/research/ReportView";
import { Spinner } from "@/components/ui/Spinner";
import { ButtonLink } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { ErrorState } from "@/components/ui/Panel";

export default function ResearchRunResultPage({ params }: { params: { id: string } }) {
  const { data: run, loading, error } = useRun(params.id);
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

      <ReportView ticker={run.ticker ?? run.report.ticker} signal={run.report.signal} report={run.report} />
    </div>
  );
}
