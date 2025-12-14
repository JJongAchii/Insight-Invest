import React from "react";
import { Line } from "react-chartjs-2";
import { ChartOptions, TooltipItem } from "chart.js";
import "chart.js/auto";

interface NavData {
  index: number[];
  columns: string[];
  data: number[][];
}

interface StrategyChartProps {
  navResult: string | null;
}

// Chart color palette - pastel colors for strategy differentiation
const chartColors = [
  "#7C5BFF", // Lavender (Strategy 1)
  "#38BDF8", // Sky Blue (Strategy 2)
  "#10B981", // Emerald (Strategy 3)
  "#F59E0B", // Amber (Strategy 4)
  "#EC4899", // Pink (Strategy 5)
  "#14B8A6", // Teal (Strategy 6)
];

const StrategyChart: React.FC<StrategyChartProps> = ({ navResult }) => {
  const navData: NavData = navResult
    ? JSON.parse(navResult)
    : { index: [], columns: [], data: [] };

  const chartLabels = navData.index.map(
    (date: number) => new Date(date).toISOString().split("T")[0]
  );

  const datasets = navData.columns.map((column: string, index: number) => ({
    label: column,
    data: navData.data.map((row: number[]) => row[index]),
    borderColor: chartColors[index % chartColors.length],
    backgroundColor: `${chartColors[index % chartColors.length]}10`,
    borderWidth: 2,
    tension: 0.3,
    pointRadius: 0,
    pointHoverRadius: 4,
    hoverBorderWidth: 2,
  }));

  const data = {
    labels: chartLabels,
    datasets: datasets,
  };

  const options: ChartOptions<"line"> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: true,
        position: "top",
        align: "end",
        labels: {
          color: "#737373",
          font: {
            size: 12,
            weight: 500,
          },
          boxWidth: 8,
          boxHeight: 8,
          padding: 16,
          usePointStyle: true,
          pointStyle: "circle",
        },
      },
      tooltip: {
        mode: "index" as const,
        intersect: false,
        backgroundColor: "rgba(255, 255, 255, 0.95)",
        titleColor: "#171717",
        bodyColor: "#525252",
        borderColor: "rgba(124, 91, 255, 0.2)",
        borderWidth: 1,
        titleFont: {
          size: 12,
          weight: 600,
        },
        bodyFont: {
          size: 11,
        },
        padding: 12,
        cornerRadius: 12,
        displayColors: true,
        callbacks: {
          labelColor: function (context: TooltipItem<"line">) {
            return {
              borderColor: context.dataset.borderColor as string,
              backgroundColor: context.dataset.borderColor as string,
              borderWidth: 2,
              borderRadius: 2,
            };
          },
        },
      },
    },
    scales: {
      x: {
        grid: {
          display: false,
        },
        ticks: {
          color: "#a3a3a3",
          font: {
            size: 10,
          },
          maxRotation: 0,
          autoSkip: true,
          maxTicksLimit: 10,
        },
      },
      y: {
        grid: {
          color: "rgba(124, 91, 255, 0.08)",
          lineWidth: 1,
        },
        ticks: {
          color: "#a3a3a3",
          font: {
            size: 10,
          },
          callback: (tickValue: string | number) => {
            if (typeof tickValue === "number") {
              return tickValue.toFixed(2);
            }
            return tickValue;
          },
        },
      },
    },
    interaction: {
      mode: "nearest" as const,
      axis: "x",
      intersect: false,
    },
    animation: {
      duration: 400,
      easing: "easeOutQuart",
    },
  };

  return (
    <div className="card">
      <h3 className="text-base font-semibold text-neutral-900 mb-4">
        Performance Chart
      </h3>
      <div className="relative" style={{ height: 400 }}>
        {navResult ? (
          <Line data={data} options={options} />
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <p className="text-neutral-400 text-sm">No data available</p>
            <p className="text-neutral-400 text-xs mt-1">
              Run a backtest to see performance
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default StrategyChart;
