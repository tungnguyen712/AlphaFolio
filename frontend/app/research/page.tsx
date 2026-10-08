"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { useReports } from "@/hooks/useResearch";
import { useStartResearchRun } from "@/hooks/useResearch";
import { useRuns } from "@/hooks/useRuns";
import { useApi } from "@/hooks/useApi";
import { EmptyState } from "@/components/ui/EmptyState";
import { Spinner } from "@/components/ui/Spinner";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { Field, inputClass } from "@/components/ui/Field";
import type { ResearchReportSummary, ResearchSignal } from "@/lib/types";

const signalWord: Record<ResearchSignal, string> = { buy: "Buy", hold: "Hold", sell: "Sell" };
const signalText: Record<ResearchSignal, string> = { buy: "text-buy", hold: "text-hold", sell: "text-sell" };

const statusTone: Record<string, "neutral" | "action" | "buy" | "sell"> = {
  queued: "neutral",
  running: "action",
  complete: "buy",
  failed: "sell",
};

const checkboxClass = "h-4 w-4 shrink-0 cursor-pointer accent-[rgb(var(--ink))]";
const shortDate = (s: string) => new Date(s).toLocaleDateString("en-US", { month: "short", day: "numeric" });

function ResearchForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [ticker, setTicker] = useState(searchParams.get("ticker") ?? "");
  const [mode, setMode] = useState<"public" | "pre_ipo">("public");
  const [lookback, setLookback] = useState("90");
  const [historical, setHistorical] = useState(!!searchParams.get("as_of_date"));
  // asOfDate is always YYYY-MM-DD (sent to API); dateDisplay is DD/MM/YYYY (shown to user)
  const initIso = searchParams.get("as_of_date") ?? "";
  const [asOfDate, setAsOfDate] = useState(initIso);
  const [dateDisplay, setDateDisplay] = useState(
    initIso ? initIso.split("-").reverse().join("/") : "",
  );
  const [navigating, setNavigating] = useState(false);
  const { mutate, loading, error } = useStartResearchRun();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ticker.trim()) return;
    const result = await mutate({
      ticker: ticker.trim().toUpperCase(),
      mode,
      lookback_days: parseInt(lookback, 10),
      as_of_date: historical && asOfDate ? asOfDate : null,
    });
    if (result) {
      setNavigating(true);
      router.push(`/research/runs/${result.run_id}`);
    }
  };

  return (
    <section className="grid grid-cols-[minmax(0,1fr)] gap-x-16 gap-y-10 pb-12 pt-4 lg:grid-cols-[minmax(0,1fr)_24rem]">
      <h1 className="text-headline font-semibold">
        Is it <span className="italic">worth holding?</span>
      </h1>

      <form onSubmit={(e) => void handleSubmit(e)} className="self-end">
        <label htmlFor="ticker" className="text-base text-muted">
          Ask about a ticker
        </label>
        <input
          id="ticker"
          type="text"
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          placeholder="AAPL"
          required
          autoComplete="off"
          className="mt-1 w-full border-0 border-b-[3px] border-ink bg-transparent pb-1 font-serif text-[2.5rem] font-semibold uppercase italic leading-tight outline-none placeholder:text-rule focus-visible:outline-none"
        />

        <div className="mt-5 flex flex-wrap items-end gap-x-5 gap-y-4">
          <div role="group" aria-label="Research date" className="inline-flex rounded-sm border border-ink">
            {(["Current", "Historical"] as const).map((label) => (
              <button
                key={label}
                type="button"
                aria-pressed={(label === "Historical") === historical}
                onClick={() => setHistorical(label === "Historical")}
                className={`px-3 py-1.5 text-sm font-semibold ${
                  (label === "Historical") === historical ? "bg-ink text-paper" : "text-ink hover:bg-highlight hover:text-[#111]"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <Field label="Mode">
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as "public" | "pre_ipo")}
              className={`${inputClass} w-auto py-1.5`}
            >
              <option value="public">Public</option>
              <option value="pre_ipo">Pre-IPO</option>
            </select>
          </Field>

          {historical ? (
            <Field label="Research as of">
              <input
                type="text"
                value={dateDisplay}
                onChange={(e) => {
                  // strip non-digits, then auto-insert slashes at positions 2 and 4
                  const digits = e.target.value.replace(/\D/g, "").slice(0, 8);
                  let formatted = digits;
                  if (digits.length > 4) formatted = `${digits.slice(0,2)}/${digits.slice(2,4)}/${digits.slice(4)}`;
                  else if (digits.length > 2) formatted = `${digits.slice(0,2)}/${digits.slice(2)}`;
                  setDateDisplay(formatted);
                  const m = formatted.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
                  setAsOfDate(m ? `${m[3]}-${m[2]}-${m[1]}` : "");
                }}
                placeholder="DD/MM/YYYY"
                maxLength={10}
                required={historical}
                className={`${inputClass} w-36 py-1.5`}
              />
            </Field>
          ) : (
            <Field label={`Lookback: ${lookback} days`}>
              <input
                type="range"
                min="7"
                max="365"
                value={lookback}
                onChange={(e) => setLookback(e.target.value)}
                className="mt-2 w-40 accent-[rgb(var(--ink))]"
              />
            </Field>
          )}
        </div>

        {historical && (
          <p className="mt-4 text-sm text-muted">
            The agents use only data available on that date: Finnhub news archive, SEC filings and yfinance prices.
          </p>
        )}
        {error && (
          <p role="alert" className="mt-3 text-sm text-sell">
            {error}
          </p>
        )}

        <Button type="submit" size="lg" className="mt-6" disabled={loading || navigating || (historical && !asOfDate)}>
          {(loading || navigating) && <Spinner size="sm" />}
          {navigating ? "Starting" : historical ? "Run historical research" : "Start research"}
        </Button>
        <p className="mt-3 text-sm text-muted">The agents take about three minutes.</p>
      </form>
    </section>
  );
}

function SelectBar({
  title,
  selectedCount,
  deleting,
  onDelete,
}: {
  title: string;
  selectedCount: number;
  deleting: boolean;
  onDelete: () => void;
}) {
  return (
    <div className="flex min-h-10 items-end justify-between border-b-[3px] border-ink pb-2">
      <h2 className="text-xl font-semibold">{title}</h2>
      {selectedCount > 0 && (
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted">{selectedCount} selected</span>
          <Button variant="danger" onClick={onDelete} disabled={deleting} className="h-8 px-3">
            {deleting ? "Deleting" : "Delete selected"}
          </Button>
        </div>
      )}
    </div>
  );
}

function Leader() {
  return <span className="mx-3 min-w-4 flex-1 border-b-2 border-dotted border-ink/40" aria-hidden />;
}

function RecentRuns() {
  const { data: runs, loading, refetch } = useRuns({ flow: "research", limit: 5 });
  const api = useApi();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [deleting, setDeleting] = useState(false);

  if (loading) return <Spinner />;
  if (runs.length === 0) return null;

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const toggleAll = () =>
    setSelected(selected.size === runs.length ? new Set() : new Set(runs.map((r) => r.id)));

  const handleDelete = async () => {
    if (deleting || selected.size === 0) return;
    setDeleting(true);
    try {
      await api.del("/runs", { ids: Array.from(selected) });
      setSelected(new Set());
      await refetch();
    } finally {
      setDeleting(false);
    }
  };

  return (
    <section className="mt-12">
      <SelectBar title="Runs in progress and recent" selectedCount={selected.size} deleting={deleting} onDelete={handleDelete} />
      <ul>
        {runs.map((run) => (
          <li key={run.id} className="flex items-center gap-3 border-b border-rule">
            <input
              type="checkbox"
              checked={selected.has(run.id)}
              onChange={() => toggle(run.id)}
              className={checkboxClass}
              aria-label={`Select ${run.ticker ?? "run"}`}
            />
            <Link href={`/research/runs/${run.id}`} className="flex min-w-0 flex-1 items-baseline py-3 hover:bg-highlight/30">
              <span className="font-serif text-xl font-semibold">{run.ticker ?? "Run"}</span>
              <Leader />
              <Chip tone={statusTone[run.status] ?? "neutral"}>{run.status}</Chip>
              <span className="ml-4 hidden w-16 text-right text-sm text-muted sm:inline-block">
                {run.started_at ? shortDate(run.started_at) : ""}
              </span>
            </Link>
          </li>
        ))}
      </ul>
      {runs.length > 1 && (
        <button onClick={toggleAll} className="mt-3 text-sm text-muted hover:text-ink">
          {selected.size === runs.length ? "Deselect all" : "Select all"}
        </button>
      )}
    </section>
  );
}

function ReportsList({
  reports,
  refetch,
}: {
  reports: ResearchReportSummary[];
  refetch: () => Promise<void>;
}) {
  const api = useApi();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [deleting, setDeleting] = useState(false);

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const toggleAll = () =>
    setSelected(selected.size === reports.length ? new Set() : new Set(reports.map((r) => r.id)));

  const handleDelete = async () => {
    if (deleting || selected.size === 0) return;
    setDeleting(true);
    try {
      await api.del("/research/reports", { ids: Array.from(selected) });
      setSelected(new Set());
      await refetch();
    } finally {
      setDeleting(false);
    }
  };

  return (
    <section>
      <SelectBar title="Latest verdicts" selectedCount={selected.size} deleting={deleting} onDelete={handleDelete} />
      <ul>
        {reports.map((r) => (
          <li key={r.id} className="flex items-center gap-3 border-b border-rule">
            <input
              type="checkbox"
              checked={selected.has(r.id)}
              onChange={() => toggle(r.id)}
              className={checkboxClass}
              aria-label={`Select ${r.ticker}`}
            />
            <Link href={`/research/reports/${r.id}`} className="flex min-w-0 flex-1 items-baseline py-3.5 hover:bg-highlight/30">
              <span className="font-serif text-2xl font-semibold tracking-tight">{r.ticker}</span>
              <Leader />
              <span className={`mr-5 font-serif text-xl italic ${signalText[r.signal]}`}>{signalWord[r.signal]}</span>
              <span className="w-9 text-right text-lg font-semibold">{Math.round(r.confidence * 100)}</span>
              <span className="ml-4 hidden w-16 text-right text-sm text-muted sm:inline-block">{shortDate(r.created_at)}</span>
            </Link>
          </li>
        ))}
      </ul>
      {reports.length > 1 && (
        <button onClick={toggleAll} className="mt-3 text-sm text-muted hover:text-ink">
          {selected.size === reports.length ? "Deselect all" : "Select all"}
        </button>
      )}
      <p className="mt-6 text-sm text-muted">Confidence is out of 100. Select a ticker to read the full note.</p>
    </section>
  );
}

function ResearchBody() {
  const { data: reports, loading, refetch } = useReports({ limit: 20 });
  const latest = reports[0];

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <Spinner />
      </div>
    );
  }

  return (
    <section className="grid grid-cols-[minmax(0,1fr)] gap-x-16 gap-y-12 border-t-4 border-ink py-12 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
      <div>
        {latest ? (
          <>
            <p className="text-base text-muted">From your latest report, {shortDate(latest.created_at)}</p>
            <p className={`font-serif text-verdict font-semibold italic ${signalText[latest.signal]}`}>
              {signalWord[latest.signal]}
            </p>
            <p className="mt-6 flex items-baseline gap-4">
              <span className="font-serif text-3xl font-semibold">{latest.ticker}</span>
              <span className="text-lg text-muted">confidence {Math.round(latest.confidence * 100)} out of 100</span>
            </p>
            <Link href={`/research/reports/${latest.id}`} className="mt-4 inline-block text-lg font-semibold text-action">
              Read the full note
            </Link>
          </>
        ) : (
          <EmptyState
            title="No reports yet"
            description="Enter a ticker above and start research. Finished reports are filed here, newest first."
          />
        )}
      </div>

      <div>
        {reports.length > 0 && <ReportsList reports={reports} refetch={refetch} />}
        <RecentRuns />
      </div>
    </section>
  );
}

export default function ResearchPage() {
  return (
    <div>
      <Suspense>
        <ResearchForm />
      </Suspense>
      <ResearchBody />
    </div>
  );
}
