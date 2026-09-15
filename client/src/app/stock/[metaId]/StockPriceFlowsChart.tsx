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
import { formatChartDate, formatDate } from "@/lib/market";

interface StockPriceFlowsChartProps {
  prices: PricePoint[];
  /** KR daily investor flows, in KRW. Missing observations stay null. */
  flows: InsightTickerFlowRow[] | null;
  flowLoading?: boolean;
  flowError?: boolean;
  onRetryFlows?: () => void;
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
  return `${sign}${eok.toLocaleString("ko-KR", { maximumFractionDigits: 1 })}억`;
};

const toEok = (value: number | null | undefined): number | null =>
  value == null || !Number.isFinite(value) ? null : value / 1e8;

/**
 * Stock detail centerpiece: adjusted close as a line (left axis) with daily
 * foreign/institution net buying as sign-colored bars (right axis, KR only).
 * Token styling matches TimeSeriesChart.
 */
const StockPriceFlowsChart: React.FC<StockPriceFlowsChartProps> = ({
  prices,
  flows,
  flowLoading = false,
  flowError = false,
  onRetryFlows,
  showFrgn,
  showInst,
  isKr,
  height = 360,
}) => {
  const data = useMemo<ChartPoint[]>(() => {
    const flowByDate = new Map<string, InsightTickerFlowRow>();
    // Price dates can include T00:00:00; flows use YYYY-MM-DD. These are
    // exchange trading dates, so match their date text without timezone shifts.
    for (const row of flows ?? []) flowByDate.set(row.date.slice(0, 10), row);
    return prices.map((p) => {
      const date = p.trade_date.slice(0, 10);
      const flow = flowByDate.get(date);
      return {
        date,
        price: p.value ?? p.adj_close,
        frgn: toEok(flow?.frgn_net),
        inst: toEok(flow?.inst_net),
      };
    });
  }, [prices, flows]);

  const frgnVisible = isKr && showFrgn && data.some((row) => row.frgn != null);
  const instVisible = isKr && showInst && data.some((row) => row.inst != null);
  const observed = data.filter((row) =>
    (frgnVisible && row.frgn != null) || (instVisible && row.inst != null)
  );
  const latest = observed.at(-1);

  const priceFormatter = (value: number): string =>
    isKr
      ? `${Math.round(value).toLocaleString()}`
      : `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

  const tooltipFormatter = (
    value: unknown,
    name: unknown
  ): [string, string] => {
    const seriesName = String(name ?? "");
    if (typeof value !== "number") return [String(value ?? "—"), seriesName];
    if (seriesName === "종가") {
      const formatted = isKr
        ? `${Math.round(value).toLocaleString()}원`
        : `$${value.toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })}`;
      return [formatted, seriesName];
    }
    // Flow bars are denominated in 억
    return [fmtEokTooltip(value), seriesName];
  };

  return (
    <div className="min-w-0 space-y-3">
      {isKr && <section aria-label="투자자 수급 정보" aria-live="polite" className="space-y-2 text-xs">
        {flowError ? (
          <div role="alert" className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-edge bg-raised px-3 py-2">
            <span className="text-warning">수급 데이터를 불러오지 못했습니다.</span>
            <button type="button" className="btn-secondary" onClick={onRetryFlows}>수급 다시 시도</button>
          </div>
        ) : flowLoading && !flows ? (
          <p className="text-ink-muted">수급 데이터를 불러오는 중…</p>
        ) : !latest ? (
          <p className="text-ink-muted">선택 기간에 제공되는 {showFrgn && showInst ? "외국인·기관" : showFrgn ? "외국인" : "기관"} 수급 데이터가 없습니다.</p>
        ) : null}
        {latest && <>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-ink-secondary">
            <span>최근 수급 · {formatDate(latest.date)}</span>
            {showFrgn && <span>외국인 <strong className="num text-ink">{latest.frgn == null ? "미제공" : fmtEokTooltip(latest.frgn)}</strong></span>}
            {showInst && <span>기관 <strong className="num text-ink">{latest.inst == null ? "미제공" : fmtEokTooltip(latest.inst)}</strong></span>}
          </div>
          <p className="text-ink-muted">
            선: 가격 · 막대: 일별 순매수(억원) · 양수는 순매수, 음수는 순매도
          </p>
          <p className="text-ink-muted">수급 표시 구간 {formatDate(observed[0].date)} ~ {formatDate(latest.date)} · 결측일은 비워 둡니다.</p>
        </>}
      </section>}
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 8, right: 0, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="var(--grid-line)" vertical={false} />
        <XAxis
          dataKey="date"
          tick={{ fill: "var(--text-muted)", fontSize: 11 }}
          axisLine={{ stroke: "var(--border)" }}
          tickLine={{ stroke: "var(--border)" }}
          minTickGap={40}
          tickFormatter={formatChartDate}
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
          labelFormatter={(label) => formatDate(String(label))}
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
    </div>
  );
};

export default StockPriceFlowsChart;
