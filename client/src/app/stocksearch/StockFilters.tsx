"use client";

import React from "react";
import { FilterState, MarketFilter, CapFilter, TypeFilter } from "./types";

interface StockFiltersProps {
  filters: FilterState;
  onFilterChange: (filters: FilterState) => void;
  sectors: string[];
}

const MARKET_OPTIONS: { value: MarketFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "US", label: "US" },
  { value: "KR", label: "KR" },
];

const TYPE_OPTIONS: { value: TypeFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "stock", label: "Stock" },
  { value: "etf", label: "ETF" },
];

const CAP_OPTIONS: { value: CapFilter; label: string }[] = [
  { value: "all", label: "All Cap" },
  { value: "large", label: "Large Cap" },
  { value: "mid", label: "Mid Cap" },
  { value: "small", label: "Small Cap" },
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
          >
            {option.label}
          </button>
        ))}
      </div>

      {/* Sector Dropdown */}
      <select
        value={filters.sector}
        onChange={handleSectorChange}
        className="px-3 py-2 text-sm border border-edge rounded-lg bg-surface
                   focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500"
      >
        <option value="">All Sectors</option>
        {sectors.map((sector) => (
          <option key={sector} value={sector}>
            {sector}
          </option>
        ))}
      </select>

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
