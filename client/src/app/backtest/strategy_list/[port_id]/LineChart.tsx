import React, { useRef, useEffect } from 'react';
import { Line } from 'react-chartjs-2';
import { Chart as ChartJS, LineElement, CategoryScale, LinearScale, PointElement, Tooltip, Filler } from 'chart.js';

ChartJS.register(LineElement, CategoryScale, LinearScale, PointElement, Tooltip, Filler);


interface NavData {
  trade_date: string;
  value: number;
}

const LineChart = ({ strategyNav }: {strategyNav: NavData[]}) => {

  return (
    <div className="flex flex-col bg-white shadow-lg rounded-2xl p-8 gap-8">
      <h4 className='text-lg font-semibold'>Performance Chart</h4>
      <div style={{ position: 'relative', height: '400px' }}>
        <Line 
          data={{
            labels: strategyNav?.map((nav) => nav.trade_date),
            datasets: [
              {
                label: "Value",
                data: strategyNav?.map((nav) => nav.value),
                fill: true,
                backgroundColor: 'rgba(75, 192, 192, 0.2)', // Gradient fill
                borderColor: 'rgb(75, 192, 192)',
                tension: 0.3,
                pointRadius: 0,
                pointHoverRadius: 6,
                borderWidth: 2,
              }
            ]
          }}
          options={{
            responsive: true,
            maintainAspectRatio: false,
            scales: {
              x: {
                display: true,
                grid: {
                  display: false,
                },
                title: {
                  display: true,
                  text: 'Date',
                  color: '#888',
                  font: { size: 12, weight: 'bold' },
                }
              },
              y: {
                display: true,
                grid: {
                  color: 'rgba(200, 200, 200, 0.2)',
                },
                title: {
                  display: true,
                  text: 'Return (%)',
                  color: '#888',
                  font: { size: 12, weight: 'bold' },
                }
              },
            },
            plugins: {
              legend: {
                display: false,
              },
              tooltip: {
                enabled: true,
                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                titleColor: '#fff',
                bodyColor: '#fff',
                borderWidth: 1,
                borderColor: 'rgba(75, 192, 192, 0.5)',
                callbacks: {
                  label: (context) => `Value: ${context.raw}`,
                  title: (context) => `Date: ${context[0].label}`,
                },
              },
            },
            hover: {
              mode: 'nearest',
              intersect: true,
            },
          }}
        />
      </div>
    </div>
  )
}

export default LineChart;
