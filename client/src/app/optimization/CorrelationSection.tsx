"use client";

import React, { useMemo } from "react";
import Select, { SingleValue } from "react-select";

import { CorrelationResponse } from "@/state/api";
import Card from "@/components/ui/Card";
import InfoTip from "@/components/ui/InfoTip";
import EmptyState from "@/components/ui/EmptyState";
import TimeSeriesChart from "@/components/charts/TimeSeriesChart";
import { tokenSelectStyles } from "@/components/ui/selectStyles";

export interface CorrelationAsset {
  meta_id: number;
  ticker: string;
}

interface PairOption {
  value: number;
  label: string;
}

interface CorrelationSectionProps {
  data: CorrelationResponse;
  /** Selected assets in matrix order (meta_id ↔ data.tickers[i]). */
  assets: CorrelationAsset[];
  /** Currently requested rolling pair as meta_ids [a, b]. */
  rollingPair: [number, number] | null;
  onPairChange: (pair: [number, number]) => void;
  isRollingLoading?: boolean;
}

/**
 * Diverging cell tint: warm (chart-5) for high positive correlation,
 * cool (chart-2) for negative, fading to transparent at 0.
 */
const cellBackground = (v: number): string => {
  const pole = v >= 0 ? "var(--chart-5)" : "var(--chart-2)";
  const pct = Math.round(Math.min(1, Math.abs(v)) * 65);
  return `color-mix(in srgb, ${pole} ${pct}%, transparent)`;
};

/** Correlation matrix heatmap + rolling pair correlation chart. */
const CorrelationSection: React.FC<CorrelationSectionProps> = ({
  data,
  assets,
  rollingPair,
  onPairChange,
  isRollingLoading = false,
}) => {
  const { tickers, matrix, rolling } = data;
  const n = tickers.length;

  const pairOptions: PairOption[] = useMemo(
    () => assets.map((a) => ({ value: a.meta_id, label: a.ticker })),
    [assets]
  );

  const pairA = rollingPair
    ? (pairOptions.find((o) => o.value === rollingPair[0]) ?? null)
    : null;
  const pairB = rollingPair
    ? (pairOptions.find((o) => o.value === rollingPair[1]) ?? null)
    : null;

  const handlePairSelect = (side: 0 | 1, opt: SingleValue<PairOption>) => {
    if (!opt || !rollingPair) return;
    const next: [number, number] = [...rollingPair];
    next[side] = opt.value;
    if (next[0] === next[1]) return; // same asset on both sides — ignore
    onPairChange(next);
  };

  const rollingData = useMemo(
    () => (rolling?.series ?? []).map((p) => ({ date: p.date, corr: p.value })),
    [rolling]
  );

  const rollingLabel = rolling
    ? `${rolling.pair[0]}–${rolling.pair[1]} 60D corr`
    : "60D corr";

  return (
    <div className="space-y-6">
      {/* Matrix heatmap */}
      <Card
        title={
          <span className="inline-flex items-center gap-1.5">
            Correlation Matrix
            <InfoTip helpKey="opt.correlation" />
          </span>
        }
        action={
          data.as_of && (
            <span className="text-xs text-ink-muted num">as of {data.as_of}</span>
          )
        }
      >
        {n === 0 ? (
          <EmptyState title="No correlation data" />
        ) : (
          <div className="overflow-x-auto">
            <div
              className="grid gap-px min-w-max"
              style={{
                gridTemplateColumns: `minmax(64px, auto) repeat(${n}, minmax(56px, 1fr))`,
              }}
            >
              {/* Header row */}
              <div />
              {tickers.map((t) => (
                <div
                  key={`col-${t}`}
                  className="px-2 py-1.5 text-xs font-medium text-ink-secondary text-center truncate"
                  title={t}
                >
                  {t}
                </div>
              ))}

              {matrix.map((row, i) => (
                <React.Fragment key={`row-${tickers[i]}`}>
                  <div
                    className="px-2 py-1.5 text-xs font-medium text-ink-secondary text-right truncate"
                    title={tickers[i]}
                  >
                    {tickers[i]}
                  </div>
                  {row.map((v, j) => {
                    const isDiag = i === j;
                    return (
                      <div
                        key={`cell-${i}-${j}`}
                        className={`px-2 py-1.5 rounded-sm text-center num text-xs ${
                          isDiag ? "bg-raised text-ink-muted" : "text-ink"
                        }`}
                        style={
                          !isDiag && v !== null
                            ? { backgroundColor: cellBackground(v) }
                            : undefined
                        }
                        title={
                          v !== null
                            ? `${tickers[i]}–${tickers[j]}: ${v.toFixed(2)}`
                            : `${tickers[i]}–${tickers[j]}: n/a`
                        }
                      >
                        {v === null ? "—" : v.toFixed(2)}
                      </div>
                    );
                  })}
                </React.Fragment>
              ))}
            </div>

            {/* Diverging legend */}
            <div className="flex items-center gap-2 mt-4 text-xs text-ink-muted">
              <span className="num">−1</span>
              <span
                className="h-2 w-40 rounded-full"
                style={{
                  background:
                    "linear-gradient(to right, color-mix(in srgb, var(--chart-2) 65%, transparent), transparent 50%, color-mix(in srgb, var(--chart-5) 65%, transparent))",
                }}
                aria-hidden
              />
              <span className="num">+1</span>
            </div>
          </div>
        )}
      </Card>

      {/* Rolling correlation */}
      <Card
        title={
          <span className="inline-flex items-center gap-1.5">
            Rolling Correlation
            <InfoTip helpKey="opt.rolling_corr" />
          </span>
        }
        action={
          <div className="flex items-center gap-2">
            <div className="w-32">
              <Select<PairOption>
                options={pairOptions.filter((o) => o.value !== pairB?.value)}
                value={pairA}
                onChange={(opt) => handlePairSelect(0, opt)}
                styles={tokenSelectStyles}
                isDisabled={isRollingLoading}
                aria-label="Rolling pair asset A"
              />
            </div>
            <span className="text-xs text-ink-muted">vs</span>
            <div className="w-32">
              <Select<PairOption>
                options={pairOptions.filter((o) => o.value !== pairA?.value)}
                value={pairB}
                onChange={(opt) => handlePairSelect(1, opt)}
                styles={tokenSelectStyles}
                isDisabled={isRollingLoading}
                aria-label="Rolling pair asset B"
              />
            </div>
          </div>
        }
      >
        {!rolling || rollingData.length === 0 ? (
          <EmptyState
            title="No rolling correlation data"
            hint="두 자산을 선택하면 롤링 상관이 표시됩니다"
          />
        ) : (
          <TimeSeriesChart
            data={rollingData}
            series={[
              { key: "corr", name: rollingLabel, color: "var(--chart-1)" },
            ]}
            height={280}
            baseline={0}
            yFormatter={(v) => v.toFixed(2)}
          />
        )}
      </Card>
    </div>
  );
};

export default CorrelationSection;
