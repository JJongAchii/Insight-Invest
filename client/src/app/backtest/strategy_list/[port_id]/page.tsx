"use client"

import { useFetchBmByIdQuery, useFetchStNavByIdQuery, useFetchStRebalByIdQuery, useFetchStrategyByIdQuery } from '@/state/api'
import React, { useState } from 'react'
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


  if (!strategyInfo || !bmDetails || !bmDetails.metrics || !bmDetails.nav) return <LoadingSpinner />


  return (
    <div className="flex flex-col xl:overflow-auto gap-5 pb-36">
      <Link
        href="/backtest/strategy_list"
        className="flex items-center text-blue-600 hover:text-blue-800 transition-colors duration-200 font-semibold">
          <FaArrowLeft className="mr-2" />
          Back to Strategy List
      </Link>
      <MetricSummary strategyInfo={strategyInfo[0]} rebalWeight={strategyRebal} bmMetrics={bmDetails.metrics}/>
      <LineChart strategyName={strategyInfo[0].port_name} strategyNav={strategyNav} bmNav={bmDetails.nav}/>
      <YearlyBarChart strategyName={strategyInfo[0].port_name} strategyNav={strategyNav} bmNav={bmDetails.nav}/>
      <MonthlyBarChart strategyName={strategyInfo[0].port_name} strategyNav={strategyNav} bmNav={bmDetails.nav}/>
    </div>
  )
}

export default StrategyDetail
