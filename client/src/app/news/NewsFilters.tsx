"use client";

import React from "react";
import { NewsCategory, NewsRegion, NewsQueryParams } from "@/state/api";

interface NewsFiltersProps {
  currentFilters: NewsQueryParams;
  onFilterChange: (filters: Partial<NewsQueryParams>) => void;
}

const CATEGORIES: { value: NewsCategory; label: string }[] = [
  { value: "topnews", label: "Top News" },
  { value: "economy", label: "Economy" },
  { value: "policy", label: "Policy" },
  { value: "tech", label: "Tech" },
  { value: "trade", label: "Trade" },
  { value: "energy", label: "Energy" },
];

const REGIONS: { value: NewsRegion; label: string }[] = [
  { value: "all", label: "All Regions" },
  { value: "global", label: "Global" },
  { value: "us", label: "US" },
  { value: "asia", label: "Asia" },
  { value: "europe", label: "Europe" },
];

const NewsFilters: React.FC<NewsFiltersProps> = ({
  currentFilters,
  onFilterChange,
}) => {
  return (
    <div className="card">
      <div className="flex flex-col md:flex-row gap-4 md:items-end">
        {/* Category Filter */}
        <div className="flex-1">
          <label className="text-xs font-medium text-neutral-500 mb-2.5 block uppercase tracking-wider">
            Category
          </label>
          <div className="flex flex-wrap gap-2">
            {CATEGORIES.map((cat) => (
              <button
                key={cat.value}
                onClick={() => onFilterChange({ category: cat.value })}
                className={`
                  px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all duration-200
                  ${
                    currentFilters.category === cat.value
                      ? "bg-gradient-to-r from-primary-400 to-primary-500 text-white shadow-md shadow-primary-500/25"
                      : "bg-white/60 text-neutral-600 hover:bg-white hover:text-neutral-900 hover:shadow-sm"
                  }
                `}
              >
                {cat.label}
              </button>
            ))}
          </div>
        </div>

        {/* Region Filter */}
        <div className="md:w-48">
          <label className="text-xs font-medium text-neutral-500 mb-2.5 block uppercase tracking-wider">
            Region
          </label>
          <select
            value={currentFilters.region}
            onChange={(e) =>
              onFilterChange({ region: e.target.value as NewsRegion })
            }
            className="w-full px-3.5 py-2 rounded-lg border border-neutral-200/80 bg-white/80 text-sm font-medium text-neutral-700 focus:outline-none focus:ring-2 focus:ring-primary-500/30 focus:border-primary-400 transition-all cursor-pointer"
          >
            {REGIONS.map((region) => (
              <option key={region.value} value={region.value}>
                {region.label}
              </option>
            ))}
          </select>
        </div>
      </div>
    </div>
  );
};

export default NewsFilters;
