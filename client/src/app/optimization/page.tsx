"use client";

import React, { useState } from "react";
import {
  useCalculateEfficientFrontierMutation,
  useCalculateRiskParityMutation,
  useCalculateCorrelationMutation,
  OptimizationPayload,
  EfficientFrontierResponse,
  OptimizedPortfolio,
  CorrelationResponse,
} from "@/state/api";
import OptimizationConfig from "./OptimizationConfig";
import EfficientFrontierChart from "./EfficientFrontierChart";
import OptimalPortfolioDisplay from "./OptimalPortfolioDisplay";
import RiskContributionChart from "./RiskContributionChart";
import CorrelationSection, { CorrelationAsset } from "./CorrelationSection";
import PageHeader from "@/components/ui/PageHeader";

type OptimizationType = "mvo" | "risk_parity" | "correlation";

const TABS: { id: OptimizationType; label: string }[] = [
  { id: "mvo", label: "평균-분산" },
  { id: "risk_parity", label: "리스크 패리티" },
  { id: "correlation", label: "상관관계" },
];

const METHOD_NOTES: Record<OptimizationType, string> = {
  mvo: "기대수익과 변동성의 조합을 비교합니다. 추정 오차에 가장 민감합니다.",
  risk_parity: "기대수익 예측 없이 자산별 위험 기여가 가까워지도록 배분합니다.",
  correlation: "배분을 만들기 전에 자산 간 동행 구조와 시간 변화를 진단합니다.",
};

const RESULT_TITLES: Record<OptimizationType, string> = {
  mvo: "효율적 투자선 · 후보 배분",
  risk_parity: "위험 기여 균형 배분",
  correlation: "상관 구조 진단",
};

