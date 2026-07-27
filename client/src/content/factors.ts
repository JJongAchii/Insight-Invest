import { FactorName } from "@/state/api";

/** Display order for the 4 style factors (모멘텀·가치·소형·저변동). */
export const FACTOR_ORDER: FactorName[] = [
  "momentum",
  "value",
  "size",
  "lowvol",
];

/** Korean display names. */
export const FACTOR_NAMES_KR: Record<FactorName, string> = {
  momentum: "모멘텀",
  value: "가치",
  size: "소형",
  lowvol: "저변동",
};

/** Stable categorical color per factor (chart-1..4). */
export const FACTOR_COLORS: Record<FactorName, string> = {
  momentum: "var(--chart-1)",
  value: "var(--chart-2)",
  size: "var(--chart-3)",
  lowvol: "var(--chart-4)",
};
