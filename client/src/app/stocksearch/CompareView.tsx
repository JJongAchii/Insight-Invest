"use client";

import React, { useState, useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { useRouter } from "next/navigation";

import { useFetchCompareDataQuery, useFetchMetaDataQuery } from "@/state/api";

interface CompareViewProps {
  selectedIds: number[];
  onBack: () => void;
  onRemove: (metaId: number) => void;
}

type Period = "1m" | "3m" | "6m" | "1y" | "all";

const PERIOD_OPTIONS: { value: Period; label: string }[] = [
  { value: "1m", label: "1M" },
  { value: "3m", label: "3M" },
  { value: "6m", label: "6M" },
  { value: "1y", label: "1Y" },
  { value: "all", label: "ALL" },
];

const CHART_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
];

const formatPercent = (value: number | null): string => {
  if (value === null) return "—";
  const sign = value >= 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(1)}%`;
};

const CompareView: React.FC<CompareViewProps> = ({
  selectedIds,
  onBack,
  onRemove,
}) => {
  const router = useRouter();
  const [period, setPeriod] = useState<Period>("1y");

  // Get meta data for ticker names
  const { data: metaData } = useFetchMetaDataQuery({});

  // Fetch comparison data
  const metaIdsString = selectedIds.join(",");
  const { data: compareData, isLoading } = useFetchCompareDataQuery(
    { metaIds: metaIdsString, period },
    { skip: selectedIds.length === 0 }
  );

  // Get ticker names from meta data
  const tickerMap = useMemo(() => {
    if (!metaData) return {};
    return (metaData as { meta_id: number; ticker: string }[]).reduce(
      (acc, item) => {
        acc[item.meta_id] = item.ticker;
        return acc;
      },
      {} as Record<number, string>
    );
  }, [metaData]);

  // Get tickers for chart lines
  const tickers = useMemo(() => {
    return selectedIds.map((id) => tickerMap[id] || `ID:${id}`);
  }, [selectedIds, tickerMap]);

  const handleRunBacktest = () => {
    // Navigate to backtest page with selected stocks
    const metaIdParams = selectedIds.join(",");
    router.push(`/backtest/simulation?meta_ids=${metaIdParams}`);
  };

  if (selectedIds.length === 0) {
    return (
      <div className="card text-center py-12">
        <p className="text-ink-muted">Select stocks to compare</p>
        <button
          onClick={onBack}
          className="mt-4 text-primary-500 hover:underline"
        >
          Back to list
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={onBack}
            className="flex items-center gap-2 text-ink-secondary hover:text-ink"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 19l-7-7 7-7"
              />
            </svg>
            Back
          </button>
          <h2 className="text-xl font-semibold text-ink">
            Compare Stocks
          </h2>
        </div>
        <button
          onClick={handleRunBacktest}
          className="px-4 py-2 bg-primary-500 text-white font-medium rounded-lg
                     hover:bg-primary-600 transition-colors"
        >
          Run Backtest
        </button>
      </div>

      {/* Selected Stocks Chips */}
      <div className="flex flex-wrap gap-2">
        {selectedIds.map((id, index) => (
          <div
            key={id}
            className="flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium"
            style={{
              backgroundColor: `color-mix(in srgb, ${CHART_COLORS[index % CHART_COLORS.length]} 12%, transparent)`,
              color: CHART_COLORS[index % CHART_COLORS.length],
            }}
          >
            <span
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: CHART_COLORS[index % CHART_COLORS.length] }}
            />
            {tickerMap[id] || `ID:${id}`}
            <button
              onClick={() => onRemove(id)}
              className="hover:opacity-70"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        ))}
      </div>

      {/* Normalized Price Chart */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold text-ink">
            Normalized Price (Base = 100)
          </h3>
          <div className="flex gap-1">
            {PERIOD_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setPeriod(opt.value)}
                className={`px-3 py-1.5 text-sm font-medium rounded ${
                  period === opt.value
                    ? "bg-primary-500 text-white"
                    : "bg-raised text-ink-secondary hover:bg-overlay"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <div className="h-80">
          {isLoading ? (
            <div className="h-full flex items-center justify-center text-ink-muted">
              Loading...
            </div>
          ) : compareData?.normalized_prices &&
            compareData.normalized_prices.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={compareData.normalized_prices}>
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11, fill: "var(--text-muted)" }}
                  axisLine={{ stroke: "var(--border)" }}
                  tickLine={{ stroke: "var(--border)" }}
                  tickFormatter={(val) => {
                    const d = new Date(val);
                    return `${d.getMonth() + 1}/${d.getDate()}`;
                  }}
                  interval="preserveStartEnd"
                />
                <YAxis
                  domain={["auto", "auto"]}
                  tick={{ fontSize: 11, fill: "var(--text-muted)" }}
                  axisLine={{ stroke: "var(--border)" }}
                  tickLine={{ stroke: "var(--border)" }}
                  width={50}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--surface-overlay)",
                    border: "1px solid var(--border)",
                    borderRadius: 12,
                    color: "var(--text-primary)",
                  }}
                  labelStyle={{ color: "var(--text-secondary)" }}
                  labelFormatter={(label) => new Date(label).toLocaleDateString()}
                  formatter={(value: number) => [value.toFixed(1), ""]}
                />
                <Legend />
                {tickers.map((ticker, index) => (
                  <Line
                    key={ticker}
                    type="monotone"
                    dataKey={ticker}
                    stroke={CHART_COLORS[index % CHART_COLORS.length]}
                    strokeWidth={2}
                    dot={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-full flex items-center justify-center text-ink-muted">
              No price data available
            </div>
          )}
        </div>
      </div>

      {/* Metrics Comparison Table */}
      <div className="card">
        <h3 className="text-base font-semibold text-ink mb-4">
          Performance Comparison
        </h3>

        {isLoading ? (
          <div className="py-8 text-center text-ink-muted">Loading...</div>
        ) : compareData?.stocks && compareData.stocks.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-edge">
                  <th className="text-left py-3 px-4 font-medium text-ink-muted">
                    Metric
                  </th>
                  {compareData.stocks.map((stock, index) => (
                    <th
                      key={stock.meta_id}
                      className="text-right py-3 px-4 font-medium"
                      style={{ color: CHART_COLORS[index % CHART_COLORS.length] }}
                    >
                      {stock.ticker}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <MetricRow
                  label="1Y Return"
                  values={compareData.stocks.map((s) => s.metrics.return_1y)}
                  format={formatPercent}
                  highlight="max"
                />
                <MetricRow
                  label="YTD Return"
                  values={compareData.stocks.map((s) => s.metrics.ytd_return)}
                  format={formatPercent}
                  highlight="max"
                />
                <MetricRow
                  label="3M Return"
                  values={compareData.stocks.map((s) => s.metrics.return_3m)}
                  format={formatPercent}
                  highlight="max"
                />
                <MetricRow
                  label="Volatility"
                  values={compareData.stocks.map((s) => s.metrics.volatility)}
                  format={formatPercent}
                  highlight="min"
                />
                <MetricRow
                  label="Sharpe Ratio"
                  values={compareData.stocks.map((s) => s.metrics.sharpe)}
                  format={(v) => (v === null ? "—" : v.toFixed(2))}
                  highlight="max"
                />
                <MetricRow
                  label="Max Drawdown"
                  values={compareData.stocks.map((s) => s.metrics.mdd)}
                  format={formatPercent}
                  highlight="max" // Less negative is better
                />
              </tbody>
            </table>
          </div>
        ) : (
          <div className="py-8 text-center text-ink-muted">
            No data available
          </div>
        )}
      </div>
    </div>
  );
};

// Helper component for metric rows
interface MetricRowProps {
  label: string;
  values: (number | null)[];
  format: (value: number | null) => string;
  highlight?: "max" | "min";
}

const MetricRow: React.FC<MetricRowProps> = ({
  label,
  values,
  format,
  highlight,
}) => {
  // Find best value index
  const validValues = values.map((v, i) => ({ value: v, index: i })).filter((x) => x.value !== null);
  let bestIndex = -1;

  if (highlight && validValues.length > 0) {
    if (highlight === "max") {
      bestIndex = validValues.reduce((best, curr) =>
        (curr.value ?? -Infinity) > (best.value ?? -Infinity) ? curr : best
      ).index;
    } else {
      bestIndex = validValues.reduce((best, curr) =>
        (curr.value ?? Infinity) < (best.value ?? Infinity) ? curr : best
      ).index;
    }
  }

  return (
    <tr className="border-b border-edge">
      <td className="py-3 px-4 text-ink-secondary">{label}</td>
      {values.map((value, index) => (
        <td
          key={index}
          className={`py-3 px-4 text-right font-medium ${
            index === bestIndex
              ? "text-primary-400 bg-primary-500/10"
              : "text-ink"
          }`}
        >
          {format(value)}
        </td>
      ))}
    </tr>
  );
};

export default CompareView;
