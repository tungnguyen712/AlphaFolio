/** Display formatting. Missing values are handled by the caller (omit them or write a plain sentence), never printed as "n/a". */

export function formatPrice(n: number): string {
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function formatMarketCap(n: number): string {
  if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(0)}M`;
  return `$${n.toLocaleString("en-US")}`;
}

export function formatMultiple(n: number): string {
  return `${n.toFixed(1)}x`;
}

export function formatSignedPct(n: number): string {
  return `${n > 0 ? "+" : ""}${n.toFixed(1)}%`;
}

export function formatMoneyShort(n: number): string {
  return n >= 1_000_000 ? `$${(n / 1_000_000).toFixed(1)}M` : `$${n.toLocaleString("en-US")}`;
}

/** Plain names for the valuation fields the backend may report as missing. */
const MISSING_FIELD_NAMES: Record<string, string> = {
  market_cap: "market cap",
  forward_pe: "P/E ratio",
  ev_revenue: "EV/revenue",
  "52w range": "52-week range",
};

/** "market cap, P/E ratio and EV/revenue" from the backend's field names. */
export function describeMissingFields(fields: string[]): string {
  const names = fields.map((f) => MISSING_FIELD_NAMES[f] ?? f.replace(/_/g, " "));
  if (names.length <= 1) return names.join("");
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}
