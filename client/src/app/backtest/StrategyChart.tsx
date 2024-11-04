import React from 'react';
import { Line } from 'react-chartjs-2';
import 'chart.js/auto';

const StrategyChart = ({ navResult }) => {
    if (!navResult) return <p>No data available</p>; 
    
    const navData = JSON.parse(navResult);

    if (!navData.index || !navData.columns || !navData.data) return <p>Invalid data format</p>;

    const chartLabels = navData.index.map((date) => new Date(date).toISOString().split('T')[0]);
    
    const datasets = navData.columns.map((column, index) => ({
        label: column,
        data: navData.data.map((row) => row[index]),
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

    const options = {
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
                mode: 'index',
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
                    callback: (value) => `${value}`, // Format y-axis values as currency
                },
            },
        },
        interaction: {
            mode: 'nearest',
            axis: 'x',
            intersect: false,
        },
        animation: {
            duration: 1000,
            easing: 'easeInOutQuart',
        },
    };

    return (
        <div className="flex flex-col bg-white shadow-lg rounded-2xl p-8" style={{ height: 450 }}>
            <h4 className='text-lg font-semibold'>Performance Chart</h4>
            <Line data={data} options={options} />
        </div>
    );
};

export default StrategyChart;
