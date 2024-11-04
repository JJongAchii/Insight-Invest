import { DataGrid, GridColDef } from '@mui/x-data-grid'
import React from 'react'


const columns: GridColDef[] = [
    { field: "strategy", headerName: "Strategy Name", width: 130, headerAlign: 'center', align: 'center' },
    { field: "ann_returns", headerName: "Annual Returns (%)", width: 130, headerAlign: 'center', align: 'center', type: 'number' },
    { field: "ann_volatilities", headerName: "Annual Volatility (%)", width: 130, headerAlign: 'center', align: 'center', type: 'number' },
    { field: "sharpe_ratios", headerName: "Sharpe Ratio", width: 130, headerAlign: 'center', align: 'center', type: 'number' },
    { field: "max_drawdowns", headerName: "Max Drawdown (%)", width: 130, headerAlign: 'center', align: 'center', type: 'number' },
    { field: "skewness", headerName: "Skewness", width: 130, headerAlign: 'center', align: 'center', type: 'number' },
    { field: "kurtosis", headerName: "Kurtosis", width: 130, headerAlign: 'center', align: 'center', type: 'number' },
    { field: "value_at_risk", headerName: "VaR (%)", width: 130, headerAlign: 'center', align: 'center', type: 'number' },
    { field: "conditional_value_at_risk", headerName: "C.VaR (%)", width: 130, headerAlign: 'center', align: 'center', type: 'number' },
]


const StrategyMetrics = ({ metricsResult }) => {
    const metricData = JSON.parse(metricsResult);
    return (
        <div className="flex flex-col bg-white shadow-lg rounded-2xl p-8">
            <h4 className='text-lg font-semibold'>Metrics</h4>
            <DataGrid 
                rows={metricData}
                columns={columns}
                getRowId={(row) => row.strategy}
                slotProps={{toolbar: {showQuickFilter: true}}}
                className="bg-white shadow rounded-lg border border-gray-200 mt-5 !text-gray-700"
            />
        </div>
    )
}

export default StrategyMetrics