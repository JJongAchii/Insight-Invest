"use client";

import React, { useMemo, useState } from "react";
import {
  RegimePhaseName,
  useFetchRegimePhasePerformanceQuery,
  useFetchRegimePhaseQuery,
} from "@/state/api";
import Card from "@/components/ui/Card";
import InfoTip from "@/components/ui/InfoTip";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";
import EmptyState from "@/components/ui/EmptyState";
import { PHASE_COLORS, PHASE_ORDER, phaseTint } from "./phases";

const pct = (v: number | null | undefined, digits = 2) =>
  v === null || v === undefined ? "—" : `${v.toFixed(digits)}%`;

const retClass = (v: number | null | undefined) =>
  v === null || v === undefined
    ? "num text-ink-muted"
    : v >= 0
      ? "metric-positive"
      : "metric-negative";

/** Per-phase asset performance table with phase tabs (current phase first). */
const PhasePerformance: React.FC = () => {
  const { data, isLoading, error, refetch } =
    useFetchRegimePhasePerformanceQuery();
  const { data: phaseData } = useFetchRegimePhaseQuery();

  const currentPhase = phaseData?.current?.phase;

  // Current phase first, then canonical order; only phases present in data.
  const availablePhases = useMemo(() => {
    const present = PHASE_ORDER.filter(
      (p) => (data?.phases?.[p]?.length ?? 0) > 0
    );
    if (currentPhase && present.includes(currentPhase)) {
      return [currentPhase, ...present.filter((p) => p !== currentPhase)];
    }
    return present;
  }, [data, currentPhase]);

  const [selected, setSelected] = useState<RegimePhaseName | null>(null);
  const activePhase = selected ?? availablePhases[0] ?? null;
  const rows = activePhase ? (data?.phases?.[activePhase] ?? []) : [];

  return (
    <Card
      className="min-h-[18rem]"
      title={
        <span className="inline-flex items-center gap-1.5">
          국면별 자산 반응
          <InfoTip helpKey="regime.performance" />
        </span>
      }
      action={
        data?.as_of && (
          <span className="text-xs text-ink-muted num">as of {data.as_of}</span>
        )
      }
    >
      {error ? (
        <ErrorState
          message="국면별 자산 반응을 불러오지 못했습니다"
          onRetry={refetch}
        />
      ) : isLoading || !data ? (
        <LoadingState label="국면별 성과 표본을 불러오는 중..." />
      ) : availablePhases.length === 0 ? (
        <EmptyState
          title="국면별 성과 표본이 없습니다"
          hint="계산이 완료되면 국면별 월 수익률과 표본 수가 표시됩니다"
        />
      ) : (
        <div className="flex flex-col gap-4">
          {/* Phase tabs */}
          <div className="flex flex-wrap items-center gap-2">
            {availablePhases.map((phase) => {
              const isActive = phase === activePhase;
              return (
                <button
                  key={phase}
                  onClick={() => setSelected(phase)}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors"
                  style={
                    isActive
                      ? {
                          color: PHASE_COLORS[phase],
                          backgroundColor: phaseTint(phase, 12),
                          borderColor: PHASE_COLORS[phase],
                        }
                      : {
                          color: "var(--text-secondary)",
                          borderColor: "var(--border)",
                        }
                  }
                >
                  {phase}
                  {phase === currentPhase && (
                    <span className="ml-1.5 opacity-80">· 현재</span>
                  )}
                </button>
              );
            })}
          </div>

          {rows.length === 0 ? (
            <EmptyState title="No data for this phase" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="table-header">
                    <th className="py-2.5 px-4 text-left rounded-l-lg">
                      자산
                    </th>
                    <th className="py-2.5 px-4 text-right">월평균</th>
                    <th className="py-2.5 px-4 text-right">연환산</th>
                    <th className="py-2.5 px-4 text-right">상승 월 비율</th>
                    <th className="py-2.5 px-4 text-right rounded-r-lg">표본 월</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.ticker} className="table-row">
                      <td className="table-cell font-medium">{row.ticker}</td>
                      <td className="table-cell text-right">
                        <span className={retClass(row.mean_monthly_ret)}>
                          {pct(row.mean_monthly_ret)}
                        </span>
                      </td>
                      <td className="table-cell text-right">
                        <span className={retClass(row.ann_ret)}>
                          {pct(row.ann_ret)}
                        </span>
                      </td>
                      <td className="table-cell text-right">
                        <span className="num text-ink-secondary">
                          {pct(row.hit_rate, 1)}
                        </span>
                      </td>
                      <td className="table-cell text-right">
                        <span className="num text-ink-muted">
                          {row.n_months}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </Card>
  );
};

export default PhasePerformance;
