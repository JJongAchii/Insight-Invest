import React from 'react';
import { Line } from 'react-chartjs-2';
import { ChartOptions, TooltipItem } from 'chart.js';
import 'chart.js/auto';

interface NavData {
    index: number[];
    columns: string[];
    data: number[][];
}

interface StrategyChartProps {
    navResult: string | null;
}

const StrategyChart: React.FC<StrategyChartProps> = ({ navResult }) => {
    const navData: NavData = navResult
        ? JSON.parse(navResult)
        : { index: [], columns: [], data: [] };

    const chartLabels = navData.index.map((date: number) => new Date(date).toISOString().split('T')[0]);

    const datasets = navData.columns.map((column: string, index: number) => ({
        label: column,
        data: navData.data.map((row: number[]) => row[index]),
        borderColor: [
            'rgb(99, 102, 241)',
            'rgb(168, 85, 247)',
            'rgb(236, 72, 153)',
            'rgb(239, 68, 68)',
            'rgb(34, 197, 94)'
        ][index % 5],
        backgroundColor: [
            'rgba(99, 102, 241, 0.1)',
            'rgba(168, 85, 247, 0.1)',
            'rgba(236, 72, 153, 0.1)',
            'rgba(239, 68, 68, 0.1)',
            'rgba(34, 197, 94, 0.1)'
        ][index % 5],
        borderWidth: 3,
        tension: 0.4,
        pointRadius: 0,
        pointHoverRadius: 6,
        hoverBorderWidth: 3,
    }));

    const data = {
        labels: chartLabels,
        datasets: datasets,
    };

    const options: ChartOptions<'line'> = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                display: true,
                position: 'top',
                labels: {
                    color: 'rgb(55, 65, 81)',
                    font: {
                        size: 13,
                        weight: 'bold' as const,
                    },
                    boxWidth: 12,
                    boxHeight: 12,
                    padding: 16,
                    usePointStyle: true,
                    pointStyle: 'circle',
                },
            },
            tooltip: {
                mode: 'index' as const,
                intersect: false,
                backgroundColor: 'rgba(255, 255, 255, 0.95)',
                titleColor: '#1f2937',
                bodyColor: '#4b5563',
                borderColor: '#e5e7eb',
                borderWidth: 1,
                titleFont: {
                    size: 13,
                    weight: 'bold' as const,
                },
                bodyFont: {
                    size: 12,
                },
                padding: 12,
                cornerRadius: 8,
                displayColors: true,
                callbacks: {
                    labelColor: function(context: TooltipItem<'line'>) {
                        return {
                            borderColor: context.dataset.borderColor as string,
                            backgroundColor: context.dataset.borderColor as string,
                            borderWidth: 2,
                            borderRadius: 2,
                        };
                    },
                }
            },
        },
        scales: {
            x: {
                grid: {
                    display: false,
                },
                ticks: {
                    color: '#6b7280',
                    font: {
                        size: 11,
                    },
                    maxRotation: 0,
                    autoSkip: true,
                    maxTicksLimit: 12,
                },
            },
            y: {
                grid: {
                    color: 'rgba(0, 0, 0, 0.05)',
                    lineWidth: 1,
                },
                ticks: {
                    color: '#6b7280',
                    font: {
                        size: 11,
                    },
                    callback: (tickValue: string | number) => {
                        if (typeof tickValue === 'number') {
                            return tickValue.toFixed(2);
                        }
                        return tickValue;
                    },
                },
            },
        },
        interaction: {
            mode: 'nearest' as const,
            axis: 'x',
            intersect: false,
        },
        animation: {
            duration: 800,
            easing: 'easeInOutQuart',
        },
    };

    return (
        <div className="card-modern">
            <div className='flex items-center gap-3 mb-6'>
                <div className="w-10 h-10 bg-gradient-to-r from-green-500 to-emerald-600 rounded-xl flex items-center justify-center">
                    <span className="text-white text-xl font-bold">📊</span>
                </div>
                <h3 className='text-xl font-bold text-gray-800'>
                    Performance Chart
                </h3>
            </div>
            <div className="bg-gradient-to-br from-gray-50 to-blue-50 rounded-xl p-4 relative" style={{ height: 450 }}>
                {navResult ? (
                    <Line data={data} options={options} />
                ) : (
                    <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 text-center">
                        <div className="text-6xl mb-4 opacity-20">📈</div>
                        <p className="text-xl text-gray-400 font-medium">No data available</p>
                        <p className="text-sm text-gray-400 mt-2">Run a backtest to see performance</p>
                    </div>
                )}
            </div>
        </div>
    );
};

export default StrategyChart;
