"use client";

import React, { useState, useMemo } from "react";
import { ArrowLeft, FlaskConical, GitCompareArrows, X } from "lucide-react";
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
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";
import EmptyState from "@/components/ui/EmptyState";

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
  const { data: compareData, isLoading, isError, refetch } = useFetchCompareDataQuery(
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
      <div className="card">
        <EmptyState
          icon={<GitCompareArrows size={28} aria-hidden />}
          title="비교할 종목이 없습니다"
          hint={<button type="button" onClick={onBack} className="mt-3 text-primary-300 underline-offset-4 hover:underline">유니버스로 돌아가기</button>}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header className="grid gap-4 border-b border-edge pb-5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
        <div>
          <button
            type="button"
            onClick={onBack}
            className="mb-3 inline-flex items-center gap-2 text-xs text-ink-muted transition-colors hover:text-ink"
          >
            <ArrowLeft size={14} aria-hidden />
            유니버스로 돌아가기
          </button>
          <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-primary-300">Comparison bench</p>
          <h2 className="mt-1 text-2xl font-semibold tracking-[-0.03em] text-ink">같은 기준으로 비교</h2>
          <p className="mt-1 text-sm text-ink-muted">가격은 100으로 정규화하고 위험·수익 지표의 산출 기간을 통일합니다.</p>
        </div>
        <button
          type="button"
          onClick={handleRunBacktest}
          className="btn-primary inline-flex items-center justify-center gap-2 text-sm"
        >
          <FlaskConical size={16} aria-hidden />
          이 종목들로 백테스트
        </button>
      </header>

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
            <button
              type="button"
              onClick={() => router.push(`/stock/${id}`)}
              className="hover:underline"
              title="종목 상세 보기"
            >
              {tickerMap[id] || `ID:${id}`}
            </button>
            <button
              type="button"
              onClick={() => onRemove(id)}
              className="rounded-full p-0.5 hover:bg-black/10 hover:opacity-70"
              aria-label={`${tickerMap[id] || `ID ${id}`} 비교에서 제거`}
            >
              <X size={14} aria-hidden />
            </button>
          </div>
        ))}
      </div>

      <div className="card">
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-ink-muted">Path comparison</p>
            <h3 className="mt-1 text-base font-semibold text-ink">정규화 가격 · 시작값 100</h3>
          </div>
          <div className="segmented-control" aria-label="비교 기간">
            {PERIOD_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setPeriod(opt.value)}
                aria-pressed={period === opt.value}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <div className="h-80">
          {isError ? (
            <ErrorState message="비교 가격을 불러오지 못했습니다" onRetry={refetch} />
          ) : isLoading ? (
            <LoadingState label="가격 경로를 정규화하는 중..." className="h-full py-0" />
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
                  labelFormatter={(label) =>
                    new Date(String(label ?? "")).toLocaleDateString()
                  }
                  formatter={(value) => [
                    typeof value === "number" ? value.toFixed(1) : String(value ?? "—"),
                    "",
                  ]}
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
            <EmptyState title="비교할 가격 경로가 없습니다" />
          )}
        </div>
      </div>

      <div className="card">
        <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-ink-muted">Risk / return evidence</p>
        <h3 className="mb-4 mt-1 text-base font-semibold text-ink">성과 지표 비교</h3>

        {isError ? (
          <ErrorState message="비교 지표를 불러오지 못했습니다" onRetry={refetch} />
        ) : isLoading ? (
          <LoadingState label="비교 지표를 계산하는 중..." />
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
                      <button
                        type="button"
                        onClick={() => router.push(`/stock/${stock.meta_id}`)}
                        className="hover:underline"
                        title="종목 상세 보기"
                      >
                        {stock.ticker}
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <MetricRow
                  label="1년 수익률"
                  values={compareData.stocks.map((s) => s.metrics.return_1y)}
                  format={formatPercent}
                  highlight="max"
                />
                <MetricRow
                  label="연초 이후"
                  values={compareData.stocks.map((s) => s.metrics.ytd_return)}
                  format={formatPercent}
                  highlight="max"
                />
                <MetricRow
                  label="3개월 수익률"
                  values={compareData.stocks.map((s) => s.metrics.return_3m)}
                  format={formatPercent}
                  highlight="max"
                />
                <MetricRow
                  label="변동성"
                  values={compareData.stocks.map((s) => s.metrics.volatility)}
                  format={formatPercent}
                  highlight="min"
                />
                <MetricRow
                  label="샤프 비율"
                  values={compareData.stocks.map((s) => s.metrics.sharpe)}
                  format={(v) => (v === null ? "—" : v.toFixed(2))}
                  highlight="max"
                />
                <MetricRow
                  label="최대 낙폭"
                  values={compareData.stocks.map((s) => s.metrics.mdd)}
                  format={formatPercent}
                  highlight="max" // Less negative is better
                />
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="비교할 성과 지표가 없습니다" />
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
