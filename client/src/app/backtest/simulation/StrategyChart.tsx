import React, { useMemo } from "react";
import TimeSeriesChart from "@/components/charts/TimeSeriesChart";
import EmptyState from "@/components/ui/EmptyState";
import { NavPoint } from "@/state/api";

interface StrategyChartProps {
  strategyName: string;
  nav: NavPoint[] | null;
  benchmark: { name: string; nav: NavPoint[] } | null;
}

/** 전략 NAV + 벤치마크 NAV를 date 기준으로 병합해 라인차트로 그린다. */
const StrategyChart: React.FC<StrategyChartProps> = ({
  strategyName,
  nav,
  benchmark,
}) => {
  const { chartData, series } = useMemo(() => {
    if (!nav || nav.length === 0) {
      return { chartData: [], series: [] };
    }

    const merged = new Map<
      string,
      { date: string; strategy: number | null; benchmark: number | null }
    >();
    for (const point of nav) {
      merged.set(point.date, {
        date: point.date,
        strategy: point.value,
        benchmark: null,
      });
    }
    for (const point of benchmark?.nav ?? []) {
      const row = merged.get(point.date);
      if (row) {
        row.benchmark = point.value;
      } else {
        merged.set(point.date, {
          date: point.date,
          strategy: null,
          benchmark: point.value,
        });
      }
    }

    const chartData = Array.from(merged.values()).sort((a, b) =>
      a.date.localeCompare(b.date)
    );

    const series = [
      { key: "strategy", name: strategyName, color: "var(--chart-1)" },
      ...(benchmark && benchmark.nav.length > 0
        ? [
            {
              key: "benchmark",
              name: benchmark.name,
              color: "var(--text-muted)",
            },
          ]
        : []),
    ];

    return { chartData, series };
  }, [nav, benchmark, strategyName]);

  if (chartData.length === 0) {
    return (
      <EmptyState
        title="No data available"
        hint="Run a backtest to see performance"
      />
    );
  }

  return (
    <TimeSeriesChart
      data={chartData}
      series={series}
      height={400}
      yFormatter={(v) => v.toFixed(0)}
    />
  );
};

export default StrategyChart;
