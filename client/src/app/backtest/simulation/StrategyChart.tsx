import React, { useMemo } from "react";
import TimeSeriesChart from "@/components/charts/TimeSeriesChart";
import EmptyState from "@/components/ui/EmptyState";

interface NavData {
  index: number[];
  columns: string[];
  data: number[][];
}

interface StrategyChartProps {
  navResult: string | null;
}

const StrategyChart: React.FC<StrategyChartProps> = ({ navResult }) => {
  const { chartData, series } = useMemo(() => {
    if (!navResult) {
      return { chartData: [], series: [] };
    }
    const navData: NavData = JSON.parse(navResult);

    const chartData = navData.index.map((date: number, rowIdx: number) => {
      const row: { date: string; [key: string]: number | string } = {
        date: new Date(date).toISOString().split("T")[0],
      };
      navData.columns.forEach((column, colIdx) => {
        row[column] = navData.data[rowIdx][colIdx];
      });
      return row;
    });

    const series = navData.columns.map((column) => ({
      key: column,
      name: column,
    }));

    return { chartData, series };
  }, [navResult]);

  return (
    <div className="card">
      <h3 className="section-header">Performance Chart</h3>
      {navResult && chartData.length > 0 ? (
        <TimeSeriesChart
          data={chartData}
          series={series}
          height={400}
          yFormatter={(v) => v.toFixed(2)}
        />
      ) : (
        <EmptyState
          title="No data available"
          hint="Run a backtest to see performance"
        />
      )}
    </div>
  );
};

export default StrategyChart;
