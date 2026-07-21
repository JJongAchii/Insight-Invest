import React from "react";
import InfoTip from "./InfoTip";

interface StatTileProps {
  label: React.ReactNode;
  value: React.ReactNode;
  delta?: React.ReactNode;
  deltaType?: "gain" | "loss" | "neutral";
  sub?: React.ReactNode;
  /** INDICATOR_HELP key; renders an InfoTip next to the label. */
  helpKey?: string;
}

/** Metric tile: uppercase label + tabular mono value, optional colored delta and sub line. */
const StatTile: React.FC<StatTileProps> = ({
  label,
  value,
  delta,
  deltaType = "neutral",
  sub,
  helpKey,
}) => {
  const deltaClass =
    deltaType === "gain"
      ? "metric-positive"
      : deltaType === "loss"
        ? "metric-negative"
        : "num text-ink-secondary font-medium";

  // When no separate delta is provided, a non-neutral deltaType colors the value itself.
  const valueClass =
    delta === undefined && deltaType === "gain"
      ? "metric-value text-gains"
      : delta === undefined && deltaType === "loss"
        ? "metric-value text-losses"
        : "metric-value";

  return (
    <div className="p-4 bg-raised rounded-xl border border-edge">
      <p className="metric-label mb-1 flex items-center gap-1">
        <span>{label}</span>
        {helpKey && <InfoTip helpKey={helpKey} />}
      </p>
      <div className="flex items-baseline gap-2">
        <p className={valueClass}>{value}</p>
        {delta !== undefined && delta !== null && (
          <span className={`text-sm ${deltaClass}`}>{delta}</span>
        )}
      </div>
      {sub && <p className="text-xs text-ink-muted mt-1">{sub}</p>}
    </div>
  );
};

export default StatTile;
