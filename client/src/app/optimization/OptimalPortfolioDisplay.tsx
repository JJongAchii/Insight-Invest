"use client";

import React from "react";
import { OptimizedPortfolio } from "@/state/api";

interface OptimalPortfolioDisplayProps {
  maxSharpe?: OptimizedPortfolio;
  minVol?: OptimizedPortfolio;
  riskParity?: OptimizedPortfolio;
  title?: string;
}

interface PortfolioCardProps {
  title: string;
  portfolio: OptimizedPortfolio;
  accentColor: string;
}

const PortfolioCard: React.FC<PortfolioCardProps> = ({
  title,
  portfolio,
  accentColor,
}) => {
  const sortedWeights = Object.entries(portfolio.weights)
    .filter(([, weight]) => weight > 0.001)
    .sort((a, b) => b[1] - a[1]);

  return (
    <div className="card">
      <div className="flex items-center gap-2 mb-4">
        <div className={`w-3 h-3 rounded-full ${accentColor}`}></div>
        <h4 className="text-sm font-semibold text-neutral-900">{title}</h4>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-3 gap-4 mb-5">
        <div className="text-center p-3 bg-neutral-50 rounded-lg">
          <p className="text-xs text-neutral-500 mb-1">Return</p>
          <p className="text-lg font-semibold text-neutral-900">
            {(portfolio.expected_return * 100).toFixed(2)}%
          </p>
        </div>
        <div className="text-center p-3 bg-neutral-50 rounded-lg">
          <p className="text-xs text-neutral-500 mb-1">Volatility</p>
          <p className="text-lg font-semibold text-neutral-900">
            {(portfolio.volatility * 100).toFixed(2)}%
          </p>
        </div>
        <div className="text-center p-3 bg-neutral-50 rounded-lg">
          <p className="text-xs text-neutral-500 mb-1">Sharpe</p>
          <p className="text-lg font-semibold text-neutral-900">
            {portfolio.sharpe_ratio.toFixed(2)}
          </p>
        </div>
      </div>

      {/* Weights */}
      <div>
        <p className="text-xs font-medium text-neutral-500 mb-3">
          Portfolio Weights
        </p>
        <div className="space-y-2">
          {sortedWeights.map(([ticker, weight]) => (
            <div key={ticker} className="flex items-center gap-3">
              <span className="w-14 text-xs font-medium text-neutral-700">
                {ticker}
              </span>
              <div className="flex-1 h-5 bg-neutral-100 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${
                    accentColor === "bg-emerald-500"
                      ? "bg-gradient-to-r from-emerald-400 to-emerald-500"
                      : accentColor === "bg-amber-500"
                        ? "bg-gradient-to-r from-amber-400 to-amber-500"
                        : "bg-gradient-to-r from-violet-400 to-violet-500"
                  }`}
                  style={{ width: `${weight * 100}%` }}
                />
              </div>
              <span className="w-14 text-xs text-neutral-600 text-right">
                {(weight * 100).toFixed(1)}%
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const OptimalPortfolioDisplay: React.FC<OptimalPortfolioDisplayProps> = ({
  maxSharpe,
  minVol,
  riskParity,
  title,
}) => {
  if (riskParity) {
    return (
      <PortfolioCard
        title={title || "Risk Parity Portfolio"}
        portfolio={riskParity}
        accentColor="bg-violet-500"
      />
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {maxSharpe && (
        <PortfolioCard
          title="Maximum Sharpe Portfolio"
          portfolio={maxSharpe}
          accentColor="bg-emerald-500"
        />
      )}
      {minVol && (
        <PortfolioCard
          title="Minimum Volatility Portfolio"
          portfolio={minVol}
          accentColor="bg-amber-500"
        />
      )}
    </div>
  );
};

export default OptimalPortfolioDisplay;
