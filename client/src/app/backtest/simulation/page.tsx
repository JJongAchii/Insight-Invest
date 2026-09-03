"use client";

import { useEffect, useMemo, useState } from "react";
import SetStrategy from "./SetStrategy";
import StrategyChart from "./StrategyChart";
import StrategyMetrics from "./StrategyMetrics";
import LoadingSpinner from "@/app/(components)/LoadingSpinner";
import TimeSeriesChart from "@/components/charts/TimeSeriesChart";
import PeriodBarChart from "@/components/charts/PeriodBarChart";
import EmptyState from "@/components/ui/EmptyState";
import InfoTip from "@/components/ui/InfoTip";
import PageHeader from "@/components/ui/PageHeader";
import {
  useRunBacktestMutation,
  BacktestPayload,
  SaveStrategyPayload,
  BacktestRunResult,
} from "@/state/api";

type TabKey =
  | "performance"
  | "drawdown"
  | "rolling"
  | "returns"
  | "contribution"
  | "stress";

const TABS: { key: TabKey; label: string }[] = [
  { key: "performance", label: "성과" },
  { key: "drawdown", label: "낙폭" },
  { key: "rolling", label: "롤링 샤프" },
  { key: "returns", label: "기간 수익" },
  { key: "contribution", label: "기여도" },
  { key: "stress", label: "위기 구간" },
];

/** localStorage에 남은 v1 결과(문자열 필드)는 무시하고 v2 형태만 복원 */
const loadStoredResult = (): BacktestRunResult | null => {
  if (typeof window === "undefined") return null;
  try {
    const saved = localStorage.getItem("backtestResult");
    if (!saved) return null;
    const parsed = JSON.parse(saved);
    if (parsed && Array.isArray(parsed.nav) && parsed.metrics?.strategy) {
      return parsed as BacktestRunResult;
    }
  } catch {
    // fallthrough
  }
  return null;
};

const formatPct = (v: number | null | undefined) =>
  typeof v === "number" ? `${v.toFixed(2)}%` : "—";

const formatNumber = (v: number | null | undefined) =>
  typeof v === "number" ? v.toFixed(2) : "—";

const apiErrorMessage = (error: unknown): string => {
  if (typeof error === "object" && error !== null && "data" in error) {
    const data = (error as { data?: { detail?: unknown } }).data;
    if (typeof data?.detail === "string") return data.detail;
  }
  return "백테스트를 실행하지 못했습니다.";
};

// 인터페이스 타입은 암묵적 인덱스 시그니처가 없어 차트 data 타입에 바로 못 넘긴다
const toSeriesData = (points: { date: string; value: number }[]) =>
  points.map((p) => ({ date: p.date, value: p.value }));

const toPeriodData = (
  points: { label: string; strategy: number | null; benchmark: number | null }[]
) =>
  points.map((p) => ({
    label: p.label,
    strategy: p.strategy,
    benchmark: p.benchmark,
  }));

