import React, { useRef, useEffect } from 'react';
import { Line } from 'react-chartjs-2';
import { Chart as ChartJS, LineElement, CategoryScale, LinearScale, PointElement, Tooltip, Filler } from 'chart.js';

ChartJS.register(LineElement, CategoryScale, LinearScale, PointElement, Tooltip, Filler);


interface NavData {
  trade_date: string;
  value: number;
}

interface BmNavData {
  trade_date: string;
  bm_name: string;
  value: number;
}

const LineChart = ({ strategyName, strategyNav, bmNav }: {strategyName: string; strategyNav: NavData[]; bmNav: string;}) => {
  const bmNavData: BmNavData[] = bmNav ? JSON.parse(bmNav) : [];
  return (
    <div className="card-modern">
      <div className='flex items-center gap-3 mb-6'>
        <div className="w-10 h-10 bg-gradient-to-r from-blue-500 to-cyan-600 rounded-xl flex items-center justify-center">
          <span className="text-white text-xl font-bold">📈</span>
        </div>
        <h4 className='text-xl font-bold text-gray-800'>Cumulative Performance</h4>
      </div>
      <div className="bg-gradient-to-br from-gray-50 to-blue-50 rounded-xl p-4">
        <div style={{ position: 'relative', height: '400px' }}>
          <Line
            data={{
              labels: strategyNav?.map((nav) => nav.trade_date),
              datasets: [
                {
                  label: strategyName,
                  data: strategyNav?.map((nav) => nav.value),
                  fill: true,
                  backgroundColor: 'rgba(99, 102, 241, 0.1)',
                  borderColor: 'rgb(99, 102, 241)',
                  tension: 0.4,
                  pointRadius: 0,
                  pointHoverRadius: 6,
                  borderWidth: 3,
                },
                {
                  label: "Benchmark",
                  data: bmNavData?.map((nav) => nav.value),
                  fill: false,
                  backgroundColor: 'rgba(168, 85, 247, 0.1)',
                  borderColor: 'rgb(168, 85, 247)',
                  tension: 0.4,
                  pointRadius: 0,
                  pointHoverRadius: 6,
                  borderWidth: 3,
                  borderDash: [5, 5],
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
                  display: true,
                  grid: {
                    color: 'rgba(0, 0, 0, 0.05)',
                    lineWidth: 1,
                  },
                  ticks: {
                    color: '#6b7280',
                    font: {
                      size: 11,
                    },
                  },
                },
              },
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
                    padding: 16,
                    usePointStyle: true,
                    pointStyle: 'circle',
                  },
                },
                tooltip: {
                  enabled: true,
                  backgroundColor: 'rgba(255, 255, 255, 0.95)',
                  titleColor: '#1f2937',
                  bodyColor: '#4b5563',
                  borderColor: '#e5e7eb',
                  borderWidth: 1,
                  padding: 12,
                  cornerRadius: 8,
                  callbacks: {
                    label: (context) => `${context.dataset.label}: ${(context.raw as number).toFixed(2)}`,
                    title: (context) => `Date: ${context[0].label}`,
                  },
                },
              },
              hover: {
                mode: 'nearest',
                intersect: false,
              },
            }}
          />
        </div>
      </div>
    </div>
  )
}

export default LineChart;
