"use client";

import React from "react";
import { FilterState, MarketFilter, CapFilter } from "./types";

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

  const handleSectorChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onFilterChange({ ...filters, sector: e.target.value });
  };

  const handleCapChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onFilterChange({ ...filters, cap: e.target.value as CapFilter });
  };

  return (
    <div className="flex flex-wrap items-center gap-4">
      {/* Market Tabs */}
      <div className="flex rounded-lg bg-neutral-100 p-1">
        {MARKET_OPTIONS.map((option) => (
          <button
            key={option.value}
            onClick={() => handleMarketChange(option.value)}
            className={`px-4 py-1.5 text-sm font-medium rounded-md transition-all ${
              filters.market === option.value
                ? "bg-white text-neutral-900 shadow-sm"
                : "text-neutral-600 hover:text-neutral-900"
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
        className="px-3 py-2 text-sm border border-neutral-200 rounded-lg bg-white
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
        className="px-3 py-2 text-sm border border-neutral-200 rounded-lg bg-white
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
