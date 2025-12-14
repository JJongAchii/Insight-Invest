"use client";

import React, { useMemo } from "react";

interface SparklineChartProps {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
}

const SparklineChart: React.FC<SparklineChartProps> = ({
  data,
  width = 80,
  height = 24,
  color,
}) => {
  const { pathD, isPositive } = useMemo(() => {
    if (!data || data.length < 2) {
      return { pathD: "", isPositive: true };
    }

    const padding = 2;
    const chartWidth = width - padding * 2;
    const chartHeight = height - padding * 2;

    const minVal = Math.min(...data);
    const maxVal = Math.max(...data);
    const range = maxVal - minVal || 1;

    const points = data.map((val, i) => {
      const x = padding + (i / (data.length - 1)) * chartWidth;
      const y = padding + chartHeight - ((val - minVal) / range) * chartHeight;
      return { x, y };
    });

    const pathD = points
      .map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
      .join(" ");

    // Check if trend is positive (last > first)
    const isPositive = data[data.length - 1] >= data[0];

    return { pathD, isPositive };
  }, [data, width, height]);

  if (!data || data.length < 2) {
    return (
      <div
        className="flex items-center justify-center text-neutral-400 text-xs"
        style={{ width, height }}
      >
        —
      </div>
    );
  }

  const strokeColor = color || (isPositive ? "#22c55e" : "#ef4444");

  return (
    <svg width={width} height={height} className="overflow-visible">
      <path
        d={pathD}
        fill="none"
        stroke={strokeColor}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
};

export default SparklineChart;
