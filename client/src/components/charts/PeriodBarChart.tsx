"use client";

import React from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
} from "recharts";

export interface PeriodBarSeries {
  key: string;
  name?: string;
  color?: string;
}

export interface PeriodBarChartProps {
  data: { label: string; [series: string]: number | string }[];
  series: PeriodBarSeries[];
  height?: number;
  yFormatter?: (value: number) => string;
}

const DEFAULT_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
  "var(--chart-6)",
];

/** Token-themed recharts bar chart for periodic (monthly/yearly) values. */
const PeriodBarChart: React.FC<PeriodBarChartProps> = ({
  data,
  series,
  height = 320,
  yFormatter,
}) => {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="var(--grid-line)" vertical={false} />
        <XAxis
          dataKey="label"
          tick={{ fill: "var(--text-muted)", fontSize: 11 }}
          axisLine={{ stroke: "var(--border)" }}
          tickLine={{ stroke: "var(--border)" }}
          minTickGap={20}
        />
        <YAxis
          tick={{ fill: "var(--text-muted)", fontSize: 11 }}
          axisLine={{ stroke: "var(--border)" }}
          tickLine={{ stroke: "var(--border)" }}
          tickFormatter={yFormatter}
          width={56}
        />
        <Tooltip
          cursor={{ fill: "var(--grid-line)" }}
          contentStyle={{
            background: "var(--surface-overlay)",
            border: "1px solid var(--border)",
            borderRadius: 12,
            color: "var(--text-primary)",
          }}
          labelStyle={{ color: "var(--text-secondary)" }}
          formatter={(value: number | string) =>
            typeof value === "number"
              ? yFormatter
                ? yFormatter(value)
                : value.toLocaleString(undefined, { maximumFractionDigits: 2 })
              : value
          }
        />
        {series.length > 1 && (
          <Legend
            wrapperStyle={{ fontSize: 12, color: "var(--text-secondary)" }}
            iconType="circle"
            iconSize={8}
          />
        )}
        {series.map((s, i) => (
          <Bar
            key={s.key}
            dataKey={s.key}
            name={s.name ?? s.key}
            fill={s.color ?? DEFAULT_COLORS[i % DEFAULT_COLORS.length]}
            radius={[3, 3, 0, 0]}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
};

export default PeriodBarChart;
