"use client";

import React from "react";
import { FactorExposureRow } from "@/state/api";
import { FACTOR_COLORS, FACTOR_NAMES_KR, FACTOR_ORDER } from "@/content/factors";

interface FactorBarsProps {
  exposures: FactorExposureRow[];
  /** Tighter spacing/typography for inline use (e.g. stock detail). */
  compact?: boolean;
}

/**
 * Horizontal 0–100 percentile bars, one per style factor, in canonical order.
 * A faint center tick marks the 50th percentile (market-average exposure).
 */
const FactorBars: React.FC<FactorBarsProps> = ({ exposures, compact = false }) => {
  const byFactor = new Map(exposures.map((e) => [e.factor, e]));
  const barH = compact ? "h-2" : "h-2.5";
  const gap = compact ? "space-y-2" : "space-y-3";

  return (
    <div className={gap}>
      {FACTOR_ORDER.map((factor) => {
        const row = byFactor.get(factor);
        if (!row) return null;
        const pct = Math.max(0, Math.min(100, row.percentile));
        const color = FACTOR_COLORS[factor];
        return (
          <div key={factor}>
            <div className="flex items-center justify-between mb-1">
              <span
                className={`font-medium text-ink ${
                  compact ? "text-xs" : "text-sm"
                }`}
              >
                {FACTOR_NAMES_KR[factor]}
              </span>
              <span
                className={`num font-semibold text-ink-secondary ${
                  compact ? "text-xs" : "text-sm"
                }`}
              >
                {Math.round(pct)}
                <span className="text-ink-muted text-[10px] ml-0.5">%ile</span>
              </span>
            </div>
            <div
              className={`relative w-full ${barH} bg-raised rounded-full overflow-hidden`}
            >
              {/* 50th-percentile reference tick */}
              <div
                className="absolute inset-y-0 w-px bg-edge-strong"
                style={{ left: "50%" }}
                aria-hidden
              />
              <div
                className="h-full rounded-full transition-all duration-500 ease-out"
                style={{ width: `${pct}%`, backgroundColor: color, opacity: 0.9 }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default FactorBars;
