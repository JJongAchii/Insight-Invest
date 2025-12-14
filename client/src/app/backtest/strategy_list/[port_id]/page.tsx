"use client";

import {
  useFetchBmByIdQuery,
  useFetchStNavByIdQuery,
  useFetchStRebalByIdQuery,
  useFetchStrategyByIdQuery,
} from "@/state/api";
import React from "react";
import MetricSummary from "./MetricSummary";
import LineChart from "./LineChart";
import MonthlyBarChart from "./MonthlyBarChart";
import YearlyBarChart from "./YearlyBarChart";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import LoadingSpinner from "@/app/(components)/LoadingSpinner";

interface StrategyDetailProps {
  params: { port_id: number };
}

const StrategyDetail = ({ params }: StrategyDetailProps) => {
  const { port_id } = params;
  const { data: strategyInfo } = useFetchStrategyByIdQuery(port_id);
  const { data: strategyNav } = useFetchStNavByIdQuery(port_id);
  const { data: strategyRebal } = useFetchStRebalByIdQuery(port_id);
  const { data: bmDetails } = useFetchBmByIdQuery(port_id);

  if (
    !strategyInfo ||
    strategyInfo.length === 0 ||
    !strategyNav ||
    !strategyRebal ||
    !bmDetails ||
    !bmDetails.metrics ||
    !bmDetails.nav
  )
    return <LoadingSpinner />;

  return (
    <div className="flex flex-col gap-6 pb-16">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-neutral-900">
            Strategy Report
          </h1>
          <p className="text-sm text-neutral-500 mt-1">
            Detailed performance analysis and metrics
          </p>
        </div>
        <Link href="/backtest/strategy_list" className="btn-secondary">
          <ArrowLeft size={16} className="mr-2" />
          Back to List
        </Link>
      </div>

      <MetricSummary
        strategyInfo={strategyInfo[0]}
        rebalWeight={strategyRebal}
        bmMetrics={bmDetails.metrics}
      />
      <LineChart
        strategyName={strategyInfo[0].port_name}
        strategyNav={strategyNav}
        bmNav={bmDetails.nav}
      />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <YearlyBarChart
          strategyName={strategyInfo[0].port_name}
          strategyNav={strategyNav}
          bmNav={bmDetails.nav}
        />
        <MonthlyBarChart
          strategyName={strategyInfo[0].port_name}
          strategyNav={strategyNav}
          bmNav={bmDetails.nav}
        />
      </div>
    </div>
  );
};

export default StrategyDetail;
