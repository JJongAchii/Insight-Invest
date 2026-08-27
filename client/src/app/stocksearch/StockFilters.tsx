"use client";

import React from "react";
import { FilterState, MarketFilter, CapFilter, TypeFilter } from "./types";

interface StockFiltersProps {
  filters: FilterState;
  onFilterChange: (filters: FilterState) => void;
  sectors: string[];
}

const MARKET_OPTIONS: { value: MarketFilter; label: string }[] = [
  { value: "all", label: "전체" },
  { value: "US", label: "미국" },
  { value: "KR", label: "한국" },
];

const TYPE_OPTIONS: { value: TypeFilter; label: string }[] = [
  { value: "all", label: "전체" },
  { value: "stock", label: "주식" },
  { value: "etf", label: "ETF" },
];

const CAP_OPTIONS: { value: CapFilter; label: string }[] = [
  { value: "all", label: "전체 규모" },
  { value: "large", label: "대형" },
  { value: "mid", label: "중형" },
  { value: "small", label: "소형" },
];

const StockFilters: React.FC<StockFiltersProps> = ({
  filters,
  onFilterChange,
  sectors,
}) => {
  const handleMarketChange = (market: MarketFilter) => {
    onFilterChange({ ...filters, market });
  };

  const handleTypeChange = (type: TypeFilter) => {
    onFilterChange({ ...filters, type });
  };

  const handleSectorChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onFilterChange({ ...filters, sector: e.target.value });
  };

  const handleCapChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onFilterChange({ ...filters, cap: e.target.value as CapFilter });
  };

  return (
    <div className="flex flex-wrap items-center gap-4">
      {/* Market Tabs */}
      <div className="flex rounded-lg bg-raised p-1">
        {MARKET_OPTIONS.map((option) => (
          <button
            key={option.value}
            onClick={() => handleMarketChange(option.value)}
            className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${
              filters.market === option.value
                ? "bg-overlay text-ink shadow-sm"
                : "text-ink-secondary hover:text-ink"
            }`}
            aria-pressed={filters.market === option.value}
          >
            {option.label}
          </button>
        ))}
      </div>

      {/* Security Type Tabs */}
      <div className="flex rounded-lg bg-raised p-1">
        {TYPE_OPTIONS.map((option) => (
          <button
            key={option.value}
            onClick={() => handleTypeChange(option.value)}
            className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${
              filters.type === option.value
                ? "bg-overlay text-ink shadow-sm"
                : "text-ink-secondary hover:text-ink"
            }`}
            aria-pressed={filters.type === option.value}
          >
            {option.label}
          </button>
        ))}
      </div>

      {/* Sector Dropdown */}
      <select
        value={filters.sector}
        onChange={handleSectorChange}
        className="w-full min-w-0 sm:w-auto sm:max-w-xs px-3 py-2 text-sm border border-edge rounded-lg bg-surface
                   focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
      >
        <option value="">전체 섹터</option>
        {sectors.map((sector) => (
          <option key={sector} value={sector}>
            {sector}
          </option>
        ))}
      </select>
      {filters.cap !== "all" && (
        <p className="basis-full text-xs text-ink-muted">
          대형/중형 기준: 미국 $10B/$2B · 한국 10조원/1조원 (원천 통화 기준)
        </p>
      )}

      {/* Market Cap Dropdown */}
      <select
        value={filters.cap}
        onChange={handleCapChange}
        className="px-3 py-2 text-sm border border-edge rounded-lg bg-surface
                   focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
      >
        {CAP_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
};

export default StockFilters;
