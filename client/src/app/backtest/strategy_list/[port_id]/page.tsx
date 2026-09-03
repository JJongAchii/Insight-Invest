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
import React, { use, useMemo } from "react";
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
import { Activity, ArrowLeft, Radio, ShieldAlert } from "lucide-react";
import PageHeader from "@/components/ui/PageHeader";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";
import PeriodBarChart from "@/components/charts/PeriodBarChart";
import { calculatePeriodReturns, NavPoint } from "@/components/charts/returns";

interface StrategyDetailProps {
  params: Promise<{ port_id: string }>;
}

interface CaseSectionProps {
  id: string;
  index: string;
  eyebrow: string;
  title: string;
  description: string;
  children: React.ReactNode;
}

/** Numbering reflects the actual review order of a saved strategy case file. */
const CaseSection: React.FC<CaseSectionProps> = ({
  id,
  index,
  eyebrow,
  title,
  description,
  children,
}) => (
  <section id={id} className="scroll-mt-24" aria-labelledby={`${id}-title`}>
    <header className="mb-4 grid gap-2 border-t border-edge pt-6 md:grid-cols-[4rem_minmax(0,1fr)] md:gap-4">
      <span className="font-mono text-xs font-semibold text-primary-300">{index}</span>
      <div>
        <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-ink-muted">
          {eyebrow}
        </p>
        <div className="mt-1 flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between sm:gap-5">
          <h2 id={`${id}-title`} className="text-xl font-semibold tracking-[-0.025em] text-ink">
            {title}
          </h2>
          <p className="max-w-2xl text-sm leading-6 text-ink-muted">{description}</p>
        </div>
      </div>
    </header>
    <div className="space-y-6 md:pl-20">{children}</div>
  </section>
);

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
  const { port_id: portIdParam } = use(params);
  const port_id = Number(portIdParam);
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
  const [setStatus, { isLoading: toggling, isError: statusError }] =
    useSetStrategyStatusMutation();

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
  const strategyMethod = strategyInfo[0].strategy_name;
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
        eyebrow="Investment case file"
        title={
          <div className="flex flex-wrap items-center gap-3">
            <span>{strategyName}</span>
            {isActive && (
              <span className="badge-success font-mono text-[9px] tracking-[0.1em]">
                LIVE TRACKING
              </span>
            )}
          </div>
        }
        description={
          strategyMethod
            ? `${strategyMethod}의 전제, 역사적 증거, 저장 후 경로를 하나의 검토 순서로 읽습니다.`
            : "전제, 역사적 증거, 저장 후 경로를 하나의 검토 순서로 읽습니다."
        }
        meta={
          <>
            <span>case #{port_id}</span>
            <span>·</span>
            <span>{isActive ? "tracking" : "research only"}</span>
            <span>·</span>
            <span>unverified</span>
          </>
        }
        actions={
          <div className="flex items-center gap-2">
            <Link
              href="/backtest/strategy_list"
              className="btn-ghost inline-flex items-center gap-2 text-sm"
            >
              <ArrowLeft size={16} aria-hidden />
              결과 목록
            </Link>
            <button
              type="button"
              onClick={() =>
                setStatus({
                  portId: port_id,
                  status: isActive ? "saved" : "active",
                })
              }
              disabled={toggling}
              aria-busy={toggling}
              className={`${isActive ? "btn-secondary" : "btn-primary"} inline-flex items-center gap-2 text-sm`}
            >
              {isActive ? <Activity size={15} aria-hidden /> : <Radio size={15} aria-hidden />}
              {toggling ? "변경 중…" : isActive ? "추적 중지" : "운영 추적 시작"}
            </button>
          </div>
        }
      />

      <aside className="relative overflow-hidden rounded-2xl border border-warning/25 bg-warning/5 px-5 py-4">
        <span aria-hidden className="absolute inset-y-0 left-0 w-px bg-warning" />
        <div className="flex items-start gap-3">
          <ShieldAlert size={18} className="mt-0.5 shrink-0 text-warning" aria-hidden />
          <div>
            <p className="text-sm font-semibold text-ink">검증되지 않은 연구 기록</p>
            <p className="mt-1 text-xs leading-5 text-ink-secondary">
              운영 추적은 저장 이후의 관찰을 시작할 뿐, 전략 승인이나 미래 성과 보장을 의미하지 않습니다.
            </p>
          </div>
        </div>
      </aside>

      {statusError && (
        <p role="alert" className="rounded-xl border border-losses/30 bg-losses/5 px-4 py-3 text-sm text-losses">
          추적 상태를 변경하지 못했습니다. 연결을 확인한 뒤 다시 시도해 주세요.
        </p>
      )}

      <nav
        aria-label="전략 보고서 목차"
        className="scrollbar-hidden flex gap-1 overflow-x-auto rounded-2xl border border-edge bg-surface p-1.5"
      >
        {[
          ["#research-contract", "01", "연구 계약"],
          ["#historical-evidence", "02", "역사적 증거"],
          ["#return-path", "03", "수익 경로"],
          ...(isActive
            ? [
                ["#live-observation", "04", "저장 후 관찰"],
                ["#next-rebalance", "05", "다음 리밸런싱"],
              ]
            : []),
        ].map(([href, index, label]) => (
          <a
            key={href}
            href={href}
            className="flex shrink-0 items-center gap-2 rounded-xl px-3 py-2 text-xs text-ink-secondary transition-colors hover:bg-raised hover:text-ink"
          >
            <span className="font-mono text-[10px] text-primary-300">{index}</span>
            {label}
          </a>
        ))}
      </nav>

      <CaseSection
        id="research-contract"
        index="01"
        eyebrow="Mandate & assumptions"
        title="연구 계약"
        description="무엇을, 어느 구간에서, 어떤 비용과 실행 규칙으로 시험했는지 먼저 고정합니다."
      >
        {renderAnalyticsGroup(premiseCard)}
      </CaseSection>

      <CaseSection
        id="historical-evidence"
        index="02"
        eyebrow="Backtest evidence"
        title="역사적 증거"
        description="헤드라인 수치보다 기간 의존성·낙폭·국면·거래 현실을 함께 봅니다."
      >
        {metricSummary}
        {renderAnalyticsGroup(
          <>
            {rollingCard}
            {drawdownCard}
            {phaseCrisisCard}
            {monthlyTradingRow}
          </>
        )}
      </CaseSection>

      <CaseSection
        id="return-path"
        index="03"
        eyebrow="Path, not point estimate"
        title="수익 경로"
        description="누적 성과와 월·연도별 분포를 벤치마크 및 저장 후 구간과 같은 축에서 확인합니다."
      >
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
      </CaseSection>

      {isActive && (
        <CaseSection
          id="live-observation"
          index="04"
          eyebrow="Post-save observation"
          title="저장 후 관찰"
          description="백테스트와 실제 저장 이후의 경로 차이, 현재 보유 비중, 분포 내 위치를 분리해 읽습니다."
        >
          <LiveHeadline live={liveData} />
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <HoldingsNowCard weights={liveData?.weights} />
            <ExpectationCard expectation={liveData?.expectation} />
          </div>
          <LiveMetricsTable live={liveData} bmMetrics={bmDetails.metrics} />
        </CaseSection>
      )}

      {isActive && (
        <CaseSection
          id="next-rebalance"
          index="05"
          eyebrow="Next observable action"
          title="다음 리밸런싱"
          description="예상일과 목표 비중은 실행 확정값이 아니라 전일 저녁 계산될 관찰 대상입니다."
        >
          <NextRebalCard portId={port_id} isActive={isActive} />
        </CaseSection>
      )}
    </div>
  );
};

export default StrategyDetail;
