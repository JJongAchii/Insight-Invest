import React from "react";

/** Format a raw KRW net value as signed 억 with commas, e.g. "+3,138억". */
export const fmtEok = (v: number | null | undefined): string => {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const eok = Math.round(v / 1e8);
  const sign = eok > 0 ? "+" : "";
  return `${sign}${eok.toLocaleString()}억`;
};

/** Format an 억-denominated value compactly for chart axes (조 above 1만억). */
export const fmtEokAxis = (eok: number): string => {
  if (Math.abs(eok) >= 1e4) return `${(eok / 1e4).toFixed(1)}조`;
  return `${Math.round(eok).toLocaleString()}억`;
};

/** Format a raw KRW market cap as 조/억, e.g. "412.4조" / "8,120억". */
export const fmtJo = (v: number | null | undefined): string => {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const eok = v / 1e8;
  if (Math.abs(eok) >= 1e4) return `${(eok / 1e4).toFixed(1)}조`;
  return `${Math.round(eok).toLocaleString()}억`;
};

/** Signed percentage, e.g. "+1.24%". */
export const fmtPct = (
  v: number | null | undefined,
  digits = 2
): string => {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(digits)}%`;
};

/** num class colored by sign (gains/losses). */
export const signClass = (v: number | null | undefined): string =>
  v === null || v === undefined || v === 0
    ? "num text-ink-secondary"
    : v > 0
      ? "metric-positive"
      : "metric-negative";

interface SegmentedProps<T extends string> {
  options: { id: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
  size?: "sm" | "md";
}

/** Token-styled segmented control (tabs/pills), matching the regime page style. */
export function Segmented<T extends string>({
  options,
  value,
  onChange,
  size = "sm",
}: SegmentedProps<T>) {
  const pad = size === "sm" ? "px-3 py-1.5 text-xs" : "px-4 py-2 text-sm";
  return (
    <div className="flex items-center gap-1 p-1 rounded-xl bg-raised border border-edge">
      {options.map((o) => (
        <button
          key={o.id}
          onClick={() => onChange(o.id)}
          className={`${pad} rounded-lg font-medium transition-colors ${
            value === o.id
              ? "bg-surface text-ink shadow-sm"
              : "text-ink-secondary hover:text-ink"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** Small KOSPI/KOSDAQ market badge. */
export const MarketBadge: React.FC<{ market: string }> = ({ market }) => (
  <span
    className="badge-neutral"
    style={{
      color: market === "KOSPI" ? "var(--chart-1)" : "var(--chart-2)",
    }}
  >
    {market}
  </span>
);
