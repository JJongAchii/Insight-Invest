"use client";

import React, { useState } from "react";
import {
  useScanStocksMutation,
  ScreenerPayload,
  ScreenerResponse,
  ScreenerSortField,
} from "@/state/api";
import FilterPanel from "./FilterPanel";
import ResultsTable from "./ResultsTable";
import HighsLowsPanel from "./HighsLowsPanel";

const ScreenerPage = () => {
  const [scanStocks, { isLoading }] = useScanStocksMutation();
  const [results, setResults] = useState<ScreenerResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"screener" | "highs_lows">("screener");

  const handleScan = async (filters: ScreenerPayload) => {
    setError(null);
    try {
      const result = await scanStocks(filters).unwrap();
      setResults(result);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Screening failed";
      setError(errorMessage);
      console.error("Screening error:", err);
    }
  };

  const handleSort = async (sortBy: ScreenerSortField, ascending: boolean) => {
    if (!results) return;

    // Re-scan with new sort
    try {
      const result = await scanStocks({
        sort_by: sortBy,
        ascending,
        limit: 100,
      }).unwrap();
      setResults(result);
    } catch (err) {
      console.error("Sort error:", err);
    }
  };

  return (
    <div className="flex flex-col gap-6 pb-16">
      {/* Loading Overlay */}
      {isLoading && (
        <div className="fixed inset-0 bg-black/20 backdrop-blur-sm z-50 flex items-center justify-center">
          <div className="bg-white rounded-2xl shadow-xl p-8 flex flex-col items-center gap-4">
            <div className="w-12 h-12 border-4 border-primary-500 border-t-transparent rounded-full animate-spin"></div>
            <p className="text-neutral-700 font-medium">Scanning stocks...</p>
          </div>
        </div>
      )}

      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-semibold text-neutral-900">Stock Screener</h1>
        <p className="text-sm text-neutral-500 mt-1">
          Filter and rank stocks by technical indicators
        </p>
      </div>

      {/* Tab Selection */}
      <div className="flex gap-2">
        <button
          onClick={() => setActiveTab("screener")}
          className={`px-4 py-2 rounded-lg font-medium text-sm transition-all ${
            activeTab === "screener"
              ? "bg-neutral-900 text-white"
              : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
          }`}
        >
          Screener
        </button>
        <button
          onClick={() => setActiveTab("highs_lows")}
          className={`px-4 py-2 rounded-lg font-medium text-sm transition-all ${
            activeTab === "highs_lows"
              ? "bg-neutral-900 text-white"
              : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
          }`}
        >
          52-Week Highs & Lows
        </button>
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-700 text-sm">{error}</p>
        </div>
      )}

      {/* Screener Tab */}
      {activeTab === "screener" && (
        <>
          <FilterPanel onScan={handleScan} isLoading={isLoading} />

          {results && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <p className="text-sm text-neutral-600">
                  Showing <span className="font-semibold">{results.filtered_count}</span> of{" "}
                  <span className="font-semibold">{results.total_count}</span> stocks
                </p>
              </div>
              <ResultsTable data={results.results} onSort={handleSort} />
            </div>
          )}

          {!results && !isLoading && (
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
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                  />
                </svg>
              </div>
              <h3 className="text-lg font-medium text-neutral-700 mb-2">
                No screening results yet
              </h3>
              <p className="text-sm text-neutral-500">
                Set your filters and click &quot;Scan Stocks&quot; to see results
              </p>
            </div>
          )}
        </>
      )}

      {/* Highs & Lows Tab */}
      {activeTab === "highs_lows" && <HighsLowsPanel />}
    </div>
  );
};

export default ScreenerPage;
