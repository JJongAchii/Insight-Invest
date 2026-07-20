import React from "react";
import StatTile from "@/components/ui/StatTile";
import WeightBar from "@/components/charts/WeightBar";

interface InfoData {
  port_name: string;
  ann_ret: number;
  ann_vol: number;
  mdd: number;
}

interface RebalData {
  rebal_date: string;
  port_id: number;
  ticker: string;
  name: string;
  weight: number;
}

interface BmData {
  strategy: string;
  ann_returns: number;
}

const MetricSummary = ({
  strategyInfo,
  rebalWeight,
  bmMetrics,
}: {
  strategyInfo: InfoData;
  rebalWeight: RebalData[];
  bmMetrics: string;
}) => {
  const bmData: BmData[] = bmMetrics ? JSON.parse(bmMetrics) : [];
  const benchmarkData = bmData.find((d) => d.strategy === "BM(SPY)");
  const excessReturn = benchmarkData
    ? parseFloat((strategyInfo.ann_ret - benchmarkData.ann_returns).toFixed(2))
    : 0;

  const lastDate =
    rebalWeight && rebalWeight.length > 0
      ? rebalWeight.reduce(
          (latest, item) =>
            item.rebal_date > latest ? item.rebal_date : latest,
          rebalWeight[0].rebal_date
        )
      : null;
  const recentRebalData = lastDate
    ? rebalWeight?.filter((item) => item.rebal_date === lastDate)
    : [];

  // Sort by weight descending for better visualization
  const sortedRebalData = [...recentRebalData].sort(
    (a, b) => b.weight - a.weight
  );

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold text-ink">
            {strategyInfo.port_name}
          </h2>
          <p className="text-sm text-ink-muted">Performance Summary</p>
        </div>
      </div>

      {/* Key Metrics Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatTile
          label="Annual Return"
          value={`${strategyInfo.ann_ret >= 0 ? "+" : ""}${strategyInfo.ann_ret}%`}
          deltaType={strategyInfo.ann_ret >= 0 ? "gain" : "loss"}
        />
        <StatTile
          label="vs Benchmark"
          value={`${excessReturn >= 0 ? "+" : ""}${excessReturn}%`}
          deltaType={excessReturn >= 0 ? "gain" : "loss"}
        />
        <StatTile label="Volatility" value={`${strategyInfo.ann_vol}%`} />
        <StatTile
          label="Max Drawdown"
          value={`${strategyInfo.mdd}%`}
          deltaType="loss"
        />
      </div>

      {/* Current Allocation - Horizontal Bars */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h4 className="text-sm font-semibold text-ink-secondary">
            Current Allocation
          </h4>
          {lastDate && (
            <span className="text-xs text-ink-muted">as of {lastDate}</span>
          )}
        </div>

        <WeightBar
          items={sortedRebalData.map((item) => ({
            label: item.ticker,
            value: item.weight,
            sub: item.name,
          }))}
        />

        {/* Total check */}
        {sortedRebalData.length > 0 && (
          <div className="mt-4 pt-3 border-t border-edge flex items-center justify-between">
            <span className="text-xs text-ink-muted">Total Allocation</span>
            <span className="num text-sm font-semibold text-ink-secondary">
              {(
                sortedRebalData.reduce((sum, item) => sum + item.weight, 0) * 100
              ).toFixed(1)}
              %
            </span>
          </div>
        )}
      </div>
    </div>
  );
};

export default MetricSummary;
