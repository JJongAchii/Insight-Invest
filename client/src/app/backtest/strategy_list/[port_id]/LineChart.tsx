import React, { useMemo } from "react";
import TimeSeriesChart from "@/components/charts/TimeSeriesChart";

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
}: {
  strategyName: string;
  strategyNav: NavData[];
  bmNav: string;
}) => {
  const { chartData, series } = useMemo(() => {
    const bmNavData: BmNavData[] = bmNav ? JSON.parse(bmNav) : [];
    const bmByDate = new Map<string, number>(
      bmNavData.map((nav) => [nav.trade_date, nav.value])
    );

    const chartData = (strategyNav ?? []).map((nav) => ({
      date: nav.trade_date,
      strategy: nav.value,
      benchmark: bmByDate.get(nav.trade_date) ?? null,
    }));

    const series = [
      { key: "strategy", name: strategyName, color: "var(--chart-1)" },
      { key: "benchmark", name: "Benchmark", color: "var(--text-muted)" },
    ];

    return { chartData, series };
  }, [strategyName, strategyNav, bmNav]);

  return (
    <div className="card">
      <h4 className="text-base font-semibold text-ink mb-4">
        Cumulative Performance
      </h4>
      <TimeSeriesChart
        data={chartData}
        series={series}
        height={400}
        yFormatter={(v) => v.toFixed(2)}
      />
    </div>
  );
};

export default LineChart;
