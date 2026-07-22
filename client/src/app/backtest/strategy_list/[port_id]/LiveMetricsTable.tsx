import React from "react";
import InfoTip from "@/components/ui/InfoTip";
import EmptyState from "@/components/ui/EmptyState";
import { MetricSet, StrategyLiveResponse } from "@/state/api";

interface MetricRowDef {
  key: keyof MetricSet;
  label: string;
  format: "pct" | "num";
  /** Direction in which a larger value is better (MDD is negative → larger = shallower = better). */
  higherIsBetter: boolean;
}

const ROWS: MetricRowDef[] = [
  { key: "ann_ret", label: "Return", format: "pct", higherIsBetter: true },
  { key: "ann_vol", label: "Vol", format: "pct", higherIsBetter: false },
  { key: "sharpe", label: "Sharpe", format: "num", higherIsBetter: true },
  { key: "sortino", label: "Sortino", format: "num", higherIsBetter: true },
  { key: "mdd", label: "MDD", format: "pct", higherIsBetter: true },
];

const formatValue = (value: unknown, format: "pct" | "num"): string => {
  if (typeof value !== "number" || Number.isNaN(value)) return "—";
  return format === "pct" ? `${value.toFixed(2)}%` : value.toFixed(2);
};

/** 저장일 이후 실전(Live) 지표 vs 백테스트 지표 비교 테이블. */
const LiveMetricsTable = ({ live }: { live?: StrategyLiveResponse }) => {
  const nav = live?.nav ?? [];

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-base font-semibold text-ink">
          <span className="inline-flex items-center gap-1.5">
            지표 비교 — Backtest vs Live
            <InfoTip helpKey="bt.live" />
          </span>
        </h4>
        {nav.length > 0 && (
          <span className="text-xs text-ink-muted">
            저장 후 {nav.length}일{live?.as_of ? ` · as_of ${live.as_of}` : ""}
          </span>
        )}
      </div>

      {nav.length === 0 ? (
        <EmptyState
          title="실전 추적 준비 중"
          hint="다음 데일리 파이프라인 실행 후 표시됩니다"
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="table-header">
                <th className="py-2.5 px-4 text-left rounded-l-lg">Metric</th>
                <th className="py-2.5 px-4 text-right">Backtest</th>
                <th className="py-2.5 px-4 text-right">Live (저장 후)</th>
                <th className="py-2.5 px-4 text-right rounded-r-lg">Δ</th>
              </tr>
            </thead>
            <tbody>
              {ROWS.map((row) => {
                const bt = live?.metrics_backtest?.[row.key];
                const lv = live?.metrics_live?.[row.key];
                const hasDelta =
                  typeof bt === "number" &&
                  typeof lv === "number" &&
                  !Number.isNaN(bt) &&
                  !Number.isNaN(lv);
                const delta = hasDelta ? lv - bt : null;
                // Live worse than backtest → losses tint on the delta.
                const worse =
                  delta !== null &&
                  (row.higherIsBetter ? delta < 0 : delta > 0);
                const deltaClass =
                  delta === null || delta === 0
                    ? "num text-ink-muted"
                    : worse
                      ? "num text-losses"
                      : "num text-gains";
                return (
                  <tr key={row.key} className="table-row">
                    <td className="table-cell font-medium">{row.label}</td>
                    <td className="table-cell text-right">
                      <span className="num text-ink-secondary">
                        {formatValue(bt, row.format)}
                      </span>
                    </td>
                    <td className="table-cell text-right">
                      <span className="num text-ink">
                        {formatValue(lv, row.format)}
                      </span>
                    </td>
                    <td className="table-cell text-right">
                      <span className={deltaClass}>
                        {delta === null
                          ? "—"
                          : `${delta >= 0 ? "+" : ""}${formatValue(
                              delta,
                              row.format
                            )}`}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default LiveMetricsTable;