const OptimizationPage = () => {
  const [calculateFrontier, { isLoading: isFrontierLoading }] =
    useCalculateEfficientFrontierMutation();
  const [calculateRiskParity, { isLoading: isRiskParityLoading }] =
    useCalculateRiskParityMutation();
  const [calculateCorrelation, { isLoading: isCorrelationLoading }] =
    useCalculateCorrelationMutation();

  const [selectedTab, setSelectedTab] = useState<OptimizationType>("mvo");
  const [frontierData, setFrontierData] = useState<EfficientFrontierResponse | null>(null);
  const [riskParityData, setRiskParityData] = useState<OptimizedPortfolio | null>(null);
  const [correlationData, setCorrelationData] = useState<CorrelationResponse | null>(null);
  const [correlationAssets, setCorrelationAssets] = useState<CorrelationAsset[]>([]);
  const [correlationLookback, setCorrelationLookback] = useState(252);
  const [rollingPair, setRollingPair] = useState<[number, number] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const runCorrelation = async (
    metaIds: number[],
    lookbackDays: number,
    pair: [number, number]
  ) => {
    const result = await calculateCorrelation({
      meta_id: metaIds,
      lookback_days: lookbackDays,
      rolling_pair: pair,
    }).unwrap();
    setCorrelationData(result);
    setCorrelationAssets(
      metaIds.map((id, i) => ({
        meta_id: id,
        ticker: result.tickers[i] ?? String(id),
      }))
    );
    setRollingPair(pair);
  };

  const handleOptimize = async (payload: OptimizationPayload) => {
    setError(null);

    try {
      if (selectedTab === "mvo") {
        const result = await calculateFrontier(payload).unwrap();
        setFrontierData(result);
        setRiskParityData(null);
      } else if (selectedTab === "risk_parity") {
        const result = await calculateRiskParity(payload).unwrap();
        setRiskParityData(result);
        setFrontierData(null);
      } else {
        const lookback = payload.lookback_period ?? 252;
        setCorrelationLookback(lookback);
        await runCorrelation(payload.meta_id, lookback, [
          payload.meta_id[0],
          payload.meta_id[1],
        ]);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "계산을 완료하지 못했습니다";
      setError(errorMessage);
      console.error("Optimization error:", err);
    }
  };

  const handlePairChange = async (pair: [number, number]) => {
    if (correlationAssets.length < 2) return;
    setError(null);
    try {
      await runCorrelation(
        correlationAssets.map((a) => a.meta_id),
        correlationLookback,
        pair
      );
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "계산을 완료하지 못했습니다";
      setError(errorMessage);
      console.error("Correlation error:", err);
    }
  };

  const isLoading = isFrontierLoading || isRiskParityLoading || isCorrelationLoading;

  const hasResult =
    (selectedTab === "mvo" && frontierData) ||
    (selectedTab === "risk_parity" && riskParityData) ||
    (selectedTab === "correlation" && correlationData);

  return (
    <div className="flex flex-col gap-6 pb-16">
      {/* Loading Overlay */}
      {isLoading && (
        <div className="fixed inset-0 bg-black/20 backdrop-blur-sm z-50 flex items-center justify-center">
          <div className="bg-surface rounded-2xl shadow-xl p-8 flex flex-col items-center gap-4">
            <div className="w-12 h-12 border-4 border-primary-500 border-t-transparent rounded-full animate-spin"></div>
            <p className="text-ink-secondary font-medium">
              {selectedTab === "correlation"
                ? "상관관계를 계산하는 중..."
                : "최적화 계산 중..."}
            </p>
          </div>
        </div>
      )}

      <PageHeader
        eyebrow="Allocation lab"
        title="포트폴리오 최적화"
        description="평균-분산·리스크 패리티 배분과 자산 간 상관관계를 비교하되, 입력 가정과 결과를 분리해 봅니다."
      />

      {/* Tab Selection */}
      <div className="segmented-control self-start" aria-label="최적화 방식">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setSelectedTab(tab.id)}
            aria-pressed={selectedTab === tab.id}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <p className="-mt-3 max-w-3xl text-xs leading-5 text-ink-muted">
        {METHOD_NOTES[selectedTab]}
      </p>

      {/* Error Display */}
      {error && (
        <div
          className="rounded-lg p-4"
          style={{
            backgroundColor:
              "color-mix(in srgb, var(--losses) 10%, transparent)",
            border:
              "1px solid color-mix(in srgb, var(--losses) 30%, transparent)",
          }}
        >
          <p className="text-losses text-sm">{error}</p>
        </div>
      )}

      {/* Configuration */}
      <OptimizationConfig
        onOptimize={handleOptimize}
        isLoading={isLoading}
        optimizationType={selectedTab}
      />

      {hasResult && (
        <section className="relative border-t border-edge pt-8" aria-labelledby="optimization-output">
          <span aria-hidden className="absolute -top-px left-0 h-px w-40 bg-gradient-to-r from-primary-400 via-primary-500 to-secondary-400" />
          <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-primary-300">
                Computed output
              </p>
              <h2 id="optimization-output" className="mt-1 text-xl font-semibold tracking-[-0.025em] text-ink">
                {RESULT_TITLES[selectedTab]}
              </h2>
            </div>
            <p className="max-w-lg text-xs leading-5 text-ink-muted sm:text-right">
              입력 표본에 대한 계산 결과입니다. 추천 비중이 아니라 검토할 후보로 다루세요.
            </p>
          </div>

          {selectedTab === "mvo" && frontierData && (
            <div className="space-y-6">
              <EfficientFrontierChart data={frontierData} />
              <OptimalPortfolioDisplay maxSharpe={frontierData.max_sharpe} minVol={frontierData.min_volatility} />
              <RiskContributionChart data={frontierData.max_sharpe.risk_contributions} title="최대 샤프 배분 · 위험 기여" />
            </div>
          )}

          {selectedTab === "risk_parity" && riskParityData && (
            <div className="space-y-6">
              <OptimalPortfolioDisplay riskParity={riskParityData} title="리스크 패리티 배분" />
              <RiskContributionChart data={riskParityData.risk_contributions} title="균등 목표 · 위험 기여" />
            </div>
          )}

          {selectedTab === "correlation" && correlationData && (
            <CorrelationSection
              data={correlationData}
              assets={correlationAssets}
              rollingPair={rollingPair}
              onPairChange={handlePairChange}
              isRollingLoading={isCorrelationLoading}
            />
          )}
        </section>
      )}

      {/* Empty State */}
      {!hasResult && !isLoading && (
        <div className="grid overflow-hidden rounded-2xl border border-dashed border-edge bg-surface/50 md:grid-cols-[minmax(0,1fr)_minmax(20rem,0.8fr)]">
          <div className="px-5 py-8 md:px-7 md:py-10">
            <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-ink-muted">Output pending</p>
            <h3 className="mt-2 text-lg font-semibold text-ink">
              {selectedTab === "correlation" ? "상관 구조를 계산할 준비가 됐습니다" : "후보 배분을 계산할 준비가 됐습니다"}
            </h3>
            <p className="mt-2 max-w-xl text-sm leading-6 text-ink-muted">
              위 가정표에서 자산을 2개 이상 선택하고 조건을 확인한 뒤 {selectedTab === "correlation" ? "분석" : "최적화"}를 실행하세요.
            </p>
          </div>
          <ol className="grid grid-cols-3 border-t border-edge bg-raised/40 md:border-l md:border-t-0">
            {["자산 선택", "가정 명시", "결과 검토"].map((label, index) => (
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

export default OptimizationPage;
