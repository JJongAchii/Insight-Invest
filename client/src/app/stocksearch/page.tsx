"use client";

import React, { Suspense, useState, useMemo, useCallback } from "react";
import { useSearchParams } from "next/navigation";

import { useFetchMetaDataQuery } from "@/state/api";
import MetaTable from "./MetaTable";
import StockFilters from "./StockFilters";
import StockDetailPanel from "./StockDetailPanel";
import CompareView from "./CompareView";
import { MetaRow, FilterState } from "./types";
import PageHeader from "@/components/ui/PageHeader";
import LoadingState from "@/components/ui/LoadingState";

type ViewMode = "list" | "compare";

const StockSearchContent = () => {
  const searchParams = useSearchParams();
  const initialQuickFilter = searchParams.get("q") ?? "";

  // View state
  const [viewMode, setViewMode] = useState<ViewMode>("list");
  const [selectedStock, setSelectedStock] = useState<MetaRow | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);

  // Filter state
  const [filters, setFilters] = useState<FilterState>({
    market: "all",
    sector: "",
    cap: "all",
    search: "",
  });

  // Fetch meta data
  const { data: rawData, isLoading } = useFetchMetaDataQuery({});

  // Memoize data to avoid re-renders
  const data = useMemo(() => {
    return (rawData as MetaRow[]) || [];
  }, [rawData]);

  // Extract unique sectors for filter dropdown
  const sectors = useMemo(() => {
    const sectorSet = new Set<string>();
    data.forEach((row) => {
      if (row.sector) sectorSet.add(row.sector);
    });
    return Array.from(sectorSet).sort();
  }, [data]);

  // Handlers
  const handleRowClick = useCallback((row: MetaRow) => {
    setSelectedStock(row);
  }, []);

  const handleClosePanel = useCallback(() => {
    setSelectedStock(null);
  }, []);

  const handleAddToCompare = useCallback((metaId: number) => {
    setSelectedIds((prev) => {
      if (prev.includes(metaId)) return prev;
      if (prev.length >= 5) {
        alert("Maximum 5 stocks can be compared");
        return prev;
      }
      return [...prev, metaId];
    });
  }, []);

  const handleRemoveFromCompare = useCallback((metaId: number) => {
    setSelectedIds((prev) => prev.filter((id) => id !== metaId));
  }, []);

  const handleCompareClick = useCallback(() => {
    if (selectedIds.length >= 2) {
      setViewMode("compare");
      setSelectedStock(null);
    }
  }, [selectedIds.length]);

  const handleBackToList = useCallback(() => {
    setViewMode("list");
  }, []);

  if (isLoading) {
    return (
      <div className="card">
        <LoadingState label="Loading stocks..." />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 pb-16">
      <PageHeader
        title="Stock Search"
        description="Search and explore stock metadata across US and Korean markets"
      />

      {viewMode === "list" ? (
        <>
          {/* Filters */}
          <StockFilters
            filters={filters}
            onFilterChange={setFilters}
            sectors={sectors}
          />

          {/* Meta Table */}
          <MetaTable
            data={data}
            filters={filters}
            selectedIds={selectedIds}
            onSelectionChange={setSelectedIds}
            onRowClick={handleRowClick}
            initialQuickFilter={initialQuickFilter}
          />

          {/* Action Bar - Show when stocks are selected */}
          {selectedIds.length > 0 && (
            <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40">
              <div className="flex items-center gap-4 px-6 py-3 bg-overlay border border-edge-strong text-ink rounded-full shadow-lg">
                <span className="text-sm">
                  {selectedIds.length} stock{selectedIds.length > 1 ? "s" : ""}{" "}
                  selected
                </span>
                <div className="w-px h-5 bg-edge-strong" />
                <button
                  onClick={handleCompareClick}
                  disabled={selectedIds.length < 2}
                  className={`px-4 py-1.5 text-sm font-medium rounded-full transition-colors ${
                    selectedIds.length >= 2
                      ? "bg-primary-500 hover:bg-primary-600 text-white"
                      : "bg-raised text-ink-muted cursor-not-allowed"
                  }`}
                >
                  Compare
                </button>
                <button
                  onClick={() => setSelectedIds([])}
                  className="px-4 py-1.5 text-sm font-medium rounded-full bg-raised hover:bg-overlay"
                >
                  Clear
                </button>
              </div>
            </div>
          )}

          {/* Stock Detail Panel */}
          {selectedStock && (
            <>
              {/* Backdrop */}
              <div
                className="fixed inset-0 bg-black/40 z-40"
                onClick={handleClosePanel}
              />
              <StockDetailPanel
                stock={selectedStock}
                onClose={handleClosePanel}
                onAddToCompare={handleAddToCompare}
              />
            </>
          )}
        </>
      ) : (
        <CompareView
          selectedIds={selectedIds}
          onBack={handleBackToList}
          onRemove={handleRemoveFromCompare}
        />
      )}
    </div>
  );
};

const StockSearch = () => {
  return (
    <Suspense
      fallback={
        <div className="card">
          <LoadingState label="Loading stocks..." />
        </div>
      }
    >
      <StockSearchContent />
    </Suspense>
  );
};

export default StockSearch;
