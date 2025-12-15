"use client";

import React, { useMemo } from "react";
import {
  Chart as ChartJS,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
  ChartOptions,
} from "chart.js";
import { Scatter } from "react-chartjs-2";
import { EfficientFrontierResponse } from "@/state/api";

ChartJS.register(LinearScale, PointElement, LineElement, Tooltip, Legend);

interface EfficientFrontierChartProps {
  data: EfficientFrontierResponse;
}

const EfficientFrontierChart: React.FC<EfficientFrontierChartProps> = ({
  data,
}) => {
  const chartData = useMemo(() => {
    // Frontier line points
    const frontierPoints = data.frontier_points.map((p) => ({
      x: p.volatility * 100,
      y: p.return * 100,
    }));

    // Individual asset points
    const assetPoints = Object.entries(data.asset_stats).map(
      ([ticker, stats]) => ({
        x: stats.volatility * 100,
        y: stats.expected_return * 100,
        label: ticker,
      })
    );

    return {
      datasets: [
        {
          label: "Efficient Frontier",
          data: frontierPoints,
          borderColor: "rgb(124, 91, 255)",
          backgroundColor: "rgba(124, 91, 255, 0.1)",
          showLine: true,
          fill: false,
          pointRadius: 2,
          borderWidth: 2,
          tension: 0.4,
          order: 2,
        },
        {
          label: "Max Sharpe",
          data: [
            {
              x: data.max_sharpe.volatility * 100,
              y: data.max_sharpe.expected_return * 100,
            },
          ],
          backgroundColor: "rgb(16, 185, 129)",
          borderColor: "rgb(5, 150, 105)",
          borderWidth: 4,
          pointRadius: 12,
          pointHoverRadius: 14,
          pointStyle: "rectRot" as const,
          order: 0,
        },
        {
          label: "Min Volatility",
          data: [
            {
              x: data.min_volatility.volatility * 100,
              y: data.min_volatility.expected_return * 100,
            },
          ],
          backgroundColor: "rgb(245, 158, 11)",
          borderColor: "rgb(255, 255, 255)",
          borderWidth: 2,
          pointRadius: 12,
          pointHoverRadius: 14,
          pointStyle: "triangle" as const,
          order: 0,
        },
        {
          label: "Individual Assets",
          data: assetPoints,
          backgroundColor: "rgb(100, 116, 139)",
          pointRadius: 8,
          order: 1,
        },
      ],
    };
  }, [data]);

  const options: ChartOptions<"scatter"> = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      x: {
        title: {
          display: true,
          text: "Volatility (%)",
          font: { size: 12, weight: "bold" },
        },
        grid: { color: "rgba(124, 91, 255, 0.08)" },
      },
      y: {
        title: {
          display: true,
          text: "Expected Return (%)",
          font: { size: 12, weight: "bold" },
        },
        grid: { color: "rgba(124, 91, 255, 0.08)" },
      },
    },
    plugins: {
      tooltip: {
        callbacks: {
          label: (context) => {
            const point = context.raw as { x: number; y: number; label?: string };
            const label = point.label ? `${point.label}: ` : "";
            return `${label}Return: ${point.y.toFixed(2)}%, Vol: ${point.x.toFixed(2)}%`;
          },
        },
      },
      legend: {
        position: "top" as const,
        labels: {
          usePointStyle: true,
          padding: 20,
        },
      },
    },
  };

  return (
    <div className="card">
      <h3 className="text-base font-semibold text-neutral-900 mb-4">
        Efficient Frontier
      </h3>
      <div style={{ height: 400 }}>
        <Scatter data={chartData} options={options} />
      </div>
      <div className="mt-4 text-xs text-neutral-500 flex gap-6">
        <span className="flex items-center gap-2">
          <span className="w-3 h-3 bg-emerald-500 rotate-45"></span>
          Max Sharpe: {(data.max_sharpe.sharpe_ratio).toFixed(2)}
        </span>
        <span className="flex items-center gap-2">
          <span className="w-0 h-0 border-l-[6px] border-r-[6px] border-b-[10px] border-l-transparent border-r-transparent border-b-amber-500"></span>
          Min Vol: {(data.min_volatility.volatility * 100).toFixed(2)}%
        </span>
      </div>
    </div>
  );
};

export default EfficientFrontierChart;
