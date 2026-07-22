"use client";

import React from "react";
import { useFetchStrategyLiveByIdQuery } from "@/state/api";
import SparklineChart from "@/components/charts/SparklineChart";

const LIVE_COLOR = "var(--chart-4)";

interface LiveBadgeProps {
  portId: number;
  /** Also render a small amber sparkline of the live NAV. */
  showSparkline?: boolean;
  sparkWidth?: number;
  sparkHeight?: number;
  className?: string;
}

/**
 * Self-fetching "저장후 +N.N%" badge for a strategy's live (out-of-sample)
 * track record. Renders nothing while loading, on error, or when the
 * strategy has no live NAV yet.
 */
const LiveBadge: React.FC<LiveBadgeProps> = ({
  portId,
  showSparkline = false,
  sparkWidth = 140,
  sparkHeight = 20,
  className = "",
}) => {
  const { data } = useFetchStrategyLiveByIdQuery(portId);
  const nav = data?.nav ?? [];
  if (nav.length === 0) return null;

  // Live NAV starts at ~1000 on the save date.
  const ret = (nav[nav.length - 1].value / 1000 - 1) * 100;
  const positive = ret >= 0;

  return (
    <span className={`inline-flex items-center gap-2 ${className}`.trim()}>
      {showSparkline && nav.length >= 2 && (
        <SparklineChart
          data={nav.map((p) => p.value)}
          width={sparkWidth}
          height={sparkHeight}
          color={LIVE_COLOR}
        />
      )}
      <span
        className={`num text-xs font-medium whitespace-nowrap ${
          positive ? "text-gains" : "text-losses"
        }`}
      >
        저장후 {positive ? "+" : ""}
        {ret.toFixed(1)}%
      </span>
    </span>
  );
};

interface LiveSparklineProps {
  portId: number;
  /** Sparkline values used when no live NAV exists yet. */
  fallbackData: number[];
  fallbackColor?: string;
  width?: number;
  height?: number;
}

/**
 * Sparkline that prefers the live (post-save) NAV — drawn in amber — and
 * falls back to the provided series (e.g. stored monthly NAV) otherwise.
 */
export const LiveSparkline: React.FC<LiveSparklineProps> = ({
  portId,
  fallbackData,
  fallbackColor = "var(--chart-1)",
  width = 90,
  height = 28,
}) => {
  const { data } = useFetchStrategyLiveByIdQuery(portId);
  const nav = data?.nav ?? [];
  const useLive = nav.length >= 2;

  return (
    <SparklineChart
      data={useLive ? nav.map((p) => p.value) : fallbackData}
      width={width}
      height={height}
      color={useLive ? LIVE_COLOR : fallbackColor}
    />
  );
};

export default LiveBadge;
