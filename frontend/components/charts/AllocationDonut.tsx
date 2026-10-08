"use client";

import {
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { chartColor, tooltipStyle } from "@/lib/chartTheme";

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
      <div className="flex h-48 items-center justify-center text-base text-muted">
        Add holdings to see the allocation
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
          paddingAngle={1}
          dataKey="value"
        >
          {data.map((_, i) => (
            <Cell key={i} fill={chartColor(i)} stroke="rgb(var(--surface))" />
          ))}
        </Pie>
        <Tooltip
          formatter={(value, name) => [
            `${fmt(value as number)} (${fmtPct(value as number, total)})`,
            name as string,
          ]}
          contentStyle={tooltipStyle}
        />
        <Legend
          iconType="circle"
          iconSize={8}
          formatter={(value) => (
            <span style={{ fontSize: "13px", color: "rgb(var(--muted))" }}>{value}</span>
          )}
        />
        {totalLabel && (
          <text
            x="50%"
            y="50%"
            textAnchor="middle"
            dominantBaseline="middle"
            style={{ fontSize: "15px", fontWeight: 600, fill: "rgb(var(--ink))" }}
          >
            {totalLabel}
          </text>
        )}
      </PieChart>
    </ResponsiveContainer>
  );
}
