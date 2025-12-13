import React from 'react';
import { Bar } from 'react-chartjs-2';
import { Chart as ChartJS, BarElement, CategoryScale, LinearScale, Tooltip, TooltipItem } from 'chart.js';
import dayjs from 'dayjs';

ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip);

interface NavData {
    trade_date: string;
    value: number;
}

interface ReturnData {
    period: string;
    return: number;
}

const calculateReturns = (data: NavData[], period: 'year' | 'month'): ReturnData[] => {
    if (!data || data.length === 0) return [];

    const sortedData = [...data].sort((a, b) => dayjs(a.trade_date).unix() - dayjs(b.trade_date).unix());

    const groupedData = sortedData.reduce((acc, { trade_date, value }) => {
        const date = dayjs(trade_date);
        const key = period === 'year' ? date.format('YYYY') : date.format('YYYY-MM');

        if (!acc[key]) {
            acc[key] = { start: value, end: value };
        } else {
            acc[key].end = value;
        }
        return acc;
    }, {} as Record<string, { start: number; end: number }>);

    const returnData: ReturnData[] = [];
    let previousEndValue: number | null = null;

    for (const [key, { start, end }] of Object.entries(groupedData)) {
        if (previousEndValue !== null) {
            const annualReturn = ((end - previousEndValue) / previousEndValue) * 100;
            returnData.push({ period: key, return: annualReturn });
        }
        previousEndValue = end;
    }

    return returnData;
};

const YearlyBarChart = ({ strategyName, strategyNav, bmNav }: { strategyName: string; strategyNav: NavData[];  bmNav: string;}) => {
    const bmNavData: NavData[] = bmNav ? JSON.parse(bmNav) : [];

    if (!strategyNav || strategyNav.length === 0) {
        return <p>No data available for chart.</p>;
    }

    const yearlyReturns = calculateReturns(strategyNav, 'year');
    const bMYearlyReturns = calculateReturns(bmNavData, 'year');

    const yearlyData = {
        labels: yearlyReturns.map((item) => item.period),
        datasets: [
            {
                label: `${strategyName}`,
                data: yearlyReturns.map((item) => item.return),
                backgroundColor: 'rgba(16, 185, 129, 0.7)',
                borderColor: 'rgb(16, 185, 129)',
                borderWidth: 2,
                borderRadius: 6,
            },
            {
                label: 'Benchmark',
                data: bMYearlyReturns.map((item) => item.return),
                backgroundColor: 'rgba(168, 85, 247, 0.7)',
                borderColor: 'rgb(168, 85, 247)',
                borderWidth: 2,
                borderRadius: 6,
            },
        ],
    };

    const options = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                display: true,
                position: 'top' as const,
                labels: {
                    color: 'rgb(55, 65, 81)',
                    font: {
                        size: 12,
                        weight: 'bold' as const,
                    },
                    padding: 12,
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
                    label: (context: TooltipItem<'bar'>) => `${context.dataset.label}: ${(context.raw as number).toFixed(2)}%`,
                },
            },
        },
        scales: {
            y: {
                grid: {
                    color: 'rgba(0, 0, 0, 0.05)',
                },
                ticks: {
                    color: '#6b7280',
                    font: {
                        size: 11,
                    },
                },
                title: {
                    display: true,
                    text: 'Return (%)',
                    color: '#6b7280',
                    font: {
                        size: 12,
                        weight: 'bold' as const,
                    },
                },
            },
            x: {
                grid: {
                    display: false,
                },
                ticks: {
                    color: '#6b7280',
                    font: {
                        size: 11,
                    },
                },
            },
        },
    };

    return (
        <div className="card-modern">
            <div className='flex items-center gap-3 mb-6'>
                <div className="w-10 h-10 bg-gradient-to-r from-emerald-500 to-teal-600 rounded-xl flex items-center justify-center">
                    <span className="text-white text-xl font-bold">📊</span>
                </div>
                <h4 className='text-xl font-bold text-gray-800'>Yearly Returns</h4>
            </div>
            <div className="bg-gradient-to-br from-gray-50 to-blue-50 rounded-xl p-4">
                <div style={{ position: 'relative', height: '350px' }}>
                    <Bar data={yearlyData} options={options} />
                </div>
            </div>
        </div>
    );
};

export default YearlyBarChart;
