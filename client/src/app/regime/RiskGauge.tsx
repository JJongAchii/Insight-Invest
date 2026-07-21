"use client";

import React from "react";
import { useFetchRegimeGaugeQuery } from "@/state/api";
import Card from "@/components/ui/Card";
import InfoTip from "@/components/ui/InfoTip";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";

/** Server component name → INDICATOR_HELP key. */
const componentHelpKey = (name: string): string | undefined => {
  const n = name.toLowerCase();
  if (n.includes("yield")) return "gauge.yield_curve";
  if (n.includes("hy")) return "gauge.hy";
  if (n.includes("vix")) return "gauge.vix";
  if (n.includes("unemploy")) return "gauge.unemployment";
  return undefined;
};

const scoreColor = (score: number) =>
  score < 35 ? "var(--gains)" : score <= 65 ? "var(--chart-4)" : "var(--losses)";

const scoreLabel = (score: number) =>
  score < 35 ? "Risk-On" : score <= 65 ? "Neutral" : "Risk-Off";

const ARC_R = 80;
const ARC_CX = 100;
const ARC_CY = 100;
const ARC_LEN = Math.PI * ARC_R;

/** Semicircle SVG gauge: 0 (left) → 100 (right), higher = risk-off. */
const GaugeArc: React.FC<{ score: number }> = ({ score }) => {
  const clamped = Math.max(0, Math.min(100, score));
  const color = scoreColor(clamped);
  // Needle: 180° at score 0 → 0° at score 100.
  const angle = Math.PI * (1 - clamped / 100);
  const nx = ARC_CX + (ARC_R - 14) * Math.cos(angle);
  const ny = ARC_CY - (ARC_R - 14) * Math.sin(angle);

  return (
    <svg viewBox="0 0 200 112" className="w-full max-w-[280px] mx-auto">
      {/* Track */}
      <path
        d={`M ${ARC_CX - ARC_R} ${ARC_CY} A ${ARC_R} ${ARC_R} 0 0 1 ${ARC_CX + ARC_R} ${ARC_CY}`}
        fill="none"
        stroke="var(--surface-raised)"
        strokeWidth="12"
        strokeLinecap="round"
      />
      {/* Filled arc up to score */}
      <path
        d={`M ${ARC_CX - ARC_R} ${ARC_CY} A ${ARC_R} ${ARC_R} 0 0 1 ${ARC_CX + ARC_R} ${ARC_CY}`}
        fill="none"
        stroke={color}
        strokeWidth="12"
        strokeLinecap="round"
        strokeDasharray={`${(clamped / 100) * ARC_LEN} ${ARC_LEN}`}
        style={{ transition: "stroke-dasharray 0.6s ease, stroke 0.3s ease" }}
      />
      {/* Needle */}
      <line
        x1={ARC_CX}
        y1={ARC_CY}
        x2={nx}
        y2={ny}
        stroke={color}
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      <circle cx={ARC_CX} cy={ARC_CY} r="5" fill={color} />
      {/* Scale labels */}
      <text
        x={ARC_CX - ARC_R}
        y={ARC_CY + 11}
        fontSize="9"
        fill="var(--text-muted)"
        textAnchor="middle"
      >
        0
      </text>
      <text
        x={ARC_CX + ARC_R}
        y={ARC_CY + 11}
        fontSize="9"
        fill="var(--text-muted)"
        textAnchor="middle"
      >
        100
      </text>
    </svg>
  );
};

/** Risk-off gauge card: semicircle score + weighted component breakdown. */
const RiskGauge: React.FC<{ className?: string }> = ({ className = "" }) => {
  const { data, isLoading, error, refetch } = useFetchRegimeGaugeQuery();

  return (
    <Card
      title={
        <span className="inline-flex items-center gap-1.5">
          Risk-Off Gauge
          <InfoTip helpKey="regime.gauge" />
        </span>
      }
      className={className}
    >
      {error ? (
        <ErrorState message="Failed to load risk gauge" onRetry={refetch} />
      ) : isLoading || !data ? (
        <LoadingState label="Loading risk gauge..." />
      ) : (
        <div className="flex flex-col gap-4">
          <div className="relative">
            <GaugeArc score={data.score} />
            <div className="absolute inset-x-0 bottom-0 text-center pointer-events-none">
              <p
                className="num text-4xl font-semibold leading-none"
                style={{ color: scoreColor(data.score) }}
              >
                {Math.round(data.score)}
              </p>
            </div>
          </div>
          <div className="flex items-center justify-center gap-2 -mt-1">
            <span
              className="badge"
              style={{
                color: scoreColor(data.score),
                backgroundColor: `color-mix(in srgb, ${scoreColor(data.score)} 10%, transparent)`,
              }}
            >
              {scoreLabel(data.score)}
            </span>
            <span className="text-xs text-ink-muted num">{data.as_of}</span>
          </div>

          {/* Component breakdown */}
          <div className="flex flex-col gap-2.5 pt-3 border-t border-edge">
            {data.components.map((c) => {
              const color = scoreColor(c.score);
              const width = Math.max(0, Math.min(100, c.score));
              const helpKey = componentHelpKey(c.name);
              return (
                <div key={c.name} className="flex items-center gap-3">
                  <span className="flex items-center gap-1 w-28 shrink-0">
                    <span className="text-xs text-ink-secondary truncate">
                      {c.name}
                    </span>
                    {helpKey && <InfoTip helpKey={helpKey} />}
                  </span>
                  <span className="num text-xs text-ink w-14 shrink-0 text-right">
                    {c.value.toFixed(2)}
                  </span>
                  <div className="flex-1 h-1.5 rounded-full bg-raised overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${width}%`,
                        backgroundColor: color,
                        transition: "width 0.6s ease",
                      }}
                    />
                  </div>
                  <span
                    className="num text-xs font-medium w-8 shrink-0 text-right"
                    style={{ color }}
                  >
                    {Math.round(c.score)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </Card>
  );
};

export default RiskGauge;
