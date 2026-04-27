import type { RunStepOut } from "@/lib/types";

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

const directionClasses: Record<string, string> = {
  bullish: "bg-green-50 border-green-200 text-green-800 dark:bg-green-950 dark:border-green-800 dark:text-green-200",
  bearish: "bg-red-50 border-red-200 text-red-800 dark:bg-red-950 dark:border-red-800 dark:text-red-200",
  neutral: "bg-neutral-50 border-neutral-200 text-neutral-700 dark:bg-zinc-800 dark:border-zinc-700 dark:text-zinc-200",
};

const labelClasses: Record<string, string> = {
  bullish: "text-green-700 bg-green-100 dark:text-green-300 dark:bg-green-950",
  bearish: "text-red-700 bg-red-100 dark:text-red-300 dark:bg-red-950",
  neutral: "text-neutral-600 bg-neutral-100 dark:text-zinc-300 dark:bg-zinc-800",
};

function SignalSection({
  items,
  dir,
}: {
  items: (Signal & { idx: number })[];
  dir: string;
}) {
  if (!items.length) return null;
  const label = dir === "bullish" ? "Bullish" : dir === "bearish" ? "Bearish" : "Neutral";
  return (
    <div>
      <p className={`mb-2 inline-flex rounded px-2 py-0.5 text-xs font-bold uppercase tracking-wider ${labelClasses[dir]}`}>
        {label} ({items.length})
      </p>
      <ol className="space-y-2">
        {items.map((sig) => (
          <li key={sig.idx} className={`rounded-lg border p-3 ${directionClasses[dir]}`}>
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="shrink-0 text-xs font-bold opacity-50">#{sig.idx}</span>
                <span className="text-sm font-semibold">{sig.name.replace(/_/g, " ")}</span>
              </div>
              <div className="flex shrink-0 items-center gap-1">
                <div className="h-1.5 w-12 overflow-hidden rounded-full bg-black/10 dark:bg-white/10">
                  <div
                    className="h-full rounded-full bg-current opacity-50"
                    style={{ width: `${Math.round(sig.strength * 100)}%` }}
                  />
                </div>
                <span className="text-[10px] font-medium opacity-60">
                  {Math.round(sig.strength * 100)}%
                </span>
              </div>
            </div>
            <p className="mt-1.5 text-sm leading-snug opacity-90">{sig.rationale}</p>
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
    <div className="rounded-xl border border-neutral-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
      <h3 className="mb-4 font-semibold text-neutral-800 dark:text-zinc-100">
        Signal breakdown{" "}
        <span className="text-sm font-normal text-neutral-400 dark:text-zinc-500">
          — numbered references in the rationale point here
        </span>
      </h3>
      <div className="space-y-5">
        <SignalSection items={bearish} dir="bearish" />
        <SignalSection items={bullish} dir="bullish" />
        <SignalSection items={neutral} dir="neutral" />
      </div>
    </div>
  );
}
