"use client";

import React from "react";

export interface WeightBarItem {
  label: string;
  /** 0..1 */
  value: number;
  color?: string;
  /** Optional secondary text next to the label (e.g. full name). */
  sub?: string;
}

export interface WeightBarProps {
  items: WeightBarItem[];
}

const DEFAULT_COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
  "var(--chart-6)",
];

/** Horizontal allocation bar list with tabular-mono values right-aligned. */
const WeightBar: React.FC<WeightBarProps> = ({ items }) => {
  return (
    <div className="space-y-3">
      {items.map((item, index) => {
        const percentage = item.value * 100;
        const color = item.color ?? DEFAULT_COLORS[index % DEFAULT_COLORS.length];

        return (
          <div key={`${item.label}-${index}`}>
            <div className="flex items-center justify-between mb-1.5">
              <div className="flex items-center gap-2">
                <div
                  className="w-2.5 h-2.5 rounded-full"
                  style={{ backgroundColor: color }}
                />
                <span className="text-sm font-medium text-ink">
                  {item.label}
                </span>
                {item.sub && (
                  <span className="text-xs text-ink-muted hidden sm:inline">
                    {item.sub}
                  </span>
                )}
              </div>
              <span className="num text-sm font-semibold text-ink-secondary">
                {percentage.toFixed(1)}%
              </span>
            </div>
            <div className="h-2.5 bg-raised rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500 ease-out"
                style={{
                  width: `${Math.max(0, Math.min(100, percentage))}%`,
                  background: `linear-gradient(90deg, ${color}, ${color})`,
                  opacity: 0.9,
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default WeightBar;
