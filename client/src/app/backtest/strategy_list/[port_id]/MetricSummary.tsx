import React from "react";
import { Pie } from "react-chartjs-2";
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
  TooltipItem,
} from "chart.js";

ChartJS.register(ArcElement, Tooltip, Legend);

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

// Neutral color palette for pie chart
const pieColors = [
  "#171717",
  "#525252",
  "#737373",
  "#a3a3a3",
  "#d4d4d4",
  "#e5e5e5",
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

  const pieData = {
    labels: recentRebalData?.map((data) => data.ticker),
    datasets: [
      {
        label: "Weight",
        data: recentRebalData?.map((data) => data.weight),
        backgroundColor: pieColors,
        borderWidth: 0,
      },
    ],
  };

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
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6 p-4 bg-neutral-50 rounded-lg">
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

      {/* Allocation Chart */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <h4 className="text-sm font-semibold text-neutral-700 mb-4">
            Current Allocation
          </h4>
          <div style={{ height: "280px" }}>
            <Pie
              data={pieData}
              options={{
                maintainAspectRatio: false,
                plugins: {
                  legend: {
                    position: "right",
                    labels: {
                      padding: 12,
                      font: { size: 11 },
                      color: "#737373",
                      usePointStyle: true,
                      pointStyle: "circle",
                    },
                  },
                  tooltip: {
                    backgroundColor: "rgba(255, 255, 255, 0.98)",
                    titleColor: "#171717",
                    bodyColor: "#737373",
                    borderColor: "#e5e5e5",
                    borderWidth: 1,
                    padding: 10,
                    cornerRadius: 6,
                    callbacks: {
                      label: function (context: TooltipItem<"pie">) {
                        return `${context.label}: ${(context.parsed * 100).toFixed(1)}%`;
                      },
                    },
                  },
                },
              }}
            />
          </div>
        </div>
        <div>
          <h4 className="text-sm font-semibold text-neutral-700 mb-4">
            Holdings
          </h4>
          <div className="space-y-2">
            {recentRebalData?.map((item, index) => (
              <div
                key={item.ticker}
                className="flex items-center justify-between py-2 border-b border-neutral-100 last:border-0"
              >
                <div className="flex items-center gap-3">
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: pieColors[index % pieColors.length] }}
                  />
                  <div>
                    <p className="text-sm font-medium text-neutral-900">
                      {item.ticker}
                    </p>
                    <p className="text-xs text-neutral-500">{item.name}</p>
                  </div>
                </div>
                <span className="text-sm font-medium text-neutral-700">
                  {(item.weight * 100).toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default MetricSummary;
