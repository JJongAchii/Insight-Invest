"use client";

import {
  useFetchBmByIdQuery,
  useFetchStNavByIdQuery,
  useFetchStRebalByIdQuery,
  useFetchStrategyByIdQuery,
  useFetchStrategyLiveByIdQuery,
  useSetStrategyStatusMutation,
  NavPoint as LiveNavPoint,
} from "@/state/api";
import React, { useMemo } from "react";
import MetricSummary from "./MetricSummary";
import LineChart from "./LineChart";
import LiveMetricsTable from "./LiveMetricsTable";
import NextRebalCard from "./NextRebalCard";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import PageHeader from "@/components/ui/PageHeader";
import LoadingState from "@/components/ui/LoadingState";
import PeriodBarChart from "@/components/charts/PeriodBarChart";
import { calculatePeriodReturns, NavPoint } from "@/components/charts/returns";

interface StrategyDetailProps {
  params: { port_id: number };
}

interface ReturnBarRow {
  [series: string]: string | number | null;
  label: string;
  strategy: number | null;
  benchmark: number | null;
  /** null when no live series was supplied, or the period has no live data yet. */
  live: number | null;
}

/** strategy/benchmark 기간 수익률에 저장 후 라이브 구간(liveNav)의 같은 기간 수익률을
 *  "실전(저장 후)" 시리즈로 병기한다. 라이브 전용 신규 기간(백테스트 구간 밖)도 행으로 추가된다. */
const buildReturnData = (
  strategyNav: NavPoint[],
  bmNav: NavPoint[],
  period: "month" | "year",
  liveNav?: LiveNavPoint[]
): ReturnBarRow[] => {
  const strategyReturns = calculatePeriodReturns(strategyNav, period);
  const bmReturns = calculatePeriodReturns(bmNav, period);
  const bmByPeriod = new Map(bmReturns.map((r) => [r.period, r.return]));

  const hasLive = !!liveNav && liveNav.length > 0;
  // liveNav[0] is the saved_at anchor (~1000 base) — pass it as initialRef so the
  // first (partial) period since save also gets a bar, not just subsequent ones.
  const liveReturns = hasLive
    ? calculatePeriodReturns(
        liveNav!.map((p) => ({ trade_date: p.date, value: p.value })),
        period,
        liveNav![0].value
      )
    : [];
  const liveByPeriod = new Map(liveReturns.map((r) => [r.period, r.return]));

  const rows: ReturnBarRow[] = strategyReturns.map((r) => ({
    label: r.period,
    strategy: r.return,
    benchmark: bmByPeriod.get(r.period) ?? 0,
    live: hasLive ? liveByPeriod.get(r.period) ?? null : null,
  }));

  if (hasLive) {
    const covered = new Set(strategyReturns.map((r) => r.period));
    for (const r of liveReturns) {
      if (covered.has(r.period)) continue;
      rows.push({
        label: r.period,
        strategy: null,
        benchmark: bmByPeriod.get(r.period) ?? null,
        live: r.return,
      });
    }
    rows.sort((a, b) => a.label.localeCompare(b.label));
  }

  return rows;
};

const StrategyDetail = ({ params }: StrategyDetailProps) => {
  const { port_id } = params;
  const { data: strategyInfo } = useFetchStrategyByIdQuery(port_id);
  const { data: strategyNav } = useFetchStNavByIdQuery(port_id);
  const { data: strategyRebal } = useFetchStRebalByIdQuery(port_id);
  const { data: bmDetails } = useFetchBmByIdQuery(port_id);
  const { data: liveData } = useFetchStrategyLiveByIdQuery(port_id);
  const [setStatus, { isLoading: toggling }] = useSetStrategyStatusMutation();

  const bmNavData: NavPoint[] = useMemo(
    () => (bmDetails?.nav ? JSON.parse(bmDetails.nav) : []),
    [bmDetails]
  );

  const monthlyData = useMemo(
    () => buildReturnData(strategyNav ?? [], bmNavData, "month", liveData?.nav),
    [strategyNav, bmNavData, liveData?.nav]
  );
  const yearlyData = useMemo(
    () => buildReturnData(strategyNav ?? [], bmNavData, "year", liveData?.nav),
    [strategyNav, bmNavData, liveData?.nav]
  );

  if (
    !strategyInfo ||
    strategyInfo.length === 0 ||
    !strategyNav ||
    !strategyRebal ||
    !bmDetails ||
    !bmDetails.metrics ||
    !bmDetails.nav
  ) {
    return (
      <div className="card">
        <LoadingState label="Loading strategy report..." />
      </div>
    );
  }

  const strategyName = strategyInfo[0].port_name;
  const status = strategyInfo[0].status;
  const isActive = status === "active";
  const hasLiveNav = (liveData?.nav?.length ?? 0) > 0;
  const barSeries = [
    { key: "strategy", name: strategyName, color: "var(--chart-1)" },
    { key: "benchmark", name: "Benchmark", color: "var(--chart-2)" },
    ...(hasLiveNav
      ? [{ key: "live", name: "실전(저장 후)", color: "var(--chart-3)" }]
      : []),
  ];

  return (
    <div className="flex flex-col gap-6 pb-16">
      <PageHeader
        title={
          <div className="flex items-center gap-3">
            <span>Strategy Report</span>
            {isActive && (
              <span className="badge-neutral" style={{ color: "var(--gains)" }}>
                ACTIVE
              </span>
            )}
          </div>
        }
        description="Detailed performance analysis and metrics"
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={() =>
                setStatus({
                  portId: port_id,
                  status: isActive ? "saved" : "active",
                })
              }
              disabled={toggling}
              className="btn-secondary inline-flex items-center text-sm"
            >
              {isActive ? "운영 중지" : "운영 시작"}
            </button>
            <Link
              href="/backtest/strategy_list"
              className="btn-secondary inline-flex items-center"
            >
              <ArrowLeft size={16} className="mr-2" />
              Back to List
            </Link>
          </div>
        }
      />

      <MetricSummary
        strategyInfo={strategyInfo[0]}
        rebalWeight={strategyRebal}
        bmMetrics={bmDetails.metrics}
      />
      <NextRebalCard portId={port_id} isActive={isActive} />
      <LineChart
        strategyName={strategyName}
        strategyNav={strategyNav}
        bmNav={bmDetails.nav}
        liveNav={liveData?.nav}
        savedAt={liveData?.saved_at}
      />
      <LiveMetricsTable live={liveData} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <h4 className="text-base font-semibold text-ink mb-4">
            Yearly Returns
          </h4>
          <PeriodBarChart
            data={yearlyData}
            series={barSeries}
            height={350}
            yFormatter={(v) => `${v.toFixed(2)}%`}
          />
        </div>
        <div className="card">
          <h4 className="text-base font-semibold text-ink mb-4">
            Monthly Returns
          </h4>
          <PeriodBarChart
            data={monthlyData}
            series={barSeries}
            height={350}
            yFormatter={(v) => `${v.toFixed(2)}%`}
          />
        </div>
      </div>
    </div>
  );
};

export default StrategyDetail;
