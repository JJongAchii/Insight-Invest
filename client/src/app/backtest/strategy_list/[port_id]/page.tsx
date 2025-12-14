"use client"

import { useFetchBmByIdQuery, useFetchStNavByIdQuery, useFetchStRebalByIdQuery, useFetchStrategyByIdQuery } from '@/state/api'
import React from 'react'
import MetricSummary from './MetricSummary'
import LineChart from './LineChart'
import MonthlyBarChart from './MonthlyBarChart'
import YearlyBarChart from './YearlyBarChart'
import Link from 'next/link'
import { FaArrowLeft } from 'react-icons/fa' // Import an icon for better visual cue
import LoadingSpinner from '@/app/(components)/LoadingSpinner'

interface StrategyDetailProps {
  params: { port_id: number }
}

const StrategyDetail = ({ params }: StrategyDetailProps) => {
  const { port_id } = params
  const { data: strategyInfo } = useFetchStrategyByIdQuery(port_id)
  const { data: strategyNav } = useFetchStNavByIdQuery(port_id)
  const { data: strategyRebal } = useFetchStRebalByIdQuery(port_id)
  const { data: bmDetails } = useFetchBmByIdQuery(port_id)


  if (!strategyInfo || strategyInfo.length === 0 || !strategyNav || !strategyRebal || !bmDetails || !bmDetails.metrics || !bmDetails.nav) return <LoadingSpinner />


  return (
    <div className="flex flex-col xl:overflow-auto gap-8 pb-36">
      {/* Page Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-4xl font-bold mb-2">
            <span className="gradient-text">Strategy Report</span>
          </h1>
          <p className="text-gray-600 text-lg">Detailed performance analysis and metrics</p>
        </div>
        <Link
          href="/backtest/strategy_list"
          className="px-6 py-3 bg-white/80 backdrop-blur-sm rounded-xl shadow-md hover:shadow-lg transition-all duration-300 group flex items-center gap-2 border-2 border-gray-200 hover:border-blue-400"
        >
          <FaArrowLeft className="text-gray-600 group-hover:text-blue-600 transition-colors group-hover:-translate-x-1 transition-transform" />
          <span className="font-semibold text-gray-700 group-hover:text-blue-600 transition-colors">Back to List</span>
        </Link>
      </div>

      <MetricSummary strategyInfo={strategyInfo[0]} rebalWeight={strategyRebal} bmMetrics={bmDetails.metrics}/>
      <LineChart strategyName={strategyInfo[0].port_name} strategyNav={strategyNav} bmNav={bmDetails.nav}/>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <YearlyBarChart strategyName={strategyInfo[0].port_name} strategyNav={strategyNav} bmNav={bmDetails.nav}/>
        <MonthlyBarChart strategyName={strategyInfo[0].port_name} strategyNav={strategyNav} bmNav={bmDetails.nav}/>
      </div>
    </div>
  )
}

export default StrategyDetail
