"use client";

import React, { useMemo, useState } from "react";
import { InsightMarket, useFetchInsightValuationQuery } from "@/state/api";
import Card from "@/components/ui/Card";
import StatTile from "@/components/ui/StatTile";
import InfoTip from "@/components/ui/InfoTip";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";
import EmptyState from "@/components/ui/EmptyState";
import TimeSeriesChart from "@/components/charts/TimeSeriesChart";
import { Segmented } from "./format";

const MARKET_OPTIONS: { id: InsightMarket; label: string }[] = [
  { id: "KOSPI", label: "KOSPI" },
  { id: "KOSDAQ", label: "KOSDAQ" },
];

type ValuationMetric = "pbr" | "per";

const METRIC_OPTIONS: { id: ValuationMetric; label: string }[] = [
  { id: "pbr", label: "PBR" },
  { id: "per", label: "PER" },
];

const fmtRatio = (v: number | null | undefined): string =>
  v === null || v === undefined || Number.isNaN(v) ? "—" : v.toFixed(2);

const fmtCoverage = (v: number | null | undefined): string =>
  v === null || v === undefined || Number.isNaN(v) ? "—" : `${v.toFixed(1)}%`;

/** Market-level cap-weighted PER/PBR/dividend valuation card. */
const ValuationSection: React.FC = () => {
  const [market, setMarket] = useState<InsightMarket>("KOSPI");
  // One metric per chart (single axis) — the toggle switches the plotted series.
  const [metric, setMetric] = useState<ValuationMetric>("pbr");

  const { data, isLoading, error, refetch } = useFetchInsightValuationQuery({
    market,
  });

  const chartData = useMemo(() => {
    return (data?.rows ?? [])
      .slice()
      .sort((a, b) => a.date.localeCompare(b.date))
      .map((r) => ({ date: r.date, PBR: r.pbr, PER: r.per }));
  }, [data]);

  const current = data?.current ?? null;
  const pctRankPbr = current?.pct_rank_pbr ?? null;

  return (
    <Card
      title={
        <span className="inline-flex items-center gap-1.5">
          {`시장 밸류에이션 · ${market}`}
          <InfoTip helpKey="valuation.gauge" />
        </span>
      }
      action={
        <div className="flex items-center gap-3">
          {data?.as_of && (
            <span className="text-xs text-ink-muted num">
              기준 {data.as_of}
            </span>
          )}
          <Segmented
            options={MARKET_OPTIONS}
            value={market}
            onChange={setMarket}
          />
        </div>
      }
    >
      {error ? (
        <ErrorState message="밸류에이션 데이터를 불러오지 못했습니다" onRetry={refetch} />
      ) : isLoading || !data ? (
        <LoadingState label="밸류에이션 데이터를 불러오는 중..." />
      ) : !current ? (
        <EmptyState
          title="밸류에이션 데이터 수집 중"
          hint="PER/PBR 백필 진행 중"
        />
      ) : (
        <div className="flex flex-col gap-6">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatTile label="PER" value={fmtRatio(current.per)} />
            <StatTile label="PBR" value={fmtRatio(current.pbr)} />
            <StatTile
              label="Dividend Yield"
              value={
                current.div === null ? "—" : `${current.div.toFixed(2)}%`
              }
            />
            <StatTile
              label="PBR Percentile"
              value={
                pctRankPbr === null
                  ? "—"
                  : pctRankPbr >= 50
                    ? `역사적 상위 ${(100 - pctRankPbr).toFixed(1)}%`
                    : `역사적 하위 ${pctRankPbr.toFixed(1)}%`
              }
              deltaType={
                pctRankPbr === null
                  ? "neutral"
                  : pctRankPbr <= 20
                    ? "gain"
                    : pctRankPbr >= 80
                      ? "loss"
                      : "neutral"
              }
              sub="역사적 백분위 (낮을수록 저평가)"
            />
          </div>

          <div className="rounded-xl border border-edge bg-raised p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="text-sm font-semibold text-ink">Coverage</p>
                <p className="mt-0.5 text-xs text-ink-muted">
                  양수 PER/PBR만 시장 배수에 포함하며, 빠진 적자·결측 종목의 비중을 함께 표시합니다.
                </p>
              </div>
              {data.calculation_version && (
                <span className="text-xs text-ink-muted num">{data.calculation_version}</span>
              )}
            </div>
            <dl className="mt-3 grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
              <div><dt className="text-ink-muted">PER · 종목</dt><dd className="mt-1 font-semibold text-ink num">{fmtCoverage(current.per_name_coverage_pct)}</dd></div>
              <div><dt className="text-ink-muted">PER · 시총</dt><dd className="mt-1 font-semibold text-ink num">{fmtCoverage(current.per_mktcap_coverage_pct)}</dd></div>
              <div><dt className="text-ink-muted">PBR · 종목</dt><dd className="mt-1 font-semibold text-ink num">{fmtCoverage(current.pbr_name_coverage_pct)}</dd></div>
              <div><dt className="text-ink-muted">적자/0 EPS · 종목</dt><dd className="mt-1 font-semibold text-ink num">{fmtCoverage(current.non_positive_eps_name_pct)}</dd></div>
            </dl>
            {current.aggregate_earnings_yield_pct != null && (
              <p className="mt-3 text-xs text-ink-secondary">
                Aggregate Earnings Yield <span className="num font-semibold text-ink">{current.aggregate_earnings_yield_pct.toFixed(2)}%</span>
                <span className="text-ink-muted"> · EPS가 있는 종목의 적자까지 포함 · 종목 {fmtCoverage(current.earnings_name_coverage_pct)} / 시총 {fmtCoverage(current.earnings_mktcap_coverage_pct)}</span>
              </p>
            )}
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <div>
                <p className="text-sm font-medium text-ink-secondary">
                  {metric === "pbr" ? "PBR History" : "PER History"}
                </p>
                {pctRankPbr !== null && (
                  <p className="text-xs text-ink-muted mt-0.5">
                    현재 PBR은 {pctRankPbr >= 50 ? `역사적 상위 ${(100 - pctRankPbr).toFixed(1)}%` : `역사적 하위 ${pctRankPbr.toFixed(1)}%`} 구간
                  </p>
                )}
              </div>
              <Segmented
                options={METRIC_OPTIONS}
                value={metric}
                onChange={setMetric}
              />
            </div>
            {chartData.length === 0 ? (
              <EmptyState title="밸류에이션 이력이 없습니다" />
            ) : (
              <TimeSeriesChart
                data={chartData}
                series={[
                  metric === "pbr"
                    ? { key: "PBR", color: "var(--chart-1)" }
                    : { key: "PER", color: "var(--chart-2)" },
                ]}
                height={280}
                yFormatter={(v) => v.toFixed(metric === "pbr" ? 2 : 1)}
              />
            )}
          </div>
        </div>
      )}
    </Card>
  );
};

export default ValuationSection;
