import React from 'react';
import { FaArrowUp, FaArrowDown } from 'react-icons/fa';
import { Pie } from 'react-chartjs-2';
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js';

ChartJS.register(ArcElement, Tooltip, Legend);

interface InfoData {
    port_name: string;
    ann_ret: number;
    ann_vol: number;
    mdd: number;
}

interface RebalData {
    rebal_date: string;
    port_id: number;
    ticker: string;
    name: string;
    weight: number;
}

interface BmData {
    ann_returns: number;
}

const MetricSummary = ({ strategyInfo, rebalWeight, bmMetrics }: { strategyInfo: InfoData; rebalWeight: RebalData[]; bmMetrics: string; }) => {
    const bmData: BmData[] = bmMetrics ? JSON.parse(bmMetrics) : [];
    const excessReturn = bmData.length > 0
        ? parseFloat((strategyInfo.ann_ret - bmData[0].ann_returns).toFixed(2))
        : 0;

    const ReturnBgColor = (value: number) => (value >= 0 ? "bg-red-300" : "bg-blue-300");

    // 빈 배열 처리
    const lastDate = rebalWeight && rebalWeight.length > 0
        ? rebalWeight.reduce(
            (latest, item) => (item.rebal_date > latest ? item.rebal_date : latest),
            rebalWeight[0].rebal_date
        )
        : null;
    const recentRebalData = lastDate
        ? rebalWeight?.filter(item => item.rebal_date === lastDate)
        : [];

    const pieData = {
        labels: recentRebalData?.map(data => data.ticker),
        datasets: [
            {
                label: 'Weight',
                data: recentRebalData?.map(data => data.weight),
                backgroundColor: ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40'],
                hoverBackgroundColor: ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40']
            }
        ]
    };

    return (
        <div className="card-modern">
            <div className='flex items-center gap-3 mb-6'>
                <div className="w-12 h-12 bg-gradient-to-r from-purple-500 to-indigo-600 rounded-xl flex items-center justify-center shadow-md">
                    <span className="text-white text-2xl font-bold">📊</span>
                </div>
                <div>
                    <h2 className="text-2xl font-bold text-gray-800">{strategyInfo.port_name}</h2>
                    <p className="text-sm text-gray-500">Performance Summary</p>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* Metrics section */}
                <div className="space-y-6">
                    {/* Annual Returns */}
                    <div className="bg-gradient-to-br from-green-50 to-emerald-50 rounded-xl p-6 border-2 border-green-200">
                        <h4 className="text-lg font-bold text-green-700 mb-4 flex items-center gap-2">
                            <span>📈</span> Annual Returns
                        </h4>
                        <div className="grid grid-cols-2 gap-4">
                            <div className="bg-white rounded-lg p-4 shadow-md">
                                <p className="text-xs text-gray-500 mb-2">Portfolio Return</p>
                                <div className="flex items-center gap-2">
                                    <span className={`text-2xl font-bold ${strategyInfo.ann_ret >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                        {strategyInfo.ann_ret}%
                                    </span>
                                    {strategyInfo.ann_ret > 0 ? (
                                        <FaArrowUp className="text-green-600" />
                                    ) : (
                                        <FaArrowDown className="text-red-600" />
                                    )}
                                </div>
                            </div>
                            <div className="bg-white rounded-lg p-4 shadow-md">
                                <p className="text-xs text-gray-500 mb-2">vs Benchmark</p>
                                <div className="flex items-center gap-2">
                                    <span className={`text-2xl font-bold ${excessReturn >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                                        {excessReturn}%
                                    </span>
                                    {excessReturn > 0 ? (
                                        <FaArrowUp className="text-green-600" />
                                    ) : (
                                        <FaArrowDown className="text-red-600" />
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Risk Metrics */}
                    <div className="bg-gradient-to-br from-orange-50 to-red-50 rounded-xl p-6 border-2 border-orange-200">
                        <h4 className="text-lg font-bold text-orange-700 mb-4 flex items-center gap-2">
                            <span>⚠️</span> Risk Metrics
                        </h4>
                        <div className="grid grid-cols-2 gap-4">
                            <div className="bg-white rounded-lg p-4 shadow-md">
                                <p className="text-xs text-gray-500 mb-2">Volatility</p>
                                <span className="text-2xl font-bold text-orange-600">
                                    {strategyInfo.ann_vol}%
                                </span>
                            </div>
                            <div className="bg-white rounded-lg p-4 shadow-md">
                                <p className="text-xs text-gray-500 mb-2">Max Drawdown</p>
                                <div className="flex items-center gap-2">
                                    <span className="text-2xl font-bold text-red-600">
                                        {strategyInfo.mdd}%
                                    </span>
                                    <FaArrowDown className="text-red-600" />
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Pie Chart section */}
                <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl p-6 border-2 border-blue-200">
                    <h4 className="text-lg font-bold text-blue-700 mb-4 flex items-center gap-2">
                        <span>🥧</span> Current Allocation
                    </h4>
                    <div style={{ position: 'relative', height: '350px' }}>
                        <Pie
                            data={pieData}
                            options={{
                                maintainAspectRatio: false,
                                plugins: {
                                    legend: {
                                        position: 'bottom',
                                        labels: {
                                            padding: 15,
                                            font: {
                                                size: 11,
                                            },
                                            usePointStyle: true,
                                        },
                                    },
                                    tooltip: {
                                        backgroundColor: 'rgba(255, 255, 255, 0.95)',
                                        titleColor: '#1f2937',
                                        bodyColor: '#4b5563',
                                        borderColor: '#e5e7eb',
                                        borderWidth: 1,
                                        padding: 12,
                                        cornerRadius: 8,
                                        callbacks: {
                                            label: function(context: any) {
                                                return `${context.label}: ${(context.parsed * 100).toFixed(2)}%`;
                                            }
                                        }
                                    }
                                }
                            }}
                        />
                    </div>
                </div>
            </div>
        </div>
    );
};

export default MetricSummary;
