"use client"

import { useFetchStNavByIdQuery, useFetchStRebalByIdQuery, useFetchStrategyByIdQuery } from '@/state/api'
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

  if (!strategyInfo) return <p>No data available</p>


  return (
    <div className="flex flex-col xl:overflow-auto gap-5 pb-36">
      <MetricSummary strategyInfo={strategyInfo[0]} rebalWeight={strategyRebal}/>
      <LineChart strategyNav={strategyNav} />
      <YearlyBarChart strategyNav={strategyNav}/>
      <MonthlyBarChart strategyNav={strategyNav}/>
    </div>
  )
}

export default StrategyDetail
