import { VerdictCard } from "@/components/ui/VerdictCard";
import { RationaleText } from "@/components/ui/RationaleText";
import { ReportSections } from "@/components/research/ReportSections";
import { ByTheNumbers } from "@/components/research/ByTheNumbers";
import { SourcesSection } from "@/components/research/SourcesSection";
import type { ResearchReportBody, ResearchSignal, SourceRef } from "@/lib/types";

/**
 * The research result, in reading order: verdict, the written analysis beside the figures behind it,
 * and the sources last. Shared by the saved report page and the run result page.
 */
export function ReportView({
  ticker,
  signal,
  report,
}: {
  ticker: string;
  signal: ResearchSignal;
  report: ResearchReportBody;
}) {
  const sources: SourceRef[] = report.sources ?? [];
  const hasNews = sources.some((s) => s.kind === "news");
  const sections = report.report_sections;

  return (
    <div className="space-y-12">
      <h1 className="text-headline font-semibold">
        Is {ticker} <span className="italic">worth holding?</span>
      </h1>

      <VerdictCard
        layers={report.layers}
        signal={signal}
        ticker={ticker}
        confidencePenalty={report.validation_result?.confidence_penalty}
      />

      {report.recommended_position_pct != null && (
        <p className="text-lg text-ink">
          Recommended position: <strong className="font-semibold">{Math.round(report.recommended_position_pct * 100)}%</strong> of
          portfolio.
        </p>
      )}

      <div className="grid grid-cols-[minmax(0,1fr)] gap-x-16 gap-y-12 lg:grid-cols-[minmax(0,44rem)_minmax(0,1fr)]">
        <section>
          <h2 className="mb-1 text-xl font-semibold">Analysis</h2>
          {hasNews && <p className="mb-6 text-base text-muted">Bracketed numbers link to the sources at the bottom of the page.</p>}
          <div className="font-serif">
            {sections && Object.keys(sections).length > 0 ? (
              <ReportSections sections={sections} sources={sources} />
            ) : (
              <RationaleText text={report.rationale} sources={sources} />
            )}
          </div>
        </section>

        <ByTheNumbers ticker={ticker} bridge={report.valuation_bridge} insiders={report.insider_summary} />
      </div>

      <SourcesSection sources={sources} />
    </div>
  );
}
