import { DataGrid, GridColDef } from "@mui/x-data-grid";
import React from "react";
import {
  useSaveStrategyMutation,
  BacktestResult,
  BacktestPayload,
} from "@/state/api";

interface StrategyMetricsProps {
  backtestResult: BacktestResult | null;
  selectedTicker: Record<string, BacktestPayload>;
}

const StrategyMetrics: React.FC<StrategyMetricsProps> = ({
  backtestResult,
  selectedTicker,
}) => {
  const [saveStrategy, { isLoading: isSaving }] = useSaveStrategyMutation();
  const metricData = backtestResult?.metrics
    ? JSON.parse(backtestResult.metrics)
    : [];

  const handleSave = async (strategy: string) => {
    const strategyData = selectedTicker[strategy];
    if (!strategyData) return;

    try {
      await saveStrategy(strategyData).unwrap();
      console.log("Strategy saved successfully");
    } catch (error) {
      console.error("Error saving strategy:", error);
    }
  };

  const columns: GridColDef[] = [
    {
      field: "strategy",
      headerName: "Strategy",
      width: 140,
      headerAlign: "left",
      align: "left",
    },
    {
      field: "ann_returns",
      headerName: "Return",
      width: 100,
      headerAlign: "right",
      align: "right",
      type: "number",
      valueFormatter: (value: unknown) => {
        if (typeof value !== "number") return "—";
        return `${value.toFixed(2)}%`;
      },
      cellClassName: (params) =>
        params.value > 0 ? "text-success" : params.value < 0 ? "text-danger" : "",
    },
    {
      field: "ann_volatilities",
      headerName: "Volatility",
      width: 100,
      headerAlign: "right",
      align: "right",
      type: "number",
      valueFormatter: (value: unknown) => {
        if (typeof value !== "number") return "—";
        return `${value.toFixed(2)}%`;
      },
    },
    {
      field: "sharpe_ratios",
      headerName: "Sharpe",
      width: 90,
      headerAlign: "right",
      align: "right",
      type: "number",
      valueFormatter: (value: unknown) => {
        if (typeof value !== "number") return "—";
        return value.toFixed(2);
      },
    },
    {
      field: "max_drawdowns",
      headerName: "MDD",
      width: 90,
      headerAlign: "right",
      align: "right",
      type: "number",
      valueFormatter: (value: unknown) => {
        if (typeof value !== "number") return "—";
        return `${value.toFixed(2)}%`;
      },
    },
    {
      field: "skewness",
      headerName: "Skew",
      width: 80,
      headerAlign: "right",
      align: "right",
      type: "number",
      valueFormatter: (value: unknown) => {
        if (typeof value !== "number") return "—";
        return value.toFixed(2);
      },
    },
    {
      field: "kurtosis",
      headerName: "Kurt",
      width: 80,
      headerAlign: "right",
      align: "right",
      type: "number",
      valueFormatter: (value: unknown) => {
        if (typeof value !== "number") return "—";
        return value.toFixed(2);
      },
    },
    {
      field: "value_at_risk",
      headerName: "VaR",
      width: 80,
      headerAlign: "right",
      align: "right",
      type: "number",
      valueFormatter: (value: unknown) => {
        if (typeof value !== "number") return "—";
        return `${value.toFixed(2)}%`;
      },
    },
    {
      field: "conditional_value_at_risk",
      headerName: "CVaR",
      width: 80,
      headerAlign: "right",
      align: "right",
      type: "number",
      valueFormatter: (value: unknown) => {
        if (typeof value !== "number") return "—";
        return `${value.toFixed(2)}%`;
      },
    },
    {
      field: "save",
      headerName: "",
      width: 90,
      headerAlign: "center",
      align: "center",
      sortable: false,
      renderCell: (params) => (
        <button
          onClick={() => handleSave(params.row.strategy)}
          disabled={isSaving}
          className="btn-primary text-xs py-1.5 px-3"
        >
          {isSaving ? "..." : "Save"}
        </button>
      ),
    },
  ];

  return (
    <div className="card">
      <h3 className="text-base font-semibold text-neutral-900 mb-4">
        Performance Metrics
      </h3>
      <div style={{ minHeight: 200 }}>
        {backtestResult?.metrics ? (
          <DataGrid
            rows={metricData}
            columns={columns}
            getRowId={(row) => row.strategy}
            autoHeight
            hideFooter
            disableColumnMenu
            sx={{
              border: 0,
              "& .MuiDataGrid-columnHeaders": {
                backgroundColor: "rgba(124, 91, 255, 0.08)",
                borderBottom: "1px solid rgba(124, 91, 255, 0.1)",
              },
              "& .MuiDataGrid-columnHeaderTitle": {
                fontSize: "0.75rem",
                fontWeight: 600,
                color: "#525252",
              },
              "& .MuiDataGrid-cell": {
                fontSize: "0.875rem",
                color: "#171717",
                borderBottom: "1px solid rgba(124, 91, 255, 0.05)",
              },
              "& .MuiDataGrid-row:hover": {
                backgroundColor: "rgba(124, 91, 255, 0.05)",
              },
              "& .text-success": {
                color: "#10B981 !important",
                fontWeight: 500,
              },
              "& .text-danger": {
                color: "#F87171 !important",
                fontWeight: 500,
              },
            }}
          />
        ) : (
          <div className="flex flex-col items-center justify-center py-12">
            <p className="text-neutral-400 text-sm">No metrics available</p>
            <p className="text-neutral-400 text-xs mt-1">
              Run a backtest to see performance metrics
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default StrategyMetrics;
