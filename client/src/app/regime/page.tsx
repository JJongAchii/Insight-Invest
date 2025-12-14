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

  const recessionInfo =
    macroInfo?.find((macro: MacroInfo) => macro.fred === "USRECD") || {};
  const recessionData = macroData?.filter(
    (data: MacroData) => data.macro_id === recessionInfo.macro_id
  );

  const t10y2yInfo =
    macroInfo?.find((macro: MacroInfo) => macro.fred === "T10Y2Y") || {};
  const t10y2yData = macroData?.filter(
    (data: MacroData) => data.macro_id === t10y2yInfo.macro_id
  );

  const unemploymentInfo =
    macroInfo?.find((macro: MacroInfo) => macro.fred === "UNRATE") || {};
  const unemploymentData = macroData?.filter(
    (data: MacroData) => data.macro_id === unemploymentInfo.macro_id
  );

  const employeesInfo =
    macroInfo?.find((macro: MacroInfo) => macro.fred === "PAYEMS") || {};
  const employeesData = macroData?.filter(
    (data: MacroData) => data.macro_id === employeesInfo.macro_id
  );

  const fedFundInfo =
    macroInfo?.find((macro: MacroInfo) => macro.fred === "FEDFUNDS") || {};
  const fedFundData = macroData?.filter(
    (data: MacroData) => data.macro_id === fedFundInfo.macro_id
  );

  const cpiInfo =
    macroInfo?.find((macro: MacroInfo) => macro.fred === "CPIAUCSL") || {};
  const cpiData = macroData?.filter(
    (data: MacroData) => data.macro_id === cpiInfo.macro_id
  );

  if (!macroInfo || !macroData) return <LoadingSpinner />;

  // Get latest recession indicator value
  const latestRecession = recessionData?.[recessionData.length - 1];
  const isRecession = latestRecession?.value === 1;

  // Get latest values for key indicators
  const latestT10Y2Y = t10y2yData?.[t10y2yData.length - 1];
  const latestUnemployment = unemploymentData?.[unemploymentData.length - 1];
  const latestFedFund = fedFundData?.[fedFundData.length - 1];

  return (
    <div className="flex flex-col gap-6 pb-16">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900">
            Market Regime Analysis
          </h1>
          <p className="text-sm text-neutral-500 mt-1">
            Macroeconomic indicators and recession probability
          </p>
        </div>
      </div>

      {/* Current Regime Indicator */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-neutral-900">
            Current Regime
          </h2>
          <span
            className={`px-3 py-1 rounded-full text-sm font-medium ${
              isRecession
                ? "bg-danger/10 text-danger"
                : "bg-success/10 text-success"
            }`}
          >
            {isRecession ? "Recession" : "Expansion"}
          </span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 bg-neutral-50 rounded-lg">
            <p className="text-xs text-neutral-500 mb-1">Yield Spread (10Y-2Y)</p>
            <p
              className={`text-xl font-semibold ${
                latestT10Y2Y?.value >= 0 ? "text-success" : "text-danger"
              }`}
            >
              {latestT10Y2Y?.value?.toFixed(2)}%
            </p>
          </div>
          <div className="p-4 bg-neutral-50 rounded-lg">
            <p className="text-xs text-neutral-500 mb-1">Unemployment Rate</p>
            <p className="text-xl font-semibold text-neutral-900">
              {latestUnemployment?.value?.toFixed(1)}%
            </p>
          </div>
          <div className="p-4 bg-neutral-50 rounded-lg">
            <p className="text-xs text-neutral-500 mb-1">Fed Funds Rate</p>
            <p className="text-xl font-semibold text-neutral-900">
              {latestFedFund?.value?.toFixed(2)}%
            </p>
          </div>
          <div className="p-4 bg-neutral-50 rounded-lg">
            <p className="text-xs text-neutral-500 mb-1">Last Updated</p>
            <p className="text-xl font-semibold text-neutral-900">
              {latestRecession?.base_date?.slice(0, 7)}
            </p>
          </div>
        </div>
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 gap-6">
        <MacroChart
          primaryData={t10y2yData}
          recessionData={recessionData}
          primaryLabel={t10y2yInfo.description}
          recessionLabel={recessionInfo.description}
          title="10-Year Minus 2-Year Treasury Spread"
        />

        <MacroChart
          primaryData={unemploymentData}
          recessionData={recessionData}
          primaryLabel={unemploymentInfo.description}
          recessionLabel={recessionInfo.description}
          title="Unemployment Rate"
          baseline={5}
        />

        <MacroChart
          primaryData={employeesData}
          recessionData={recessionData}
          primaryLabel={employeesInfo.description}
          recessionLabel={recessionInfo.description}
          title="All Employees, Total Nonfarm"
          baseline={150000}
        />

        <MacroChart
          primaryData={fedFundData}
          recessionData={recessionData}
          primaryLabel={fedFundInfo.description}
          recessionLabel={recessionInfo.description}
          title="Federal Funds Rate"
        />

        <MacroChart
          primaryData={cpiData}
          recessionData={recessionData}
          primaryLabel={cpiInfo.description}
          recessionLabel={recessionInfo.description}
          title="Consumer Price Index for All Urban Consumers"
          baseline={0.02}
        />
      </div>
    </div>
  );
};

export default Regime;
