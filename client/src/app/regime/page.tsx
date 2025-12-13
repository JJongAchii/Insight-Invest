"use client";

import { useFetchMacroDataQuery, useFetchMacroInfoQuery } from "@/state/api";
import React from "react";
import MacroChart from "./MacroChart";
import LoadingSpinner from "../(components)/LoadingSpinner";


interface MacroInfo {
  macro_id: string;
  fred: string;
  description: string;
}

interface MacroData {
  macro_id: string;
  base_date: string;
  value: number;
}


const Regime = () => {
  const { data: macroInfo } = useFetchMacroInfoQuery({});
  const { data: macroData } = useFetchMacroDataQuery({});

  const recessionInfo = macroInfo?.find((macro: MacroInfo) => macro.fred === "USRECD") || {};
  const recessionData = macroData?.filter((data: MacroData) => data.macro_id === recessionInfo.macro_id);

  const t10y2yInfo = macroInfo?.find((macro: MacroInfo) => macro.fred === "T10Y2Y") || {};
  const t10y2yData = macroData?.filter((data: MacroData) => data.macro_id === t10y2yInfo.macro_id);

  const unemploymentInfo = macroInfo?.find((macro: MacroInfo) => macro.fred === "UNRATE") || {};
  const unemploymentData = macroData?.filter((data: MacroData) => data.macro_id === unemploymentInfo.macro_id);

  const employeesInfo = macroInfo?.find((macro: MacroInfo) => macro.fred === "PAYEMS") || {};
  const employeesData = macroData?.filter((data: MacroData) => data.macro_id === employeesInfo.macro_id);

  const fedFundInfo = macroInfo?.find((macro: MacroInfo) => macro.fred === "FEDFUNDS") || {};
  const fedFundData = macroData?.filter((data: MacroData) => data.macro_id === fedFundInfo.macro_id);

  const cpiInfo = macroInfo?.find((macro: MacroInfo) => macro.fred === "CPIAUCSL") || {};
  const cpiData = macroData?.filter((data: MacroData) => data.macro_id === cpiInfo.macro_id);

  if (!macroInfo || !macroData) return <LoadingSpinner />

  return (
    <div className="flex flex-col xl:overflow-auto gap-8 pb-36">
      {/* Page Header */}
      <div className="mb-4">
        <h1 className="text-4xl font-bold mb-2">
          <span className="gradient-text">Market Regime Analysis</span>
        </h1>
        <p className="text-gray-600 text-lg">Macroeconomic indicators and recession probability</p>
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 gap-6">
        <MacroChart
          primaryData={t10y2yData}
          recessionData={recessionData}
          primaryLabel={t10y2yInfo.description}
          recessionLabel={recessionInfo.description}
          title="10-Year Minus 2-Year Treasury Interest Rate Spread"
          icon="📈"
        />

        <MacroChart
          primaryData={unemploymentData}
          recessionData={recessionData}
          primaryLabel={unemploymentInfo.description}
          recessionLabel={recessionInfo.description}
          title="Unemployment Rate"
          baseline={5}
          icon="👥"
        />

        <MacroChart
          primaryData={employeesData}
          recessionData={recessionData}
          primaryLabel={employeesInfo.description}
          recessionLabel={recessionInfo.description}
          title="All Employees, Total Nonfarm"
          baseline={150000}
          icon="💼"
        />

        <MacroChart
          primaryData={fedFundData}
          recessionData={recessionData}
          primaryLabel={fedFundInfo.description}
          recessionLabel={recessionInfo.description}
          title="Federal Funds Rate"
          icon="🏦"
        />

        <MacroChart
          primaryData={cpiData}
          recessionData={recessionData}
          primaryLabel={cpiInfo.description}
          recessionLabel={recessionInfo.description}
          title="Consumer Price Index for All Urban Consumers"
          baseline={0.02}
          icon="💰"
        />
      </div>
    </div>
  );
};

export default Regime;
