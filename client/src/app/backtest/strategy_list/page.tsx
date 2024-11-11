"use client"

import React from 'react'
import Searchbar from './Searchbar'
import Contents from './Contents';
import { useFetchStrategiesQuery, useFetchStrategyMonthlyNavQuery } from '@/state/api';


const StrategyList = () => {

  const { data: strategyInfo } = useFetchStrategiesQuery({});
  const { data: strategyNav } = useFetchStrategyMonthlyNavQuery({});
  
  return (
    <div className="flex flex-col bg-white shadow-lg rounded-2xl p-8 gap-5">
      <h4 className='text-lg font-semibold'>Strategy List</h4>
      <Searchbar />
      <Contents strategyList={strategyInfo} strategyNav={strategyNav} />
    </div>
  );
}

export default StrategyList