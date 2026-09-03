"use client";

import React from "react";
import { RegimePhaseName, useFetchRegimePhaseQuery } from "@/state/api";
import Card from "@/components/ui/Card";
import InfoTip from "@/components/ui/InfoTip";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";
import { PHASE_AXES, PHASE_COLORS, phaseTint } from "./phases";

/** Quadrant grid position: [row, col] with growth↑ on top, inflation→ up rightwards. */
const QUADRANT_LAYOUT: RegimePhaseName[][] = [
  ["Goldilocks", "Reflation"],
  ["Deflation", "Stagflation"],
];

const fmtNum = (v: number | undefined | null, digits = 2) =>
  v === undefined || v === null ? "—" : v.toFixed(digits);

const fmtDelta = (v: number | undefined | null, digits = 2) => {
  if (v === undefined || v === null) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(digits)}`;
};

interface PhaseQuadrantProps {
  className?: string;
}

/** 2x2 growth/inflation regime quadrant with the current phase highlighted. */
const PhaseQuadrant: React.FC<PhaseQuadrantProps> = ({ className = "" }) => {
  const { data, isLoading, error, refetch } = useFetchRegimePhaseQuery();

  const current = data?.current;

  return (
    <Card
      title={
        <span className="inline-flex items-center gap-1.5">
          성장 × 물가 좌표
          <InfoTip helpKey="regime.phase" />
        </span>
      }
      className={className}
      action={
        current && (
          <span
            className="badge"
            style={{
              color: PHASE_COLORS[current.phase],
              backgroundColor: phaseTint(current.phase, 12),
            }}
          >
            {current.phase}
          </span>
        )
      }
    >
      {error ? (
        <ErrorState message="Failed to load regime phase" onRetry={refetch} />
      ) : isLoading || !data ? (
        <LoadingState label="Loading regime phase..." />
      ) : (
        <div className="flex flex-col gap-4">
          {current && (
            <div className="grid gap-3 rounded-xl border border-edge bg-raised/55 p-4 sm:grid-cols-[1fr_auto] sm:items-end">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-ink-muted">Current coordinate</p>
                <p className="mt-1 text-2xl font-semibold tracking-[-0.03em]" style={{ color: PHASE_COLORS[current.phase] }}>
                  {current.phase}
                </p>
                <p className="mt-1 text-xs text-ink-secondary">{PHASE_AXES[current.phase]}</p>
              </div>
              <p className="font-mono text-[10px] text-ink-muted">OBS {current.as_of}</p>
            </div>
          )}
          <div
            className="flex gap-3"
            role="img"
            aria-label={current ? `현재 시장 국면은 ${current.phase}, ${PHASE_AXES[current.phase]}` : "성장과 물가 방향에 따른 4개 시장 국면"}
          >
            {/* Y axis label */}
            <div className="flex flex-col items-center justify-between py-6 text-[11px] text-ink-muted shrink-0">
              <span>성장 ↑</span>
              <span
                className="uppercase tracking-wider"
                style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}
              >
                Growth
              </span>
              <span>성장 ↓</span>
            </div>

            <div className="flex-1 flex flex-col gap-2">
              <div className="grid grid-cols-2 grid-rows-2 gap-2">
                {QUADRANT_LAYOUT.flat().map((phase) => {
                  const isCurrent = current?.phase === phase;
                  return (
                    <div
                      key={phase}
                      className="relative rounded-xl border p-4 min-h-[108px] flex flex-col justify-between transition-colors"
                      style={{
                        backgroundColor: phaseTint(phase, isCurrent ? 16 : 5),
                        borderColor: isCurrent
                          ? PHASE_COLORS[phase]
                          : "var(--border)",
                        boxShadow: isCurrent
                          ? `0 0 0 1px ${PHASE_COLORS[phase]}, 0 0 24px ${phaseTint(phase, 25)}`
                          : undefined,
                      }}
                    >
                      <div>
                        <p
                          className="text-sm font-semibold"
                          style={{ color: PHASE_COLORS[phase] }}
                        >
                          {phase}
                        </p>
                        <p className="mt-0.5 text-[11px] text-ink-secondary">
                          {PHASE_AXES[phase]}
                        </p>
                      </div>
                      {isCurrent && (
                        <div className="flex items-center gap-1.5">
                          <span
                            className="w-2.5 h-2.5 rounded-full animate-pulse"
                            style={{
                              backgroundColor: PHASE_COLORS[phase],
                              boxShadow: `0 0 8px ${PHASE_COLORS[phase]}`,
                            }}
                          />
                          <span
                            className="font-mono text-[10px] font-semibold uppercase tracking-wider"
                            style={{ color: PHASE_COLORS[phase] }}
                          >
                            observed
                          </span>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
              {/* X axis label */}
              <div className="flex items-center justify-between text-[11px] text-ink-muted px-1">
                <span>물가 ↓</span>
                <span className="uppercase tracking-wider">Inflation</span>
                <span>물가 ↑</span>
              </div>
            </div>
          </div>

          {/* Observation row */}
          <div className="flex flex-wrap items-center gap-x-6 gap-y-1 pt-3 border-t border-edge text-xs text-ink-secondary">
            <span>
              CLI{" "}
              <span className="num text-ink">{fmtNum(current?.cli)}</span>{" "}
              <span
                className={
                  (current?.cli_delta ?? 0) >= 0
                    ? "metric-positive"
                    : "metric-negative"
                }
              >
                (Δ{fmtDelta(current?.cli_delta)})
              </span>
            </span>
            <span>
              CPI YoY{" "}
              <span className="num text-ink">{fmtNum(current?.cpi_yoy)}%</span>{" "}
              <span
                className={
                  (current?.cpi_yoy_delta ?? 0) <= 0
                    ? "metric-positive"
                    : "metric-negative"
                }
              >
                (Δ{fmtDelta(current?.cpi_yoy_delta)})
              </span>
            </span>
          </div>
        </div>
      )}
    </Card>
  );
};

export default PhaseQuadrant;
