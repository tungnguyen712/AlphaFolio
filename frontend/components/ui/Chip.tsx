import type { ReactNode } from "react";

type Tone = "neutral" | "buy" | "hold" | "sell" | "action";

const tones: Record<Tone, string> = {
  neutral: "bg-rule text-ink",
  buy: "bg-buy-soft text-buy",
  hold: "bg-hold-soft text-hold",
  sell: "bg-sell-soft text-sell",
  action: "bg-highlight text-[#111]",
};

export function Chip({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center rounded-sm px-2 py-0.5 text-sm font-semibold ${tones[tone]}`}>
      {children}
    </span>
  );
}
