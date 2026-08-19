"use client";

import {
  useFetchBmByIdQuery,
  useFetchStNavByIdQuery,
  useFetchStRebalByIdQuery,
  useFetchStrategyAnalyticsQuery,
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
import LiveHeadline from "./LiveHeadline";
import HoldingsNowCard from "./HoldingsNowCard";
import ExpectationCard from "./ExpectationCard";
import PremiseCard from "./analysis/PremiseCard";
import RollingCard from "./analysis/RollingCard";
import DrawdownCard from "./analysis/DrawdownCard";
import PhaseCrisisCard from "./analysis/PhaseCrisisCard";
import MonthlyStatsCard from "./analysis/MonthlyStatsCard";
import TradingRealityCard from "./analysis/TradingRealityCard";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import PageHeader from "@/components/ui/PageHeader";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";
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
  const {
    data: analytics,
    isLoading: analyticsLoading,
    isError: analyticsIsError,
    refetch: refetchAnalytics,
  } = useFetchStrategyAnalyticsQuery(port_id);
  const [setStatus, { isLoading: toggling }] = useSetStrategyStatusMutation();

  const bmNavData: NavPoint[] = useMemo(
    () => (bmDetails?.nav ? JSON.parse(bmDetails.nav) : []),
    [bmDetails]
  );

  // 벤치마크 실체 표시명 — bm nav 행의 bm_name("BM(SPY)")에서 추출해
  // 차트 범례가 "Benchmark (SPY)"처럼 무엇과 비교 중인지 보이게 한다.
  const bmLabel = useMemo(() => {
    const raw = (bmNavData[0] as { bm_name?: string } | undefined)?.bm_name;
    if (!raw) return undefined;
    const m = raw.match(/^BM\((.+)\)$/);
    return `Benchmark (${m ? m[1] : raw})`;
  }, [bmNavData]);

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

  // 분석 계층(6카드)은 하나의 analytics 응답을 공유한다 — 로딩·에러·부재 상태도 함께
  // 취급한다. saved 배치는 MetricSummary가 카드 사이에 끼어들어 그룹이 둘로 나뉘지만,
  // 각 그룹은 같은 판정을 그대로 재사용한다. 에러·부재 시 null을 반환하면 "백테스트
  // 분석" 구분 헤더만 빈 공간 위에 남으므로, 항상 카드(로딩/에러/부재/본문)를 반환한다.
  const analyticsEmpty = !analyticsLoading && !analyticsIsError && (!analytics || analytics.empty);
  const analyticsReady =
    !analyticsLoading && !analyticsIsError && !!analytics && !analytics.empty;
  const analyticsNotes = analytics?.notes;
  const bmNote = analyticsNotes?.["bm"];

  const renderAnalyticsGroup = (children: React.ReactNode): React.ReactNode => {
    if (analyticsLoading) {
      return (
        <div className="card">
          <LoadingState label="분석 지표를 불러오는 중..." />
        </div>
      );
    }
    // 로딩 분기와 같은 무제목 카드 — active 모드의 "백테스트 분석" h3와 제목이
    // 중복되지 않게 한다 (saved 모드에서 두 그룹이 각각 렌더될 때도 동일)
    if (analyticsIsError) {
      return (
        <div className="card">
          <ErrorState message="분석 지표를 불러오지 못했습니다" onRetry={refetchAnalytics} />
        </div>
      );
    }
    if (analyticsEmpty) {
      return (
        <div className="card">
          <p className="text-sm text-ink-muted">분석할 데이터가 없습니다</p>
        </div>
      );
    }
    if (!analyticsReady) return null;
    return children;
  };

  const premiseCard = (
    <PremiseCard premise={analytics?.premise ?? null} note={analyticsNotes?.["premise"]} />
  );
  const rollingCard = (
    <RollingCard
      rolling={analytics?.rolling ?? null}
      note={analyticsNotes?.["rolling"]}
      bmNote={bmNote}
    />
  );
  const drawdownCard = (
    <DrawdownCard drawdowns={analytics?.drawdowns ?? null} note={analyticsNotes?.["drawdowns"]} />
  );
  const phaseCrisisCard = (
    <PhaseCrisisCard
      phases={analytics?.phases ?? null}
      crisis={analytics?.crisis ?? []}
      phasesNote={analyticsNotes?.["phases"]}
      bmNote={bmNote}
    />
  );
  const monthlyTradingRow = (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <MonthlyStatsCard
        monthly={analytics?.monthly ?? null}
        note={analyticsNotes?.["monthly"]}
        bmNote={bmNote}
      />
      <TradingRealityCard trading={analytics?.trading ?? null} note={analyticsNotes?.["trading"]} />
    </div>
  );

  const yearlyMonthlyReturns = (
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
  );

  const metricSummary = (
    <MetricSummary
      strategyInfo={strategyInfo[0]}
      rebalWeight={strategyRebal}
      bmMetrics={bmDetails.metrics}
    />
  );

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

      {isActive ? (
        <>
          <LiveHeadline live={liveData} />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <HoldingsNowCard weights={liveData?.weights} />
            <ExpectationCard expectation={liveData?.expectation} />
          </div>
          <NextRebalCard portId={port_id} isActive={isActive} />
          <LineChart
            strategyName={strategyName}
            strategyNav={strategyNav}
            bmNav={bmDetails.nav}
            liveNav={liveData?.nav}
            savedAt={liveData?.saved_at}
            bmLiveNav={liveData?.bm_live?.nav}
            bmLabel={bmLabel}
          />
          <LiveMetricsTable live={liveData} bmMetrics={bmDetails.metrics} />
          {yearlyMonthlyReturns}

          <h3 className="section-header border-t border-edge pt-6">Backtest Analysis</h3>
          {renderAnalyticsGroup(
            <>
              {premiseCard}
              {rollingCard}
              {drawdownCard}
              {phaseCrisisCard}
              {monthlyTradingRow}
            </>
          )}
          {metricSummary}
        </>
      ) : (
        <>
          {renderAnalyticsGroup(premiseCard)}
          {metricSummary}
          {renderAnalyticsGroup(
            <>
              {rollingCard}
              {drawdownCard}
              {phaseCrisisCard}
              {monthlyTradingRow}
            </>
          )}
          <LineChart
            strategyName={strategyName}
            strategyNav={strategyNav}
            bmNav={bmDetails.nav}
            liveNav={liveData?.nav}
            savedAt={liveData?.saved_at}
            bmLiveNav={liveData?.bm_live?.nav}
            bmLabel={bmLabel}
          />
          {yearlyMonthlyReturns}
        </>
      )}
    </div>
  );
};

export default StrategyDetail;
