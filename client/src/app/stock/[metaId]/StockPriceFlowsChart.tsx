"use client";

import React, { useMemo } from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Bar,
  Cell,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
} from "recharts";

import { InsightTickerFlowRow, PricePoint } from "@/state/api";
import { fmtEokAxis } from "../../insight/format";

interface StockPriceFlowsChartProps {
  prices: PricePoint[];
  /** KR daily investor flows; null/empty hides the bar layer (US stocks). */
  flows: InsightTickerFlowRow[] | null;
  showFrgn: boolean;
  showInst: boolean;
  isKr: boolean;
  height?: number;
}

interface ChartPoint {
  date: string;
  price: number | null;
  /** Daily net buys in 억 (KRW / 1e8). */
  frgn: number | null;
  inst: number | null;
}

const tooltipContentStyle: React.CSSProperties = {
  background: "var(--surface-overlay)",
  border: "1px solid var(--border)",
  borderRadius: 12,
  color: "var(--text-primary)",
};

const fmtEokTooltip = (eok: number): string => {
  const sign = eok > 0 ? "+" : "";
  return `${sign}${Math.round(eok).toLocaleString()}억`;
};

/**
 * Stock detail centerpiece: adjusted close as a line (left axis) with daily
 * foreign/institution net buying as sign-colored bars (right axis, KR only).
 * Token styling matches TimeSeriesChart.
 */
const StockPriceFlowsChart: React.FC<StockPriceFlowsChartProps> = ({
  prices,
  flows,
  showFrgn,
  showInst,
  isKr,
  height = 360,
}) => {
  const hasFlows = isKr && !!flows && flows.length > 0;
  const frgnVisible = hasFlows && showFrgn;
  const instVisible = hasFlows && showInst;

  const data = useMemo<ChartPoint[]>(() => {
    const flowByDate = new Map<string, InsightTickerFlowRow>();
    for (const row of flows ?? []) flowByDate.set(row.date, row);
    return prices.map((p) => {
      const flow = flowByDate.get(p.trade_date);
      return {
        date: p.trade_date,
        price: p.adj_close,
        frgn: flow ? flow.frgn_net / 1e8 : null,
        inst: flow ? flow.inst_net / 1e8 : null,
      };
    });
  }, [prices, flows]);

  const priceFormatter = (value: number): string =>
    isKr
      ? `${Math.round(value).toLocaleString()}`
      : `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

  const tooltipFormatter = (
    value: number | string,
    name: string
  ): [string, string] => {
    if (typeof value !== "number") return [String(value), name];
    if (name === "종가") {
      const formatted = isKr
        ? `${Math.round(value).toLocaleString()}원`
        : `$${value.toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })}`;
      return [formatted, name];
    }
    // Flow bars are denominated in 억
    return [fmtEokTooltip(value), name];
  };

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 8, right: 0, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="var(--grid-line)" vertical={false} />
        <XAxis
          dataKey="date"
          tick={{ fill: "var(--text-muted)", fontSize: 11 }}
          axisLine={{ stroke: "var(--border)" }}
          tickLine={{ stroke: "var(--border)" }}
          minTickGap={40}
        />
        <YAxis
          yAxisId="price"
          orientation="left"
          domain={["auto", "auto"]}
          tick={{ fill: "var(--text-muted)", fontSize: 11 }}
          axisLine={{ stroke: "var(--border)" }}
          tickLine={{ stroke: "var(--border)" }}
          tickFormatter={priceFormatter}
          width={64}
        />
        {(frgnVisible || instVisible) && (
          <YAxis
            yAxisId="flows"
            orientation="right"
            tick={{ fill: "var(--text-muted)", fontSize: 11 }}
            axisLine={{ stroke: "var(--border)" }}
            tickLine={{ stroke: "var(--border)" }}
            tickFormatter={fmtEokAxis}
            width={56}
          />
        )}
        <Tooltip
          contentStyle={tooltipContentStyle}
          labelStyle={{ color: "var(--text-secondary)" }}
          formatter={tooltipFormatter}
        />
        {(frgnVisible || instVisible) && (
          <ReferenceLine
            yAxisId="flows"
            y={0}
            stroke="var(--text-muted)"
            strokeDasharray="4 4"
          />
        )}
        {frgnVisible && (
          <Bar
            yAxisId="flows"
            dataKey="frgn"
            name="외국인 순매수"
            fillOpacity={0.5}
            isAnimationActive={false}
          >
            {data.map((d) => (
              <Cell
                key={`frgn-${d.date}`}
                fill={(d.frgn ?? 0) >= 0 ? "var(--gains)" : "var(--losses)"}
              />
            ))}
          </Bar>
        )}
        {instVisible && (
          <Bar
            yAxisId="flows"
            dataKey="inst"
            name="기관 순매수"
            fillOpacity={0.3}
            isAnimationActive={false}
          >
            {data.map((d) => (
              <Cell
                key={`inst-${d.date}`}
                fill={(d.inst ?? 0) >= 0 ? "var(--gains)" : "var(--losses)"}
              />
            ))}
          </Bar>
        )}
        <Line
          yAxisId="price"
          type="monotone"
          dataKey="price"
          name="종가"
          stroke="var(--chart-1)"
          strokeWidth={1.8}
          dot={false}
          connectNulls
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
};

export default StockPriceFlowsChart;
