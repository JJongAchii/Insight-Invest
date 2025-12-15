"use client";

import React, { useState } from "react";
import { useFetchHighsLowsQuery, ScreenerStock } from "@/state/api";

const formatPercent = (value: number) => {
  const formatted = value.toFixed(2);
  if (value > 0) return `+${formatted}%`;
  return `${formatted}%`;
};

const formatPrice = (value: number) => {
  if (value >= 1000) return value.toLocaleString("en-US", { maximumFractionDigits: 0 });
  return value.toFixed(2);
};

interface StockCardProps {
  stock: ScreenerStock;
  type: "high" | "low";
}

const StockCard: React.FC<StockCardProps> = ({ stock, type }) => {
  const isHigh = type === "high";
  const position = isHigh ? stock.pct_from_high : stock.pct_from_low;

  return (
    <div className="flex items-center justify-between py-3 border-b border-neutral-100 last:border-0">
      <div className="flex items-center gap-3">
        <div
          className={`w-10 h-10 rounded-lg flex items-center justify-center ${
            isHigh ? "bg-emerald-50" : "bg-red-50"
          }`}
        >
          <span className={`text-xs font-bold ${isHigh ? "text-emerald-600" : "text-red-600"}`}>
            {stock.ticker.slice(0, 3)}
          </span>
        </div>
        <div>
          <p className="font-medium text-neutral-900">{stock.ticker}</p>
          <p className="text-xs text-neutral-500 truncate max-w-[150px]">
            {stock.name || stock.sector || "-"}
          </p>
        </div>
      </div>
      <div className="text-right">
        <p className="font-medium text-neutral-900">${formatPrice(stock.current_price)}</p>
        <p className={`text-xs ${isHigh ? "text-emerald-600" : "text-red-600"}`}>
          {formatPercent(position)} from {isHigh ? "high" : "low"}
        </p>
      </div>
    </div>
  );
};

const HighsLowsPanel: React.FC = () => {
  const [isoCode, setIsoCode] = useState<string>("US");
  const [threshold, setThreshold] = useState<number>(5);

  const { data, isLoading, error } = useFetchHighsLowsQuery({
    iso_code: isoCode,
    threshold,
  });

  return (
    <div className="space-y-6">
      {/* Filters */}
      <div className="card">
        <h3 className="text-base font-semibold text-neutral-900 mb-4">Filters</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="input-label">Country</label>
            <select
              value={isoCode}
              onChange={(e) => setIsoCode(e.target.value)}
              className="input"
            >
              <option value="US">United States</option>
              <option value="KR">South Korea</option>
            </select>
          </div>
          <div>
            <label className="input-label">Threshold (%)</label>
            <select
              value={threshold}
              onChange={(e) => setThreshold(parseFloat(e.target.value))}
              className="input"
            >
              <option value={2}>Within 2%</option>
              <option value={5}>Within 5%</option>
              <option value={10}>Within 10%</option>
              <option value={15}>Within 15%</option>
            </select>
          </div>
        </div>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="text-center py-8">
          <div className="w-8 h-8 border-4 border-primary-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p className="text-neutral-500 mt-2">Loading...</p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-700 text-sm">Failed to load data</p>
        </div>
      )}

      {/* Results */}
      {data && !isLoading && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* New Highs */}
          <div className="card">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-3 h-3 bg-emerald-500 rounded-full"></div>
              <h3 className="text-base font-semibold text-neutral-900">
                Near 52-Week Highs
              </h3>
              <span className="text-sm text-neutral-500">({data.new_highs.length})</span>
            </div>
            {data.new_highs.length > 0 ? (
              <div className="max-h-[400px] overflow-y-auto">
                {data.new_highs.map((stock) => (
                  <StockCard key={stock.meta_id} stock={stock} type="high" />
                ))}
              </div>
            ) : (
              <p className="text-neutral-500 text-sm py-4 text-center">
                No stocks near 52-week highs
              </p>
            )}
          </div>

          {/* New Lows */}
          <div className="card">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-3 h-3 bg-red-500 rounded-full"></div>
              <h3 className="text-base font-semibold text-neutral-900">
                Near 52-Week Lows
              </h3>
              <span className="text-sm text-neutral-500">({data.new_lows.length})</span>
            </div>
            {data.new_lows.length > 0 ? (
              <div className="max-h-[400px] overflow-y-auto">
                {data.new_lows.map((stock) => (
                  <StockCard key={stock.meta_id} stock={stock} type="low" />
                ))}
              </div>
            ) : (
              <p className="text-neutral-500 text-sm py-4 text-center">
                No stocks near 52-week lows
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default HighsLowsPanel;
