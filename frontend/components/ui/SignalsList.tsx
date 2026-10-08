import type { RunStepOut } from "@/lib/types";
import { noEmDash } from "@/lib/text";

interface Signal {
  name: string;
  direction: "bullish" | "bearish" | "neutral";
  strength: number;
  rationale: string;
}

function parseSignals(steps: RunStepOut[]): Signal[] {
  const step = steps.find((s) => s.agent_name === "signal_analysis");
  if (!step?.output) return [];
  const signals = (step.output as Record<string, unknown>).signals;
  if (!Array.isArray(signals)) return [];
  return signals as Signal[];
}

const tone: Record<string, { text: string; bar: string; label: string }> = {
  bullish: { text: "text-buy", bar: "bg-buy", label: "Bullish" },
  bearish: { text: "text-sell", bar: "bg-sell", label: "Bearish" },
  neutral: { text: "text-muted", bar: "bg-muted", label: "Neutral" },
};

function SignalSection({ items, dir }: { items: (Signal & { idx: number })[]; dir: string }) {
  if (!items.length) return null;
  const t = tone[dir];
  return (
    <div>
      <h3 className={`mb-1 font-serif text-lg font-semibold ${t.text}`}>
        {t.label} ({items.length})
      </h3>
      <ol className="divide-y divide-rule">
        {items.map((sig) => (
          <li key={sig.idx} className="py-3">
            <div className="flex items-baseline justify-between gap-4">
              <p className="text-base font-medium text-ink">
                <span className="mr-2 tabular-nums text-muted">#{sig.idx}</span>
                {sig.name.replace(/_/g, " ")}
              </p>
              <div className="flex shrink-0 items-center gap-2">
                <div className="h-1.5 w-16 overflow-hidden rounded-sm bg-rule">
                  <div className={`h-full ${t.bar}`} style={{ width: `${Math.round(sig.strength * 100)}%` }} />
                </div>
                <span className="w-9 text-right text-sm tabular-nums text-muted">
                  {Math.round(sig.strength * 100)}%
                </span>
              </div>
            </div>
            <p className="mt-1 max-w-reading text-base text-muted">{noEmDash(sig.rationale)}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}

interface Props {
  steps: RunStepOut[];
}

export function SignalsList({ steps }: Props) {
  const signals = parseSignals(steps);
  if (!signals.length) return null;

  const withIdx = signals.map((s, i) => ({ ...s, idx: i + 1 }));
  const bullish = withIdx.filter((s) => s.direction === "bullish");
  const bearish = withIdx.filter((s) => s.direction === "bearish");
  const neutral = withIdx.filter((s) => s.direction === "neutral");

  return (
    <section>
      <h2 className="text-xl font-semibold text-ink">Signal breakdown</h2>
      <p className="mb-4 text-base text-muted">The numbered references in the rationale point here.</p>
      <div className="space-y-6">
        <SignalSection items={bearish} dir="bearish" />
        <SignalSection items={bullish} dir="bullish" />
        <SignalSection items={neutral} dir="neutral" />
      </div>
    </section>
  );
}
