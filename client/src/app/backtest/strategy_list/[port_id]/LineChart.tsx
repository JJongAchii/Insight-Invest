import React from "react";
import { Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  LineElement,
  CategoryScale,
  LinearScale,
  PointElement,
  Tooltip,
  Filler,
} from "chart.js";

ChartJS.register(
  LineElement,
  CategoryScale,
  LinearScale,
  PointElement,
  Tooltip,
  Filler
);

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
  const bmNavData: BmNavData[] = bmNav ? JSON.parse(bmNav) : [];

  return (
    <div className="card">
      <h4 className="text-base font-semibold text-neutral-900 mb-4">
        Cumulative Performance
      </h4>
      <div style={{ height: "400px" }}>
        <Line
          data={{
            labels: strategyNav?.map((nav) => nav.trade_date),
            datasets: [
              {
                label: strategyName,
                data: strategyNav?.map((nav) => nav.value),
                fill: true,
                backgroundColor: "rgba(124, 91, 255, 0.1)",
                borderColor: "#7C5BFF",
                tension: 0.3,
                pointRadius: 0,
                pointHoverRadius: 4,
                borderWidth: 2,
              },
              {
                label: "Benchmark",
                data: bmNavData?.map((nav) => nav.value),
                fill: false,
                borderColor: "#94A3B8",
                tension: 0.3,
                pointRadius: 0,
                pointHoverRadius: 4,
                borderWidth: 1.5,
                borderDash: [4, 4],
              },
            ],
          }}
          options={{
            responsive: true,
            maintainAspectRatio: false,
            scales: {
              x: {
                display: true,
                grid: { display: false },
                ticks: {
                  color: "#a3a3a3",
                  font: { size: 10 },
                  maxRotation: 0,
                  autoSkip: true,
                  maxTicksLimit: 10,
                },
              },
              y: {
                display: true,
                grid: {
                  color: "rgba(124, 91, 255, 0.08)",
                  lineWidth: 1,
                },
                ticks: {
                  color: "#a3a3a3",
                  font: { size: 10 },
                },
              },
            },
            plugins: {
              legend: {
                display: true,
                position: "top",
                align: "end",
                labels: {
                  color: "#525252",
                  font: { size: 12, weight: 500 },
                  padding: 16,
                  usePointStyle: true,
                  pointStyle: "circle",
                  boxWidth: 8,
                  boxHeight: 8,
                },
              },
              tooltip: {
                enabled: true,
                backgroundColor: "rgba(255, 255, 255, 0.95)",
                titleColor: "#171717",
                bodyColor: "#525252",
                borderColor: "rgba(124, 91, 255, 0.2)",
                borderWidth: 1,
                padding: 12,
                cornerRadius: 12,
                callbacks: {
                  label: (context) =>
                    `${context.dataset.label}: ${(context.raw as number).toFixed(2)}`,
                  title: (context) => context[0].label,
                },
              },
            },
            hover: {
              mode: "nearest",
              intersect: false,
            },
          }}
        />
      </div>
    </div>
  );
};

export default LineChart;
