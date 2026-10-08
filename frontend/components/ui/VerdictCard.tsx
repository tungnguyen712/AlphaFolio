import type { ResearchSignal, VerdictLayer } from "@/lib/types";
import { noEmDash } from "@/lib/text";

interface VerdictCardProps {
  layers: VerdictLayer;
  signal?: ResearchSignal;
  ticker?: string;
  /** Validation-gate penalty (0..1) already subtracted from layers.confidence; shown as dashed dots. */
  confidencePenalty?: number;
}

function signalFromVerdict(verdict: string): ResearchSignal {
  const word = verdict.split(" ")[0]?.toUpperCase();
  if (word === "BUY") return "buy";
  if (word === "SELL") return "sell";
  return "hold";
}

/** The verdict text often starts with the call itself ("HOLD: ..."); the big word already says it. */
function verdictSentence(verdict: string): string {
  const rest = verdict.replace(/^(BUY|HOLD|SELL)\s*[:,.\-—]?\s*/i, "") || verdict;
  return rest.charAt(0).toUpperCase() + rest.slice(1);
}

const wordClass: Record<ResearchSignal, string> = {
  buy: "text-buy",
  hold: "text-hold",
  sell: "text-sell",
};

const ringClass: Record<ResearchSignal, string> = {
  buy: "border-buy",
  hold: "border-hold",
  sell: "border-sell",
};

const signalLabel: Record<ResearchSignal, string> = { buy: "Buy", hold: "Hold", sell: "Sell" };

/**
 * Confidence as 100 dots: filled = confidence, dashed = points removed by the validation gate.
 * The dots fill in once on load (the page's single orchestrated motion).
 */
export function DotGauge({
  confidence,
  penalty = 0,
  signal,
}: {
  confidence: number;
  penalty?: number;
  signal: ResearchSignal;
}) {
  const pct = Math.round(confidence * 100);
  const penaltyPct = Math.min(Math.round(penalty * 100), 100 - pct);
  return (
    <div
      role="img"
      aria-label={`Confidence ${pct} out of 100${penaltyPct > 0 ? `, ${penaltyPct} points taken off because some data was missing` : ""}`}
      className="grid w-max grid-cols-10 gap-[5px]"
    >
      {Array.from({ length: 100 }).map((_, i) => (
        <span
          key={i}
          style={{ animationDelay: `${i * 7}ms` }}
          className={`dot-in h-[11px] w-[11px] rounded-full ${
            i < pct
              ? "bg-ink"
              : i < pct + penaltyPct
                ? `border-2 border-dashed ${ringClass[signal]}`
                : "bg-rule"
          }`}
        />
      ))}
    </div>
  );
}

export function VerdictCard({ layers, signal, ticker, confidencePenalty = 0 }: VerdictCardProps) {
  const resolvedSignal = signal ?? signalFromVerdict(layers.verdict);
  const confidencePct = Math.round(layers.confidence * 100);
  const penaltyPct = Math.round(confidencePenalty * 100);
  const target = layers.entry_price_target ?? layers.exit_price_target;
  const isEntry = !!layers.entry_price_target;

  return (
    <article>
      <div className="grid grid-cols-[minmax(0,1fr)] gap-x-16 gap-y-10 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <div className="min-w-0">
          <p className="text-base text-muted">{ticker ? `${ticker}, the verdict` : "The verdict"}</p>
          <p className={`font-serif text-verdict font-semibold italic ${wordClass[resolvedSignal]}`}>
            {signalLabel[resolvedSignal]}
          </p>
          <p className="mt-6 max-w-2xl font-serif text-[1.7rem] leading-[1.2] tracking-tight">
            {"“"}
            {noEmDash(verdictSentence(layers.verdict))}
            {"”"}
          </p>
        </div>

        <div className="flex flex-col justify-end gap-8">
          <div className="flex flex-wrap items-center gap-8">
            <DotGauge confidence={layers.confidence} penalty={confidencePenalty} signal={resolvedSignal} />
            <div>
              <p className="font-serif text-3xl font-semibold leading-none">{confidencePct}</p>
              <p className="mt-1 max-w-[14rem] text-sm text-muted">
                confidence, out of 100
                {penaltyPct > 0 && `. The dashed dots are ${penaltyPct} points taken off because some data was missing.`}
              </p>
            </div>
          </div>

          {target && (
            <div className="border-l-[3px] border-highlight pl-5">
              <p className="text-sm text-muted">
                {isEntry ? "Entry target" : "Exit target"}, {target.horizon}
              </p>
              <p className="font-serif text-2xl font-semibold leading-none">${target.price.toFixed(2)}</p>
              <p className="mt-2 whitespace-pre-wrap text-base text-ink">{noEmDash(target.rationale)}</p>
            </div>
          )}
        </div>
      </div>

      <section className="mt-14">
        <h2 className="mb-5 text-xl font-semibold">What drove it</h2>
        <div className="grid gap-x-10 gap-y-6 md:grid-cols-3">
          {layers.top_3_signals.map((sig, i) => (
            <p key={i} className="border-t-[3px] border-ink pt-4 font-serif text-[1.2rem] leading-[1.35]">
              {noEmDash(sig)}
            </p>
          ))}
        </div>
      </section>

      <section className="mt-12 border-y-[3px] border-double border-ink py-7">
        <h2 className="text-xl font-semibold">Watch out for</h2>
        <p className="mt-2 max-w-3xl font-serif text-[1.35rem] leading-[1.35]">{noEmDash(layers.key_uncertainty)}</p>
      </section>
    </article>
  );
}
