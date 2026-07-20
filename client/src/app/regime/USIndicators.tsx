"use client";

import React from "react";
import { useFetchMacroDataQuery, useFetchMacroInfoQuery } from "@/state/api";
import MacroChart from "./MacroChart";
import StatTile from "@/components/ui/StatTile";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";

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

/** US macro tab: recession snapshot tiles + the five FRED indicator charts. */
const USIndicators: React.FC = () => {
  const {
    data: macroInfo,
    error: infoError,
    refetch: refetchInfo,
  } = useFetchMacroInfoQuery({});
  const {
    data: macroData,
    error: dataError,
    refetch: refetchData,
  } = useFetchMacroDataQuery({});

  const findIndicator = (fred: string) => {
    const info =
      macroInfo?.find((macro: MacroInfo) => macro.fred === fred) ||
      ({} as Partial<MacroInfo>);
    const data =
      macroData?.filter((d: MacroData) => d.macro_id === info.macro_id) || [];
    return { info, data };
  };

  const { info: recessionInfo, data: recessionData } = findIndicator("USRECD");
  const { info: t10y2yInfo, data: t10y2yData } = findIndicator("T10Y2Y");
  const { info: unemploymentInfo, data: unemploymentData } =
    findIndicator("UNRATE");
  const { info: employeesInfo, data: employeesData } = findIndicator("PAYEMS");
  const { info: fedFundInfo, data: fedFundData } = findIndicator("FEDFUNDS");
  const { info: cpiInfo, data: cpiData } = findIndicator("CPIAUCSL");

  if (infoError || dataError) {
    return (
      <div className="card">
        <ErrorState
          message="Failed to load macro data"
          onRetry={() => {
            refetchInfo();
            refetchData();
          }}
        />
      </div>
    );
  }

  if (!macroInfo || !macroData) {
    return (
      <div className="card">
        <LoadingState label="Loading macro indicators..." />
      </div>
    );
  }

  // Get latest recession indicator value
  const latestRecession = recessionData?.[recessionData.length - 1];
  const isRecession = latestRecession?.value === 1;

  // Get latest values for key indicators
  const latestT10Y2Y = t10y2yData?.[t10y2yData.length - 1];
  const latestUnemployment = unemploymentData?.[unemploymentData.length - 1];
  const latestFedFund = fedFundData?.[fedFundData.length - 1];

  return (
    <div className="flex flex-col gap-6">
      {/* Current Regime Indicator */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="section-header mb-0">US Cycle Snapshot</h2>
          <span className={isRecession ? "badge-danger" : "badge-success"}>
            {isRecession ? "Recession" : "Expansion"}
          </span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatTile
            label="Yield Spread (10Y-2Y)"
            value={`${latestT10Y2Y?.value?.toFixed(2) ?? "—"}%`}
            deltaType={
              latestT10Y2Y && latestT10Y2Y.value >= 0 ? "gain" : "loss"
            }
          />
          <StatTile
            label="Unemployment Rate"
            value={`${latestUnemployment?.value?.toFixed(1) ?? "—"}%`}
          />
          <StatTile
            label="Fed Funds Rate"
            value={`${latestFedFund?.value?.toFixed(2) ?? "—"}%`}
          />
          <StatTile
            label="Last Updated"
            value={latestRecession?.base_date?.slice(0, 7) ?? "—"}
          />
        </div>
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 gap-6">
        <MacroChart
          primaryData={t10y2yData}
          recessionData={recessionData}
          primaryLabel={t10y2yInfo.description ?? "T10Y2Y"}
          recessionLabel={recessionInfo.description ?? "US Recession"}
          title="10-Year Minus 2-Year Treasury Spread"
          baseline={0}
        />

        <MacroChart
          primaryData={unemploymentData}
          recessionData={recessionData}
          primaryLabel={unemploymentInfo.description ?? "Unemployment Rate"}
          recessionLabel={recessionInfo.description ?? "US Recession"}
          title="Unemployment Rate"
          baseline={5}
        />

        <MacroChart
          primaryData={employeesData}
          recessionData={recessionData}
          primaryLabel={employeesInfo.description ?? "Nonfarm Payrolls"}
          recessionLabel={recessionInfo.description ?? "US Recession"}
          title="All Employees, Total Nonfarm"
          baseline={150000}
        />

        <MacroChart
          primaryData={fedFundData}
          recessionData={recessionData}
          primaryLabel={fedFundInfo.description ?? "Federal Funds Rate"}
          recessionLabel={recessionInfo.description ?? "US Recession"}
          title="Federal Funds Rate"
        />

        <MacroChart
          primaryData={cpiData}
          recessionData={recessionData}
          primaryLabel={cpiInfo.description ?? "CPI"}
          recessionLabel={recessionInfo.description ?? "US Recession"}
          title="Consumer Price Index for All Urban Consumers"
          baseline={0.02}
        />
      </div>
    </div>
  );
};

export default USIndicators;
