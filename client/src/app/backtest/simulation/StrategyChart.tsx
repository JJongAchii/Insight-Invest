import React from 'react';
import { Line } from 'react-chartjs-2';
import { ChartOptions } from 'chart.js';
import 'chart.js/auto';

const StrategyChart = ({ navResult }: { navResult: any }) => {

    const navData = navResult ? JSON.parse(navResult) : { index: [], columns: [], data: [] };

    const chartLabels = navData.index.map((date: any) => new Date(date).toISOString().split('T')[0]);

    const datasets = navData.columns.map((column: any, index: any) => ({
        label: column,
        data: navData.data.map((row: any) => row[index]),
        borderColor: ['#4A90E2', '#50E3C2', '#F5A623', '#D0021B', '#BD10E0'][index % 5],
        backgroundColor: 'rgba(74, 144, 226, 0.1)',
        borderWidth: 2.5,
        tension: 0.3,
        pointRadius: 0,
        pointHoverRadius: 5,
        hoverBorderWidth: 2,
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
                    color: '#333',
                    font: {
                        size: 14,
                    },
                    boxWidth: 20,
                    padding: 20,
                },
            },
            tooltip: {
                mode: 'index' as const,
                intersect: false,
                backgroundColor: 'rgba(0, 0, 0, 0.7)',
                titleFont: {
                    size: 14,
                },
                bodyFont: {
                    size: 12,
                },
                padding: 12,
                cornerRadius: 5,
            },
        },
        scales: {
            x: {
                grid: {
                    display: false,
                },
                ticks: {
                    color: '#333',
                    font: {
                        size: 12,
                    },
                },
            },
            y: {
                grid: {
                    color: 'rgba(200, 200, 200, 0.3)',
                    lineWidth: 0.5,
                },
                ticks: {
                    color: '#333',
                    font: {
                        size: 12,
                    },
                    callback: (tickValue: string | number) => {
                        if (typeof tickValue === 'number') {
                            return `${tickValue}`;
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
            duration: 1000,
            easing: 'easeInOutQuart',
        },
    };

    return (
        <div className="flex flex-col bg-white shadow-lg rounded-2xl p-8 relative" style={{ height: 450 }}>
            <h4 className='text-lg text-center font-semibold'>Performance Chart</h4>
            {navResult ? (
                <Line data={data} options={options} />
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
};

export default StrategyChart;
