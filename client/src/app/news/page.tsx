"use client";

import React, { useState, useCallback } from "react";
import { useFetchNewsQuery, NewsQueryParams } from "@/state/api";
import NewsFilters from "./NewsFilters";
import NewsGrid from "./NewsGrid";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";
import { IoRefresh, IoNewspaper } from "react-icons/io5";

const NewsPage = () => {
  const [filters, setFilters] = useState<NewsQueryParams>({
    category: "topnews",
    region: "all",
  });

  const { data, isLoading, isFetching, error, refetch } =
    useFetchNewsQuery(filters);

  const handleFilterChange = useCallback(
    (newFilters: Partial<NewsQueryParams>) => {
      setFilters((prev) => ({ ...prev, ...newFilters }));
    },
    []
  );

  const handleRefresh = useCallback(async () => {
    // Clear backend cache first, then refetch
    try {
      await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/news/cache`, {
        method: "DELETE",
      });
    } catch (e) {
      // Ignore cache clear errors
    }
    refetch();
  }, [refetch]);

  if (isLoading) {
    return (
      <div className="card">
        <LoadingState label="Loading news..." />
      </div>
    );
  }

  if (error) {
    return (
      <div className="card">
        <ErrorState message="Failed to load news" onRetry={handleRefresh} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 pb-16">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary-400 to-primary-600 flex items-center justify-center shadow-lg shadow-primary-500/25">
            <IoNewspaper className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="page-title">World Economy News</h1>
            <p className="page-description">
              Real-time financial news from global sources
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {data?.cached && (
            <span className="text-xs text-ink-muted px-2.5 py-1 bg-raised rounded-lg font-medium">
              Cached
            </span>
          )}
          <button
            onClick={handleRefresh}
            disabled={isFetching}
            className={`
              flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200
              ${
                isFetching
                  ? "bg-raised text-ink-muted cursor-not-allowed"
                  : "bg-gradient-to-r from-primary-400 to-primary-500 text-white shadow-md shadow-primary-500/25 hover:shadow-lg hover:shadow-primary-500/30"
              }
            `}
          >
            <IoRefresh
              className={`w-4 h-4 ${isFetching ? "animate-spin" : ""}`}
            />
            {isFetching ? "Refreshing..." : "Refresh"}
          </button>
        </div>
      </div>

      {/* Filters */}
      <NewsFilters
        currentFilters={filters}
        onFilterChange={handleFilterChange}
      />

      {/* Article Count */}
      {data && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-ink-muted">
            Showing{" "}
            <span className="font-semibold text-ink-secondary">
              {data.articles.length}
            </span>{" "}
            of{" "}
            <span className="font-semibold text-ink-secondary">
              {data.total_count}
            </span>{" "}
            articles
          </p>
          {data.fetched_at && (
            <p className="text-xs text-ink-muted">
              Updated:{" "}
              {new Date(data.fetched_at).toLocaleTimeString("en-US", {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </p>
          )}
        </div>
      )}

      {/* News Grid */}
      {data && <NewsGrid articles={data.articles} isLoading={isFetching} />}
    </div>
  );
};

export default NewsPage;
