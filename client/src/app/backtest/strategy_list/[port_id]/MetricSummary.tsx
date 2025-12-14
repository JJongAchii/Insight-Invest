import React from "react";

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

// Pastel color palette for allocation bars
const barColors = [
  "#7C5BFF", // Lavender
  "#38BDF8", // Sky Blue
  "#10B981", // Emerald
  "#F59E0B", // Amber
  "#EC4899", // Pink
  "#14B8A6", // Teal
  "#8B5CF6", // Violet
  "#F97316", // Orange
];

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
          <h2 className="text-xl font-semibold text-neutral-900">
            {strategyInfo.port_name}
          </h2>
          <p className="text-sm text-neutral-500">Performance Summary</p>
        </div>
      </div>

      {/* Key Metrics Strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6 p-4 bg-white/40 backdrop-blur-md rounded-xl border border-white/30">
        <div>
          <p className="text-xs text-neutral-500 mb-1">Annual Return</p>
          <p
            className={`text-xl font-semibold ${strategyInfo.ann_ret >= 0 ? "text-success" : "text-danger"}`}
          >
            {strategyInfo.ann_ret >= 0 ? "+" : ""}
            {strategyInfo.ann_ret}%
          </p>
        </div>
        <div>
          <p className="text-xs text-neutral-500 mb-1">vs Benchmark</p>
          <p
            className={`text-xl font-semibold ${excessReturn >= 0 ? "text-success" : "text-danger"}`}
          >
            {excessReturn >= 0 ? "+" : ""}
            {excessReturn}%
          </p>
        </div>
        <div>
          <p className="text-xs text-neutral-500 mb-1">Volatility</p>
          <p className="text-xl font-semibold text-neutral-900">
            {strategyInfo.ann_vol}%
          </p>
        </div>
        <div>
          <p className="text-xs text-neutral-500 mb-1">Max Drawdown</p>
          <p className="text-xl font-semibold text-danger">
            {strategyInfo.mdd}%
          </p>
        </div>
      </div>

      {/* Current Allocation - Horizontal Bars */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h4 className="text-sm font-semibold text-neutral-700">
            Current Allocation
          </h4>
          {lastDate && (
            <span className="text-xs text-neutral-400">
              as of {lastDate}
            </span>
          )}
        </div>

        <div className="space-y-3">
          {sortedRebalData?.map((item, index) => {
            const percentage = item.weight * 100;
            const color = barColors[index % barColors.length];

            return (
              <div key={item.ticker} className="group">
                {/* Ticker info row */}
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <div
                      className="w-2.5 h-2.5 rounded-full"
                      style={{ backgroundColor: color }}
                    />
                    <span className="text-sm font-medium text-neutral-800">
                      {item.ticker}
                    </span>
                    <span className="text-xs text-neutral-400 hidden sm:inline">
                      {item.name}
                    </span>
                  </div>
                  <span className="text-sm font-semibold text-neutral-700">
                    {percentage.toFixed(1)}%
                  </span>
                </div>

                {/* Progress bar */}
                <div className="h-2.5 bg-neutral-100 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500 ease-out"
                    style={{
                      width: `${percentage}%`,
                      background: `linear-gradient(90deg, ${color}, ${color}dd)`,
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>

        {/* Total check */}
        {sortedRebalData.length > 0 && (
          <div className="mt-4 pt-3 border-t border-neutral-100 flex items-center justify-between">
            <span className="text-xs text-neutral-500">Total Allocation</span>
            <span className="text-sm font-semibold text-neutral-700">
              {(sortedRebalData.reduce((sum, item) => sum + item.weight, 0) * 100).toFixed(1)}%
            </span>
          </div>
        )}
      </div>
    </div>
  );
};

export default MetricSummary;
