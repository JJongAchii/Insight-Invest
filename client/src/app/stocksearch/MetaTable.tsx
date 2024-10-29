import { useFetch } from '@/state/api';
import { DataGrid, GridColDef, GridToolbar } from '@mui/x-data-grid';
import React from 'react'


const columns: GridColDef[] = [
    { field: "meta_id", headerName: "ID", width: 90 },
    { field: "ticker", headerName: "TICKER", width: 110 },
    { field: "name", headerName: "NAME", width: 200 },
    { field: "isin", headerName: "ISIN CODE", width: 200 },
    { field: "security_type", headerName: "TYPE", width: 200 },
    { field: "asset_class", headerName: "ASSET CLASS", width: 200, valueGetter: (value, row) => row.asset_class ? row.asset_class : "N/A" },
    { field: "sector", headerName: "SECTOR", width: 200, valueGetter: (value, row) => row.sector ? row.sector : "N/A" },
    { field: "iso_code", headerName: "ISO CODE", width: 90 },
    { field: "marketcap", headerName: "MARKET CAP", width: 200, type: "number" },
    { field: "fee", headerName: "FEE", width: 90, type: "number", valueGetter: (value, row) => row.fee ? row.fee : "N/A" },
]

const MetaTable = () => {

    const { data, loading, error } = useFetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/meta`)

    if (loading) return <p>Loading...</p>;
    if (error) return <p>Error: {error}</p>;

    return (
        <div className="row-span-3 xl:row-span-6 bg-white shadow-md rounded-2xl pb-16">
            <h3 className='text-lg font-semibold px-7 pt-5 pb-2'>
                META DATA
            </h3>
            <DataGrid 
                rows={data}
                columns={columns}
                getRowId={(row) => row.meta_id}
                slots={{ toolbar: GridToolbar}}
                slotProps={{toolbar: {showQuickFilter: true}}}
                className="bg-white shadow rounded-lg border border-gray-200 mt-5 !text-gray-700"
            />
        </div>
    )
}

export default MetaTable