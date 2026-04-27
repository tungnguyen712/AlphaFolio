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
import type {
  ConfidenceBreakdown,
  InsiderSummary,
  ScenarioCase,
  SourceRef,
  ValuationBridge,
  ValidationResult,
} from "@/lib/types";

const ORDERED_SECTIONS = [
  "Recommendation",
  "Investment Thesis",
  "Top Signals",
  "Valuation Bridge",
  "Key Uncertainties",
  "Devil's Advocate",
  "Data Quality",
  "Final Rationale",
] as const;

function ValuationBridgeSection({ bridge }: { bridge: ValuationBridge }) {
  const fmt = (n: number | null, prefix = "$") =>
    n == null ? "—" : `${prefix}${n.toLocaleString()}`;
  const fmtPct = (n: number | null) => (n == null ? "—" : `${n > 0 ? "+" : ""}${n.toFixed(1)}%`);
  const scenarioColor: Record<string, string> = {
    bull: "text-green-600 dark:text-green-400",
    base: "text-blue-600 dark:text-sky-400",
    bear: "text-red-600 dark:text-red-400",
  };

  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
      <h3 className="mb-4 font-semibold text-neutral-800 dark:text-zinc-100">Valuation Bridge</h3>
      <div className="mb-4 grid grid-cols-2 gap-x-8 gap-y-2 text-sm sm:grid-cols-4">
        <div>
          <p className="text-xs text-neutral-400 dark:text-zinc-500">Current Price</p>
          <p className="font-medium text-neutral-900 dark:text-zinc-100">{fmt(bridge.current_price)}</p>
        </div>
        <div>
          <p className="text-xs text-neutral-400 dark:text-zinc-500">Market Cap</p>
          <p className="font-medium text-neutral-900 dark:text-zinc-100">{fmt(bridge.market_cap)}</p>
        </div>
        <div>
          <p className="text-xs text-neutral-400 dark:text-zinc-500">Forward P/E</p>
          <p className="font-medium text-neutral-900 dark:text-zinc-100">{fmt(bridge.forward_pe, "")}</p>
        </div>
        <div>
          <p className="text-xs text-neutral-400 dark:text-zinc-500">EV/Revenue</p>
          <p className="font-medium text-neutral-900 dark:text-zinc-100">{fmt(bridge.ev_revenue, "")}</p>
        </div>
      </div>
      {bridge.scenarios.length > 0 && (
        <div className="mb-4 grid grid-cols-3 gap-3 text-sm">
          {bridge.scenarios.map((s: ScenarioCase) => (
            <div key={s.label} className="rounded-lg border border-neutral-100 bg-neutral-50 p-3 dark:border-zinc-700 dark:bg-zinc-800">
              <p className={`text-xs font-semibold uppercase ${scenarioColor[s.label]}`}>{s.label}</p>
              <p className="text-base font-bold text-neutral-900 dark:text-zinc-100">{fmt(s.price_target)}</p>
              <p className={`text-xs font-medium ${scenarioColor[s.label]}`}>{fmtPct(s.implied_upside_pct)}</p>
              <p className="mt-1 text-xs text-neutral-500 dark:text-zinc-400 leading-snug">{s.key_assumption}</p>
            </div>
          ))}
        </div>
      )}
      {bridge.missing_fields.length > 0 && (
        <p className="text-xs text-amber-600 dark:text-amber-400">
          Missing data: {bridge.missing_fields.join(", ")}
        </p>
      )}
    </div>
  );
}

