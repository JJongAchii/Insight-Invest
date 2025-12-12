import { useFetchMetaDataQuery } from '@/state/api';
import { DataGrid, GridColDef, GridToolbar } from '@mui/x-data-grid';
import React, { useState } from 'react'


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

const MetaTable = ({ onSelectionChange }: { onSelectionChange: any }) => {

    const { data } = useFetchMetaDataQuery({});
    const [selectedRows, setSelectedRows] = useState([]);

    const handleSelectionChange = (selectionModel: any) => {
        const selectedData = selectionModel.map((id: any) => data.find((row: any) => row.meta_id === id));
        setSelectedRows(selectedData);
        onSelectionChange(selectedData); // Pass data to parent
    };

    if (!data) return <p>No data available</p>;

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
                checkboxSelection
                className="bg-white shadow rounded-lg border border-gray-200 mt-5 !text-gray-700"
                onRowSelectionModelChange={handleSelectionChange}
            />
        </div>
    )
}

export default MetaTable
