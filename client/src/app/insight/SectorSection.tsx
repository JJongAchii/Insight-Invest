"use client";

import React, { useMemo, useState } from "react";
import {
  InsightMarket,
  InsightSectorHeatmapRow,
  InsightSectorPeriod,
  useFetchInsightSectorHeatmapQuery,
  useFetchInsightSectorRotationQuery,
} from "@/state/api";
import Card from "@/components/ui/Card";
import InfoTip from "@/components/ui/InfoTip";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";
import EmptyState from "@/components/ui/EmptyState";
import TimeSeriesChart, {
  TimeSeriesSeries,
} from "@/components/charts/TimeSeriesChart";
import { fmtPct, Segmented } from "./format";

const MARKET_OPTIONS: { id: InsightMarket; label: string }[] = [
  { id: "KOSPI", label: "KOSPI" },
  { id: "KOSDAQ", label: "KOSDAQ" },
];

const PERIOD_OPTIONS: { id: InsightSectorPeriod; label: string }[] = [
  { id: "1d", label: "1D" },
  { id: "1w", label: "1W" },
  { id: "1m", label: "1M" },
  { id: "3m", label: "3M" },
  { id: "ytd", label: "YTD" },
];

/** Number of sector lines shown in the rotation chart. */
const MAX_ROTATION_SERIES = 8;

/** Fixed 8-slot categorical palette (6 chart tokens + 2 extras), assigned alphabetically. */
const SECTOR_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
  "var(--chart-6)",
  "#f472b6",
  "#94a3b8",
];

const retForPeriod = (
  row: InsightSectorHeatmapRow,
  period: InsightSectorPeriod
): number | null => {
  switch (period) {
    case "1d":
      return row.ret_1d;
    case "1w":
      return row.ret_1w;
    case "1m":
      return row.ret_1m;
    case "3m":
      return row.ret_3m;
    case "ytd":
      return row.ret_ytd;
  }
};

/** Diverging tile background: gains/losses mixed into the raised surface by |ret| clamped at ±10%. */
const tileBackground = (ret: number | null): string => {
  if (ret === null || ret === 0 || Number.isNaN(ret)) {
    return "var(--surface-raised)";
  }
  const mag = Math.min(Math.abs(ret), 10) / 10;
  const alpha = Math.round(6 + mag * 40); // 6%–46%
  const hue = ret > 0 ? "var(--gains)" : "var(--losses)";
  return `color-mix(in srgb, ${hue} ${alpha}%, var(--surface-raised))`;
};

/** 3 subtle size buckets by market-cap weight. */
const tileSizeClass = (weight: number): string => {
  if (weight >= 0.15) return "basis-44";
  if (weight >= 0.05) return "basis-36";
  return "basis-28";
};

