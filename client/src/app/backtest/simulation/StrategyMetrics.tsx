import React, { useState } from "react";
import Link from "next/link";
import InfoTip from "@/components/ui/InfoTip";
import {
  useSaveStrategyMutation,
  BacktestRunResult,
  MetricSet,
  SaveStrategyPayload,
} from "@/state/api";

interface StrategyMetricsProps {
  result: BacktestRunResult | null;
  selectedTicker: Record<string, SaveStrategyPayload>;
}

type MetricKey = keyof MetricSet;

type SaveFeedback = {
  token: string;
  kind: "success" | "error";
} | null;

interface MetricColumn {
  key: MetricKey;
  label: string;
  helpKey?: string;
  format: "pct" | "num";
  /** Color positive/negative values (return column only). */
  signed?: boolean;
}

const METRIC_COLUMNS: MetricColumn[] = [
  { key: "ann_ret", label: "연환산 수익", format: "pct", signed: true },
  { key: "ann_vol", label: "연환산 변동성", format: "pct" },
  { key: "sharpe", label: "샤프", helpKey: "bt.sharpe", format: "num" },
  { key: "sortino", label: "소르티노", helpKey: "bt.sortino", format: "num" },
  { key: "calmar", label: "칼마", helpKey: "bt.calmar", format: "num" },
  { key: "mdd", label: "최대 낙폭", helpKey: "bt.mdd", format: "pct" },
  { key: "var", label: "VaR", helpKey: "bt.var", format: "pct" },
  { key: "cvar", label: "CVaR", helpKey: "bt.cvar", format: "pct" },
];

const formatValue = (value: unknown, format: "pct" | "num"): string => {
  if (typeof value !== "number" || Number.isNaN(value)) return "—";
  return format === "pct" ? `${value.toFixed(2)}%` : value.toFixed(2);
};

const valueClass = (value: unknown, signed?: boolean): string => {
  if (!signed || typeof value !== "number" || value === 0) return "num";
  return value > 0 ? "num text-gains" : "num text-losses";
};

const StrategyMetrics: React.FC<StrategyMetricsProps> = ({
  result,
  selectedTicker,
}) => {
  const [saveStrategy, { isLoading: isSaving }] = useSaveStrategyMutation();
  const [saveFeedback, setSaveFeedback] = useState<SaveFeedback>(null);
  const currentFeedback =
    saveFeedback?.token === result?.result_token ? saveFeedback : null;

  const handleSave = async (strategy: string, resultToken: string) => {
    const strategyData = selectedTicker[strategy];
    if (!strategyData) return;

    setSaveFeedback(null);
    try {
      await saveStrategy(strategyData).unwrap();
      setSaveFeedback({ token: resultToken, kind: "success" });
    } catch (error) {
      console.error("Error saving strategy:", error);
      setSaveFeedback({ token: resultToken, kind: "error" });
    }
  };

  return (
    <div className="mt-6 border-t border-edge pt-5">
      {result ? (
        <>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h4 className="text-sm font-semibold text-ink">성과 지표 원장</h4>
              <p className="mt-1 text-xs text-ink-muted">전략과 벤치마크를 같은 정의로 비교합니다.</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Link
                href="/backtest/strategy_list"
                className="btn-ghost px-3 py-1.5 text-xs"
              >
                저장된 결과
              </Link>
              <button
                type="button"
                onClick={() => handleSave(result.strategy_name, result.result_token)}
                disabled={
                  isSaving ||
                  !selectedTicker[result.strategy_name] ||
                  currentFeedback?.kind === "success"
                }
                className="btn-secondary px-3 py-1.5 text-xs"
              >
                {isSaving
                  ? "저장 중..."
                  : currentFeedback?.kind === "success"
                    ? "저장 완료"
                    : "결과 저장"}
              </button>
            </div>
          </div>
          {currentFeedback && (
            <p
              role={currentFeedback.kind === "error" ? "alert" : "status"}
              className={`mb-4 rounded-lg border px-3 py-2 text-xs ${
                currentFeedback.kind === "error"
                  ? "border-losses/30 bg-losses/5 text-losses"
                  : "border-gains/30 bg-gains/5 text-gains"
              }`}
            >
              {currentFeedback.kind === "error" ? (
                "결과를 저장하지 못했습니다. 연결을 확인한 뒤 다시 시도해 주세요."
              ) : (
                <>
                  저장했습니다. {" "}
                  <Link
                    href="/backtest/strategy_list"
                    className="font-semibold underline underline-offset-2"
                  >
                    결과 목록에서 확인
                  </Link>
                </>
              )}
            </p>
          )}
          <div className="scrollbar-hidden overflow-x-auto">
          <table className="min-w-[32rem] w-full text-sm">
            <thead>
              <tr className="table-header">
                <th className="rounded-l-lg px-4 py-2.5 text-left">지표</th>
                <th className="px-4 py-2.5 text-right">{result.strategy_name}</th>
                <th className="rounded-r-lg px-4 py-2.5 text-right">{result.benchmark.name}</th>
              </tr>
            </thead>
            <tbody>
              {METRIC_COLUMNS.map((metric) => (
                <tr key={metric.key} className="table-row">
                  <td className="table-cell whitespace-nowrap font-medium text-ink-secondary">
                    <span className="inline-flex items-center gap-1.5">
                      {metric.label}
                      {metric.helpKey && <InfoTip helpKey={metric.helpKey} />}
                    </span>
                  </td>
                  <td className="table-cell text-right">
                    <span className={valueClass(result.metrics.strategy[metric.key], metric.signed)}>
                      {formatValue(result.metrics.strategy[metric.key], metric.format)}
                    </span>
                  </td>
                  <td className="table-cell text-right">
                    <span className={valueClass(result.metrics.benchmark[metric.key], metric.signed)}>
                      {formatValue(result.metrics.benchmark[metric.key], metric.format)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        </>
      ) : (
        <div className="flex flex-col items-center justify-center py-12">
          <p className="text-sm text-ink-muted">표시할 성과 지표가 없습니다.</p>
        </div>
      )}
    </div>
  );
};

export default StrategyMetrics;
