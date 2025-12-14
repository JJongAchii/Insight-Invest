"use client";

import React, { useState, useCallback } from "react";
import { useFetchNewsQuery, NewsQueryParams } from "@/state/api";
import NewsFilters from "./NewsFilters";
import NewsGrid from "./NewsGrid";
import LoadingSpinner from "../(components)/LoadingSpinner";
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

  if (isLoading) return <LoadingSpinner />;

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-64">
        <div className="w-16 h-16 rounded-full bg-rose-50 flex items-center justify-center mb-4">
          <svg
            className="w-8 h-8 text-rose-500"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>
        <p className="text-rose-600 text-lg font-medium mb-2">
          Failed to load news
        </p>
        <p className="text-neutral-500 text-sm mb-4">
          Please check your connection and try again
        </p>
        <button
          onClick={handleRefresh}
          className="px-5 py-2.5 bg-gradient-to-r from-primary-400 to-primary-500 text-white rounded-xl font-medium shadow-lg shadow-primary-500/25 hover:shadow-xl hover:shadow-primary-500/30 transition-all duration-200"
        >
          Try Again
        </button>
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
            <h1 className="text-2xl font-semibold text-neutral-900">
              World Economy News
            </h1>
            <p className="text-sm text-neutral-500 mt-0.5">
              Real-time financial news from global sources
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {data?.cached && (
            <span className="text-xs text-neutral-400 px-2.5 py-1 bg-neutral-100/80 rounded-lg font-medium">
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
                  ? "bg-neutral-200 text-neutral-400 cursor-not-allowed"
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
          <p className="text-sm text-neutral-500">
            Showing{" "}
            <span className="font-semibold text-neutral-700">
              {data.articles.length}
            </span>{" "}
            of{" "}
            <span className="font-semibold text-neutral-700">
              {data.total_count}
            </span>{" "}
            articles
          </p>
          {data.fetched_at && (
            <p className="text-xs text-neutral-400">
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
