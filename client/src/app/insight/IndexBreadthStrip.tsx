"use client";

import React, { useMemo } from "react";
import {
  InsightMarket,
  useFetchInsightBreadthQuery,
  useFetchInsightIndexQuery,
} from "@/state/api";
import Card from "@/components/ui/Card";
import StatTile from "@/components/ui/StatTile";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";
import EmptyState from "@/components/ui/EmptyState";
import TimeSeriesChart from "@/components/charts/TimeSeriesChart";
import { Segmented } from "./format";

interface IndexBreadthStripProps {
  market: InsightMarket;
  onMarketChange: (market: InsightMarket) => void;
}

const MARKET_OPTIONS: { id: InsightMarket; label: string }[] = [
  { id: "KOSPI", label: "KOSPI" },
  { id: "KOSDAQ", label: "KOSDAQ" },
];

/** KOSPI/KOSDAQ indexed performance (1Y, base 100) + latest breadth stat tiles. */
const IndexBreadthStrip: React.FC<IndexBreadthStripProps> = ({
  market,
  onMarketChange,
}) => {
  const {
    data: indexData,
    isLoading: indexLoading,
    error: indexError,
    refetch: refetchIndex,
  } = useFetchInsightIndexQuery({ days: 365 });
  const {
    data: breadthData,
    isLoading: breadthLoading,
    error: breadthError,
    refetch: refetchBreadth,
  } = useFetchInsightBreadthQuery({ days: 30, market });

  // Pivot index rows to {date, KOSPI, KOSDAQ}, each normalized to 100 at range start.
  const chartData = useMemo(() => {
    const rows = indexData?.rows ?? [];
    if (rows.length === 0) return [];
    const base: Partial<Record<InsightMarket, number>> = {};
    const byDate = new Map<string, { KOSPI?: number; KOSDAQ?: number }>();
    const sorted = [...rows].sort((a, b) => a.date.localeCompare(b.date));
    for (const r of sorted) {
      if (base[r.index] === undefined && r.close) base[r.index] = r.close;
      const b = base[r.index];
      if (!b) continue;
      const g = byDate.get(r.date) ?? {};
      g[r.index] = (r.close / b) * 100;
      byDate.set(r.date, g);
    }
    return Array.from(byDate.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, g]) => ({
        date,
        KOSPI: g.KOSPI ?? null,
        KOSDAQ: g.KOSDAQ ?? null,
      }));
  }, [indexData]);

  const latest = breadthData?.rows?.length
    ? breadthData.rows[breadthData.rows.length - 1]
    : null;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card
        title="KOSPI vs KOSDAQ"
        action={
          <span className="text-xs text-ink-muted">1Y · indexed to 100</span>
        }
      >
        {indexError ? (
          <ErrorState message="Failed to load index data" onRetry={refetchIndex} />
        ) : indexLoading || !indexData ? (
          <LoadingState label="Loading index data..." />
        ) : chartData.length === 0 ? (
          <EmptyState title="No index data" />
        ) : (
          <TimeSeriesChart
            data={chartData}
            series={[
              { key: "KOSPI", color: "var(--chart-1)" },
              { key: "KOSDAQ", color: "var(--chart-2)" },
            ]}
            height={280}
            yFormatter={(v) => v.toFixed(0)}
            showBrush={false}
          />
        )}
      </Card>

      <Card
        title="Market Breadth"
        action={
          <div className="flex items-center gap-3">
            {breadthData?.as_of && (
              <span className="text-xs text-ink-muted num">
                as of {breadthData.as_of}
              </span>
            )}
            <Segmented
              options={MARKET_OPTIONS}
              value={market}
              onChange={onMarketChange}
            />
          </div>
        }
      >
        {breadthError ? (
          <ErrorState
            message="Failed to load breadth data"
            onRetry={refetchBreadth}
          />
        ) : breadthLoading || !breadthData ? (
          <LoadingState label="Loading breadth data..." />
        ) : !latest ? (
          <EmptyState title="No breadth data" />
        ) : (
          <div className="grid grid-cols-2 gap-4">
            <StatTile
              label="Advance / Decline"
              helpKey="breadth.ad"
              value={
                <>
                  <span className="text-gains">
                    {latest.advances.toLocaleString()}
                  </span>
                  <span className="text-ink-muted"> / </span>
                  <span className="text-losses">
                    {latest.declines.toLocaleString()}
                  </span>
                </>
              }
              sub={`Unchanged ${latest.unchanged.toLocaleString()}`}
            />
            <StatTile
              label="New 52w High / Low"
              helpKey="breadth.high_low"
              value={
                <>
                  <span className="text-gains">{latest.new_high_52w}</span>
                  <span className="text-ink-muted"> / </span>
                  <span className="text-losses">{latest.new_low_52w}</span>
                </>
              }
            />
            <StatTile
              label="Limit-up"
              helpKey="breadth.limit"
              value={latest.limit_up}
              sub={`Limit-down ${latest.limit_down}`}
            />
            <StatTile
              label="% Above MA20"
              helpKey="breadth.ma20"
              value={`${latest.pct_above_ma20.toFixed(1)}%`}
              deltaType={latest.pct_above_ma20 >= 50 ? "gain" : "loss"}
            />
          </div>
        )}
      </Card>
    </div>
  );
};

export default IndexBreadthStrip;
