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
    <div className="grid gap-4 xl:grid-cols-[auto_auto_minmax(180px,1fr)_minmax(150px,auto)] xl:items-end">
      <fieldset className="min-w-0">
        <legend className="mb-2 font-mono text-[9px] font-semibold uppercase tracking-[0.14em] text-ink-muted">Market</legend>
        <div className="segmented-control bg-canvas/25">
        {MARKET_OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => handleMarketChange(option.value)}
            aria-pressed={filters.market === option.value}
          >
            {option.label}
          </button>
        ))}
        </div>
      </fieldset>

      <fieldset className="min-w-0">
        <legend className="mb-2 font-mono text-[9px] font-semibold uppercase tracking-[0.14em] text-ink-muted">Instrument</legend>
        <div className="segmented-control bg-canvas/25">
        {TYPE_OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => handleTypeChange(option.value)}
            aria-pressed={filters.type === option.value}
          >
            {option.label}
          </button>
        ))}
        </div>
      </fieldset>

      <label className="block min-w-0">
        <span className="mb-2 block font-mono text-[9px] font-semibold uppercase tracking-[0.14em] text-ink-muted">Sector</span>
        <select
          value={filters.sector}
          onChange={handleSectorChange}
          className="input h-[42px] py-2 text-sm"
        >
          <option value="">전체 섹터</option>
          {sectors.map((sector) => (
            <option key={sector} value={sector}>
              {sector}
            </option>
          ))}
        </select>
      </label>

      <label className="block min-w-0">
        <span className="mb-2 block font-mono text-[9px] font-semibold uppercase tracking-[0.14em] text-ink-muted">Size</span>
        <select
          value={filters.cap}
          onChange={handleCapChange}
          className="input h-[42px] py-2 text-sm"
        >
          {CAP_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>
      {filters.cap !== "all" && (
        <p className="text-xs leading-5 text-ink-muted xl:col-span-4">
          규모 기준 · 미국 $10B / $2B · 한국 10조원 / 1조원, 원천 통화 기준
        </p>
      )}
    </div>
  );
};

export default StockFilters;
