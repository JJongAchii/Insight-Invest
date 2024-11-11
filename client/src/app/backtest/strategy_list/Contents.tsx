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
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            {
                strategyList?.map((strategy) => (
                    <div 
                        key={strategy.port_id} 
                        className='flex bg-gradient-to-br from-sky-100 to-white p-6 rounded-xl shadow-md border border-gray-200 hover:shadow-lg transition-shadow duration-200 transform hover:scale-105'
                        onClick={() => handleGridClick(strategy.port_id)}
                    >
                        <div className='w-1/2'>
                            <div className='flex items-center gap-2 text-sky-500 mb-2'>
                                <FaChartLine size={18} />
                                <span className='font-semibold text-lg'>{strategy.port_name}</span>
                            </div>
                            <div className='text-gray-600 font-medium'>{strategy.strategy_name}</div>
                            <div className='text-green-500 font-semibold text-sm mt-2'>Annual Return: {strategy.ann_ret} %</div>
                            <div className='text-orange-500 font-semibold text-sm'>Annual Vol: {strategy.ann_vol} %</div>
                            <div className='text-red-500 font-semibold text-sm'>Sharpe Ratio: {strategy.sharpe}</div>
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
                                            backgroundColor: 'rgba(75, 192, 192, 0.2)',
                                            borderColor: 'rgb(75, 192, 192)',
                                            tension: 0.3,
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
                                            backgroundColor: 'rgba(0,0,0,0.7)',
                                            titleColor: '#fff',
                                            bodyColor: '#fff',
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
