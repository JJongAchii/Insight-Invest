import { useFetchMetaDataQuery } from '@/state/api';
import { DataGrid, GridColDef, GridToolbar, GridRowSelectionModel } from '@mui/x-data-grid';
import React from 'react'

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
    { field: "meta_id", headerName: "ID", width: 90 },
    { field: "ticker", headerName: "TICKER", width: 110 },
    { field: "name", headerName: "NAME", width: 250 },
    { field: "isin", headerName: "ISIN CODE", width: 150 },
    { field: "security_type", headerName: "TYPE", width: 130 },
    { field: "asset_class", headerName: "ASSET CLASS", width: 150, valueGetter: (_value, row) => row.asset_class ? row.asset_class : "N/A" },
    { field: "sector", headerName: "SECTOR", width: 180, valueGetter: (_value, row) => row.sector ? row.sector : "N/A" },
    { field: "iso_code", headerName: "ISO CODE", width: 100 },
    { field: "marketcap", headerName: "MARKET CAP", width: 150, type: "number" },
    { field: "fee", headerName: "FEE", width: 90, type: "number", valueGetter: (_value, row) => row.fee ? row.fee : "N/A" },
]

const MetaTable: React.FC<MetaTableProps> = ({ onSelectionChange }) => {

    const { data } = useFetchMetaDataQuery({});

    const handleSelectionChange = (selectionModel: GridRowSelectionModel) => {
        const selectedData = selectionModel.map((id) => (data as MetaRow[]).find((row) => row.meta_id === id)).filter((row): row is MetaRow => row !== undefined);
        onSelectionChange(selectedData);
    };

    if (!data) return (
        <div className="card-modern">
            <p className="text-gray-500 text-center py-8">No data available</p>
        </div>
    );

    return (
        <div className="card-modern">
            <div className='flex items-center gap-3 mb-6'>
                <div className="w-10 h-10 bg-gradient-to-r from-emerald-500 to-teal-600 rounded-xl flex items-center justify-center">
                    <span className="text-white text-xl font-bold">📊</span>
                </div>
                <h3 className='text-xl font-bold text-gray-800'>
                    Stock Metadata
                </h3>
            </div>
            <div className="bg-gradient-to-br from-gray-50 to-blue-50 rounded-xl p-4">
                <DataGrid
                    rows={data}
                    columns={columns}
                    getRowId={(row) => row.meta_id}
                    slots={{ toolbar: GridToolbar}}
                    slotProps={{
                        toolbar: {
                            showQuickFilter: true,
                            quickFilterProps: { debounceMs: 500 },
                        }
                    }}
                    checkboxSelection
                    disableRowSelectionOnClick
                    className="!border-0"
                    onRowSelectionModelChange={handleSelectionChange}
                    sx={{
                        backgroundColor: 'white',
                        borderRadius: '12px',
                        '& .MuiDataGrid-columnHeaders': {
                            backgroundColor: 'rgb(241 245 249)',
                            borderRadius: '8px 8px 0 0',
                            fontSize: '0.875rem',
                            fontWeight: '600',
                            color: 'rgb(51 65 85)',
                        },
                        '& .MuiDataGrid-cell': {
                            fontSize: '0.875rem',
                            color: 'rgb(71 85 105)',
                        },
                        '& .MuiDataGrid-row:hover': {
                            backgroundColor: 'rgb(239 246 255)',
                        },
                        '& .MuiDataGrid-row.Mui-selected': {
                            backgroundColor: 'rgb(224 242 254)',
                            '&:hover': {
                                backgroundColor: 'rgb(219 234 254)',
                            },
                        },
                        '& .MuiCheckbox-root': {
                            color: 'rgb(99 102 241)',
                        },
                        '& .MuiCheckbox-root.Mui-checked': {
                            color: 'rgb(79 70 229)',
                        },
                        '& .MuiDataGrid-toolbarContainer': {
                            padding: '12px',
                            gap: '8px',
                            '& .MuiButton-root': {
                                color: 'rgb(71 85 105)',
                                fontSize: '0.875rem',
                                fontWeight: '500',
                            },
                        },
                    }}
                    initialState={{
                        pagination: {
                            paginationModel: { pageSize: 25 },
                        },
                    }}
                    pageSizeOptions={[10, 25, 50, 100]}
                />
            </div>
        </div>
    )
}

export default MetaTable
