"use client";

import React, { useMemo } from "react";
import {
  DataGrid,
  GridColDef,
  GridToolbar,
  GridRowSelectionModel,
  GridRenderCellParams,
} from "@mui/x-data-grid";

import { useFetchSparklinesQuery } from "@/state/api";
import { MetaRow, FilterState, CAP_THRESHOLDS } from "./types";
import SparklineChart from "./SparklineChart";

interface MetaTableProps {
  data: MetaRow[];
  filters: FilterState;
  selectedIds: number[];
  onSelectionChange: (selectedIds: number[]) => void;
  onRowClick: (row: MetaRow) => void;
}

const MetaTable: React.FC<MetaTableProps> = ({
  data,
  filters,
  selectedIds,
  onSelectionChange,
  onRowClick,
}) => {
  // Filter data based on filters
  const filteredData = useMemo(() => {
    return data.filter((row) => {
      // Market filter
      if (filters.market !== "all" && row.iso_code !== filters.market) {
        return false;
      }

      // Sector filter
      if (filters.sector && row.sector !== filters.sector) {
        return false;
      }

      // Cap filter
      if (filters.cap !== "all" && row.marketcap) {
        const cap = row.marketcap;
        if (filters.cap === "large" && cap < CAP_THRESHOLDS.large) return false;
        if (
          filters.cap === "mid" &&
          (cap >= CAP_THRESHOLDS.large || cap < CAP_THRESHOLDS.mid)
        )
          return false;
        if (filters.cap === "small" && cap >= CAP_THRESHOLDS.mid) return false;
      }

      // Search filter (in Quick Filter toolbar)
      return true;
    });
  }, [data, filters]);

  // Get meta_ids for sparkline query
  const metaIds = useMemo(() => {
    return filteredData.map((row) => row.meta_id).join(",");
  }, [filteredData]);

  // Fetch sparklines for visible stocks
  const { data: sparklineData } = useFetchSparklinesQuery(metaIds, {
    skip: !metaIds,
  });

  const columns: GridColDef[] = [
    { field: "ticker", headerName: "Ticker", width: 90 },
    { field: "name", headerName: "Name", width: 200, flex: 1 },
    {
      field: "sector",
      headerName: "Sector",
      width: 140,
      valueGetter: (_value, row) => row.sector || "—",
    },
    { field: "iso_code", headerName: "Market", width: 70 },
    {
      field: "marketcap",
      headerName: "Market Cap",
      width: 110,
      type: "number",
      valueFormatter: (value: unknown) => {
        if (typeof value !== "number") return "—";
        if (value >= 1e12) return `$${(value / 1e12).toFixed(1)}T`;
        if (value >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
        if (value >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
        return `$${value.toLocaleString()}`;
      },
    },
    {
      field: "sparkline",
      headerName: "30D Trend",
      width: 100,
      sortable: false,
      filterable: false,
      renderCell: (params: GridRenderCellParams) => {
        const metaId = params.row.meta_id;
        const sparkline = sparklineData?.sparklines?.[String(metaId)] || [];
        return <SparklineChart data={sparkline} />;
      },
    },
    {
      field: "security_type",
      headerName: "Type",
      width: 80,
    },
  ];

  const handleSelectionChange = (selectionModel: GridRowSelectionModel) => {
    const ids = selectionModel.map((id) => Number(id));
    onSelectionChange(ids);
  };

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-base font-semibold text-neutral-900">
            Stock Metadata
          </h3>
          <p className="text-sm text-neutral-500 mt-0.5">
            {filteredData.length} securities
            {filteredData.length !== data.length && ` (filtered from ${data.length})`}
          </p>
        </div>
      </div>
      <DataGrid
        rows={filteredData}
        columns={columns}
        getRowId={(row) => row.meta_id}
        slots={{ toolbar: GridToolbar }}
        slotProps={{
          toolbar: {
            showQuickFilter: true,
            quickFilterProps: { debounceMs: 500 },
          },
        }}
        checkboxSelection
        disableRowSelectionOnClick
        rowSelectionModel={selectedIds}
        onRowSelectionModelChange={handleSelectionChange}
        onRowClick={(params) => onRowClick(params.row as MetaRow)}
        initialState={{
          pagination: {
            paginationModel: { pageSize: 25 },
          },
        }}
        pageSizeOptions={[10, 25, 50, 100]}
        sx={{
          "& .MuiDataGrid-row": {
            cursor: "pointer",
          },
          "& .MuiDataGrid-row:hover": {
            backgroundColor: "rgba(59, 130, 246, 0.04)",
          },
        }}
      />
    </div>
  );
};

export default MetaTable;
