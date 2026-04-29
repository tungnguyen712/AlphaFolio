"use client";

import {
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { SimDailyPoint } from "@/lib/types";

const COLORS = [
  "#10b981", // emerald
  "#3b82f6", // blue
  "#f59e0b", // amber
  "#8b5cf6", // violet
  "#f43f5e", // rose
  "#06b6d4", // cyan
];

interface Props {
  series: Record<string, SimDailyPoint[]>;
  benchmark: string;
  portfolioSeries?: SimDailyPoint[] | null;
}

interface ChartRow {
  date: string;
  [key: string]: number | string;
}

function buildChartData(
  series: Record<string, SimDailyPoint[]>,
  portfolioSeries: SimDailyPoint[] | null | undefined,
): ChartRow[] {
  const allDates = new Set<string>();
  for (const points of Object.values(series)) {
    points.forEach((p) => allDates.add(p.date));
  }
  const sortedDates = Array.from(allDates).sort();

  const lookup: Record<string, Record<string, number>> = {};
  for (const [ticker, points] of Object.entries(series)) {
    for (const p of points) {
      if (!lookup[p.date]) lookup[p.date] = {};
      lookup[p.date][ticker] = p.cumulative_pct;
    }
  }
  if (portfolioSeries) {
    for (const p of portfolioSeries) {
      if (!lookup[p.date]) lookup[p.date] = {};
      lookup[p.date]["Portfolio"] = p.cumulative_pct;
    }
  }

  return sortedDates.map((date) => ({
    date: date.slice(0, 7), // YYYY-MM label
    ...lookup[date],
  }));
}

function formatPct(value: number) {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

export function MultiLineReturnChart({ series, benchmark, portfolioSeries }: Props) {
  const data = buildChartData(series, portfolioSeries);
  const tickers = Object.keys(series);
  const allKeys = portfolioSeries ? [...tickers, "Portfolio"] : tickers;

  return (
    <ResponsiveContainer width="100%" height={360}>
      <LineChart data={data} margin={{ top: 8, right: 24, left: 8, bottom: 8 }}>
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11, fill: "#71717a" }}
          tickLine={false}
          axisLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          tickFormatter={formatPct}
          tick={{ fontSize: 11, fill: "#71717a" }}
          tickLine={false}
          axisLine={false}
          width={64}
        />
        <Tooltip
          formatter={(value, name) => [formatPct(value as number), name as string]}
          contentStyle={{
            background: "var(--tooltip-bg, #fff)",
            border: "1px solid #e4e4e7",
            borderRadius: 8,
            fontSize: 12,
          }}
        />
        <Legend wrapperStyle={{ fontSize: 12, paddingTop: 12 }} />
        <ReferenceLine y={0} stroke="#d4d4d8" strokeDasharray="4 2" />

        {allKeys.map((key, i) => (
          <Line
            key={key}
            type="monotone"
            dataKey={key}
            stroke={key === "Portfolio" ? "#1d4ed8" : COLORS[i % COLORS.length]}
            strokeWidth={key === "Portfolio" ? 2.5 : key === benchmark ? 2 : 1.5}
            strokeDasharray={key === "Portfolio" ? "6 3" : undefined}
            dot={false}
            activeDot={{ r: 4 }}
            connectNulls
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
