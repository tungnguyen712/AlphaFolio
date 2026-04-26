"use client";

import {
  Bar,
  BarChart,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface BarItem {
  name: string;
  value: number;
}

interface SectorBarProps {
  data: BarItem[];
}

const SECTOR_COLORS = [
  "#0ea5e9", "#8b5cf6", "#10b981", "#f59e0b",
  "#f43f5e", "#6366f1", "#14b8a6", "#f97316",
];

function fmt(v: number) {
  return v.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

export function SectorBar({ data }: SectorBarProps) {
  if (data.length === 0) {
    return (
      <div className="flex h-20 items-center justify-center text-xs text-zinc-400 dark:text-zinc-500">
        Sector data unavailable — set POLYGON_API_KEY to enable
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={Math.max(80, data.length * 44)}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 48, top: 4, bottom: 4 }}>
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="name"
          tick={{ fontSize: 11, fill: "#71717a" }}
          width={160}
        />
        <Tooltip
          formatter={(v) => [fmt(v as number), "Cost basis"]}
          contentStyle={{
            borderRadius: "8px",
            border: "1px solid #3f3f46",
            backgroundColor: "#18181b",
            color: "#f4f4f5",
            fontSize: "12px",
          }}
        />
        <Bar dataKey="value" radius={[0, 4, 4, 0]}>
          {data.map((_, i) => (
            <Cell key={i} fill={SECTOR_COLORS[i % SECTOR_COLORS.length]} />
          ))}
          <LabelList
            dataKey="value"
            position="right"
            formatter={(v: unknown) => fmt(v as number)}
            style={{ fontSize: "11px", fill: "#71717a", fontFamily: "monospace" }}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