const Simulation = () => {
  const [runBacktest, { isLoading }] = useRunBacktestMutation();
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [activeTab, setActiveTab] = useState<TabKey>("performance");
  const [runError, setRunError] = useState<string | null>(null);

  const [selectedTicker, setSelectedTicker] = useState<
    Record<string, SaveStrategyPayload>
  >(() => {
    if (typeof window === "undefined") return {};
    const savedTicker = localStorage.getItem("selectedTicker");
    return savedTicker ? JSON.parse(savedTicker) : {};
  });
  const [backtestResult, setBacktestResult] =
    useState<BacktestRunResult | null>(loadStoredResult);

  const handleRunBacktest = async (payload: BacktestPayload) => {
    try {
      setRunError(null);
      const result = await runBacktest(payload).unwrap();
      setBacktestResult(result);
      setActiveTab("performance");
      setSelectedTicker((prevSelectedTicker) => ({
        ...prevSelectedTicker,
        [payload.strategy_name]: {
          ...payload,
          result_token: result.result_token,
        },
      }));
    } catch (error) {
      console.error("Error running backtest:", error);
      setRunError(apiErrorMessage(error));
      setBacktestResult(null);
    }
  };

  useEffect(() => {
    localStorage.setItem("backtestResult", JSON.stringify(backtestResult));
  }, [backtestResult]);

  useEffect(() => {
    localStorage.setItem("selectedTicker", JSON.stringify(selectedTicker));
  }, [selectedTicker]);

  const handleClearClick = () => {
    setShowClearConfirm(true);
  };

  // 서버 호출 없이 로컬 상태만 정리 (백테스트 결과는 어차피 토큰 기반 임시 저장)
  const confirmClear = () => {
    localStorage.removeItem("backtestResult");
    localStorage.removeItem("selectedTicker");
    setBacktestResult(null);
    setSelectedTicker({});
    setShowClearConfirm(false);
  };

  const cancelClear = () => {
    setShowClearConfirm(false);
  };

  const analytics = backtestResult?.analytics;

  const monthlyReturns = useMemo(
    () => (analytics ? analytics.monthly_returns.slice(-36) : []),
    [analytics]
  );

  const contributionMaxAbs = useMemo(() => {
    if (!analytics || analytics.contribution.length === 0) return 0;
    return Math.max(...analytics.contribution.map((c) => Math.abs(c.value)));
  }, [analytics]);

  return (
    <div className="flex flex-col gap-6 pb-16">
      {isLoading && <LoadingSpinner />}

      {/* Clear Confirmation Modal */}
      {showClearConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="card-elevated max-w-md mx-4">
            <h3 className="text-lg font-semibold text-ink mb-2">
              모든 실험 결과를 지울까요?
            </h3>
            <p className="text-ink-secondary text-sm mb-6">
              이 브라우저에 저장된 백테스트 결과와 선택 종목이 모두 삭제됩니다. 되돌릴 수 없습니다.
            </p>
            <div className="flex gap-3 justify-end">
              <button onClick={cancelClear} className="btn-secondary">
                취소
              </button>
              <button onClick={confirmClear} className="btn-danger">
                모두 지우기
              </button>
            </div>
          </div>
        </div>
      )}

      <PageHeader
        eyebrow="Strategy lab"
        title="리서치 · 전략 실험"
        description="가설을 과거 데이터에서 탐색하되, 미검증 결과를 실전 판단과 분리합니다."
        actions={
          <button onClick={handleClearClick} disabled={isLoading} className="btn-danger">
            결과 모두 지우기
          </button>
        }
      />

      <SetStrategy onRunBacktest={handleRunBacktest} isLoading={isLoading} />

      {runError && (
        <div className="rounded-xl border border-losses/30 bg-losses/5 px-4 py-3 text-sm text-losses">
          {runError}
        </div>
      )}

      {backtestResult ? (
        <section className="relative space-y-6 border-t border-edge pt-8" aria-labelledby="backtest-output">
          <span aria-hidden className="absolute -top-px left-0 h-px w-44 bg-gradient-to-r from-primary-400 via-primary-500 to-secondary-400" />
          <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-primary-300">Historical output</p>
              <h2 id="backtest-output" className="mt-1 text-xl font-semibold tracking-[-0.025em] text-ink">
                {backtestResult.strategy_name}
              </h2>
              <p className="mt-1 text-sm text-ink-muted">과거 시뮬레이션 결과 · 실전 성과가 아닙니다.</p>
            </div>
            <div className="flex flex-wrap gap-x-3 gap-y-1 font-mono text-[10px] uppercase tracking-[0.06em] text-ink-muted">
              <span>관측 {backtestResult.nav.length}</span>
              <span>·</span>
              <span>리밸런스 기록 {backtestResult.weights.length}</span>
              <span>·</span>
              <span>BM {backtestResult.benchmark.name}</span>
            </div>
          </header>

          <div
            className="scrollbar-hidden -mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0"
            role="group"
            aria-label="백테스트 핵심 지표"
            tabIndex={0}
          >
            <dl className="metric-strip min-w-[38rem] grid-cols-4 sm:min-w-0" aria-label="전략 핵심 지표">
              {[
                ["연환산 수익", formatPct(backtestResult.metrics.strategy.ann_ret), backtestResult.metrics.strategy.ann_ret],
                ["연환산 변동성", formatPct(backtestResult.metrics.strategy.ann_vol), null],
                ["샤프 비율", formatNumber(backtestResult.metrics.strategy.sharpe), null],
                ["최대 낙폭", formatPct(backtestResult.metrics.strategy.mdd), backtestResult.metrics.strategy.mdd],
              ].map(([label, value, signed]) => (
                <div key={String(label)} className="metric-tile p-4 sm:p-5">
                  <dt className="metric-label">{String(label)}</dt>
                  <dd className={`mt-2 text-2xl font-semibold num ${typeof signed === "number" ? signed >= 0 ? "text-gains" : "text-losses" : "text-ink"}`}>
                    {String(value)}
                  </dd>
                </div>
              ))}
            </dl>
          </div>

      {backtestResult.calculation_contract && (
        <div className="rounded-xl border border-edge bg-raised px-4 py-3 text-xs text-ink-secondary">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="font-semibold text-ink">계산·체결 계약</span>
            <span className="text-ink-muted num">
              {backtestResult.calculation_contract.calculation_version}
            </span>
          </div>
          <p className="mt-1">
            수익률 기준 · {backtestResult.calculation_contract.return_basis} · 체결 · 리밸런스 거래일 종가
          </p>
          {backtestResult.calculation_contract.cash_distributions !== "included" && (
            <p className="mt-1 text-warning">
              정확한 현금분배 이벤트를 합성한 Total Return이 아닙니다. 서로 다른 수익률 기준의 자산은 한 실행에서 혼합하지 않습니다.
            </p>
          )}
        </div>
      )}

      {/* Result Tabs */}
      <div className="segmented-control self-start" aria-label="전략 결과 보기">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            aria-pressed={activeTab === tab.key}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Performance */}
      {activeTab === "performance" && (
        <div className="card">
          <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
            <h3 className="text-base font-semibold text-ink">누적 성과</h3>
            <p className="text-xs text-ink-muted">초기 NAV 1,000 기준 · 벤치마크 동시 비교</p>
          </div>
          <StrategyChart
            strategyName={backtestResult?.strategy_name ?? "Strategy"}
            nav={backtestResult?.nav ?? null}
            benchmark={backtestResult?.benchmark ?? null}
          />
          <StrategyMetrics
            result={backtestResult}
            selectedTicker={selectedTicker}
          />
        </div>
      )}

      {/* Drawdown */}
      {activeTab === "drawdown" && (
        <div className="card">
          <div className="flex items-start justify-between">
            <h3 className="section-header">낙폭</h3>
            <InfoTip helpKey="bt.drawdown" />
          </div>
          {analytics && analytics.drawdown.length > 0 ? (
            <TimeSeriesChart
              data={toSeriesData(analytics.drawdown)}
              series={[
                { key: "value", name: "Drawdown", color: "var(--losses)" },
              ]}
              height={360}
              yFormatter={(v) => `${v.toFixed(0)}%`}
              baseline={0}
            />
          ) : (
            <EmptyState
              title="낙폭 데이터가 없습니다"
              hint="백테스트를 실행하면 고점 대비 하락이 표시됩니다"
            />
          )}
        </div>
      )}

      {/* Rolling Sharpe */}
      {activeTab === "rolling" && (
        <div className="card">
          <div className="flex items-start justify-between">
            <h3 className="section-header">롤링 샤프</h3>
            <InfoTip helpKey="bt.rolling" />
          </div>
          {analytics && analytics.rolling_sharpe.length > 0 ? (
            <TimeSeriesChart
              data={toSeriesData(analytics.rolling_sharpe)}
              series={[
                {
                  key: "value",
                  name: "Rolling Sharpe",
                  color: "var(--chart-1)",
                },
              ]}
              height={360}
              yFormatter={(v) => v.toFixed(1)}
              baseline={0}
            />
          ) : (
            <EmptyState
              title="롤링 샤프 데이터가 없습니다"
              hint="백테스트를 실행하면 시간에 따른 위험 조정 성과가 표시됩니다"
            />
          )}
        </div>
      )}

      {/* Returns */}
      {activeTab === "returns" && (
        <div className="flex flex-col gap-6">
          <div className="card">
            <h3 className="section-header">연도별 수익</h3>
            {analytics && analytics.yearly_returns.length > 0 ? (
              <PeriodBarChart
                data={toPeriodData(analytics.yearly_returns)}
                series={[
                  {
                    key: "strategy",
                    name: backtestResult?.strategy_name ?? "Strategy",
                    color: "var(--gains)",
                  },
                  {
                    key: "benchmark",
                    name: backtestResult?.benchmark.name ?? "Benchmark",
                    color: "var(--text-muted)",
                  },
                ]}
                height={300}
                yFormatter={(v) => `${v.toFixed(0)}%`}
              />
            ) : (
              <EmptyState
                title="연도별 수익 데이터가 없습니다"
                hint="백테스트를 실행하면 기간별 수익이 표시됩니다"
              />
            )}
          </div>
          <div className="card">
            <h3 className="section-header">월별 수익 · 최근 36개월</h3>
            {monthlyReturns.length > 0 ? (
              <PeriodBarChart
                data={toPeriodData(monthlyReturns)}
                series={[
                  {
                    key: "strategy",
                    name: backtestResult?.strategy_name ?? "Strategy",
                    color: "var(--gains)",
                  },
                  {
                    key: "benchmark",
                    name: backtestResult?.benchmark.name ?? "Benchmark",
                    color: "var(--text-muted)",
                  },
                ]}
                height={300}
                yFormatter={(v) => `${v.toFixed(1)}%`}
              />
            ) : (
              <EmptyState
                title="월별 수익 데이터가 없습니다"
                hint="백테스트를 실행하면 기간별 수익이 표시됩니다"
              />
            )}
          </div>
        </div>
      )}

      {/* Contribution */}
      {activeTab === "contribution" && (
        <div className="card">
          <div className="flex items-start justify-between">
            <h3 className="section-header">자산별 수익 기여</h3>
            <InfoTip helpKey="bt.contribution" />
          </div>
          {analytics && analytics.contribution.length > 0 ? (
            <div className="space-y-3">
              {[...analytics.contribution]
                .sort((a, b) => b.value - a.value)
                .map((item) => {
                  const color =
                    item.value >= 0 ? "var(--gains)" : "var(--losses)";
                  const width =
                    contributionMaxAbs > 0
                      ? (Math.abs(item.value) / contributionMaxAbs) * 100
                      : 0;
                  return (
                    <div key={item.ticker}>
                      <div className="flex items-center justify-between mb-1.5">
                        <div className="flex items-center gap-2">
                          <div
                            className="w-2.5 h-2.5 rounded-full"
                            style={{ backgroundColor: color }}
                          />
                          <span className="text-sm font-medium text-ink">
                            {item.ticker}
                          </span>
                        </div>
                        <span
                          className="num text-sm font-semibold"
                          style={{ color }}
                        >
                          {item.value >= 0 ? "+" : ""}
                          {item.value.toFixed(2)}%
                        </span>
                      </div>
                      <div className="h-2.5 bg-raised rounded-full overflow-hidden">
                        <div
                          className="h-full rounded-full transition-all duration-500 ease-out"
                          style={{
                            width: `${Math.max(0, Math.min(100, width))}%`,
                            backgroundColor: color,
                            opacity: 0.9,
                          }}
                        />
                      </div>
                    </div>
                  );
                })}
            </div>
          ) : (
            <EmptyState
              title="기여도 데이터가 없습니다"
              hint="백테스트를 실행하면 자산별 기여가 표시됩니다"
            />
          )}
        </div>
      )}

      {/* Stress */}
      {activeTab === "stress" && (
        <div className="card">
          <div className="flex items-start justify-between">
            <h3 className="section-header">위기 구간 스트레스</h3>
            <InfoTip helpKey="bt.stress" />
          </div>
          {analytics && analytics.crisis.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-edge">
                    <th className="text-left py-3 px-4 font-medium text-ink-muted">
                      위기 구간
                    </th>
                    <th className="text-left py-3 px-4 font-medium text-ink-muted">
                      기간
                    </th>
                    <th className="text-right py-3 px-4 font-medium text-ink-muted">
                      수익률
                    </th>
                    <th className="text-right py-3 px-4 font-medium text-ink-muted">
                      MDD
                    </th>
                    <th className="text-right py-3 px-4 font-medium text-ink-muted">
                      회복
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {analytics.crisis.map((row) => (
                    <tr key={row.name} className="border-b border-edge">
                      <td className="py-3 px-4 font-medium text-ink">
                        {row.name}
                      </td>
                      <td className="py-3 px-4 text-ink-secondary num">
                        {row.start} — {row.end}
                      </td>
                      <td
                        className={`py-3 px-4 text-right num font-medium ${
                          row.ret >= 0 ? "text-gains" : "text-losses"
                        }`}
                      >
                        {formatPct(row.ret)}
                      </td>
                      <td className="py-3 px-4 text-right num text-losses">
                        {formatPct(row.mdd)}
                      </td>
                      <td className="py-3 px-4 text-right num text-ink-secondary">
                        {typeof row.recovery_days === "number"
                          ? `${row.recovery_days}d`
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              title="선택 구간에 위기 이벤트가 없습니다"
              hint="주요 하락 구간을 포함하도록 백테스트 기간을 넓혀 보세요"
            />
          )}
        </div>
      )}
        </section>
      ) : (
        <div className="grid overflow-hidden rounded-2xl border border-dashed border-edge bg-surface/50 md:grid-cols-[minmax(0,1fr)_minmax(20rem,0.8fr)]">
          <div className="px-5 py-8 md:px-7 md:py-10">
            <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-ink-muted">Output pending</p>
            <h2 className="mt-2 text-lg font-semibold text-ink">첫 결과를 기다리는 실험 벤치</h2>
            <p className="mt-2 max-w-xl text-sm leading-6 text-ink-muted">
              위 가정표를 채우고 백테스트를 실행하면 성과·낙폭·롤링 지표·기여도·위기 구간이 이곳에 기록됩니다.
            </p>
          </div>
          <ol className="grid grid-cols-3 border-t border-edge bg-raised/40 md:border-l md:border-t-0">
            {["가정 고정", "과거 실행", "결과 반증"].map((label, index) => (
              <li key={label} className="flex flex-col justify-center border-r border-edge px-3 py-5 last:border-r-0 md:px-4">
                <span className="font-mono text-[10px] text-primary-300">0{index + 1}</span>
                <span className="mt-1 text-xs font-medium text-ink-secondary">{label}</span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
};

export default Simulation;
