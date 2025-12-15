"use client";

import React, { useState } from "react";
import {
  useCalculateEfficientFrontierMutation,
  useCalculateRiskParityMutation,
  OptimizationPayload,
  EfficientFrontierResponse,
  OptimizedPortfolio,
} from "@/state/api";
import OptimizationConfig from "./OptimizationConfig";
import EfficientFrontierChart from "./EfficientFrontierChart";
import OptimalPortfolioDisplay from "./OptimalPortfolioDisplay";
import RiskContributionChart from "./RiskContributionChart";

type OptimizationType = "mvo" | "risk_parity";

const OptimizationPage = () => {
  const [calculateFrontier, { isLoading: isFrontierLoading }] =
    useCalculateEfficientFrontierMutation();
  const [calculateRiskParity, { isLoading: isRiskParityLoading }] =
    useCalculateRiskParityMutation();

  const [selectedTab, setSelectedTab] = useState<OptimizationType>("mvo");
  const [frontierData, setFrontierData] = useState<EfficientFrontierResponse | null>(null);
  const [riskParityData, setRiskParityData] = useState<OptimizedPortfolio | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleOptimize = async (payload: OptimizationPayload) => {
    setError(null);

    try {
      if (selectedTab === "mvo") {
        const result = await calculateFrontier(payload).unwrap();
        setFrontierData(result);
        setRiskParityData(null);
      } else {
        const result = await calculateRiskParity(payload).unwrap();
        setRiskParityData(result);
        setFrontierData(null);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Optimization failed";
      setError(errorMessage);
      console.error("Optimization error:", err);
    }
  };

  const isLoading = isFrontierLoading || isRiskParityLoading;

  return (
    <div className="flex flex-col gap-6 pb-16">
      {/* Loading Overlay */}
      {isLoading && (
        <div className="fixed inset-0 bg-black/20 backdrop-blur-sm z-50 flex items-center justify-center">
          <div className="bg-white rounded-2xl shadow-xl p-8 flex flex-col items-center gap-4">
            <div className="w-12 h-12 border-4 border-primary-500 border-t-transparent rounded-full animate-spin"></div>
            <p className="text-neutral-700 font-medium">Running optimization...</p>
          </div>
        </div>
      )}

      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-semibold text-neutral-900">
          Portfolio Optimization
        </h1>
        <p className="text-sm text-neutral-500 mt-1">
          Optimize your portfolio using Mean-Variance or Risk Parity methods
        </p>
      </div>

      {/* Tab Selection */}
      <div className="flex gap-2">
        <button
          onClick={() => setSelectedTab("mvo")}
          className={`px-4 py-2 rounded-lg font-medium text-sm transition-all ${
            selectedTab === "mvo"
              ? "bg-neutral-900 text-white"
              : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
          }`}
        >
          Mean-Variance (MVO)
        </button>
        <button
          onClick={() => setSelectedTab("risk_parity")}
          className={`px-4 py-2 rounded-lg font-medium text-sm transition-all ${
            selectedTab === "risk_parity"
              ? "bg-neutral-900 text-white"
              : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
          }`}
        >
          Risk Parity
        </button>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-700 text-sm">{error}</p>
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

      {/* Empty State */}
      {!frontierData && !riskParityData && !isLoading && (
        <div className="card text-center py-12">
          <div className="w-16 h-16 mx-auto mb-4 bg-neutral-100 rounded-full flex items-center justify-center">
            <svg
              className="w-8 h-8 text-neutral-400"
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
          <h3 className="text-lg font-medium text-neutral-700 mb-2">
            No optimization results yet
          </h3>
          <p className="text-sm text-neutral-500">
            Select at least 2 assets and click &quot;Run Optimization&quot; to see results
          </p>
        </div>
      )}
    </div>
  );
};

export default OptimizationPage;
