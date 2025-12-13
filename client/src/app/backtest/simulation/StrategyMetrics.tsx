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
                    className="px-4 py-2 bg-gradient-to-r from-blue-500 to-indigo-600 text-white rounded-lg font-semibold shadow-md hover:shadow-lg hover:from-blue-600 hover:to-indigo-700 transition-all duration-300 text-sm"
                >
                    Save
                </button>
            ),
        },
    ];


    return (
        <div className="card-modern">
            <div className='flex items-center gap-3 mb-6'>
                <div className="w-10 h-10 bg-gradient-to-r from-orange-500 to-red-600 rounded-xl flex items-center justify-center">
                    <span className="text-white text-xl font-bold">📈</span>
                </div>
                <h3 className='text-xl font-bold text-gray-800'>
                    Performance Metrics
                </h3>
            </div>
            <div className="bg-gradient-to-br from-gray-50 to-blue-50 rounded-xl p-4" style={{ minHeight: 400 }}>
                {backtestResult?.metrics ? (
                    <DataGrid
                        rows={metricData}
                        columns={columns}
                        getRowId={(row) => row.strategy}
                        className="!border-0"
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
                        }}
                        autoHeight
                    />
                ) : (
                    <div className="flex flex-col items-center justify-center py-16">
                        <div className="text-6xl mb-4 opacity-20">📊</div>
                        <p className="text-xl text-gray-400 font-medium">No metrics available</p>
                        <p className="text-sm text-gray-400 mt-2">Run a backtest to see performance metrics</p>
                    </div>
                )}
            </div>
        </div>
    );
}

export default StrategyMetrics;
