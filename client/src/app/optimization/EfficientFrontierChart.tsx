"use client";

import React, { useMemo } from "react";
import {
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
} from "recharts";
import { EfficientFrontierResponse } from "@/state/api";

interface EfficientFrontierChartProps {
  data: EfficientFrontierResponse;
}

interface FrontierPoint {
  x: number;
  y: number;
  label?: string;
}

const EfficientFrontierChart: React.FC<EfficientFrontierChartProps> = ({
  data,
}) => {
  const { frontierPoints, assetPoints, maxSharpePoint, minVolPoint } =
    useMemo(() => {
      const frontierPoints: FrontierPoint[] = data.frontier_points.map((p) => ({
        x: p.volatility * 100,
        y: p.return * 100,
      }));

      const assetPoints: FrontierPoint[] = Object.entries(data.asset_stats).map(
        ([ticker, stats]) => ({
          x: stats.volatility * 100,
          y: stats.expected_return * 100,
          label: ticker,
        })
      );

      const maxSharpePoint: FrontierPoint[] = [
        {
          x: data.max_sharpe.volatility * 100,
          y: data.max_sharpe.expected_return * 100,
          label: "Max Sharpe",
        },
      ];

      const minVolPoint: FrontierPoint[] = [
        {
          x: data.min_volatility.volatility * 100,
          y: data.min_volatility.expected_return * 100,
          label: "Min Volatility",
        },
      ];

      return { frontierPoints, assetPoints, maxSharpePoint, minVolPoint };
    }, [data]);

  return (
    <div className="card">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
        <h3 className="text-base font-semibold text-ink">효율적 투자선</h3>
        <p className="text-xs text-ink-muted">오른쪽 위일수록 기대수익과 변동성이 함께 큽니다.</p>
      </div>
      <div style={{ height: 400 }}>
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 8, right: 8, bottom: 16, left: 8 }}>
            <CartesianGrid stroke="var(--grid-line)" />
            <XAxis
              type="number"
              dataKey="x"
              name="Volatility"
              unit="%"
              domain={["auto", "auto"]}
              tick={{ fill: "var(--text-muted)", fontSize: 11 }}
              axisLine={{ stroke: "var(--border)" }}
              tickLine={{ stroke: "var(--border)" }}
              label={{
                value: "변동성 (%)",
                position: "insideBottom",
                offset: -8,
                fill: "var(--text-secondary)",
                fontSize: 12,
              }}
            />
            <YAxis
              type="number"
              dataKey="y"
              name="Return"
              unit="%"
              domain={["auto", "auto"]}
              tick={{ fill: "var(--text-muted)", fontSize: 11 }}
              axisLine={{ stroke: "var(--border)" }}
              tickLine={{ stroke: "var(--border)" }}
              label={{
                value: "기대수익률 (%)",
                angle: -90,
                position: "insideLeft",
                fill: "var(--text-secondary)",
                fontSize: 12,
              }}
            />
            <Tooltip
              cursor={{ strokeDasharray: "3 3", stroke: "var(--border-strong)" }}
              contentStyle={{
                background: "var(--surface-overlay)",
                border: "1px solid var(--border)",
                borderRadius: 12,
                color: "var(--text-primary)",
              }}
              formatter={(value, name) => [
                typeof value === "number" ? `${value.toFixed(2)}%` : String(value ?? "—"),
                String(name),
              ]}
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              labelFormatter={(_label: unknown, payload: any) =>
                payload?.[0]?.payload?.label ?? ""
              }
            />
            <Legend
              wrapperStyle={{ fontSize: 12, color: "var(--text-secondary)" }}
              iconSize={8}
            />
            <Scatter
              name="Efficient Frontier"
              data={frontierPoints}
              fill="var(--chart-1)"
              line={{ stroke: "var(--chart-1)", strokeWidth: 1.8 }}
              shape="circle"
            />
            <Scatter
              name="Individual Assets"
              data={assetPoints}
              fill="var(--text-muted)"
            />
            <Scatter
              name="Max Sharpe"
              data={maxSharpePoint}
              fill="var(--gains)"
              shape="diamond"
            />
            <Scatter
              name="Min Volatility"
              data={minVolPoint}
              fill="var(--chart-4)"
              shape="triangle"
            />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-4 text-xs text-ink-muted flex gap-6">
        <span className="flex items-center gap-2">
          <span
            className="w-3 h-3 rotate-45"
            style={{ backgroundColor: "var(--gains)" }}
          ></span>
          Max Sharpe:{" "}
          <span className="num">{data.max_sharpe.sharpe_ratio.toFixed(2)}</span>
        </span>
        <span className="flex items-center gap-2">
          <span
            className="w-0 h-0 border-l-[6px] border-r-[6px] border-b-[10px] border-l-transparent border-r-transparent"
            style={{ borderBottomColor: "var(--chart-4)" }}
          ></span>
          Min Vol:{" "}
          <span className="num">
            {(data.min_volatility.volatility * 100).toFixed(2)}%
          </span>
        </span>
      </div>
    </div>
  );
};

export default EfficientFrontierChart;
