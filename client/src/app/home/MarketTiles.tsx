"use client";

import React, { useMemo } from "react";
import Link from "next/link";
import {
  InsightMarket,
  useFetchInsightIndexQuery,
  useFetchIntradayMarketQuery,
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

const IndexTile: React.FC<{
  market: InsightMarket;
  snap: IndexSnapshot | null;
  badge?: string;
}> = ({ market, snap, badge }) => (
  <Tile>
    <p className={badge ? "metric-label flex items-center gap-1.5" : "metric-label"}>
      {market}
      {badge && <span className="text-xs font-normal text-losses">{badge}</span>}
    </p>
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
  const { data: intraday } = useFetchIntradayMarketQuery(undefined, {
    pollingInterval: 5 * 60 * 1000,
    skipPollingIfUnfocused: true,
  });

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

  // 장중 스냅샷이 active면 KR 지수 타일만 장중 값으로 교체 (스펙 D4 — US 무관).
  const liveSnapshots = useMemo(() => {
    if (!intraday?.active || !intraday.indices) return snapshots;
    const out = { ...snapshots };
    for (const idx of intraday.indices) {
      if (idx.key === "KOSPI" || idx.key === "KOSDAQ") {
        out[idx.key as InsightMarket] = { close: idx.level, chgPct: idx.chg_pct };
      }
    }
    return out;
  }, [snapshots, intraday]);

  const liveBadge = intraday?.active
    ? `🔴 ${intraday.as_of?.slice(-5)}`
    : undefined;

  const phase = phaseData?.current?.phase;
  const score = gaugeData?.score;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <IndexTile market="KOSPI" snap={liveSnapshots.KOSPI ?? null} badge={liveBadge} />
      <IndexTile market="KOSDAQ" snap={liveSnapshots.KOSDAQ ?? null} badge={liveBadge} />

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
