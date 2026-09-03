"use client";

import React from "react";
import { useRouter } from "next/navigation";
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
  const router = useRouter();
  const sortedWeights = Object.entries(portfolio.weights)
    .filter(([, weight]) => weight > 0.001)
    .sort((a, b) => b[1] - a[1]);

  const handleBacktest = () => {
    const weightsParam = sortedWeights
      .map(([ticker, weight]) => `${ticker}:${weight.toFixed(4)}`)
      .join(",");
    router.push(
      `/backtest/simulation?weights=${encodeURIComponent(weightsParam)}`
    );
  };

  return (
    <article className="overflow-hidden rounded-2xl border border-edge bg-surface">
      <div className="h-px" style={{ backgroundColor: accentColor.includes("emerald") ? "var(--gains)" : accentColor.includes("amber") ? "var(--warning)" : "var(--primary)" }} />
      <div className="p-5 md:p-6">
      <div className="mb-4 flex items-center gap-2">
        <div className={`w-3 h-3 rounded-full ${accentColor}`}></div>
        <h4 className="text-sm font-semibold text-ink">{title}</h4>
      </div>

      {/* Metrics */}
      <div className="mb-5 grid grid-cols-3 divide-x divide-edge border-y border-edge">
        <div className="px-2 py-3">
          <p className="mb-1 text-[10px] uppercase tracking-wide text-ink-muted">기대수익</p>
          <p className="num text-lg font-semibold text-ink">
            {(portfolio.expected_return * 100).toFixed(2)}%
          </p>
        </div>
        <div className="px-3 py-3">
          <p className="mb-1 text-[10px] uppercase tracking-wide text-ink-muted">변동성</p>
          <p className="num text-lg font-semibold text-ink">
            {(portfolio.volatility * 100).toFixed(2)}%
          </p>
        </div>
        <div className="px-3 py-3">
          <p className="mb-1 text-[10px] uppercase tracking-wide text-ink-muted">샤프</p>
          <p className="num text-lg font-semibold text-ink">
            {portfolio.sharpe_ratio.toFixed(2)}
          </p>
        </div>
      </div>

      {/* Weights */}
      <div>
        <p className="text-xs font-medium text-ink-muted mb-3">
          계산 비중
        </p>
        <div className="space-y-2">
          {sortedWeights.map(([ticker, weight]) => (
            <div key={ticker} className="flex items-center gap-3">
              <span className="w-14 text-xs font-medium text-ink-secondary">
                {ticker}
              </span>
              <div className="flex-1 h-5 bg-raised rounded-full overflow-hidden">
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
              <span className="w-14 text-xs text-ink-secondary text-right">
                {(weight * 100).toFixed(1)}%
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Backtest handoff */}
      <div className="flex justify-end mt-5">
        <button onClick={handleBacktest} className="btn-secondary text-xs">
          이 비중으로 백테스트
        </button>
      </div>
      </div>
    </article>
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
        title={title || "리스크 패리티 배분"}
        portfolio={riskParity}
        accentColor="bg-violet-500"
      />
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {maxSharpe && (
        <PortfolioCard
          title="최대 샤프 배분"
          portfolio={maxSharpe}
          accentColor="bg-emerald-500"
        />
      )}
      {minVol && (
        <PortfolioCard
          title="최소 변동성 배분"
          portfolio={minVol}
          accentColor="bg-amber-500"
        />
      )}
    </div>
  );
};

export default OptimalPortfolioDisplay;
