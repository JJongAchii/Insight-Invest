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
          {`Market Valuation — ${market}`}
          <InfoTip helpKey="valuation.gauge" />
        </span>
      }
      action={
        <div className="flex items-center gap-3">
          {data?.as_of && (
            <span className="text-xs text-ink-muted num">
              as of {data.as_of}
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
        <ErrorState message="Failed to load valuation data" onRetry={refetch} />
      ) : isLoading || !data ? (
        <LoadingState label="Loading valuation data..." />
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
              label="배당수익률"
              value={
                current.div === null ? "—" : `${current.div.toFixed(2)}%`
              }
            />
            <StatTile
              label="PBR 백분위"
              value={
                pctRankPbr === null ? "—" : `하위 ${pctRankPbr.toFixed(0)}%`
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

          <div>
            <div className="flex items-center justify-between mb-2">
              <div>
                <p className="text-sm font-medium text-ink-secondary">
                  {metric === "pbr" ? "PBR 추이" : "PER 추이"}
                </p>
                {pctRankPbr !== null && (
                  <p className="text-xs text-ink-muted mt-0.5">
                    현재 PBR은 역사적 하위 {pctRankPbr.toFixed(0)}% 구간
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
              <EmptyState title="No valuation history" />
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
