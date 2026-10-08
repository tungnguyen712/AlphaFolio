"use client";

import { useState } from "react";
import Link from "next/link";
import { useReport } from "@/hooks/useResearch";
import { useRunSteps } from "@/hooks/useRuns";
import { VerdictCard } from "@/components/ui/VerdictCard";
import { AddToPortfolioModal } from "@/components/portfolio/AddToPortfolioModal";
import { Spinner } from "@/components/ui/Spinner";
import { RationaleText } from "@/components/ui/RationaleText";
import { ReportSections } from "@/components/research/ReportSections";
import { SignalsList } from "@/components/ui/SignalsList";
import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/Panel";
import { SourcesRail } from "@/components/research/SourcesRail";
import type {
  ConfidenceBreakdown,
  InsiderSummary,
  ScenarioCase,
  SourceRef,
  ValuationBridge,
  ValidationResult,
} from "@/lib/types";
import { noEmDash } from "@/lib/text";

const scenarioText: Record<string, string> = {
  bull: "text-buy",
  base: "text-action",
  bear: "text-sell",
};

const scenarioBg: Record<string, string> = {
  bull: "bg-buy",
  base: "bg-action",
  bear: "bg-sell",
};

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-t-[3px] border-ink pt-5">
      <h2 className="mb-5 text-xl font-semibold text-ink">{title}</h2>
      {children}
    </section>
  );
}

function Figure({ label, value, tone = "text-ink" }: { label: string; value: string | number; tone?: string }) {
  return (
    <div>
      <dt className="text-sm text-muted">{label}</dt>
      <dd className={`text-lg font-semibold ${tone}`}>{value}</dd>
    </div>
  );
}

function ValuationBridgeSection({ bridge }: { bridge: ValuationBridge }) {
  const fmt = (n: number | null, prefix = "$") =>
    n == null ? "n/a" : `${prefix}${n.toLocaleString()}`;
  const fmtCap = (n: number | null) =>
    n == null
      ? "n/a"
      : n >= 1e12
        ? `$${(n / 1e12).toFixed(2)}T`
        : n >= 1e9
          ? `$${(n / 1e9).toFixed(1)}B`
          : `$${n.toLocaleString()}`;
  const fmtPct = (n: number | null) => (n == null ? "n/a" : `${n > 0 ? "+" : ""}${n.toFixed(1)}%`);

  // Shared price axis: every scenario target and the current price on one line.
  const targets = bridge.scenarios
    .map((s) => s.price_target)
    .filter((n): n is number => n != null);
  const points = [...targets, ...(bridge.current_price != null ? [bridge.current_price] : [])];
  const lo = points.length ? Math.min(...points) : 0;
  const hi = points.length ? Math.max(...points) : 0;
  const pos = (n: number) => (hi === lo ? 50 : 6 + ((n - lo) / (hi - lo)) * 88);

  return (
    <Section title="Valuation bridge">
      <dl className="mb-6 grid grid-cols-2 gap-x-8 gap-y-3 sm:grid-cols-4">
        <Figure label="Current price" value={fmt(bridge.current_price)} />
        <Figure label="Market cap" value={fmtCap(bridge.market_cap)} />
        <Figure label="Forward P/E" value={fmt(bridge.forward_pe, "")} />
        <Figure label="EV/Revenue" value={fmt(bridge.ev_revenue, "")} />
      </dl>

      {bridge.scenarios.length > 0 && (
        <>
          {points.length > 1 && (
            <div className="relative mb-8 mt-2 h-10" aria-hidden="true">
              <div className="absolute left-0 right-0 top-1/2 h-px bg-rule" />
              {bridge.current_price != null && (
                <div className="absolute top-0 h-full w-px bg-ink" style={{ left: `${pos(bridge.current_price)}%` }}>
                  <span className="absolute -bottom-5 left-1/2 -translate-x-1/2 whitespace-nowrap text-sm text-muted">
                    Now
                  </span>
                </div>
              )}
              {bridge.scenarios.map(
                (s: ScenarioCase) =>
                  s.price_target != null && (
                    <span
                      key={s.label}
                      className={`absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full ${scenarioBg[s.label]}`}
                      style={{ left: `${pos(s.price_target)}%` }}
                    />
                  ),
              )}
            </div>
          )}

          <div className="grid gap-6 sm:grid-cols-3">
            {bridge.scenarios.map((s: ScenarioCase) => (
              <div key={s.label} className="border-l-2 border-rule pl-4">
                <p className={`font-semibold capitalize ${scenarioText[s.label]}`}>{s.label}</p>
                <p className="text-2xl font-semibold text-ink">{fmt(s.price_target)}</p>
                <p className={`text-base font-medium ${scenarioText[s.label]}`}>
                  {fmtPct(s.implied_upside_pct)}
                </p>
                <p className="mt-1 text-sm text-muted">{s.key_assumption}</p>
              </div>
            ))}
          </div>
        </>
      )}
      {bridge.missing_fields.length > 0 && (
        <p className="mt-4 text-sm text-hold">Missing data: {bridge.missing_fields.join(", ")}</p>
      )}
    </Section>
  );
}

