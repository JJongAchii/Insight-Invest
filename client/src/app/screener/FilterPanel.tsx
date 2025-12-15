"use client";

import React, { useState } from "react";
import { ScreenerPayload, ScreenerSortField } from "@/state/api";

interface FilterPanelProps {
  onScan: (filters: ScreenerPayload) => void;
  isLoading: boolean;
}

const SORT_OPTIONS: { value: ScreenerSortField; label: string }[] = [
  { value: "return_3m", label: "3-Month Return" },
  { value: "return_1m", label: "1-Month Return" },
  { value: "return_6m", label: "6-Month Return" },
  { value: "return_12m", label: "12-Month Return" },
  { value: "return_ytd", label: "YTD Return" },
  { value: "volatility_3m", label: "Volatility" },
  { value: "mdd_1y", label: "Max Drawdown" },
  { value: "pct_from_high", label: "% from 52W High" },
  { value: "pct_from_low", label: "% from 52W Low" },
];

const FilterPanel: React.FC<FilterPanelProps> = ({ onScan, isLoading }) => {
  // Country filter (required - default to US)
  const [isoCode, setIsoCode] = useState<string>("US");

  // Momentum filters
  const [return3mMin, setReturn3mMin] = useState<string>("");
  const [return3mMax, setReturn3mMax] = useState<string>("");
  const [return12mMin, setReturn12mMin] = useState<string>("");
  const [return12mMax, setReturn12mMax] = useState<string>("");

  // Volatility filter
  const [volatilityMin, setVolatilityMin] = useState<string>("");
  const [volatilityMax, setVolatilityMax] = useState<string>("");

  // Drawdown filter
  const [mddMax, setMddMax] = useState<string>("");

  // 52-week filter
  const [pctFromHighMin, setPctFromHighMin] = useState<string>("");
  const [pctFromHighMax, setPctFromHighMax] = useState<string>("");

  // Market cap filter (in billions USD)
  const [marketcapMin, setMarketcapMin] = useState<string>("");
  const [marketcapMax, setMarketcapMax] = useState<string>("");

  // Sort
  const [sortBy, setSortBy] = useState<ScreenerSortField>("return_3m");
  const [ascending, setAscending] = useState(false);

  const handleScan = () => {
    const filters: ScreenerPayload = {
      iso_code: isoCode,
      return_3m_min: return3mMin ? parseFloat(return3mMin) : undefined,
      return_3m_max: return3mMax ? parseFloat(return3mMax) : undefined,
      return_12m_min: return12mMin ? parseFloat(return12mMin) : undefined,
      return_12m_max: return12mMax ? parseFloat(return12mMax) : undefined,
      volatility_min: volatilityMin ? parseFloat(volatilityMin) : undefined,
      volatility_max: volatilityMax ? parseFloat(volatilityMax) : undefined,
      mdd_max: mddMax ? parseFloat(mddMax) : undefined,
      pct_from_high_min: pctFromHighMin ? parseFloat(pctFromHighMin) : undefined,
      pct_from_high_max: pctFromHighMax ? parseFloat(pctFromHighMax) : undefined,
      // Convert billions to actual number (e.g., 10B -> 10,000,000,000)
      marketcap_min: marketcapMin ? parseFloat(marketcapMin) * 1e9 : undefined,
      marketcap_max: marketcapMax ? parseFloat(marketcapMax) * 1e9 : undefined,
      sort_by: sortBy,
      ascending,
      limit: 100,
    };
    onScan(filters);
  };

  const handleReset = () => {
    setIsoCode("US");
    setReturn3mMin("");
    setReturn3mMax("");
    setReturn12mMin("");
    setReturn12mMax("");
    setVolatilityMin("");
    setVolatilityMax("");
    setMddMax("");
    setPctFromHighMin("");
    setPctFromHighMax("");
    setMarketcapMin("");
    setMarketcapMax("");
    setSortBy("return_3m");
    setAscending(false);
  };

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-base font-semibold text-neutral-900">Screening Filters</h3>
        <button
          onClick={handleReset}
          className="text-sm text-neutral-500 hover:text-neutral-700"
        >
          Reset
        </button>
      </div>

      <div className="space-y-5">
        {/* Row 1: Country & Sort */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
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
            <label className="input-label">Sort By</label>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as ScreenerSortField)}
              className="input"
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="input-label">Order</label>
            <select
              value={ascending ? "asc" : "desc"}
              onChange={(e) => setAscending(e.target.value === "asc")}
              className="input"
            >
              <option value="desc">High to Low</option>
              <option value="asc">Low to High</option>
            </select>
          </div>
        </div>

        {/* Row 2: Momentum Filters */}
        <div>
          <p className="text-sm font-medium text-neutral-700 mb-3">Momentum Filters (%)</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <label className="input-label">3M Return Min</label>
              <input
                type="number"
                value={return3mMin}
                onChange={(e) => setReturn3mMin(e.target.value)}
                placeholder="-50"
                className="input"
              />
            </div>
            <div>
              <label className="input-label">3M Return Max</label>
              <input
                type="number"
                value={return3mMax}
                onChange={(e) => setReturn3mMax(e.target.value)}
                placeholder="100"
                className="input"
              />
            </div>
            <div>
              <label className="input-label">12M Return Min</label>
              <input
                type="number"
                value={return12mMin}
                onChange={(e) => setReturn12mMin(e.target.value)}
                placeholder="-50"
                className="input"
              />
            </div>
            <div>
              <label className="input-label">12M Return Max</label>
              <input
                type="number"
                value={return12mMax}
                onChange={(e) => setReturn12mMax(e.target.value)}
                placeholder="200"
                className="input"
              />
            </div>
          </div>
        </div>

        {/* Row 3: Risk Filters */}
        <div>
          <p className="text-sm font-medium text-neutral-700 mb-3">Risk Filters (%)</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <label className="input-label">Volatility Min</label>
              <input
                type="number"
                value={volatilityMin}
                onChange={(e) => setVolatilityMin(e.target.value)}
                placeholder="0"
                className="input"
              />
            </div>
            <div>
              <label className="input-label">Volatility Max</label>
              <input
                type="number"
                value={volatilityMax}
                onChange={(e) => setVolatilityMax(e.target.value)}
                placeholder="50"
                className="input"
              />
            </div>
            <div>
              <label className="input-label">Max Drawdown (1Y)</label>
              <input
                type="number"
                value={mddMax}
                onChange={(e) => setMddMax(e.target.value)}
                placeholder="-30"
                className="input"
              />
            </div>
            <div className="hidden md:block"></div>
          </div>
        </div>

        {/* Row 4: 52-Week Filters */}
        <div>
          <p className="text-sm font-medium text-neutral-700 mb-3">52-Week Price Position (%)</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <label className="input-label">% from High Min</label>
              <input
                type="number"
                value={pctFromHighMin}
                onChange={(e) => setPctFromHighMin(e.target.value)}
                placeholder="-50"
                className="input"
              />
            </div>
            <div>
              <label className="input-label">% from High Max</label>
              <input
                type="number"
                value={pctFromHighMax}
                onChange={(e) => setPctFromHighMax(e.target.value)}
                placeholder="0"
                className="input"
              />
            </div>
            <div className="hidden md:block"></div>
            <div className="hidden md:block"></div>
          </div>
        </div>

        {/* Row 5: Market Cap Filters */}
        <div>
          <p className="text-sm font-medium text-neutral-700 mb-3">Market Cap (Billions USD)</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <label className="input-label">Min Market Cap</label>
              <input
                type="number"
                value={marketcapMin}
                onChange={(e) => setMarketcapMin(e.target.value)}
                placeholder="10"
                className="input"
              />
            </div>
            <div>
              <label className="input-label">Max Market Cap</label>
              <input
                type="number"
                value={marketcapMax}
                onChange={(e) => setMarketcapMax(e.target.value)}
                placeholder="1000"
                className="input"
              />
            </div>
            <div className="hidden md:block"></div>
            <div className="hidden md:block"></div>
          </div>
        </div>

        {/* Scan Button */}
        <div className="flex justify-end pt-2">
          <button
            onClick={handleScan}
            disabled={isLoading}
            className="btn-primary"
          >
            {isLoading ? "Scanning..." : "Scan Stocks"}
          </button>
        </div>
      </div>
    </div>
  );
};

export default FilterPanel;
