"use client";

import React, { useMemo } from "react";

interface RiskContributionChartProps {
  data: Record<string, number>;
  title: string;
}

const RiskContributionChart: React.FC<RiskContributionChartProps> = ({
  data,
  title,
}) => {
  const { sortedData, total, maxContrib } = useMemo(() => {
    const sorted = Object.entries(data).sort((a, b) => b[1] - a[1]);
    const totalRisk = sorted.reduce((sum, [, value]) => sum + Math.abs(value), 0);
    const max = Math.max(...sorted.map(([, v]) => Math.abs(v)));
    return { sortedData: sorted, total: totalRisk, maxContrib: max };
  }, [data]);

  const colors = [
    "from-violet-400 to-violet-500",
    "from-blue-400 to-blue-500",
    "from-cyan-400 to-cyan-500",
    "from-emerald-400 to-emerald-500",
    "from-amber-400 to-amber-500",
    "from-rose-400 to-rose-500",
    "from-purple-400 to-purple-500",
    "from-indigo-400 to-indigo-500",
  ];

  return (
    <div className="card">
      <h3 className="text-base font-semibold text-neutral-900 mb-4">{title}</h3>

      {/* Summary */}
      <div className="flex gap-4 mb-5 text-sm">
        <div className="px-3 py-2 bg-neutral-50 rounded-lg">
          <span className="text-neutral-500">Total Risk: </span>
          <span className="font-medium text-neutral-900">
            {(total * 100).toFixed(2)}%
          </span>
        </div>
        <div className="px-3 py-2 bg-neutral-50 rounded-lg">
          <span className="text-neutral-500">Assets: </span>
          <span className="font-medium text-neutral-900">{sortedData.length}</span>
        </div>
      </div>

      {/* Bar Chart */}
      <div className="space-y-3">
        {sortedData.map(([ticker, value], index) => {
          const percentage = (Math.abs(value) / total) * 100;
          const barWidth = (Math.abs(value) / maxContrib) * 100;
          const colorClass = colors[index % colors.length];

          return (
            <div key={ticker} className="flex items-center gap-3">
              <span className="w-14 text-sm font-medium text-neutral-700">
                {ticker}
              </span>
              <div className="flex-1 h-7 bg-neutral-100 rounded-lg overflow-hidden relative">
                <div
                  className={`h-full bg-gradient-to-r ${colorClass} rounded-lg transition-all duration-500`}
                  style={{ width: `${barWidth}%` }}
                />
                <span className="absolute inset-0 flex items-center justify-center text-xs font-medium text-neutral-700">
                  {percentage.toFixed(1)}%
                </span>
              </div>
              <span className="w-20 text-xs text-neutral-500 text-right">
                {(value * 100).toFixed(3)}%
              </span>
            </div>
          );
        })}
      </div>

      {/* Equal distribution indicator for Risk Parity */}
      <div className="mt-4 pt-4 border-t border-neutral-100">
        <div className="flex items-center justify-between text-xs text-neutral-500">
          <span>Equal contribution target:</span>
          <span className="font-medium">
            {((total / sortedData.length) * 100).toFixed(3)}% each
          </span>
        </div>
      </div>
    </div>
  );
};

export default RiskContributionChart;
