"use client";

import React from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ReferenceArea,
  ReferenceLine,
  Brush,
} from "recharts";

export interface TimeSeriesSeries {
  key: string;
  name?: string;
  color?: string;
  /** Line width; defaults to 1.8. */
  strokeWidth?: number;
  /** Line opacity (0–1); defaults to 1. Useful to mute non-highlighted series. */
  opacity?: number;
}

export interface TimeSeriesReferenceArea {
  x1: string;
  x2: string;
  color?: string;
}

export interface TimeSeriesChartProps {
  data: { date: string; [series: string]: number | string | null }[];
  series: TimeSeriesSeries[];
  height?: number;
  yFormatter?: (value: number) => string;
  showBrush?: boolean;
  referenceAreas?: TimeSeriesReferenceArea[];
  baseline?: number;
}

const DEFAULT_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
  "var(--chart-6)",
];

const tooltipContentStyle: React.CSSProperties = {
  background: "var(--surface-overlay)",
  border: "1px solid var(--border)",
  borderRadius: 12,
  color: "var(--text-primary)",
};

/** Token-themed recharts line chart for date-indexed series. */
const TimeSeriesChart: React.FC<TimeSeriesChartProps> = ({
  data,
  series,
  height = 320,
  yFormatter,
  showBrush = false,
  referenceAreas,
  baseline,
}) => {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="var(--grid-line)" vertical={false} />
        <XAxis
          dataKey="date"
          tick={{ fill: "var(--text-muted)", fontSize: 11 }}
          axisLine={{ stroke: "var(--border)" }}
          tickLine={{ stroke: "var(--border)" }}
          minTickGap={40}
        />
        <YAxis
          tick={{ fill: "var(--text-muted)", fontSize: 11 }}
          axisLine={{ stroke: "var(--border)" }}
          tickLine={{ stroke: "var(--border)" }}
          tickFormatter={yFormatter}
          domain={["auto", "auto"]}
          width={56}
        />
        <Tooltip
          contentStyle={tooltipContentStyle}
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
        {referenceAreas?.map((area, i) => (
          <ReferenceArea
            key={`${area.x1}-${area.x2}-${i}`}
            x1={area.x1}
            x2={area.x2}
            fill={area.color ?? "var(--losses)"}
            fillOpacity={0.08}
            strokeOpacity={0}
          />
        ))}
        {baseline !== undefined && (
          <ReferenceLine
            y={baseline}
            stroke="var(--text-muted)"
            strokeDasharray="4 4"
          />
        )}
        {series.map((s, i) => (
          <Line
            key={s.key}
            type="monotone"
            dataKey={s.key}
            name={s.name ?? s.key}
            stroke={s.color ?? DEFAULT_COLORS[i % DEFAULT_COLORS.length]}
            strokeWidth={s.strokeWidth ?? 1.8}
            strokeOpacity={s.opacity ?? 1}
            dot={false}
            connectNulls
          />
        ))}
        {showBrush && (
          <Brush
            dataKey="date"
            height={24}
            stroke="var(--border)"
            fill="var(--surface-raised)"
            travellerWidth={8}
            tickFormatter={() => ""}
          />
        )}
      </LineChart>
    </ResponsiveContainer>
  );
};

export default TimeSeriesChart;
