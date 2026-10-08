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
import { axisTick, chartColor, labelStyle, tooltipStyle } from "@/lib/chartTheme";

interface BarItem {
  name: string;
  value: number;
}

interface SectorBarProps {
  data: BarItem[];
}

function fmt(v: number) {
  return v.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

export function SectorBar({ data }: SectorBarProps) {
  if (data.length === 0) {
    return (
      <div className="flex h-20 items-center justify-center text-base text-muted">
        The price provider returned no sector for these holdings
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
          tick={axisTick}
          width={160}
        />
        <Tooltip
          formatter={(v) => [fmt(v as number), "Cost basis"]}
          contentStyle={tooltipStyle}
        />
        <Bar dataKey="value" radius={[0, 4, 4, 0]}>
          {data.map((_, i) => (
            <Cell key={i} fill={chartColor(i)} />
          ))}
          <LabelList
            dataKey="value"
            position="right"
            formatter={(v: unknown) => fmt(v as number)}
            style={labelStyle}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
