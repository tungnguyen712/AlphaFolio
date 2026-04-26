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
  buy: "bg-green-100 text-green-800 ring-green-200",
  hold: "bg-yellow-100 text-yellow-800 ring-yellow-200",
  sell: "bg-red-100 text-red-800 ring-red-200",
};

const barClasses: Record<ResearchSignal, string> = {
  buy: "bg-green-500",
  hold: "bg-yellow-500",
  sell: "bg-red-500",
};

export function VerdictCard({ layers, signal, ticker }: VerdictCardProps) {
  const resolvedSignal = signal ?? signalFromVerdict(layers.verdict);
  const confidencePct = Math.round(layers.confidence * 100);

  return (
    <div className="rounded-xl border border-neutral-200 bg-white p-6 shadow-sm">
      <div className="flex items-start justify-between gap-6">
        <div className="flex-1">
          {ticker && (
            <p className="mb-1 text-sm font-semibold uppercase tracking-wider text-neutral-400">
              {ticker}
            </p>
          )}
          <div className="flex items-center gap-3">
            <span
              className={`inline-flex rounded-full px-4 py-1.5 text-base font-bold ring-1 ring-inset ${badgeClasses[resolvedSignal]}`}
            >
              {resolvedSignal.toUpperCase()}
            </span>
            <p className="text-lg font-semibold text-neutral-800">{layers.verdict}</p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <span className="text-xl font-bold text-neutral-700">{confidencePct}%</span>
          <div className="h-2 w-24 overflow-hidden rounded-full bg-neutral-200">
            <div
              className={`h-full rounded-full ${barClasses[resolvedSignal]}`}
              style={{ width: `${confidencePct}%` }}
            />
          </div>
          <span className="text-xs text-neutral-400">confidence</span>
        </div>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-neutral-500">
            Top signals
          </p>
          <ul className="space-y-2">
            {layers.top_3_signals.map((signal, i) => (
              <li key={i} className="flex items-start gap-2 text-base text-neutral-700">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-neutral-400" />
                {signal}
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-md border border-yellow-200 bg-yellow-50 p-4">
          <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-yellow-700">
            ⚠ Key uncertainty
          </p>
          <p className="text-base text-yellow-800">{layers.key_uncertainty}</p>
        </div>
      </div>
    </div>
  );
}
