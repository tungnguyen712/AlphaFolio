import type { InsiderSummary, ScenarioCase, ValuationBridge } from "@/lib/types";
import {
  describeMissingFields,
  formatMarketCap,
  formatMoneyShort,
  formatMultiple,
  formatPrice,
  formatSignedPct,
} from "@/lib/format";
import { noEmDash } from "@/lib/text";

const scenarioText: Record<string, string> = { bull: "text-buy", base: "text-ink", bear: "text-sell" };
const scenarioDot: Record<string, string> = { bull: "bg-buy", base: "bg-ink", bear: "bg-sell" };
const scenarioName: Record<string, string> = { bull: "Bull case", base: "Base case", bear: "Bear case" };

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-rule py-2">
      <dt className="text-base text-muted">{label}</dt>
      <dd className="font-serif text-lg font-semibold text-ink">{value}</dd>
    </div>
  );
}

function Valuation({ bridge, ticker }: { bridge: ValuationBridge; ticker: string }) {
  // Only show what we actually have. Missing values are explained once, in plain words, below.
  const facts: { label: string; value: string }[] = [];
  if (bridge.current_price != null) facts.push({ label: "Current price", value: formatPrice(bridge.current_price) });
  if (bridge.market_cap != null) facts.push({ label: "Market cap", value: formatMarketCap(bridge.market_cap) });
  if (bridge.forward_pe != null) facts.push({ label: "Forward P/E", value: formatMultiple(bridge.forward_pe) });
  if (bridge.ev_revenue != null) facts.push({ label: "EV/revenue", value: formatMultiple(bridge.ev_revenue) });

  const scenarios = bridge.scenarios.filter((s: ScenarioCase) => s.price_target != null);
  if (facts.length === 0 && scenarios.length === 0) return null;

  const valuationGaps = bridge.missing_fields.filter((f) => ["market_cap", "forward_pe", "ev_revenue"].includes(f));

  const prices = [...scenarios.map((s) => s.price_target as number), ...(bridge.current_price != null ? [bridge.current_price] : [])];
  const lo = Math.min(...prices);
  const hi = Math.max(...prices);
  const pos = (n: number) => (hi === lo ? 50 : 5 + ((n - lo) / (hi - lo)) * 90);

  return (
    <section>
      <h2 className="mb-3 border-b-[3px] border-ink pb-2 text-xl font-semibold">Valuation</h2>
      {facts.length > 0 && <dl>{facts.map((f) => <Fact key={f.label} {...f} />)}</dl>}

      {valuationGaps.length > 0 && (
        <p className="mt-3 text-sm text-muted">
          We could not get the {describeMissingFields(valuationGaps)} for {ticker}, so this view relies on the price scenarios.
        </p>
      )}

      {scenarios.length > 0 && (
        <div className="mt-6">
          {scenarios.length > 1 && (
            <div className="relative mb-9 h-8" aria-hidden="true">
              <div className="absolute left-0 right-0 top-1/2 h-px bg-ink/40" />
              {bridge.current_price != null && (
                <div className="absolute top-0 h-full w-px bg-ink" style={{ left: `${pos(bridge.current_price)}%` }}>
                  <span className="absolute -bottom-5 left-1/2 -translate-x-1/2 whitespace-nowrap text-sm text-muted">Today</span>
                </div>
              )}
              {scenarios.map((s) => (
                <span
                  key={s.label}
                  className={`absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full ${scenarioDot[s.label]}`}
                  style={{ left: `${pos(s.price_target as number)}%` }}
                />
              ))}
            </div>
          )}
          <ul className="space-y-4">
            {scenarios.map((s) => (
              <li key={s.label} className="border-l-[3px] border-ink pl-4">
                <p className="flex items-baseline gap-3">
                  <span className={`font-serif text-lg font-semibold ${scenarioText[s.label]}`}>{scenarioName[s.label]}</span>
                  <span className="font-serif text-xl font-semibold">{formatPrice(s.price_target as number)}</span>
                  {s.implied_upside_pct != null && (
                    <span className={`text-base font-medium ${scenarioText[s.label]}`}>{formatSignedPct(s.implied_upside_pct)}</span>
                  )}
                </p>
                {s.key_assumption && <p className="mt-0.5 text-sm text-muted">{noEmDash(s.key_assumption)}</p>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

function Insiders({ summary }: { summary: InsiderSummary }) {
  if (summary.raw_transaction_count === 0) return null;
  const facts: { label: string; value: string }[] = [];
  if (summary.unique_sellers > 0) {
    const execs = summary.csuite_sellers > 0 ? ` (${summary.csuite_sellers} ${summary.csuite_sellers === 1 ? "executive" : "executives"})` : "";
    facts.push({ label: "Insiders who sold", value: `${summary.unique_sellers}${execs}` });
  }
  if (summary.total_sales_value > 0) facts.push({ label: "Total sold", value: formatMoneyShort(summary.total_sales_value) });
  facts.push({
    label: "Insiders who bought",
    value: summary.unique_buyers > 0 ? `${summary.unique_buyers}` : "None",
  });
  if (summary.total_purchase_value > 0) facts.push({ label: "Total bought", value: formatMoneyShort(summary.total_purchase_value) });

  return (
    <section>
      <h2 className="mb-3 border-b-[3px] border-ink pb-2 text-xl font-semibold">Insider activity</h2>
      <dl>{facts.map((f) => <Fact key={f.label} {...f} />)}</dl>
    </section>
  );
}

/** Side column next to the analysis: the figures behind the call, only the ones we have. */
export function ByTheNumbers({
  ticker,
  bridge,
  insiders,
}: {
  ticker: string;
  bridge?: ValuationBridge | null;
  insiders?: InsiderSummary | null;
}) {
  const hasInsiders = insiders != null && insiders.raw_transaction_count > 0;
  if (!bridge && !hasInsiders) return null;
  return (
    <aside className="space-y-10 lg:sticky lg:top-40 lg:self-start">
      {bridge && <Valuation bridge={bridge} ticker={ticker} />}
      {insiders && <Insiders summary={insiders} />}
    </aside>
  );
}