function DataQualitySection({
  validation,
  confidenceBreakdown,
}: {
  validation: ValidationResult;
  confidenceBreakdown?: ConfidenceBreakdown | null;
}) {
  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
      <h3 className="mb-4 font-semibold text-neutral-800 dark:text-zinc-100">Data Quality</h3>
      {validation.errors.length > 0 && (
        <ul className="mb-3 space-y-1">
          {validation.errors.map((e, i) => (
            <li key={i} className="flex gap-2 text-sm text-red-600 dark:text-red-400">
              <span className="mt-0.5 shrink-0">✗</span>
              <span>{e}</span>
            </li>
          ))}
        </ul>
      )}
      {validation.warnings.length > 0 && (
        <ul className="mb-3 space-y-1">
          {validation.warnings.map((w, i) => (
            <li key={i} className="flex gap-2 text-sm text-amber-600 dark:text-amber-400">
              <span className="mt-0.5 shrink-0">⚠</span>
              <span>{w}</span>
            </li>
          ))}
        </ul>
      )}
      {validation.confidence_penalty > 0 && (
        <p className="text-xs text-neutral-500 dark:text-zinc-400">
          Confidence reduced by {Math.round(validation.confidence_penalty * 100)}% due to data gaps.
        </p>
      )}
      {confidenceBreakdown && (
        <div className="mt-4 space-y-2">
          {confidenceBreakdown.positive_contributors.length > 0 && (
            <div>
              <p className="mb-1 text-xs font-medium text-green-600 dark:text-green-400">Positive</p>
              <ul className="space-y-0.5">
                {confidenceBreakdown.positive_contributors.map((c, i) => (
                  <li key={i} className="text-xs text-neutral-600 dark:text-zinc-300">{c}</li>
                ))}
              </ul>
            </div>
          )}
          {confidenceBreakdown.negative_contributors.length > 0 && (
            <div>
              <p className="mb-1 text-xs font-medium text-red-600 dark:text-red-400">Negative</p>
              <ul className="space-y-0.5">
                {confidenceBreakdown.negative_contributors.map((c, i) => (
                  <li key={i} className="text-xs text-neutral-600 dark:text-zinc-300">{c}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function InsiderActivitySection({ summary }: { summary: InsiderSummary }) {
  if (summary.raw_transaction_count === 0) return null;
  const fmtM = (n: number) =>
    n >= 1_000_000 ? `$${(n / 1_000_000).toFixed(1)}M` : `$${n.toLocaleString()}`;

  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
      <h3 className="mb-4 font-semibold text-neutral-800 dark:text-zinc-100">Insider Activity</h3>
      <div className="grid grid-cols-2 gap-x-8 gap-y-2 text-sm sm:grid-cols-4">
        <div>
          <p className="text-xs text-neutral-400 dark:text-zinc-500">Unique Sellers</p>
          <p className="font-medium text-neutral-900 dark:text-zinc-100">{summary.unique_sellers}</p>
        </div>
        <div>
          <p className="text-xs text-neutral-400 dark:text-zinc-500">Unique Buyers</p>
          <p className="font-medium text-neutral-900 dark:text-zinc-100">{summary.unique_buyers}</p>
        </div>
        <div>
          <p className="text-xs text-neutral-400 dark:text-zinc-500">C-Suite Sellers</p>
          <p className="font-medium text-neutral-900 dark:text-zinc-100">{summary.csuite_sellers}</p>
        </div>
        <div>
          <p className="text-xs text-neutral-400 dark:text-zinc-500">Board Sellers</p>
          <p className="font-medium text-neutral-900 dark:text-zinc-100">{summary.board_sellers}</p>
        </div>
        {summary.total_sales_value > 0 && (
          <div>
            <p className="text-xs text-neutral-400 dark:text-zinc-500">Total Sales</p>
            <p className="font-medium text-red-600 dark:text-red-400">{fmtM(summary.total_sales_value)}</p>
          </div>
        )}
        {summary.total_purchase_value > 0 && (
          <div>
            <p className="text-xs text-neutral-400 dark:text-zinc-500">Total Purchases</p>
            <p className="font-medium text-green-600 dark:text-green-400">{fmtM(summary.total_purchase_value)}</p>
          </div>
        )}
      </div>
      <p className="mt-3 text-xs text-neutral-400 dark:text-zinc-500">
        Based on {summary.num_distinct_filings} distinct filing{summary.num_distinct_filings !== 1 ? "s" : ""}{" "}
        ({summary.raw_transaction_count} raw transaction row{summary.raw_transaction_count !== 1 ? "s" : ""})
      </p>
    </div>
  );
}

/** Renders inline **bold** markers without raw asterisks. */
function InlineText({ text }: { text: string }) {
  const parts = text.split(/\*\*(.+?)\*\*/g);
  return (
    <>
      {parts.map((p, i) =>
        i % 2 === 1 ? (
          <strong key={i} className="font-semibold text-neutral-900 dark:text-zinc-100">
            {p}
          </strong>
        ) : (
          p
        )
      )}
    </>
  );
}

/**
 * Renders structured report_sections for new-format reports.
 * Each section has an explicit heading and prose body.
 */
function ReportSectionsRenderer({
  sections,
  sources,
}: {
  sections: Record<string, string>;
  sources: SourceRef[];
}) {
  const news = sources.filter((s) => s.kind === "news");

  // Render in canonical order, then any unexpected extras from the LLM
  const knownOrder = ORDERED_SECTIONS.filter((h) => h in sections);
  const extras = Object.keys(sections).filter(
    (h) => !(ORDERED_SECTIONS as readonly string[]).includes(h)
  );
  const orderedKeys = [...knownOrder, ...extras];

  return (
    <div className="space-y-5">
      {orderedKeys.map((heading) => {
        const body = sections[heading] ?? "";
        const paragraphs = body.split(/\n{2,}/).filter(Boolean);

        return (
          <section key={heading}>
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-neutral-400 dark:text-zinc-500">
              {heading}
            </h4>
            <div className="space-y-3">
              {paragraphs.map((para, pi) => {
                // Find citation indices for this paragraph
                const citedIndices: number[] = [];
                if (news.length > 0) {
                  const lower = para.toLowerCase();
                  news.forEach((src, i) => {
                    const label = src.label.replace(/\s*\(\d{4}-\d{2}-\d{2}\)\s*$/, "");
                    const outlets = ["CNBC", "Reuters", "Bloomberg", "WSJ", "TipRanks", "Forbes"];
                    const hit = outlets.some((o) => label.toLowerCase().includes(o.toLowerCase()) && lower.includes(o.toLowerCase()));
                    if (hit) citedIndices.push(i + 1);
                  });
                }

                return (
                  <p
                    key={pi}
                    className="text-base leading-relaxed text-neutral-700 dark:text-zinc-300"
                  >
                    <InlineText text={para} />
                    {citedIndices.map((n) => (
                      <sup
                        key={n}
                        className="ml-0.5 text-[10px] font-semibold text-blue-500 select-none"
                      >
                        [{n}]
                      </sup>
                    ))}
                  </p>
                );
              })}
            </div>
          </section>
        );
      })}
    </div>
  );
}

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
        {/* Rationale — structured sections for new reports, legacy renderer for old */}
        <div className="rounded-xl border border-neutral-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="font-semibold text-neutral-800 dark:text-zinc-100">Rationale</h3>
            {sources.filter((s) => s.kind === "news").length > 0 && (
              <span className="text-xs text-neutral-400 dark:text-zinc-500">
                {sources.filter((s) => s.kind === "news").length} source{sources.filter((s) => s.kind === "news").length !== 1 ? "s" : ""} →
              </span>
            )}
          </div>
          {report.report.report_sections &&
          Object.keys(report.report.report_sections).length > 0 ? (
            <ReportSectionsRenderer
              sections={report.report.report_sections}
              sources={sources}
            />
          ) : (
            <RationaleText text={report.report.rationale} sources={sources} />
          )}
        </div>

        {/* Sticky sources sidebar */}
        {sources.length > 0 && (
          <div className="lg:sticky lg:top-6 lg:self-start rounded-xl border border-neutral-200 bg-white p-5 dark:border-zinc-800 dark:bg-zinc-900">
            <h3 className="mb-4 font-semibold text-neutral-800 dark:text-zinc-100">Sources</h3>
            <SourcesSidebar sources={sources} />
          </div>
        )}
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
