import { DataGrid, GridColDef } from "@mui/x-data-grid";
import React from "react";
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

const pctFormatter = (value: unknown) => {
  if (typeof value !== "number") return "—";
  return `${value.toFixed(2)}%`;
};

const numFormatter = (value: unknown) => {
  if (typeof value !== "number") return "—";
  return value.toFixed(2);
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

  const columns: GridColDef[] = [
    {
      field: "strategy",
      headerName: "Strategy",
      width: 150,
      headerAlign: "left",
      align: "left",
    },
    {
      field: "ann_ret",
      headerName: "Return",
      width: 100,
      headerAlign: "right",
      align: "right",
      type: "number",
      valueFormatter: pctFormatter,
      cellClassName: (params) =>
        typeof params.value === "number"
          ? params.value > 0
            ? "num text-success"
            : params.value < 0
              ? "num text-danger"
              : "num"
          : "num",
    },
    {
      field: "ann_vol",
      headerName: "Vol",
      width: 90,
      headerAlign: "right",
      align: "right",
      type: "number",
      valueFormatter: pctFormatter,
      cellClassName: "num",
    },
    {
      field: "sharpe",
      headerName: "Sharpe",
      width: 90,
      headerAlign: "right",
      align: "right",
      type: "number",
      valueFormatter: numFormatter,
      cellClassName: "num",
    },
    {
      field: "sortino",
      headerName: "Sortino",
      width: 90,
      headerAlign: "right",
      align: "right",
      type: "number",
      valueFormatter: numFormatter,
      cellClassName: "num",
    },
    {
      field: "calmar",
      headerName: "Calmar",
      width: 90,
      headerAlign: "right",
      align: "right",
      type: "number",
      valueFormatter: numFormatter,
      cellClassName: "num",
    },
    {
      field: "mdd",
      headerName: "MDD",
      width: 90,
      headerAlign: "right",
      align: "right",
      type: "number",
      valueFormatter: pctFormatter,
      cellClassName: "num",
    },
    {
      field: "var",
      headerName: "VaR",
      width: 90,
      headerAlign: "right",
      align: "right",
      type: "number",
      valueFormatter: pctFormatter,
      cellClassName: "num",
    },
    {
      field: "cvar",
      headerName: "CVaR",
      width: 90,
      headerAlign: "right",
      align: "right",
      type: "number",
      valueFormatter: pctFormatter,
      cellClassName: "num",
    },
    {
      field: "save",
      headerName: "",
      width: 90,
      headerAlign: "center",
      align: "center",
      sortable: false,
      renderCell: (params) =>
        params.row.isStrategy ? (
          <button
            onClick={() => handleSave(params.row.strategy)}
            disabled={isSaving}
            className="btn-primary text-xs py-1.5 px-3"
          >
            {isSaving ? "..." : "Save"}
          </button>
        ) : null,
    },
  ];

  return (
    <div>
      <h4 className="text-sm font-semibold text-ink mb-3 mt-6">
        Performance Metrics
      </h4>
      {rows.length > 0 ? (
        <DataGrid
          rows={rows}
          columns={columns}
          getRowId={(row) => row.strategy}
          autoHeight
          hideFooter
          disableColumnMenu
          sx={{
            border: 0,
            "& .text-success": {
              color: "var(--gains) !important",
              fontWeight: 500,
            },
            "& .text-danger": {
              color: "var(--losses) !important",
              fontWeight: 500,
            },
          }}
        />
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
