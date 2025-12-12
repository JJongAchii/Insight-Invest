import { DataGrid, GridColDef } from '@mui/x-data-grid';
import React from 'react';
import { SaveStrategy } from './BacktestFetcher';


const StrategyMetrics = ({ backtestResult, selectedTicker }: { backtestResult: any; selectedTicker: any }) => {
    const metricData = backtestResult?.metrics ? JSON.parse(backtestResult.metrics) : [];

    const handleSave = (strategy: any) => {
        const strategyData = selectedTicker[strategy];
        SaveStrategy(strategyData);
    };

    const columns: GridColDef[] = [
        { field: "strategy", headerName: "Strategy Name", width: 130, headerAlign: 'center', align: 'center' },
        { field: "ann_returns", headerName: "Annual Returns (%)", width: 130, headerAlign: 'center', align: 'center', type: 'number', valueFormatter: (value?: number) => {if (value == null) {return '';}return `${value.toLocaleString()} %`;}, },
        { field: "ann_volatilities", headerName: "Annual Volatility (%)", width: 130, headerAlign: 'center', align: 'center', type: 'number', valueFormatter: (value?: number) => {if (value == null) {return '';}return `${value.toLocaleString()} %`;},  },
        { field: "sharpe_ratios", headerName: "Sharpe Ratio", width: 130, headerAlign: 'center', align: 'center', type: 'number' },
        { field: "max_drawdowns", headerName: "Max Drawdown (%)", width: 130, headerAlign: 'center', align: 'center', type: 'number', valueFormatter: (value?: number) => {if (value == null) {return '';}return `${value.toLocaleString()} %`;},  },
        { field: "skewness", headerName: "Skewness", width: 90, headerAlign: 'center', align: 'center', type: 'number' },
        { field: "kurtosis", headerName: "Kurtosis", width: 90, headerAlign: 'center', align: 'center', type: 'number' },
        { field: "value_at_risk", headerName: "VaR (%)", width: 100, headerAlign: 'center', align: 'center', type: 'number', valueFormatter: (value?: number) => {if (value == null) {return '';}return `${value.toLocaleString()} %`;},  },
        { field: "conditional_value_at_risk", headerName: "C.VaR (%)", width: 100, headerAlign: 'center', align: 'center', type: 'number', valueFormatter: (value?: number) => {if (value == null) {return '';}return `${value.toLocaleString()} %`;},  },
        {
            field: "save",
            headerName: "Save",
            width: 100,
            headerAlign: 'center',
            align: 'center',
            renderCell: (params) => (
                <button
                    onClick={() => handleSave(params.row.strategy)}
                    className="p-1 bg-blue-500 text-white rounded"
                >
                    Save
                </button>
            ),
        },
    ];
    

    return (
        <div className="flex flex-col bg-white shadow-lg rounded-2xl p-8 relative" style={{ height: 450 }}>
            <h4 className='text-lg text-center font-semibold'>Metrics</h4>
            {backtestResult?.metrics ? (
                <DataGrid
                    rows={metricData}
                    columns={columns}
                    getRowId={(row) => row.strategy}
                    slotProps={{ toolbar: { showQuickFilter: true } }}
                    className="bg-white shadow rounded-lg border border-gray-200 mt-5 !text-gray-700"
                />    
            ) : (
                <div style={{
                    position: 'absolute',
                    top: '50%',
                    left: '50%',
                    transform: 'translate(-50%, -50%)',
                    fontSize: '1.5rem',
                    color: '#555'
                }}>
                    No data available...
                </div>
            )}
        </div>
    );
}

export default StrategyMetrics;