/** Sector heatmap + 12M rotation chart for the KR market. */
const SectorSection: React.FC = () => {
  const [market, setMarket] = useState<InsightMarket>("KOSPI");
  const [period, setPeriod] = useState<InsightSectorPeriod>("1m");
  const [selectedSector, setSelectedSector] = useState<string | null>(null);

  const {
    data: heatmapData,
    isLoading: heatmapLoading,
    error: heatmapError,
    refetch: refetchHeatmap,
  } = useFetchInsightSectorHeatmapQuery();
  const {
    data: rotationData,
    isLoading: rotationLoading,
    error: rotationError,
    refetch: refetchRotation,
  } = useFetchInsightSectorRotationQuery({ months: 12 });

  // Heatmap tiles for the toggled market, largest cap weight first.
  const tiles = useMemo(() => {
    return (heatmapData?.rows ?? [])
      .filter((r) => r.market === market)
      .slice()
      .sort((a, b) => b.mktcap_weight - a.mktcap_weight);
  }, [heatmapData, market]);

  // Top sectors by |selected-period return|; a clicked sector is always included.
  const rotationSectors = useMemo(() => {
    const ranked = tiles
      .filter((r) => retForPeriod(r, period) !== null)
      .slice()
      .sort(
        (a, b) =>
          Math.abs(retForPeriod(b, period) ?? 0) -
          Math.abs(retForPeriod(a, period) ?? 0)
      )
      .map((r) => r.sector);
    const top = ranked.slice(0, MAX_ROTATION_SERIES);
    if (
      selectedSector &&
      ranked.includes(selectedSector) &&
      !top.includes(selectedSector)
    ) {
      top[top.length - 1] = selectedSector;
    }
    // Alphabetical order keeps each sector's color stable across periods.
    return top.sort((a, b) => a.localeCompare(b, "ko"));
  }, [tiles, period, selectedSector]);

  // Pivot rotation rows to {date, [sector]: value rebased to 100 at window start}.
  const rotationChartData = useMemo(() => {
    const rows = (rotationData?.rows ?? []).filter(
      (r) => r.market === market && rotationSectors.includes(r.sector)
    );
    if (rows.length === 0) return [];
    const base = new Map<string, number>();
    const byDate = new Map<string, Record<string, number | null>>();
    const sorted = rows.slice().sort((a, b) => a.date.localeCompare(b.date));
    for (const r of sorted) {
      if (!base.has(r.sector) && r.index_value) base.set(r.sector, r.index_value);
      const b = base.get(r.sector);
      if (!b) continue;
      const g = byDate.get(r.date) ?? {};
      g[r.sector] = (r.index_value / b) * 100;
      byDate.set(r.date, g);
    }
    return Array.from(byDate.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, g]) => ({ date, ...g }));
  }, [rotationData, market, rotationSectors]);

  const rotationSeries: TimeSeriesSeries[] = useMemo(() => {
    const highlighted = selectedSector;
    return rotationSectors.map((sector, i) => ({
      key: sector,
      color: SECTOR_COLORS[i % SECTOR_COLORS.length],
      strokeWidth: highlighted === sector ? 3 : 1.8,
      opacity: highlighted && highlighted !== sector ? 0.25 : 1,
    }));
  }, [rotationSectors, selectedSector]);

  const toggleSector = (sector: string) => {
    setSelectedSector((prev) => (prev === sector ? null : sector));
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-lg font-semibold text-ink">Sectors</h2>
        <Segmented
          options={MARKET_OPTIONS}
          value={market}
          onChange={(m) => {
            setMarket(m);
            setSelectedSector(null);
          }}
        />
        <Segmented options={PERIOD_OPTIONS} value={period} onChange={setPeriod} />
      </div>

      <Card
        title={
          <span className="inline-flex items-center gap-1.5">
            Sector Heatmap
            <InfoTip helpKey="sector.heatmap" />
          </span>
        }
        action={
          heatmapData?.as_of && (
            <span className="text-xs text-ink-muted num">
              as of {heatmapData.as_of}
            </span>
          )
        }
      >
        {heatmapError ? (
          <ErrorState
            message="Failed to load sector heatmap"
            onRetry={refetchHeatmap}
          />
        ) : heatmapLoading || !heatmapData ? (
          <LoadingState label="Loading sector heatmap..." />
        ) : tiles.length === 0 ? (
          <EmptyState title="No sector data" />
        ) : (
          <div className="flex flex-wrap gap-2">
            {tiles.map((tile) => {
              const ret = retForPeriod(tile, period);
              const selected = selectedSector === tile.sector;
              return (
                <button
                  key={tile.sector}
                  onClick={() => toggleSector(tile.sector)}
                  className={`${tileSizeClass(
                    tile.mktcap_weight
                  )} grow rounded-xl border p-3 text-left transition-all ${
                    selected
                      ? "border-primary-400 ring-1 ring-primary-400"
                      : "border-edge hover:border-edge-strong"
                  }`}
                  style={{ backgroundColor: tileBackground(ret) }}
                  aria-pressed={selected}
                >
                  <p className="text-xs font-medium text-ink truncate">
                    {tile.sector}
                  </p>
                  <p className="mt-1 text-sm num text-ink font-medium">
                    {fmtPct(ret)}
                  </p>
                  <p className="mt-0.5 text-[11px] text-ink-muted num">
                    {tile.n_stocks} 종목
                  </p>
                </button>
              );
            })}
          </div>
        )}
      </Card>

      <Card
        title={
          <span className="inline-flex items-center gap-1.5">
            Sector Rotation
            <InfoTip helpKey="sector.rotation" />
          </span>
        }
        action={
          <span className="text-xs text-ink-muted">
            12M · indexed to 100 · top {MAX_ROTATION_SERIES} by |
            {PERIOD_OPTIONS.find((o) => o.id === period)?.label}|
          </span>
        }
      >
        {rotationError ? (
          <ErrorState
            message="Failed to load sector rotation"
            onRetry={refetchRotation}
          />
        ) : rotationLoading || !rotationData ? (
          <LoadingState label="Loading sector rotation..." />
        ) : rotationChartData.length === 0 ? (
          <EmptyState title="No rotation data" />
        ) : (
          <TimeSeriesChart
            data={rotationChartData}
            series={rotationSeries}
            height={320}
            yFormatter={(v) => v.toFixed(0)}
            baseline={100}
          />
        )}
      </Card>
    </div>
  );
};

export default SectorSection;
