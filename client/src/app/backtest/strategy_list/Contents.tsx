import React from 'react'
import { Line } from 'react-chartjs-2'
import { Chart as ChartJS, LineElement, CategoryScale, LinearScale, PointElement, Tooltip } from 'chart.js'
import { FaChartLine } from 'react-icons/fa'
import { useRouter } from 'next/navigation'

ChartJS.register(LineElement, CategoryScale, LinearScale, PointElement, Tooltip)


interface Strategy {
    port_id: number
    port_name: string
    strategy_name: string
    ann_ret: number
    ann_vol: number
    sharpe: number
}

interface StrategyNav {
    port_id: number
    trade_date: string
    value: number
}

const Contents = ({ strategyList, strategyNav }: {strategyList: Strategy[]; strategyNav: StrategyNav[]}) => {

    const router = useRouter();
    const handleGridClick = (port_id: number) => {
        router.push(`/backtest/strategy_list/${port_id}`)
    }

    return (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 mt-6">
            {
                strategyList?.map((strategy) => (
                    <div
                        key={strategy.port_id}
                        className='flex bg-gradient-to-br from-white to-blue-50 p-6 rounded-xl shadow-md border-2 border-transparent hover:border-blue-400 cursor-pointer hover:shadow-2xl transition-all duration-300 transform hover:-translate-y-2 group'
                        onClick={() => handleGridClick(strategy.port_id)}
                    >
                        <div className='w-1/2 pr-4'>
                            <div className='flex items-center gap-2 text-blue-600 mb-3'>
                                <FaChartLine size={18} className="group-hover:scale-110 transition-transform" />
                                <span className='font-bold text-lg'>{strategy.port_name}</span>
                            </div>
                            <div className='text-gray-600 font-medium mb-3 text-sm'>{strategy.strategy_name}</div>
                            <div className='space-y-1'>
                                <div className='flex items-center gap-2'>
                                    <span className='text-xs text-gray-500'>Annual Return:</span>
                                    <span className='text-green-600 font-bold text-sm'>{strategy.ann_ret}%</span>
                                </div>
                                <div className='flex items-center gap-2'>
                                    <span className='text-xs text-gray-500'>Volatility:</span>
                                    <span className='text-orange-600 font-bold text-sm'>{strategy.ann_vol}%</span>
                                </div>
                                <div className='flex items-center gap-2'>
                                    <span className='text-xs text-gray-500'>Sharpe:</span>
                                    <span className='text-indigo-600 font-bold text-sm'>{strategy.sharpe}</span>
                                </div>
                            </div>
                        </div>
                        <div className='w-1/2 relative'>
                            {/* Mini Chart */}
                            <Line
                                data={{
                                    labels: strategyNav
                                        ?.filter((nav) => nav.port_id === strategy.port_id)
                                        .map((nav) => nav.trade_date),
                                    datasets: [
                                        {
                                            label: 'Value',
                                            data: strategyNav
                                                ?.filter((nav) => nav.port_id === strategy.port_id)
                                                .map((nav) => nav.value),
                                            fill: true,
                                            backgroundColor: 'rgba(99, 102, 241, 0.1)',
                                            borderColor: 'rgb(99, 102, 241)',
                                            borderWidth: 2,
                                            tension: 0.4,
                                            pointRadius: 0,
                                        },
                                    ],
                                }}
                                options={{
                                    responsive: true,
                                    maintainAspectRatio: false,
                                    scales: {
                                        x: {
                                            display: false,
                                        },
                                        y: {
                                            display: false,
                                        },
                                    },
                                    plugins: {
                                        legend: {
                                            display: false,
                                        },
                                        tooltip: {
                                            enabled: true,
                                            backgroundColor: 'rgba(255, 255, 255, 0.95)',
                                            titleColor: '#1f2937',
                                            bodyColor: '#4b5563',
                                            borderColor: '#e5e7eb',
                                            borderWidth: 1,
                                            padding: 8,
                                            cornerRadius: 6,
                                        },
                                    },
                                }}
                                height={50}
                            />
                        </div>
                    </div>
                ))
            }
        </div>
    )
}

export default Contents