function DataQualitySection({
  validation,
  confidenceBreakdown,
}: {
  validation: ValidationResult;
  confidenceBreakdown?: ConfidenceBreakdown | null;
}) {
  const rows = [
    ...validation.errors.map((text) => ({ text, kind: "Error" as const })),
    ...validation.warnings.map((text) => ({ text, kind: "Warning" as const })),
  ];
  return (
    <Section title="Data quality">
      {rows.length > 0 ? (
        <ul className="divide-y divide-rule">
          {rows.map((r, i) => (
            <li key={i} className="flex gap-3 py-2 text-base">
              <span className={`w-16 shrink-0 font-medium ${r.kind === "Error" ? "text-sell" : "text-hold"}`}>
                {r.kind}
              </span>
              <span className="text-ink">{noEmDash(r.text)}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-base text-muted">No data problems were found.</p>
      )}
      {validation.confidence_penalty > 0 && (
        <p className="mt-3 text-base text-muted">
          Confidence was reduced by {Math.round(validation.confidence_penalty * 100)}% because of these gaps.
        </p>
      )}
      {confidenceBreakdown && (
        <div className="mt-6 grid gap-6 sm:grid-cols-2">
          {confidenceBreakdown.positive_contributors.length > 0 && (
            <div>
              <h4 className="mb-1 font-semibold text-buy">Raised confidence</h4>
              <ul className="space-y-1">
                {confidenceBreakdown.positive_contributors.map((c, i) => (
                  <li key={i} className="text-base text-ink">{noEmDash(c)}</li>
                ))}
              </ul>
            </div>
          )}
          {confidenceBreakdown.negative_contributors.length > 0 && (
            <div>
              <h4 className="mb-1 font-semibold text-sell">Lowered confidence</h4>
              <ul className="space-y-1">
                {confidenceBreakdown.negative_contributors.map((c, i) => (
                  <li key={i} className="text-base text-ink">{noEmDash(c)}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </Section>
  );
}

function InsiderActivitySection({ summary }: { summary: InsiderSummary }) {
  if (summary.raw_transaction_count === 0) return null;
  const fmtM = (n: number) =>
    n >= 1_000_000 ? `$${(n / 1_000_000).toFixed(1)}M` : `$${n.toLocaleString()}`;

  return (
    <Section title="Insider activity">
      <dl className="grid grid-cols-2 gap-x-8 gap-y-4 sm:grid-cols-3 lg:grid-cols-6">
        <Figure label="Unique sellers" value={summary.unique_sellers} />
        <Figure label="Unique buyers" value={summary.unique_buyers} />
        <Figure label="C-suite sellers" value={summary.csuite_sellers} />
        <Figure label="Board sellers" value={summary.board_sellers} />
        {summary.total_sales_value > 0 && (
          <Figure label="Total sales" value={fmtM(summary.total_sales_value)} tone="text-sell" />
        )}
        {summary.total_purchase_value > 0 && (
          <Figure label="Total purchases" value={fmtM(summary.total_purchase_value)} tone="text-buy" />
        )}
      </dl>
      <p className="mt-4 text-sm text-muted">
        Based on {summary.num_distinct_filings} distinct filing{summary.num_distinct_filings !== 1 ? "s" : ""}{" "}
        ({summary.raw_transaction_count} raw transaction row{summary.raw_transaction_count !== 1 ? "s" : ""}).
      </p>
    </Section>
  );
}

export default function ResearchReportPage({ params }: { params: { id: string } }) {
  const { data: report, loading, error, refetch } = useReport(params.id);
  const { data: steps } = useRunSteps(report?.run_id ?? null);
  const [modalOpen, setModalOpen] = useState(false);

  if (loading) {
    return (
      <div className="flex items-center gap-3 py-12">
        <Spinner />
        <span className="text-muted">Loading report</span>
      </div>
    );
  }

  if (error) return <ErrorState title="Couldn't load this report" message={error} onRetry={refetch} />;
  if (!report) return null;

  const sources: SourceRef[] = report.report.sources ?? [];
  const hasSections =
    report.report.report_sections && Object.keys(report.report.report_sections).length > 0;

  return (
    <div className="space-y-10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-4">
          <Link href="/research" className="text-base text-muted hover:text-ink">
            ← Research
          </Link>
          <span className="text-base text-muted">{new Date(report.created_at).toLocaleString()}</span>
        </div>
        {report.signal === "buy" && <Button onClick={() => setModalOpen(true)}>Add to portfolio</Button>}
      </div>

      <h1 className="text-headline font-semibold">
        Is {report.ticker} <span className="italic">worth holding?</span>
      </h1>

      <VerdictCard
        layers={report.report.layers}
        signal={report.signal}
        ticker={report.ticker}
        confidencePenalty={report.report.validation_result?.confidence_penalty}
      />

      {report.report.recommended_position_pct != null && (
        <p className="text-lg text-ink">
          Recommended position:{" "}
          <strong className="font-semibold">
            {Math.round(report.report.recommended_position_pct * 100)}%
          </strong>{" "}
          of portfolio.
        </p>
      )}

      <SignalsList steps={steps} />

      <div className="grid gap-10 lg:grid-cols-[minmax(0,45rem)_1fr]">
        <section>
          <h2 className="mb-1 text-xl font-semibold text-ink">Rationale</h2>
          {sources.filter((s) => s.kind === "news").length > 0 && (
            <p className="mb-6 text-base text-muted">Numbers in brackets match the source list.</p>
          )}
          <div className="font-serif">
            {hasSections ? (
              <ReportSections sections={report.report.report_sections!} sources={sources} />
            ) : (
              <RationaleText text={report.report.rationale} sources={sources} />
            )}
          </div>
        </section>

        <SourcesRail sources={sources} />
      </div>

      {report.report.valuation_bridge != null && (
        <ValuationBridgeSection bridge={report.report.valuation_bridge} />
      )}

      {report.report.validation_result != null && (
        <DataQualitySection
          validation={report.report.validation_result}
          confidenceBreakdown={report.report.confidence_breakdown}
        />
      )}

      {report.report.insider_summary != null && (
        <InsiderActivitySection summary={report.report.insider_summary} />
      )}

      <AddToPortfolioModal
        reportId={params.id}
        ticker={report.ticker}
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
      />
    </div>
  );
}
