"use client";

import React, { useState, useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

import { useFetchPriceHistoryQuery, useFetchPriceSummaryQuery } from "@/state/api";
import { MetaRow } from "./types";

interface StockDetailPanelProps {
  stock: MetaRow | null;
  onClose: () => void;
  onAddToCompare: (metaId: number) => void;
}

type Period = "1m" | "3m" | "6m" | "1y" | "all";

const PERIOD_OPTIONS: { value: Period; label: string; days: number }[] = [
  { value: "1m", label: "1M", days: 30 },
  { value: "3m", label: "3M", days: 90 },
  { value: "6m", label: "6M", days: 180 },
  { value: "1y", label: "1Y", days: 365 },
  { value: "all", label: "ALL", days: 365 * 5 },
];

const formatPercent = (value: number | null): string => {
  if (value === null) return "—";
  const sign = value >= 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(1)}%`;
};

const formatPrice = (value: number | null): string => {
  if (value === null) return "—";
  return `$${value.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
};

const formatMarketCap = (value: number | null): string => {
  if (value === null) return "—";
  if (value >= 1e12) return `$${(value / 1e12).toFixed(1)}T`;
  if (value >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
  if (value >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  return `$${value.toLocaleString()}`;
};

const StockDetailPanel: React.FC<StockDetailPanelProps> = ({
  stock,
  onClose,
  onAddToCompare,
}) => {
  const [period, setPeriod] = useState<Period>("1y");

  // Calculate date range based on period
  const dateRange = useMemo(() => {
    const endDate = new Date();
    const periodDays =
      PERIOD_OPTIONS.find((p) => p.value === period)?.days || 365;
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - periodDays);

    return {
      startDate: startDate.toISOString().split("T")[0],
      endDate: endDate.toISOString().split("T")[0],
    };
  }, [period]);

  // Fetch price history
  const { data: priceData, isLoading: priceLoading } = useFetchPriceHistoryQuery(
    {
      metaId: stock?.meta_id || 0,
      startDate: dateRange.startDate,
      endDate: dateRange.endDate,
    },
    { skip: !stock }
  );

  // Fetch summary metrics
  const { data: summaryData, isLoading: summaryLoading } =
    useFetchPriceSummaryQuery(stock?.meta_id || 0, { skip: !stock });

  // Format chart data
  const chartData = useMemo(() => {
    if (!priceData?.prices) return [];
    return priceData.prices.map((p) => ({
      date: p.trade_date,
      price: p.adj_close,
    }));
  }, [priceData]);

  if (!stock) return null;

  const isLoading = priceLoading || summaryLoading;
  const metrics = summaryData?.metrics;

  return (
    <div className="fixed inset-y-0 right-0 w-[400px] bg-white shadow-2xl z-50 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-neutral-200">
        <div>
          <h2 className="text-lg font-semibold text-neutral-900">
            {stock.ticker}
          </h2>
          <p className="text-sm text-neutral-500">{stock.name}</p>
        </div>
        <button
          onClick={onClose}
          className="p-2 hover:bg-neutral-100 rounded-lg transition-colors"
        >
          <svg
            className="w-5 h-5 text-neutral-500"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {/* Price Chart */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-neutral-700">Price Chart</h3>
            <div className="flex gap-1">
              {PERIOD_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setPeriod(opt.value)}
                  className={`px-2 py-1 text-xs font-medium rounded ${
                    period === opt.value
                      ? "bg-primary-500 text-white"
                      : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          <div className="h-48 bg-neutral-50 rounded-lg p-2">
            {isLoading ? (
              <div className="h-full flex items-center justify-center text-neutral-400">
                Loading...
              </div>
            ) : chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 10 }}
                    tickFormatter={(val) => {
                      const d = new Date(val);
                      return `${d.getMonth() + 1}/${d.getDate()}`;
                    }}
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    domain={["auto", "auto"]}
                    tick={{ fontSize: 10 }}
                    width={50}
                    tickFormatter={(val) => `$${val.toFixed(0)}`}
                  />
                  <Tooltip
                    formatter={(value: number) => [formatPrice(value), "Price"]}
                    labelFormatter={(label) => new Date(label).toLocaleDateString()}
                  />
                  <Line
                    type="monotone"
                    dataKey="price"
                    stroke="#3b82f6"
                    strokeWidth={1.5}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-neutral-400">
                No price data available
              </div>
            )}
          </div>
        </div>

        {/* Key Metrics */}
        <div>
          <h3 className="text-sm font-medium text-neutral-700 mb-3">
            Performance Metrics
          </h3>
          <div className="grid grid-cols-3 gap-3">
            <MetricCard
              label="YTD"
              value={formatPercent(metrics?.ytd_return ?? null)}
              isPositive={metrics?.ytd_return ? metrics.ytd_return >= 0 : null}
            />
            <MetricCard
              label="1Y Return"
              value={formatPercent(metrics?.return_1y ?? null)}
              isPositive={metrics?.return_1y ? metrics.return_1y >= 0 : null}
            />
            <MetricCard
              label="3M Return"
              value={formatPercent(metrics?.return_3m ?? null)}
              isPositive={metrics?.return_3m ? metrics.return_3m >= 0 : null}
            />
            <MetricCard
              label="Volatility"
              value={formatPercent(metrics?.volatility ?? null)}
            />
            <MetricCard
              label="Sharpe"
              value={metrics?.sharpe?.toFixed(2) ?? "—"}
            />
            <MetricCard
              label="Max DD"
              value={formatPercent(metrics?.mdd ?? null)}
              isPositive={false}
            />
          </div>
        </div>

        {/* Stock Info */}
        <div>
          <h3 className="text-sm font-medium text-neutral-700 mb-3">
            Stock Information
          </h3>
          <div className="space-y-2 text-sm">
            <InfoRow label="Sector" value={stock.sector || "—"} />
            <InfoRow label="Market" value={stock.iso_code} />
            <InfoRow label="Type" value={stock.security_type} />
            <InfoRow label="Market Cap" value={formatMarketCap(stock.marketcap)} />
            {summaryData?.latest_price && (
              <InfoRow
                label="Latest Price"
                value={formatPrice(summaryData.latest_price)}
              />
            )}
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="p-4 border-t border-neutral-200 space-y-2">
        <button
          onClick={() => onAddToCompare(stock.meta_id)}
          className="w-full py-2 px-4 bg-primary-500 text-white font-medium rounded-lg
                     hover:bg-primary-600 transition-colors"
        >
          Add to Compare
        </button>
      </div>
    </div>
  );
};

// Helper components
interface MetricCardProps {
  label: string;
  value: string;
  isPositive?: boolean | null;
}

const MetricCard: React.FC<MetricCardProps> = ({ label, value, isPositive }) => {
  let textColor = "text-neutral-900";
  if (isPositive === true) textColor = "text-green-600";
  if (isPositive === false) textColor = "text-red-600";

  return (
    <div className="bg-neutral-50 rounded-lg p-3">
      <p className="text-xs text-neutral-500 mb-1">{label}</p>
      <p className={`text-sm font-semibold ${textColor}`}>{value}</p>
    </div>
  );
};

interface InfoRowProps {
  label: string;
  value: string;
}

const InfoRow: React.FC<InfoRowProps> = ({ label, value }) => (
  <div className="flex justify-between">
    <span className="text-neutral-500">{label}</span>
    <span className="text-neutral-900 font-medium">{value}</span>
  </div>
);

export default StockDetailPanel;
