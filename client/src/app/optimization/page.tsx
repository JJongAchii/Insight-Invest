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

type OptimizationType = "mvo" | "risk_parity" | "correlation";

const TABS: { id: OptimizationType; label: string }[] = [
  { id: "mvo", label: "Mean-Variance (MVO)" },
  { id: "risk_parity", label: "Risk Parity" },
  { id: "correlation", label: "Correlation" },
];

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
      const errorMessage = err instanceof Error ? err.message : "Calculation failed";
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
      const errorMessage = err instanceof Error ? err.message : "Calculation failed";
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
                ? "Calculating correlations..."
                : "Running optimization..."}
            </p>
          </div>
        </div>
      )}

      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-semibold text-ink">
          Portfolio Optimization
        </h1>
        <p className="text-sm text-ink-muted mt-1">
          Optimize your portfolio using Mean-Variance or Risk Parity methods, or
          analyze asset correlations
        </p>
      </div>

      {/* Tab Selection */}
      <div className="flex gap-2">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setSelectedTab(tab.id)}
            className={`px-4 py-2 rounded-lg font-medium text-sm transition-all ${
              selectedTab === tab.id
                ? "bg-primary-500 text-white shadow-md shadow-primary-500/25"
                : "bg-raised text-ink-secondary hover:bg-overlay"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

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

      {/* MVO Results */}
      {selectedTab === "mvo" && frontierData && (
        <div className="space-y-6">
          <EfficientFrontierChart data={frontierData} />
          <OptimalPortfolioDisplay
            maxSharpe={frontierData.max_sharpe}
            minVol={frontierData.min_volatility}
          />
          <RiskContributionChart
            data={frontierData.max_sharpe.risk_contributions}
            title="Risk Contributions (Max Sharpe Portfolio)"
          />
        </div>
      )}

      {/* Risk Parity Results */}
      {selectedTab === "risk_parity" && riskParityData && (
        <div className="space-y-6">
          <OptimalPortfolioDisplay
            riskParity={riskParityData}
            title="Risk Parity Portfolio"
          />
          <RiskContributionChart
            data={riskParityData.risk_contributions}
            title="Risk Contributions (Equal by Design)"
          />
        </div>
      )}

      {/* Correlation Results */}
      {selectedTab === "correlation" && correlationData && (
        <CorrelationSection
          data={correlationData}
          assets={correlationAssets}
          rollingPair={rollingPair}
          onPairChange={handlePairChange}
          isRollingLoading={isCorrelationLoading}
        />
      )}

      {/* Empty State */}
      {!hasResult && !isLoading && (
        <div className="card text-center py-12">
          <div className="w-16 h-16 mx-auto mb-4 bg-raised rounded-full flex items-center justify-center">
            <svg
              className="w-8 h-8 text-ink-muted"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
              />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-ink-secondary mb-2">
            {selectedTab === "correlation"
              ? "No correlation results yet"
              : "No optimization results yet"}
          </h3>
          <p className="text-sm text-ink-muted">
            Select at least 2 assets and click{" "}
            {selectedTab === "correlation"
              ? "“Run Analysis”"
              : "“Run Optimization”"}{" "}
            to see results
          </p>
        </div>
      )}
    </div>
  );
};

export default OptimizationPage;
