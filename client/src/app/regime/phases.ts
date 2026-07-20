import { RegimePhaseName } from "@/state/api";

/** Fixed phase → color mapping (entity-stable, never reassigned). */
export const PHASE_COLORS: Record<RegimePhaseName, string> = {
  Goldilocks: "var(--gains)",
  Reflation: "var(--chart-4)",
  Stagflation: "var(--losses)",
  Deflation: "var(--chart-2)",
};

/** Canonical display order for legends/tabs. */
export const PHASE_ORDER: RegimePhaseName[] = [
  "Goldilocks",
  "Reflation",
  "Stagflation",
  "Deflation",
];

/** Growth/inflation direction caption per phase. */
export const PHASE_AXES: Record<RegimePhaseName, string> = {
  Goldilocks: "성장 ↑ · 물가 ↓",
  Reflation: "성장 ↑ · 물가 ↑",
  Stagflation: "성장 ↓ · 물가 ↑",
  Deflation: "성장 ↓ · 물가 ↓",
};

/** color-mix tint helper for phase backgrounds. */
export const phaseTint = (phase: RegimePhaseName, pct: number) =>
  `color-mix(in srgb, ${PHASE_COLORS[phase]} ${pct}%, transparent)`;
