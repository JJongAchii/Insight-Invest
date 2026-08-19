"use client";

import React, { useState, useMemo } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
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
import InfoTip from "@/components/ui/InfoTip";
import WatchlistStar from "@/components/ui/WatchlistStar";
import { fmtEok, fmtJo } from "../insight/format";
import {
  formatChartDate,
  formatDate,
  formatMarketCap,
  formatPrice,
} from "@/lib/market";

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
  const isKr = stock.iso_code === "KR";
  const mktcap = summaryData?.mktcap ?? stock.marketcap ?? null;
  const flows = summaryData?.flows_recent ?? null;

  return (
    <aside
      aria-label={`${stock.name || stock.ticker} 상세 정보`}
      className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[400px] flex-col bg-surface shadow-2xl"
    >
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-edge">
        <div className="flex items-center gap-1">
          <div>
            <h2 className="text-lg font-semibold text-ink">
              {stock.ticker}
            </h2>
            <p className="text-sm text-ink-muted">{stock.name}</p>
          </div>
          <WatchlistStar metaId={stock.meta_id} size={18} />
        </div>
        <div className="flex items-center gap-1">
          <Link
            href={`/stock/${stock.meta_id}`}
            className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium
                       rounded-lg bg-raised text-ink-secondary hover:bg-overlay
                       hover:text-ink transition-colors"
          >
            전체 보기
            <ArrowRight size={12} aria-hidden />
          </Link>
          <button
            onClick={onClose}
            className="p-2 hover:bg-raised rounded-lg transition-colors"
            aria-label="상세 패널 닫기"
          >
            <svg
              className="w-5 h-5 text-ink-muted"
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
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {/* Top meta tiles: market cap & traded value */}
        <div className="grid grid-cols-2 gap-3">
          <MetricCard
            label="시가총액"
            value={isKr ? fmtJo(mktcap) : formatMarketCap(mktcap, stock.iso_code)}
          />
          <MetricCard
            label={isKr ? "거래대금" : "최근 가격"}
            value={isKr
              ? summaryData?.value != null
                ? fmtJo(summaryData.value)
                : "—"
              : formatPrice(summaryData?.latest_price, stock.iso_code)}
          />
        </div>

        {/* Price Chart */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-ink-secondary">Price Chart</h3>
            <div className="flex gap-1">
              {PERIOD_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setPeriod(opt.value)}
                  className={`px-2 py-1 text-xs font-medium rounded ${
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

          <div className="h-48 bg-raised rounded-lg p-2">
            {isLoading ? (
              <div className="h-full flex items-center justify-center text-ink-muted">
                가격을 불러오는 중...
              </div>
            ) : chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 10, fill: "var(--text-muted)" }}
                    axisLine={{ stroke: "var(--border)" }}
                    tickLine={{ stroke: "var(--border)" }}
                    tickFormatter={formatChartDate}
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    domain={["auto", "auto"]}
                    tick={{ fontSize: 10, fill: "var(--text-muted)" }}
                    axisLine={{ stroke: "var(--border)" }}
                    tickLine={{ stroke: "var(--border)" }}
                    width={50}
                    tickFormatter={(val) =>
                      isKr ? `${Math.round(val).toLocaleString("ko-KR")}` : `$${val.toFixed(0)}`
                    }
                  />
                  <Tooltip
                    contentStyle={{
                      background: "var(--surface-overlay)",
                      border: "1px solid var(--border)",
                      borderRadius: 12,
                      color: "var(--text-primary)",
                    }}
                    labelStyle={{ color: "var(--text-secondary)" }}
                    formatter={(value: number) => [formatPrice(value, stock.iso_code), "가격"]}
                    labelFormatter={(label) => formatDate(String(label))}
                  />
                  <Line
                    type="monotone"
                    dataKey="price"
                    stroke="var(--chart-1)"
                    strokeWidth={1.5}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center text-ink-muted">
                표시할 가격 데이터가 없습니다
              </div>
            )}
          </div>
        </div>

        {/* Key Metrics */}
        <div>
          <h3 className="text-sm font-medium text-ink-secondary mb-3">
            성과 지표
          </h3>
          <div className="grid grid-cols-3 gap-3">
            <MetricCard
              label="YTD"
              value={formatPercent(metrics?.ytd_return ?? null)}
              isPositive={metrics?.ytd_return != null ? metrics.ytd_return >= 0 : null}
            />
            <MetricCard
              label="1년 수익률"
              value={formatPercent(metrics?.return_1y ?? null)}
              isPositive={metrics?.return_1y != null ? metrics.return_1y >= 0 : null}
            />
            <MetricCard
              label="3개월 수익률"
              value={formatPercent(metrics?.return_3m ?? null)}
              isPositive={metrics?.return_3m != null ? metrics.return_3m >= 0 : null}
            />
            <MetricCard
              label="변동성"
              value={formatPercent(metrics?.volatility ?? null)}
            />
            <MetricCard
              label="샤프"
              value={metrics?.sharpe?.toFixed(2) ?? "—"}
            />
            <MetricCard
              label="최대 낙폭"
              value={formatPercent(metrics?.mdd ?? null)}
              isPositive={false}
            />
          </div>
        </div>

        {/* Valuation */}
        {(summaryData?.per != null || summaryData?.pbr != null || summaryData?.div != null) && <div>
          <h3 className="text-sm font-medium text-ink-secondary mb-3">
            밸류에이션
          </h3>
          <div className="grid grid-cols-3 gap-3">
            <MetricCard
              label="PER"
              value={summaryData?.per != null ? summaryData.per.toFixed(2) : "—"}
            />
            <MetricCard
              label="PBR"
              value={summaryData?.pbr != null ? summaryData.pbr.toFixed(2) : "—"}
            />
            <MetricCard
              label="배당수익률"
              value={
                summaryData?.div != null
                  ? `${summaryData.div.toFixed(2)}%`
                  : "—"
              }
            />
          </div>
        </div>}

        {/* Recent investor flows (KR only) */}
        {flows && (
          <div>
            <h3 className="text-sm font-medium text-ink-secondary mb-3 flex items-center gap-1">
              최근 수급 (20일)
              <InfoTip helpKey="signal.intensity" />
            </h3>
            <div className="space-y-2 text-sm bg-raised rounded-lg p-3">
              <div className="flex justify-between">
                <span className="text-ink-muted">외국인 20일 순매수</span>
                <span
                  className={`num font-medium ${
                    flows.frgn_net_20d > 0
                      ? "text-gains"
                      : flows.frgn_net_20d < 0
                        ? "text-losses"
                        : "text-ink"
                  }`}
                >
                  {fmtEok(flows.frgn_net_20d)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-muted">기관 20일 순매수</span>
                <span
                  className={`num font-medium ${
                    flows.inst_net_20d > 0
                      ? "text-gains"
                      : flows.inst_net_20d < 0
                        ? "text-losses"
                        : "text-ink"
                  }`}
                >
                  {fmtEok(flows.inst_net_20d)}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Stock Info */}
        <div>
          <h3 className="text-sm font-medium text-ink-secondary mb-3">
            종목 정보
          </h3>
          <div className="space-y-2 text-sm">
            <InfoRow label="섹터" value={stock.sector || "—"} />
            <InfoRow label="시장" value={stock.iso_code} />
            <InfoRow label="유형" value={stock.security_type} />
            <InfoRow label="시가총액" value={formatMarketCap(stock.marketcap, stock.iso_code)} />
            {summaryData?.latest_price && (
              <InfoRow
                label="최근 가격"
                value={formatPrice(summaryData.latest_price, stock.iso_code)}
              />
            )}
            {summaryData?.latest_date && (
              <InfoRow label="가격 기준일" value={formatDate(summaryData.latest_date)} />
            )}
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="p-4 border-t border-edge space-y-2">
        <button
          onClick={() => onAddToCompare(stock.meta_id)}
          className="w-full py-2 px-4 bg-primary-500 text-white font-medium rounded-lg
                     hover:bg-primary-600 transition-colors"
        >
          비교 목록에 추가
        </button>
      </div>
    </aside>
  );
};

// Helper components
interface MetricCardProps {
  label: string;
  value: string;
  isPositive?: boolean | null;
}

const MetricCard: React.FC<MetricCardProps> = ({ label, value, isPositive }) => {
  let textColor = "text-ink";
  if (isPositive === true) textColor = "text-gains";
  if (isPositive === false) textColor = "text-losses";

  return (
    <div className="bg-raised rounded-lg p-3">
      <p className="text-xs text-ink-muted mb-1">{label}</p>
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
    <span className="text-ink-muted">{label}</span>
    <span className="text-ink font-medium">{value}</span>
  </div>
);

export default StockDetailPanel;
