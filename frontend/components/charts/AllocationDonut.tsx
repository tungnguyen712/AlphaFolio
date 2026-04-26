"use client";

import {
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

const PALETTE = [
  "#0ea5e9", // sky-500
  "#8b5cf6", // violet-500
  "#10b981", // emerald-500
  "#f59e0b", // amber-500
  "#f43f5e", // rose-500
  "#6366f1", // indigo-500
  "#14b8a6", // teal-500
  "#f97316", // orange-500
];

interface Slice {
  name: string;
  value: number;
}

interface AllocationDonutProps {
  data: Slice[];
  totalLabel?: string;
}

function fmt(v: number) {
  return v.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function fmtPct(v: number, total: number) {
  return total > 0 ? ((v / total) * 100).toFixed(1) + "%" : "0%";
}

export function AllocationDonut({ data, totalLabel }: AllocationDonutProps) {
  const total = data.reduce((s, d) => s + d.value, 0);

  if (data.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center text-sm text-zinc-400 dark:text-zinc-500">
        No holdings to chart
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={240}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={60}
          outerRadius={90}
          paddingAngle={2}
          dataKey="value"
        >
          {data.map((_, i) => (
            <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
          ))}
        </Pie>
        <Tooltip
          formatter={(value, name) => [
            `${fmt(value as number)} (${fmtPct(value as number, total)})`,
            name as string,
          ]}
          contentStyle={{
            borderRadius: "8px",
            border: "1px solid #3f3f46",
            backgroundColor: "#18181b",
            color: "#f4f4f5",
            fontSize: "12px",
          }}
        />
        <Legend
          iconType="circle"
          iconSize={8}
          formatter={(value) => (
            <span style={{ fontSize: "12px", color: "#71717a" }}>{value}</span>
          )}
        />
        {totalLabel && (
          <text
            x="50%"
            y="50%"
            textAnchor="middle"
            dominantBaseline="middle"
            style={{ fontSize: "13px", fontWeight: 600, fill: "#71717a", fontFamily: "monospace" }}
          >
            {totalLabel}
          </text>
        )}
      </PieChart>
    </ResponsiveContainer>
  );
}
