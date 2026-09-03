"use client";

import React, { Suspense, useState, useMemo, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { GitCompareArrows, SlidersHorizontal, Star, X } from "lucide-react";

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

  const universeMeta = useMemo(() => {
    const us = data.filter((row) => row.iso_code === "US").length;
    const kr = data.filter((row) => row.iso_code === "KR").length;
    return { us, kr };
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
        eyebrow="Security registry"
        title="종목 탐색"
        description="관심종목을 출발점으로 유니버스를 좁히고, 최대 5개 종목의 가격 경로와 위험 지표를 같은 기준으로 비교합니다."
        meta={
          <>
            <span>{data.length.toLocaleString()} securities</span>
            <span>·</span>
            <span>US {universeMeta.us.toLocaleString()}</span>
            <span>·</span>
            <span>KR {universeMeta.kr.toLocaleString()}</span>
          </>
        }
        actions={
          <a href="#watchlist" className="btn-secondary inline-flex items-center gap-2 text-sm">
            <Star size={15} aria-hidden />
            관심종목
          </a>
        }
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
          <WatchlistSection />

          <section aria-labelledby="universe-title" className="overflow-hidden rounded-2xl border border-edge bg-surface shadow-[0_18px_60px_rgba(0,0,0,0.12)]">
            <header className="grid gap-3 border-b border-edge px-5 py-5 md:grid-cols-[minmax(0,1fr)_auto] md:items-end md:px-6">
              <div>
                <p className="flex items-center gap-1.5 font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-primary-300">
                  <SlidersHorizontal size={12} aria-hidden />
                  Universe controls
                </p>
                <h2 id="universe-title" className="mt-1 text-xl font-semibold tracking-[-0.025em] text-ink">시장 유니버스</h2>
              </div>
              <p className="text-xs text-ink-muted">행을 열어 요약 확인 · 체크박스로 비교 바구니 추가</p>
            </header>
            <div className="border-b border-edge bg-raised/30 px-5 py-4 md:px-6">
              <StockFilters
                filters={filters}
                onFilterChange={setFilters}
                sectors={sectors}
              />
            </div>
            <MetaTable
              data={data}
              filters={filters}
              selectedIds={selectedIds}
              onSelectionChange={setSelectedIds}
              onRowClick={handleRowClick}
              initialQuickFilter={initialQuickFilter}
            />
          </section>

          {selectedIds.length > 0 && (
            <div className="fixed bottom-20 left-1/2 z-40 w-[calc(100%-2rem)] max-w-xl -translate-x-1/2 md:bottom-6" aria-live="polite">
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-primary-400/35 bg-overlay/95 px-4 py-3 text-ink shadow-2xl shadow-black/30 backdrop-blur-xl sm:flex-nowrap">
                <span className="flex items-center gap-2 text-sm">
                  <GitCompareArrows size={16} className="text-primary-300" aria-hidden />
                  비교 바구니 <strong className="num text-ink">{selectedIds.length}/5</strong>
                </span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setSelectedIds([])}
                    className="btn-ghost inline-flex items-center gap-1.5 px-3 py-2 text-xs"
                  >
                    <X size={14} aria-hidden /> 모두 해제
                  </button>
                  <button
                    type="button"
                    onClick={handleCompareClick}
                    disabled={selectedIds.length < 2}
                    className="btn-primary px-4 py-2 text-sm"
                  >
                    {selectedIds.length < 2 ? "한 종목 더 선택" : "같은 축에서 비교"}
                  </button>
                </div>
              </div>
            </div>
          )}

          {selectedStock && (
            <>
              <button
                type="button"
                aria-label="종목 상세 패널 닫기"
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
            eyebrow="Security registry"
            title="종목 탐색"
            description="관심종목을 출발점으로 유니버스를 좁히고, 가격 경로와 위험 지표를 같은 기준으로 비교합니다."
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
