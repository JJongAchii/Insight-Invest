"use client"

import { useFetchBmByIdQuery, useFetchStNavByIdQuery, useFetchStRebalByIdQuery, useFetchStrategyByIdQuery } from '@/state/api'
import React from 'react'
import MetricSummary from './MetricSummary'
import LineChart from './LineChart'
import MonthlyBarChart from './MonthlyBarChart'
import YearlyBarChart from './YearlyBarChart'

interface StrategyDetailProps {
  params: { port_id: number }
}

const StrategyDetail = ({ params }: StrategyDetailProps) => {
  const { port_id } = params
  const { data: strategyInfo } = useFetchStrategyByIdQuery(port_id)
  const { data: strategyNav } = useFetchStNavByIdQuery(port_id)
  const { data: strategyRebal } = useFetchStRebalByIdQuery(port_id)
  const { data: bmDetails } = useFetchBmByIdQuery(port_id)

  if (!strategyInfo || !bmDetails || !bmDetails.metrics || !bmDetails.nav) return <p>No data available</p>


  return (
    <div className="flex flex-col xl:overflow-auto gap-5 pb-36">
      <MetricSummary strategyInfo={strategyInfo[0]} rebalWeight={strategyRebal} bmMetrics={bmDetails.metrics}/>
      <LineChart strategyName={strategyInfo[0].port_name} strategyNav={strategyNav} bmNav={bmDetails.nav}/>
      <YearlyBarChart strategyName={strategyInfo[0].port_name} strategyNav={strategyNav} bmNav={bmDetails.nav}/>
      <MonthlyBarChart strategyName={strategyInfo[0].port_name} strategyNav={strategyNav} bmNav={bmDetails.nav}/>
    </div>
  )
}

export default StrategyDetail
