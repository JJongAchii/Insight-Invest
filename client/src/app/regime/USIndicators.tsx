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
      macroData?.filter((d: MacroData) => d.macro_id === info.macro_id).sort((a: MacroData, b: MacroData) => a.base_date.localeCompare(b.base_date)) || [];
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
          message="미국 경제 지표를 불러오지 못했습니다"
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
        <LoadingState label="미국 경제 지표를 불러오는 중…" />
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
          <h2 className="section-header mb-0">미국 경제 지표 요약</h2>
          <span className={!latestRecession ? "badge-neutral" : isRecession ? "badge-danger" : "badge-success"}>
            {!latestRecession ? "경기 관측값 없음" : isRecession ? "침체 관측" : "비침체 관측"}
          </span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatTile
            label="장단기 금리차 (10년−2년)"
            helpKey="macro.t10y2y"
            value={latestT10Y2Y ? `${latestT10Y2Y.value.toFixed(2)}%p` : "—"}
            sub={`${latestT10Y2Y?.base_date ?? "기준일 미확인"} · FRED`}
            deltaType={
              !latestT10Y2Y ? "neutral" : latestT10Y2Y.value >= 0 ? "gain" : "loss"
            }
          />
          <StatTile
            label="실업률"
            helpKey="macro.unrate"
            value={latestUnemployment ? `${latestUnemployment.value.toFixed(1)}%` : "—"}
            sub={`${latestUnemployment?.base_date ?? "기준일 미확인"} · FRED`}
          />
          <StatTile
            label="유효 연방기금금리"
            helpKey="macro.fedfunds"
            value={latestFedFund ? `${latestFedFund.value.toFixed(2)}%` : "—"}
            sub={`${latestFedFund?.base_date ?? "기준일 미확인"} · FRED`}
          />
          <StatTile
            label="침체 지표 기준월"
            value={latestRecession?.base_date?.slice(0, 7) ?? "—"}
          />
        </div>
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <MacroChart
          primaryData={t10y2yData}
          recessionData={recessionData}
          primaryLabel={t10y2yInfo.description ?? "T10Y2Y"}
          recessionLabel={recessionInfo.description ?? "US Recession"}
          title="미 국채 장단기 금리차 (%p)"
          helpKey="macro.t10y2y"
          baseline={0}
        />

        <MacroChart
          primaryData={unemploymentData}
          recessionData={recessionData}
          primaryLabel={unemploymentInfo.description ?? "Unemployment Rate"}
          recessionLabel={recessionInfo.description ?? "US Recession"}
          title="실업률 (%)"
          helpKey="macro.unrate"
          baseline={5}
        />

        <MacroChart
          primaryData={employeesData}
          recessionData={recessionData}
          primaryLabel={employeesInfo.description ?? "Nonfarm Payrolls"}
          recessionLabel={recessionInfo.description ?? "US Recession"}
          title="비농업 고용 (천 명)"
          helpKey="macro.payems"
          baseline={150000}
        />

        <MacroChart
          primaryData={fedFundData}
          recessionData={recessionData}
          primaryLabel={fedFundInfo.description ?? "Federal Funds Rate"}
          recessionLabel={recessionInfo.description ?? "US Recession"}
          title="유효 연방기금금리 (%)"
          helpKey="macro.fedfunds"
        />

        <MacroChart
          primaryData={cpiData}
          recessionData={recessionData}
          primaryLabel={cpiInfo.description ?? "CPI"}
          recessionLabel={recessionInfo.description ?? "US Recession"}
          title="소비자물가지수 (CPI, 지수 수준)"
          helpKey="macro.cpi"
        />
      </div>
    </div>
  );
};

export default USIndicators;
