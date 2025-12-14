"use client";

import React, { useEffect, useState } from "react";
import { Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
  TooltipItem,
} from "chart.js";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

interface MacroData {
  macro_id: string;
  base_date: string;
  value: number;
}

interface MacroChartProps {
  primaryData: MacroData[];
  recessionData: MacroData[];
  primaryLabel: string;
  recessionLabel: string;
  title: string;
  baseline?: number;
}

const MacroChart: React.FC<MacroChartProps> = ({
  primaryData,
  recessionData,
  primaryLabel,
  recessionLabel,
  title,
  baseline = 0,
}) => {
  const [pluginsLoaded, setPluginsLoaded] = useState(false);

  useEffect(() => {
    const loadPlugins = async () => {
      const [{ default: annotationPlugin }, { default: zoomPlugin }] =
        await Promise.all([
          import("chartjs-plugin-annotation"),
          import("chartjs-plugin-zoom"),
        ]);
      ChartJS.register(annotationPlugin, zoomPlugin);
      setPluginsLoaded(true);
    };
    loadPlugins();
  }, []);

  if (!pluginsLoaded) return null;

  const mappedRecessionData = primaryData?.map((primary) => {
    const matchingRecession = recessionData?.find(
      (recession) => recession.base_date === primary.base_date
    );
    return matchingRecession ? matchingRecession.value : null;
  });

  // Get latest value for display
  const latestValue = primaryData?.[primaryData.length - 1]?.value;

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-base font-semibold text-neutral-900">{title}</h4>
        {latestValue !== undefined && (
          <span className="text-sm font-medium text-neutral-600">
            Latest: {latestValue.toFixed(2)}
          </span>
        )}
      </div>
      <div style={{ height: "300px" }}>
        <Line
          data={{
            labels: primaryData?.map((data) => data.base_date),
            datasets: [
              {
                label: primaryLabel,
                data: primaryData?.map((data) => data.value),
                borderColor: "#7C5BFF",
                backgroundColor: "rgba(124, 91, 255, 0.1)",
                borderWidth: 2,
                pointRadius: 0,
                pointHoverRadius: 4,
                tension: 0.3,
                yAxisID: "left-axis",
              },
              {
                label: recessionLabel,
                data: mappedRecessionData,
                backgroundColor: "rgba(248, 113, 113, 0.15)",
                borderColor: "rgba(248, 113, 113, 0)",
                fill: true,
                tension: 0.3,
                yAxisID: "right-axis",
              },
            ],
          }}
          options={{
            responsive: true,
            maintainAspectRatio: false,
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
                backgroundColor: "rgba(255, 255, 255, 0.95)",
                titleColor: "#171717",
                bodyColor: "#525252",
                borderColor: "rgba(124, 91, 255, 0.2)",
                borderWidth: 1,
                padding: 12,
                cornerRadius: 12,
                boxPadding: 4,
                usePointStyle: true,
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
              zoom: {
                zoom: {
                  wheel: { enabled: true },
                  pinch: { enabled: true },
                  mode: "x",
                },
                pan: {
                  enabled: true,
                  mode: "x",
                },
              },
              annotation: {
                annotations: {
                  baselineLine: {
                    type: "line",
                    yMin: baseline,
                    yMax: baseline,
                    borderColor: "#F87171",
                    borderWidth: 1.5,
                    borderDash: [4, 4],
                  },
                },
              },
            },
            scales: {
              "left-axis": {
                type: "linear",
                position: "left",
                grid: {
                  drawOnChartArea: true,
                  color: (context) =>
                    context.tick.value === baseline
                      ? "rgba(248, 113, 113, 0.2)"
                      : "rgba(124, 91, 255, 0.08)",
                  lineWidth: (context) =>
                    context.tick.value === baseline ? 1.5 : 1,
                },
                ticks: {
                  font: { size: 10 },
                  color: "#a3a3a3",
                },
              },
              "right-axis": {
                type: "linear",
                position: "right",
                grid: { drawOnChartArea: false },
                min: 0,
                max: 1,
                ticks: { display: false },
              },
              x: {
                grid: { display: false },
                ticks: {
                  font: { size: 10 },
                  color: "#a3a3a3",
                  maxRotation: 0,
                  autoSkip: true,
                  maxTicksLimit: 12,
                },
              },
            },
            interaction: { mode: "nearest", intersect: false },
          }}
        />
      </div>
    </div>
  );
};

export default MacroChart;
