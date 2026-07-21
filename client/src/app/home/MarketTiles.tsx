"use client";

import React, { useMemo } from "react";
import Link from "next/link";
import {
  InsightMarket,
  useFetchInsightIndexQuery,
  useFetchRegimeGaugeQuery,
  useFetchRegimePhaseQuery,
} from "@/state/api";
import { PHASE_AXES, PHASE_COLORS, phaseTint } from "@/app/regime/phases";
import { fmtPct, signClass } from "@/app/insight/format";

interface IndexSnapshot {
  close: number;
  chgPct: number | null;
}

const gaugeColor = (score: number) =>
  score < 35 ? "var(--gains)" : score <= 65 ? "var(--chart-4)" : "var(--losses)";

const gaugeLabel = (score: number) =>
  score < 35 ? "Risk-On" : score <= 65 ? "중립" : "Risk-Off";

const Tile: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="card flex flex-col justify-between gap-1 min-h-[92px]">
    {children}
  </div>
);

const IndexTile: React.FC<{ market: InsightMarket; snap: IndexSnapshot | null }> = ({
  market,
  snap,
}) => (
  <Tile>
    <p className="metric-label">{market}</p>
    {snap ? (
      <div className="flex items-baseline gap-2">
        <p className="metric-value">
          {snap.close.toLocaleString(undefined, { maximumFractionDigits: 2 })}
        </p>
        <span className={`text-sm ${signClass(snap.chgPct)}`}>
          {fmtPct(snap.chgPct)}
        </span>
      </div>
    ) : (
      <p className="metric-value text-ink-muted">—</p>
    )}
  </Tile>
);

/** Row 1 of the dashboard: KOSPI / KOSDAQ snapshots + regime & risk-gauge chips. */
const MarketTiles: React.FC = () => {
  const { data: indexData } = useFetchInsightIndexQuery({ days: 30 });
  const { data: phaseData } = useFetchRegimePhaseQuery();
  const { data: gaugeData } = useFetchRegimeGaugeQuery();

  // Latest close + day % per index from the last two points of each series.
  const snapshots = useMemo(() => {
    const out: Partial<Record<InsightMarket, IndexSnapshot>> = {};
    const rows = indexData?.rows ?? [];
    for (const market of ["KOSPI", "KOSDAQ"] as InsightMarket[]) {
      const series = rows
        .filter((r) => r.index === market && r.close != null)
        .sort((a, b) => a.date.localeCompare(b.date));
      if (series.length === 0) continue;
      const last = series[series.length - 1];
      const prev = series.length > 1 ? series[series.length - 2] : null;
      out[market] = {
        close: last.close,
        chgPct: prev ? (last.close / prev.close - 1) * 100 : null,
      };
    }
    return out;
  }, [indexData]);

  const phase = phaseData?.current?.phase;
  const score = gaugeData?.score;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <IndexTile market="KOSPI" snap={snapshots.KOSPI ?? null} />
      <IndexTile market="KOSDAQ" snap={snapshots.KOSDAQ ?? null} />

      <Link href="/regime" className="block">
        <div className="card-interactive flex flex-col justify-between gap-1 min-h-[92px] h-full">
          <p className="metric-label">Market Regime</p>
          {phase ? (
            <div className="flex items-center gap-2">
              <span
                className="px-2.5 py-1 rounded-lg text-sm font-semibold"
                style={{
                  color: PHASE_COLORS[phase],
                  backgroundColor: phaseTint(phase, 12),
                }}
              >
                {phase}
              </span>
              <span className="text-xs text-ink-muted">{PHASE_AXES[phase]}</span>
            </div>
          ) : (
            <p className="metric-value text-ink-muted">—</p>
          )}
        </div>
      </Link>

      <Link href="/regime" className="block">
        <div className="card-interactive flex flex-col justify-between gap-1 min-h-[92px] h-full">
          <p className="metric-label">Risk-Off Gauge</p>
          {score !== undefined ? (
            <div className="flex items-baseline gap-2">
              <p className="metric-value" style={{ color: gaugeColor(score) }}>
                {Math.round(score)}
              </p>
              <span
                className="px-2 py-0.5 rounded-md text-xs font-semibold"
                style={{
                  color: gaugeColor(score),
                  backgroundColor: `color-mix(in srgb, ${gaugeColor(score)} 10%, transparent)`,
                }}
              >
                {gaugeLabel(score)}
              </span>
            </div>
          ) : (
            <p className="metric-value text-ink-muted">—</p>
          )}
        </div>
      </Link>
    </div>
  );
};

export default MarketTiles;
