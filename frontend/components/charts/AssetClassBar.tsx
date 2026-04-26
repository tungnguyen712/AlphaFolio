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

interface AssetClassBarProps {
  data: BarItem[];
}

const COLOR_MAP: Record<string, string> = {
  ipo: "#0ea5e9",
  established: "#10b981",
};

function fmt(v: number) {
  return v.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

export function AssetClassBar({ data }: AssetClassBarProps) {
  if (data.length === 0) {
    return (
      <div className="flex h-32 items-center justify-center text-sm text-zinc-400 dark:text-zinc-500">
        No data
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
          tick={{ fontSize: 12, fill: "#71717a" }}
          width={90}
          tickFormatter={(v: string) => v.charAt(0).toUpperCase() + v.slice(1)}
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
          {data.map((entry, i) => (
            <Cell key={i} fill={COLOR_MAP[entry.name.toLowerCase()] ?? "#6366f1"} />
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
