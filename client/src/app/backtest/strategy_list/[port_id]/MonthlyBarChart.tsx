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
            const periodReturn = ((end - previousEndValue) / previousEndValue) * 100;
            returnData.push({ period: key, return: periodReturn });
        }
        previousEndValue = end;
    }

    return returnData;
};

const MonthlyBarChart = ({ strategyName, strategyNav, bmNav }: { strategyName: string; strategyNav: NavData[];  bmNav: string;}) => {
    const bmNavData: NavData[] = JSON.parse(bmNav);

    if (!strategyNav || strategyNav.length === 0) {
        return <p>No data available for chart.</p>;
    }

    const monthlyReturns = calculateReturns(strategyNav, 'month');
    const bMYearlyReturns = calculateReturns(bmNavData, 'month');

    const monthlyData = {
        labels: monthlyReturns.map((item) => item.period),
        datasets: [
            {
                label: `${strategyName} (%)`,
                data: monthlyReturns.map((item) => item.return),
                backgroundColor: 'rgba(54, 162, 235, 0.6)',
                borderColor: 'rgba(54, 162, 235, 1)',
                borderWidth: 1,
            },
            {
                label: 'Benchmark (%)',
                data: bMYearlyReturns.map((item) => item.return),
                backgroundColor: 'rgba(192, 75, 192, 0.2)',
                borderColor: 'rgb(192, 75, 192)',
                borderWidth: 1,
            },
        ],
    };

    const options = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                display: true,
            },
            tooltip: {
                callbacks: {
                    label: (context: TooltipItem<'bar'>) => `${(context.raw as number).toFixed(2)}%`,
                },
            },
        },
        scales: {
            y: {
                title: {
                    display: true,
                    text: 'Return (%)',
                },
            },
            x: {
                title: {
                    display: true,
                    text: 'Date',
                },
            },
        },
    };

    return (
        <div className="flex flex-col gap-8 bg-white shadow-lg rounded-2xl p-8">
            <h4 className="text-lg font-semibold">Monthly Returns</h4>
            <div style={{ position: 'relative', height: '400px' }}>
                <Bar data={monthlyData} options={options} />
            </div>
        </div>
    );
};

export default MonthlyBarChart;
