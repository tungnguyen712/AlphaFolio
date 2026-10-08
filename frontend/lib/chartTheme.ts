import type { CSSProperties } from "react";

/** Ordered series colors, driven by CSS variables so they follow light/dark mode. */
export const CHART_COLORS = [1, 2, 3, 4, 5].map((n) => `rgb(var(--chart-${n}))`);

export const chartColor = (i: number) => CHART_COLORS[i % CHART_COLORS.length];

export const axisTick = { fontSize: 13, fill: "rgb(var(--muted))" };

export const tooltipStyle: CSSProperties = {
  borderRadius: 8,
  border: "1px solid rgb(var(--rule))",
  backgroundColor: "rgb(var(--surface))",
  color: "rgb(var(--ink))",
  fontSize: 13,
  boxShadow: "0 4px 16px rgb(0 0 0 / 0.12)",
};

export const labelStyle: CSSProperties = { fontSize: 13, fill: "rgb(var(--muted))" };
