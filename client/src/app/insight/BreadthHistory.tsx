"use client";

import React, { useMemo } from "react";
import { InsightMarket, useFetchInsightBreadthQuery } from "@/state/api";
import Card from "@/components/ui/Card";
import InfoTip from "@/components/ui/InfoTip";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";
import EmptyState from "@/components/ui/EmptyState";
import TimeSeriesChart from "@/components/charts/TimeSeriesChart";
import { Segmented } from "./format";

interface BreadthHistoryProps {
  market: InsightMarket;
  onMarketChange: (market: InsightMarket) => void;
}

const MARKET_OPTIONS: { id: InsightMarket; label: string }[] = [
  { id: "KOSPI", label: "KOSPI" },
  { id: "KOSDAQ", label: "KOSDAQ" },
];

/** Breadth history: % above MA20 (baseline 50) and 52w new highs vs lows. */
const BreadthHistory: React.FC<BreadthHistoryProps> = ({
  market,
  onMarketChange,
}) => {
  const { data, isLoading, error, refetch } = useFetchInsightBreadthQuery({
    days: 365,
    market,
  });

  const { maData, hlData } = useMemo(() => {
    const rows = data?.rows ?? [];
    return {
      maData: rows.map((r) => ({
        date: r.date,
        pct_above_ma20: r.pct_above_ma20,
      })),
      hlData: rows.map((r) => ({
        date: r.date,
        "New Highs": r.new_high_52w,
        "New Lows": r.new_low_52w,
      })),
    };
  }, [data]);

  return (
    <Card
      title={`Breadth History — ${market}`}
      action={
        <div className="flex items-center gap-3">
          {data?.as_of && (
            <span className="text-xs text-ink-muted num">
              as of {data.as_of}
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
      {error ? (
        <ErrorState message="Failed to load breadth history" onRetry={refetch} />
      ) : isLoading || !data ? (
        <LoadingState label="Loading breadth history..." />
      ) : maData.length === 0 ? (
        <EmptyState title="No breadth history" />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div>
            <p className="text-sm font-medium text-ink-secondary mb-2 flex items-center gap-1.5">
              <span>% Above MA20</span>
              <InfoTip helpKey="breadth.ma20" />
            </p>
            <TimeSeriesChart
              data={maData}
              series={[
                {
                  key: "pct_above_ma20",
                  name: "% above MA20",
                  color: "var(--chart-1)",
                },
              ]}
              height={240}
              yFormatter={(v) => `${v.toFixed(0)}%`}
              baseline={50}
            />
          </div>
          <div>
            <p className="text-sm font-medium text-ink-secondary mb-2 flex items-center gap-1.5">
              <span>52w New Highs / New Lows</span>
              <InfoTip helpKey="breadth.high_low" />
            </p>
            <TimeSeriesChart
              data={hlData}
              series={[
                { key: "New Highs", color: "var(--gains)" },
                { key: "New Lows", color: "var(--losses)" },
              ]}
              height={240}
              yFormatter={(v) => v.toFixed(0)}
            />
          </div>
        </div>
      )}
    </Card>
  );
};

export default BreadthHistory;
