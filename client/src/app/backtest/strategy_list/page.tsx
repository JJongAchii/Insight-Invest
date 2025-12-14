"use client";

import React from "react";
import Searchbar from "./Searchbar";
import Contents from "./Contents";
import {
  useFetchStrategiesQuery,
  useFetchStrategyMonthlyNavQuery,
} from "@/state/api";

const StrategyList = () => {
  const { data: strategyInfo } = useFetchStrategiesQuery({});
  const { data: strategyNav } = useFetchStrategyMonthlyNavQuery({});

  return (
    <div className="flex flex-col gap-6 pb-16">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-semibold text-neutral-900">
          Strategy Library
        </h1>
        <p className="text-sm text-neutral-500 mt-1">
          Explore and manage your saved backtest strategies
        </p>
      </div>

      <div className="card">
        <Searchbar />
        <Contents strategyList={strategyInfo} strategyNav={strategyNav} />
      </div>
    </div>
  );
};

export default StrategyList;
