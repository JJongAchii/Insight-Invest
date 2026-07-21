"use client";

import React, { useState } from "react";
import { ChevronDown, ChevronUp, Star } from "lucide-react";

import { useFetchWatchlistQuery } from "@/state/api";
import Card from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import LoadingState from "@/components/ui/LoadingState";
import WatchlistTable from "@/components/watchlist/WatchlistTable";

/** Collapsible watchlist table shown at the top of the stock search page. */
const WatchlistSection: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);

  const { data, isLoading } = useFetchWatchlistQuery();
  const items = data?.items ?? [];

  return (
    <Card
      title={
        <span className="inline-flex items-center gap-2">
          <Star size={16} className="text-amber-400" fill="currentColor" aria-hidden />
          {`My Watchlist (${items.length})`}
        </span>
      }
      action={
        <button
          onClick={() => setCollapsed((prev) => !prev)}
          aria-expanded={!collapsed}
          aria-label={collapsed ? "관심종목 펼치기" : "관심종목 접기"}
          className="p-1.5 rounded-lg text-ink-muted hover:text-ink hover:bg-raised transition-colors"
        >
          {collapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
        </button>
      }
    >
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
    </Card>
  );
};

export default WatchlistSection;
