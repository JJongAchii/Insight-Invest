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
    const bmNavData: NavData[] = JSON.parse(bmNav);

    if (!strategyNav || strategyNav.length === 0) {
        return <p>No data available for chart.</p>;
    }

    const yearlyReturns = calculateReturns(strategyNav, 'year');
    const bMYearlyReturns = calculateReturns(bmNavData, 'year');

    const yearlyData = {
        labels: yearlyReturns.map((item) => item.period),
        datasets: [
            {
                label: `${strategyName} (%)`,
                data: yearlyReturns.map((item) => item.return),
                backgroundColor: 'rgba(75, 192, 192, 0.6)',
                borderColor: 'rgba(75, 192, 192, 1)',
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
                    label: (context: TooltipItem<'bar'>) => `${(context.raw as number).toFixed(2)}%`, // Explicitly cast context.raw to number
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
                    display: false,
                    text: 'Date',
                },
            },
        },
    };

    return (
        <div className="flex flex-col bg-white shadow-lg rounded-2xl px-2 py-3 gap-5">
            <h4 className="text-lg text-center font-semibold">Yearly Returns</h4>
            <div style={{ position: 'relative', height: '400px' }}>
                <Bar data={yearlyData} options={options} />
            </div>
        </div>
    );
};

export default YearlyBarChart;
