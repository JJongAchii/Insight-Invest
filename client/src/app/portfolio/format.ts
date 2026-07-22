import { fmtJo } from "@/app/insight/format";

/** Native-currency price/value formatter (원 for KRW, $ for others). */
export const fmtNative = (
  value: number | null | undefined,
  currency: string
): string => {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  if (currency === "KRW") return `${Math.round(value).toLocaleString()}원`;
  return `$${value.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
};

/** Signed 조/억 KRW total, e.g. "+1.2조" / "-8,120억". */
export const fmtSignedJo = (v: number | null | undefined): string => {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const sign = v > 0 ? "+" : v < 0 ? "-" : "";
  return `${sign}${fmtJo(Math.abs(v))}`;
};

/** Fraction (0.12) → "+12.0%". */
export const fmtFracPct = (
  v: number | null | undefined,
  digits = 1
): string => {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const sign = v >= 0 ? "+" : "";
  return `${sign}${(v * 100).toFixed(digits)}%`;
};

/** Percent (already 0-100 scale, e.g. day_chg_pct), signed. */
export const fmtPctVal = (
  v: number | null | undefined,
  digits = 2
): string => {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const sign = v > 0 ? "+" : "";
  return `${sign}${v.toFixed(digits)}%`;
};

export const pnlDeltaType = (
  v: number | null | undefined
): "gain" | "loss" | "neutral" => {
  if (v === null || v === undefined || v === 0) return "neutral";
  return v > 0 ? "gain" : "loss";
};

/** num class colored by sign of a fraction/number (gains/losses). */
export const signClassNum = (v: number | null | undefined): string =>
  v === null || v === undefined || v === 0
    ? "num text-ink-secondary"
    : v > 0
      ? "metric-positive"
      : "metric-negative";

/** Small market badge derived from iso_code (KR/US). */
export const marketLabel = (iso: string): string =>
  iso === "KR" ? "KR" : iso === "US" ? "US" : iso;
