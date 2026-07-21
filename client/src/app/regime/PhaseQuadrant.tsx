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
          Growth / Inflation Phase
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
          <div className="flex gap-3">
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
                        <p className="text-[11px] text-ink-muted mt-0.5">
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
                            className="text-xs font-medium"
                            style={{ color: PHASE_COLORS[phase] }}
                          >
                            현재
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

          {/* Caption row */}
          <div className="flex flex-wrap items-center gap-x-6 gap-y-1 pt-3 border-t border-edge text-xs text-ink-secondary">
            <span className="text-ink-muted">
              기준일 <span className="num text-ink-secondary">{current?.as_of ?? "—"}</span>
            </span>
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
