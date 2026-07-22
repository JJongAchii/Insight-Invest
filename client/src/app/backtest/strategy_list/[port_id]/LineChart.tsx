import React, { useMemo } from "react";
import TimeSeriesChart, {
  TimeSeriesReferenceLineX,
} from "@/components/charts/TimeSeriesChart";
import InfoTip from "@/components/ui/InfoTip";
import { NavPoint } from "@/state/api";

interface NavData {
  trade_date: string;
  value: number;
}

interface BmNavData {
  trade_date: string;
  bm_name: string;
  value: number;
}

const LineChart = ({
  strategyName,
  strategyNav,
  bmNav,
  liveNav,
  savedAt,
}: {
  strategyName: string;
  strategyNav: NavData[];
  bmNav: string;
  /** Live (post-save) NAV, ~1000-based at savedAt. */
  liveNav?: NavPoint[];
  savedAt?: string | null;
}) => {
  const { chartData, series, referenceLinesX, hasLive } = useMemo(() => {
    const bmNavData: BmNavData[] = bmNav ? JSON.parse(bmNav) : [];
    const bmByDate = new Map<string, number>(
      bmNavData.map((nav) => [nav.trade_date, nav.value])
    );

    type Row = {
      date: string;
      strategy: number | null;
      benchmark: number | null;
      live: number | null;
    };

    const rowByDate = new Map<string, Row>();
    for (const nav of strategyNav ?? []) {
      rowByDate.set(nav.trade_date, {
        date: nav.trade_date,
        strategy: nav.value,
        benchmark: bmByDate.get(nav.trade_date) ?? null,
        live: null,
      });
    }

    // Rescale the 1000-based live NAV so it visually continues from the
    // stored backtest NAV's last value (saved_at == stored NAV end).
    const storedLast =
      strategyNav && strategyNav.length > 0
        ? strategyNav[strategyNav.length - 1].value
        : null;
    const live = liveNav ?? [];
    const hasLive = live.length > 0 && storedLast !== null;
    if (hasLive) {
      const scale = storedLast / 1000;
      for (const p of live) {
        const existing = rowByDate.get(p.date);
        if (existing) {
          existing.live = p.value * scale;
        } else {
          rowByDate.set(p.date, {
            date: p.date,
            strategy: null,
            benchmark: bmByDate.get(p.date) ?? null,
            live: p.value * scale,
          });
        }
      }
      // Anchor the live segment to the backtest endpoint for continuity.
      const lastStored = strategyNav[strategyNav.length - 1];
      const boundary = rowByDate.get(lastStored.trade_date);
      if (boundary && boundary.live === null) boundary.live = storedLast;
    }

    const chartData = [...rowByDate.values()].sort((a, b) =>
      a.date.localeCompare(b.date)
    );

    const series = [
      { key: "strategy", name: strategyName, color: "var(--chart-1)" },
      { key: "benchmark", name: "Benchmark", color: "var(--text-muted)" },
      ...(hasLive
        ? [{ key: "live", name: "Live (저장 후)", color: "var(--chart-4)" }]
        : []),
    ];

    const referenceLinesX: TimeSeriesReferenceLineX[] | undefined =
      hasLive && savedAt
        ? [{ x: savedAt, label: "저장", color: "var(--chart-4)" }]
        : undefined;

    return { chartData, series, referenceLinesX, hasLive };
  }, [strategyName, strategyNav, bmNav, liveNav, savedAt]);

  return (
    <div className="card">
      <h4 className="text-base font-semibold text-ink mb-4">
        <span className="inline-flex items-center gap-1.5">
          {hasLive ? "Backtest vs Live" : "Cumulative Performance"}
          {hasLive && <InfoTip helpKey="bt.live" />}
        </span>
      </h4>
      <TimeSeriesChart
        data={chartData}
        series={series}
        height={400}
        yFormatter={(v) => v.toFixed(2)}
        referenceLinesX={referenceLinesX}
      />
    </div>
  );
};

export default LineChart;
