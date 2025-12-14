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

    for (const [key, { end }] of Object.entries(groupedData)) {
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
                borderColor: '#10B981',
                borderWidth: 2,
                borderRadius: 8,
            },
            {
                label: 'Benchmark',
                data: bMYearlyReturns.map((item) => item.return),
                backgroundColor: 'rgba(56, 189, 248, 0.7)',
                borderColor: '#38BDF8',
                borderWidth: 2,
                borderRadius: 8,
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
                    color: '#525252',
                    font: {
                        size: 12,
                        weight: 500 as const,
                    },
                    padding: 16,
                    usePointStyle: true,
                },
            },
            tooltip: {
                backgroundColor: 'rgba(255, 255, 255, 0.95)',
                titleColor: '#171717',
                bodyColor: '#525252',
                borderColor: 'rgba(124, 91, 255, 0.2)',
                borderWidth: 1,
                padding: 12,
                cornerRadius: 12,
                callbacks: {
                    label: (context: TooltipItem<'bar'>) => `${context.dataset.label}: ${(context.raw as number).toFixed(2)}%`,
                },
            },
        },
        scales: {
            y: {
                grid: {
                    color: 'rgba(124, 91, 255, 0.08)',
                },
                ticks: {
                    color: '#a3a3a3',
                    font: {
                        size: 11,
                    },
                },
                title: {
                    display: true,
                    text: 'Return (%)',
                    color: '#737373',
                    font: {
                        size: 12,
                        weight: 500 as const,
                    },
                },
            },
            x: {
                grid: {
                    display: false,
                },
                ticks: {
                    color: '#a3a3a3',
                    font: {
                        size: 11,
                    },
                },
            },
        },
    };

    return (
        <div className="card">
            <h4 className='text-base font-semibold text-neutral-800 mb-4'>Yearly Returns</h4>
            <div style={{ position: 'relative', height: '350px' }}>
                <Bar data={yearlyData} options={options} />
            </div>
        </div>
    );
};

export default YearlyBarChart;
