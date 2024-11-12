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
    const bmData: BmData[] = JSON.parse(bmMetrics);
    const excessReturn = parseFloat((strategyInfo.ann_ret - bmData[0].ann_returns).toFixed(2));
    
    const ReturnBgColor = (value: number) => (value >= 0 ? "bg-red-300" : "bg-blue-300");

    const lastDate = rebalWeight?.reduce(
        (latest, item) => (item.rebal_date > latest ? item.rebal_date : latest),
        rebalWeight[0].rebal_date
    );
    const recentRebalData = rebalWeight?.filter(item => item.rebal_date === lastDate);

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
        <div className="flex flex-col bg-white shadow-lg rounded-2xl p-8 gap-8">
            <h2 className="text-2xl font-semibold text-gray-800">{strategyInfo.port_name}</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-stretch">
                {/* Annual Returns and Volatility/Drawdown section */}
                <div className="grid grid-cols-1 gap-6">
                    {/* Section 1: Annual Returns */}
                        <h4 className="text-lg font-semibold text-green-700">Annual Returns</h4>
                        <div className="flex justify-between items-center">
                            <div className="flex flex-col items-center gap-2">
                                <p className="text-gray-600 font-semibold">Portfolio Return</p>
                                <div className={`${ReturnBgColor(strategyInfo.ann_ret)} text-white text-2xl font-semibold px-6 py-3 rounded-md shadow-lg`}>
                                    {strategyInfo.ann_ret}%
                                    {strategyInfo.ann_ret > 0 ? (
                                        <FaArrowUp className="inline text-red-700" />
                                    ) : (
                                        <FaArrowDown className="inline text-blue-700" />
                                    )}
                                </div>
                            </div>
                            <div className="flex flex-col items-center gap-2">
                                <p className="text-gray-600 font-semibold">Benchmark Relative</p>
                                <div className={`${ReturnBgColor(excessReturn)} text-white text-2xl font-semibold px-6 py-3 rounded-md shadow-lg`}>
                                    {excessReturn}
                                    {excessReturn > 0 ? (
                                        <FaArrowUp className="inline text-red-700" />
                                    ) : (
                                        <FaArrowDown className="inline text-blue-700" />
                                    )}
                                </div>
                            </div>
                        </div>
                        <hr className="h-px my-8 bg-gray-300 border-0"></hr>
                        <h4 className="text-lg font-semibold text-orange-700">Volatility and Drawdown</h4>
                        <div className="flex justify-between items-center">
                            <div className="flex flex-col items-center gap-2">
                                <p className="text-gray-600 font-semibold">Standard Deviation</p>
                                <div className="bg-orange-200 text-red-700 text-2xl font-semibold px-6 py-3 rounded-md shadow-lg">
                                    {strategyInfo.ann_vol}%
                                </div>
                            </div>
                            <div className="flex flex-col items-center gap-2">
                                <p className="text-gray-600 font-semibold">Max DrawDown</p>
                                <div className="bg-orange-200 text-red-700 text-2xl font-semibold px-6 py-3 rounded-md shadow-lg">
                                    {strategyInfo.mdd}%
                                    <FaArrowDown aria-label="Negative drawdown" className="inline text-red-700" />
                                </div>
                            </div>
                        </div>
                </div>

                {/* Pie Chart section with auto-fit height */}
                <div className="flex flex-col justify-center">
                    <h4 className="text-lg font-semibold text-gray-700 mb-4">Rebalancing Weights(Recent)</h4>
                    <div style={{ position: 'relative', height: '100%' }}>
                        <Pie data={pieData} options={{ maintainAspectRatio: false }} />
                    </div>
                </div>
            </div>
        </div>
    );
};

export default MetricSummary;
