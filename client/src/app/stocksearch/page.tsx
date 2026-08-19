"use client";

import React, { Suspense, useState, useMemo, useCallback } from "react";
import { useSearchParams } from "next/navigation";

import { useFetchMetaDataQuery } from "@/state/api";
import MetaTable from "./MetaTable";
import StockFilters from "./StockFilters";
import StockDetailPanel from "./StockDetailPanel";
import CompareView from "./CompareView";
import WatchlistSection from "./WatchlistSection";
import { MetaRow, FilterState } from "./types";
import PageHeader from "@/components/ui/PageHeader";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";

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
    type: "all",
    search: "",
  });

  // Fetch meta data
  const { data: rawData, isLoading, error, refetch } = useFetchMetaDataQuery({});

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
        alert("비교 종목은 최대 5개까지 선택할 수 있습니다.");
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

  return (
    <div className="flex flex-col gap-6 pb-16">
      <PageHeader
        title="Stock Search"
        description="미국·한국 시장의 종목을 검색하고 비교합니다"
      />

      {error ? (
        <div className="card">
          <ErrorState message="종목 목록을 불러오지 못했습니다" onRetry={refetch} />
        </div>
      ) : isLoading ? (
        <div className="card">
          <LoadingState label="종목 목록을 불러오는 중..." />
        </div>
      ) : viewMode === "list" ? (
        <>
          {/* Watchlist */}
          <WatchlistSection />

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
            <div className="fixed bottom-20 md:bottom-6 left-1/2 -translate-x-1/2 z-40">
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
        <div className="flex flex-col gap-6 pb-16">
          <PageHeader
            title="Stock Search"
            description="미국·한국 시장의 종목을 검색하고 비교합니다"
          />
          <div className="card">
            <LoadingState label="종목 목록을 불러오는 중..." />
          </div>
        </div>
      }
    >
      <StockSearchContent />
    </Suspense>
  );
};

export default StockSearch;
