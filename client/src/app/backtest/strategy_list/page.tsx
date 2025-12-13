"use client"

import React from 'react'
import Searchbar from './Searchbar'
import Contents from './Contents';
import { useFetchStrategiesQuery, useFetchStrategyMonthlyNavQuery } from '@/state/api';


const StrategyList = () => {

  const { data: strategyInfo } = useFetchStrategiesQuery({});
  const { data: strategyNav } = useFetchStrategyMonthlyNavQuery({});

  return (
    <div className="flex flex-col gap-8 pb-36">
      {/* Page Header */}
      <div className="mb-4">
        <h1 className="text-4xl font-bold mb-2">
          <span className="gradient-text">Strategy Library</span>
        </h1>
        <p className="text-gray-600 text-lg">Explore and manage your saved backtest strategies</p>
      </div>

      <div className="card-modern">
        <Searchbar />
        <Contents strategyList={strategyInfo} strategyNav={strategyNav} />
      </div>
    </div>
  );
}

export default StrategyList
