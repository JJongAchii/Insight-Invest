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
                backgroundColor: "rgba(23, 23, 23, 0.05)",
                borderColor: "#171717",
                tension: 0.3,
                pointRadius: 0,
                pointHoverRadius: 4,
                borderWidth: 2,
              },
              {
                label: "Benchmark",
                data: bmNavData?.map((nav) => nav.value),
                fill: false,
                borderColor: "#a3a3a3",
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
                  color: "rgba(0, 0, 0, 0.04)",
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
                  color: "#737373",
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
                backgroundColor: "rgba(255, 255, 255, 0.98)",
                titleColor: "#171717",
                bodyColor: "#737373",
                borderColor: "#e5e5e5",
                borderWidth: 1,
                padding: 10,
                cornerRadius: 6,
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
