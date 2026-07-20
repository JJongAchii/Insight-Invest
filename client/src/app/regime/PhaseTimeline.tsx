"use client";

import React, { useMemo } from "react";
import { useFetchRegimePhaseQuery } from "@/state/api";
import Card from "@/components/ui/Card";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";
import EmptyState from "@/components/ui/EmptyState";
import TimeSeriesChart, {
  TimeSeriesReferenceArea,
} from "@/components/charts/TimeSeriesChart";
import { PHASE_COLORS, PHASE_ORDER } from "./phases";

/** Phase history timeline: CLI & CPI YoY lines over phase-colored bands. */
const PhaseTimeline: React.FC = () => {
  const { data, isLoading, error, refetch } = useFetchRegimePhaseQuery();

  const { chartData, phaseAreas } = useMemo(() => {
    const history = data?.history ?? [];
    const points = history.map((h) => ({
      date: `${h.month}-01`,
      cli: h.cli,
      cpi_yoy: h.cpi_yoy,
    }));

    // Contiguous runs of the same phase → one reference area per run.
    const areas: TimeSeriesReferenceArea[] = [];
    let runStart: string | null = null;
    let runPhase: string | null = null;
    let prevDate: string | null = null;

    for (const h of history) {
      const date = `${h.month}-01`;
      if (h.phase !== runPhase) {
        if (runStart !== null && runPhase !== null && prevDate !== null) {
          areas.push({
            x1: runStart,
            x2: prevDate,
            color: PHASE_COLORS[runPhase as keyof typeof PHASE_COLORS],
          });
        }
        runStart = date;
        runPhase = h.phase;
      }
      prevDate = date;
    }
    if (runStart !== null && runPhase !== null && prevDate !== null) {
      areas.push({
        x1: runStart,
        x2: prevDate,
        color: PHASE_COLORS[runPhase as keyof typeof PHASE_COLORS],
      });
    }

    return { chartData: points, phaseAreas: areas };
  }, [data]);

  return (
    <Card
      title="Phase Timeline"
      action={
        <div className="flex flex-wrap items-center gap-2">
          {PHASE_ORDER.map((phase) => (
            <span
              key={phase}
              className="inline-flex items-center gap-1.5 text-xs text-ink-secondary"
            >
              <span
                className="w-2.5 h-2.5 rounded-sm"
                style={{
                  backgroundColor: `color-mix(in srgb, ${PHASE_COLORS[phase]} 45%, transparent)`,
                }}
              />
              {phase}
            </span>
          ))}
        </div>
      }
    >
      {error ? (
        <ErrorState message="Failed to load phase history" onRetry={refetch} />
      ) : isLoading || !data ? (
        <LoadingState label="Loading phase history..." />
      ) : chartData.length === 0 ? (
        <EmptyState title="No phase history" hint="History will appear once computed" />
      ) : (
        <>
          <p className="text-xs text-ink-muted mb-3">
            CLI · CPI YoY — 배경 음영은 각 시점의 레짐 국면
          </p>
          <TimeSeriesChart
            data={chartData}
            series={[
              { key: "cli", name: "CLI", color: "var(--chart-1)" },
              { key: "cpi_yoy", name: "CPI YoY", color: "var(--chart-5)" },
            ]}
            height={320}
            showBrush
            referenceAreas={phaseAreas}
          />
        </>
      )}
    </Card>
  );
};

export default PhaseTimeline;
