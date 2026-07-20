"use client";

import { useEffect, useMemo, useState } from "react";
import SetStrategy from "./SetStrategy";
import StrategyChart from "./StrategyChart";
import StrategyMetrics from "./StrategyMetrics";
import LoadingSpinner from "@/app/(components)/LoadingSpinner";
import TimeSeriesChart from "@/components/charts/TimeSeriesChart";
import PeriodBarChart from "@/components/charts/PeriodBarChart";
import EmptyState from "@/components/ui/EmptyState";
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
  { key: "performance", label: "Performance" },
  { key: "drawdown", label: "Drawdown" },
  { key: "rolling", label: "Rolling Sharpe" },
  { key: "returns", label: "Returns" },
  { key: "contribution", label: "Contribution" },
  { key: "stress", label: "Stress" },
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
              Clear All Strategies?
            </h3>
            <p className="text-ink-secondary text-sm mb-6">
              This will remove all backtest results and selected tickers from
              this browser. This action cannot be undone.
            </p>
            <div className="flex gap-3 justify-end">
              <button onClick={cancelClear} className="btn-secondary">
                Cancel
              </button>
              <button onClick={confirmClear} className="btn-danger">
                Clear All
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="page-title">Backtest Simulation</h1>
          <p className="page-description">
            Test your investment strategies with historical data
          </p>
        </div>
        <button
          onClick={handleClearClick}
          disabled={isLoading}
          className="btn-danger"
        >
          Clear All
        </button>
      </div>

      <SetStrategy onRunBacktest={handleRunBacktest} isLoading={isLoading} />

      {/* Result Tabs */}
      <div className="inline-flex self-start rounded-lg bg-raised p-1 overflow-x-auto max-w-full">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-sm font-medium rounded-md whitespace-nowrap transition-colors ${
              activeTab === tab.key
                ? "bg-surface text-ink shadow-sm"
                : "text-ink-muted hover:text-ink-secondary"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Performance */}
      {activeTab === "performance" && (
        <div className="card">
          <h3 className="section-header">Performance</h3>
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
          <h3 className="section-header">Drawdown</h3>
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
              title="No drawdown data"
              hint="Run a backtest to see drawdowns"
            />
          )}
        </div>
      )}

      {/* Rolling Sharpe */}
      {activeTab === "rolling" && (
        <div className="card">
          <h3 className="section-header">Rolling Sharpe</h3>
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
              title="No rolling Sharpe data"
              hint="Run a backtest to see the rolling Sharpe ratio"
            />
          )}
        </div>
      )}

      {/* Returns */}
      {activeTab === "returns" && (
        <div className="flex flex-col gap-6">
          <div className="card">
            <h3 className="section-header">Yearly Returns</h3>
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
                title="No yearly returns"
                hint="Run a backtest to see period returns"
              />
            )}
          </div>
          <div className="card">
            <h3 className="section-header">Monthly Returns (last 36)</h3>
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
                title="No monthly returns"
                hint="Run a backtest to see period returns"
              />
            )}
          </div>
        </div>
      )}

      {/* Contribution */}
      {activeTab === "contribution" && (
        <div className="card">
          <h3 className="section-header">Return Contribution by Asset</h3>
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
              title="No contribution data"
              hint="Run a backtest to see per-asset contributions"
            />
          )}
        </div>
      )}

      {/* Stress */}
      {activeTab === "stress" && (
        <div className="card">
          <h3 className="section-header">Crisis Stress Windows</h3>
          {analytics && analytics.crisis.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-edge">
                    <th className="text-left py-3 px-4 font-medium text-ink-muted">
                      Crisis
                    </th>
                    <th className="text-left py-3 px-4 font-medium text-ink-muted">
                      Period
                    </th>
                    <th className="text-right py-3 px-4 font-medium text-ink-muted">
                      Return
                    </th>
                    <th className="text-right py-3 px-4 font-medium text-ink-muted">
                      MDD
                    </th>
                    <th className="text-right py-3 px-4 font-medium text-ink-muted">
                      Recovery
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
              title="No crisis windows in range"
              hint="Extend the backtest period to cover major drawdown events"
            />
          )}
        </div>
      )}
    </div>
  );
};

export default Simulation;
