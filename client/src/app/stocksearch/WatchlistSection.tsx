"use client";

import React, { useState } from "react";
import { ChevronDown, ChevronUp, Star } from "lucide-react";

import { useFetchWatchlistQuery } from "@/state/api";
import EmptyState from "@/components/ui/EmptyState";
import LoadingState from "@/components/ui/LoadingState";
import WatchlistTable from "@/components/watchlist/WatchlistTable";

/** Collapsible watchlist table shown at the top of the stock search page. */
const WatchlistSection: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);

  const { data, isLoading } = useFetchWatchlistQuery();
  const items = data?.items ?? [];

  return (
    <section id="watchlist" className="scroll-mt-24 overflow-hidden rounded-2xl border border-edge bg-surface" aria-labelledby="watchlist-title">
      <header className="flex items-center justify-between gap-4 px-5 py-4 md:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-warning/25 bg-warning/10 text-warning">
            <Star size={15} fill="currentColor" aria-hidden />
          </span>
          <div className="min-w-0">
            <p className="font-mono text-[9px] font-semibold uppercase tracking-[0.16em] text-ink-muted">Pinned register · {items.length}</p>
            <h2 id="watchlist-title" className="mt-0.5 truncate text-base font-semibold text-ink">관심 논거가 있는 종목</h2>
          </div>
        </div>
        <button
          type="button"
          onClick={() => setCollapsed((prev) => !prev)}
          aria-expanded={!collapsed}
          aria-controls="watchlist-content"
          aria-label={collapsed ? "관심종목 펼치기" : "관심종목 접기"}
          className="btn-ghost inline-flex items-center gap-2 px-3 py-2 text-xs"
        >
          {collapsed ? "펼치기" : "접기"}
          {collapsed ? <ChevronDown size={15} aria-hidden /> : <ChevronUp size={15} aria-hidden />}
        </button>
      </header>
      <div id="watchlist-content" className={collapsed ? "hidden" : "border-t border-edge px-5 py-4 md:px-6"}>
        {collapsed ? null : isLoading ? (
          <LoadingState label="관심종목을 불러오는 중..." />
        ) : items.length === 0 ? (
          <EmptyState
            icon={<Star size={28} aria-hidden />}
            title="관심종목이 없습니다"
            hint="별표로 종목을 추가하세요"
          />
        ) : (
          <WatchlistTable items={items} />
        )}
      </div>
    </section>
  );
};

export default WatchlistSection;
