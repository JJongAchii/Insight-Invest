import React from "react";
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

interface MetricRow extends Partial<MetricSet> {
  strategy: string;
  isStrategy: boolean;
}

type MetricKey = keyof MetricSet;

interface MetricColumn {
  key: MetricKey;
  label: string;
  helpKey?: string;
  format: "pct" | "num";
  /** Color positive/negative values (return column only). */
  signed?: boolean;
}

const METRIC_COLUMNS: MetricColumn[] = [
  { key: "ann_ret", label: "Return", format: "pct", signed: true },
  { key: "ann_vol", label: "Vol", format: "pct" },
  { key: "sharpe", label: "Sharpe", helpKey: "bt.sharpe", format: "num" },
  { key: "sortino", label: "Sortino", helpKey: "bt.sortino", format: "num" },
  { key: "calmar", label: "Calmar", helpKey: "bt.calmar", format: "num" },
  { key: "mdd", label: "MDD", helpKey: "bt.mdd", format: "pct" },
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

  const rows: MetricRow[] = [];
  if (result) {
    rows.push({
      strategy: result.strategy_name,
      isStrategy: true,
      ...result.metrics.strategy,
    });
    const bm = result.metrics.benchmark;
    if (bm && Object.keys(bm).length > 0) {
      rows.push({
        strategy: result.benchmark.name,
        isStrategy: false,
        ...bm,
      });
    }
  }

  const handleSave = async (strategy: string) => {
    const strategyData = selectedTicker[strategy];
    if (!strategyData) return;

    try {
      await saveStrategy(strategyData).unwrap();
    } catch (error) {
      console.error("Error saving strategy:", error);
    }
  };

  return (
    <div>
      <h4 className="text-sm font-semibold text-ink mb-3 mt-6">
        Performance Metrics
      </h4>
      {rows.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="table-header">
                <th className="py-2.5 px-4 text-left rounded-l-lg">Strategy</th>
                {METRIC_COLUMNS.map((col) => (
                  <th
                    key={col.key}
                    className="py-2.5 px-4 text-right whitespace-nowrap"
                  >
                    <span className="inline-flex items-center gap-1">
                      {col.label}
                      {col.helpKey && <InfoTip helpKey={col.helpKey} />}
                    </span>
                  </th>
                ))}
                <th className="py-2.5 px-4 rounded-r-lg" />
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.strategy} className="table-row">
                  <td className="table-cell font-medium whitespace-nowrap">
                    {row.strategy}
                  </td>
                  {METRIC_COLUMNS.map((col) => (
                    <td key={col.key} className="table-cell text-right">
                      <span className={valueClass(row[col.key], col.signed)}>
                        {formatValue(row[col.key], col.format)}
                      </span>
                    </td>
                  ))}
                  <td className="table-cell text-center">
                    {row.isStrategy ? (
                      <button
                        onClick={() => handleSave(row.strategy)}
                        disabled={isSaving}
                        className="btn-primary text-xs py-1.5 px-3"
                      >
                        {isSaving ? "..." : "Save"}
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center py-12">
          <p className="text-ink-muted text-sm">No metrics available</p>
          <p className="text-ink-muted text-xs mt-1">
            Run a backtest to see performance metrics
          </p>
        </div>
      )}
    </div>
  );
};

export default StrategyMetrics;
