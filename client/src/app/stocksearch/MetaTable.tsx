import { useFetchMetaDataQuery } from "@/state/api";
import {
  DataGrid,
  GridColDef,
  GridToolbar,
  GridRowSelectionModel,
} from "@mui/x-data-grid";
import React from "react";

interface MetaRow {
  meta_id: number;
  ticker: string;
  name: string;
  isin: string;
  security_type: string;
  asset_class: string | null;
  sector: string | null;
  iso_code: string;
  marketcap: number;
  fee: number | null;
}

interface MetaTableProps {
  onSelectionChange: (selectedData: MetaRow[]) => void;
}

const columns: GridColDef[] = [
  { field: "meta_id", headerName: "ID", width: 70 },
  { field: "ticker", headerName: "Ticker", width: 100 },
  { field: "name", headerName: "Name", width: 250 },
  { field: "isin", headerName: "ISIN", width: 140 },
  { field: "security_type", headerName: "Type", width: 100 },
  {
    field: "asset_class",
    headerName: "Asset Class",
    width: 130,
    valueGetter: (_value, row) => row.asset_class || "—",
  },
  {
    field: "sector",
    headerName: "Sector",
    width: 160,
    valueGetter: (_value, row) => row.sector || "—",
  },
  { field: "iso_code", headerName: "Market", width: 80 },
  {
    field: "marketcap",
    headerName: "Market Cap",
    width: 130,
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
    field: "fee",
    headerName: "Fee",
    width: 80,
    type: "number",
    valueFormatter: (value: unknown) =>
      typeof value === "number" ? `${(value * 100).toFixed(2)}%` : "—",
  },
];

const MetaTable: React.FC<MetaTableProps> = ({ onSelectionChange }) => {
  const { data } = useFetchMetaDataQuery({});

  const handleSelectionChange = (selectionModel: GridRowSelectionModel) => {
    const selectedData = selectionModel
      .map((id) => (data as MetaRow[]).find((row) => row.meta_id === id))
      .filter((row): row is MetaRow => row !== undefined);
    onSelectionChange(selectedData);
  };

  if (!data)
    return (
      <div className="card">
        <p className="text-neutral-500 text-center py-8">No data available</p>
      </div>
    );

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-base font-semibold text-neutral-900">
            Stock Metadata
          </h3>
          <p className="text-sm text-neutral-500 mt-0.5">
            {data.length} securities available
          </p>
        </div>
      </div>
      <DataGrid
        rows={data}
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
        onRowSelectionModelChange={handleSelectionChange}
        initialState={{
          pagination: {
            paginationModel: { pageSize: 25 },
          },
        }}
        pageSizeOptions={[10, 25, 50, 100]}
      />
    </div>
  );
};

export default MetaTable;
