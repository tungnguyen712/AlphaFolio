import type { ResearchSignal, VerdictLayer } from "@/lib/types";

interface VerdictCardProps {
  layers: VerdictLayer;
  signal?: ResearchSignal;
  ticker?: string;
}

function signalFromVerdict(verdict: string): ResearchSignal {
  const word = verdict.split(" ")[0]?.toUpperCase();
  if (word === "BUY") return "buy";
  if (word === "SELL") return "sell";
  return "hold";
}

const badgeClasses: Record<ResearchSignal, string> = {
  buy: "bg-emerald-100 text-emerald-800 ring-emerald-200 dark:bg-emerald-950 dark:text-emerald-300 dark:ring-emerald-800",
  hold: "bg-amber-100 text-amber-800 ring-amber-200 dark:bg-amber-950 dark:text-amber-300 dark:ring-amber-800",
  sell: "bg-red-100 text-red-800 ring-red-200 dark:bg-red-950 dark:text-red-300 dark:ring-red-800",
};

const barClasses: Record<ResearchSignal, string> = {
  buy: "bg-emerald-500",
  hold: "bg-amber-500",
  sell: "bg-red-500",
};

export function VerdictCard({ layers, signal, ticker }: VerdictCardProps) {
  const resolvedSignal = signal ?? signalFromVerdict(layers.verdict);
  const confidencePct = Math.round(layers.confidence * 100);

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-900">
      <div className="flex items-start justify-between gap-6">
        <div className="flex-1">
          {ticker && (
            <p className="mb-1 text-sm font-semibold uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
              {ticker}
            </p>
          )}
          <div className="flex items-center gap-3">
            <span
              className={`inline-flex rounded-full px-4 py-1.5 text-base font-bold ring-1 ring-inset ${badgeClasses[resolvedSignal]}`}
            >
              {resolvedSignal.toUpperCase()}
            </span>
            <p className="text-lg font-semibold text-zinc-800 dark:text-zinc-100">{layers.verdict}</p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <span className="font-mono text-xl font-bold text-zinc-700 dark:text-zinc-200">
            {confidencePct}%
          </span>
          <div className="h-2 w-24 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-700">
            <div
              className={`h-full rounded-full ${barClasses[resolvedSignal]}`}
              style={{ width: `${confidencePct}%` }}
            />
          </div>
          <span className="text-xs text-zinc-400 dark:text-zinc-500">confidence</span>
        </div>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
            Top signals
          </p>
          <ul className="space-y-2">
            {layers.top_3_signals.map((sig, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-zinc-700 dark:text-zinc-300">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-zinc-400 dark:bg-zinc-500" />
                {sig}
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 dark:border-amber-800 dark:bg-amber-950/40">
          <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-amber-700 dark:text-amber-400">
            ⚠ Key uncertainty
          </p>
          <p className="text-sm text-amber-800 dark:text-amber-200">{layers.key_uncertainty}</p>
        </div>
      </div>
    </div>
  );
}
