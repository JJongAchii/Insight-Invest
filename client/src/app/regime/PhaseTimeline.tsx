"use client";

import React, { useMemo } from "react";
import { useFetchRegimePhaseQuery } from "@/state/api";
import Card from "@/components/ui/Card";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";
import EmptyState from "@/components/ui/EmptyState";
import TimeSeriesChart from "@/components/charts/TimeSeriesChart";
import { PHASE_COLORS } from "./phases";

/** CLI와 CPI를 독립 축으로 분리하고, 최근 국면은 연속 구간만 압축해서 표시한다. */
const PhaseTimeline: React.FC = () => {
  const { data, isLoading, error, refetch } = useFetchRegimePhaseQuery();

  const { chartData, recentRuns } = useMemo(() => {
    const history = data?.history ?? [];
    const points = history.map((row) => ({
      date: `${row.month}-01`,
      cli: row.cli,
      cpi_yoy: row.cpi_yoy,
    }));
    const recent = history.slice(-60);
    const runs: { phase: (typeof recent)[number]["phase"]; start: string; end: string; months: number }[] = [];
    for (const row of recent) {
      const previous = runs[runs.length - 1];
      if (previous?.phase === row.phase) {
        previous.end = row.month;
        previous.months += 1;
      } else {
        runs.push({ phase: row.phase, start: row.month, end: row.month, months: 1 });
      }
    }
    return { chartData: points, recentRuns: runs };
  }, [data]);

  return (
    <Card title="Growth & Inflation Trend">
      {error ? (
        <ErrorState message="국면 이력을 불러오지 못했습니다" onRetry={refetch} />
      ) : isLoading || !data ? (
        <LoadingState label="국면 이력을 불러오는 중..." />
      ) : chartData.length === 0 ? (
        <EmptyState title="국면 이력이 없습니다" />
      ) : (
        <div className="space-y-5">
          <p className="text-xs text-ink-muted">
            수준 차이가 큰 CLI와 CPI YoY를 별도 축으로 표시합니다. {data.methodology?.release_lag}
          </p>
          <div>
            <p className="mb-2 text-sm font-medium text-ink-secondary">OECD 경기선행지수 (CLI)</p>
            <TimeSeriesChart
              data={chartData}
              series={[{ key: "cli", name: "CLI", color: "var(--chart-1)" }]}
              height={220}
              showBrush
            />
          </div>
          <div>
            <p className="mb-2 text-sm font-medium text-ink-secondary">미국 CPI 전년동월비 (%)</p>
            <TimeSeriesChart
              data={chartData}
              series={[{ key: "cpi_yoy", name: "CPI YoY", color: "var(--chart-5)" }]}
              height={220}
              baseline={0}
              showBrush
            />
          </div>
          <div>
            <p className="mb-2 text-sm font-medium text-ink-secondary">최근 5년 국면 구간</p>
            <div className="flex min-h-12 overflow-hidden rounded-xl border border-edge">
              {recentRuns.map((run) => (
                <div
                  key={`${run.phase}-${run.start}`}
                  className="flex min-w-10 items-center justify-center px-2 text-center text-xs font-medium"
                  style={{
                    flexGrow: run.months,
                    color: PHASE_COLORS[run.phase],
                    backgroundColor: `color-mix(in srgb, ${PHASE_COLORS[run.phase]} 15%, transparent)`,
                  }}
                  title={`${run.phase} · ${run.start}~${run.end}`}
                >
                  {run.months >= 5 ? run.phase : ""}
                </div>
              ))}
            </div>
          </div>
          {data.methodology?.warning && (
            <p className="text-xs text-ink-muted">빈티지 주의: {data.methodology.warning}</p>
          )}
        </div>
      )}
    </Card>
  );
};

export default PhaseTimeline;
