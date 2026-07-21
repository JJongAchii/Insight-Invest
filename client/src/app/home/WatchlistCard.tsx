"use client";

import React from "react";
import Link from "next/link";
import { Star } from "lucide-react";

import { useFetchWatchlistQuery } from "@/state/api";
import Card from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import LoadingState from "@/components/ui/LoadingState";
import WatchlistTable from "@/components/watchlist/WatchlistTable";

/** Dashboard watchlist card — shared table, non-collapsible. */
const WatchlistCard: React.FC = () => {
  const { data, isLoading } = useFetchWatchlistQuery();
  const items = data?.items ?? [];

  return (
    <Card
      title={
        <span className="inline-flex items-center gap-2">
          <Star size={16} className="text-amber-400" fill="currentColor" aria-hidden />
          My Watchlist
        </span>
      }
      action={
        <Link
          href="/stocksearch"
          className="text-xs font-medium text-ink-muted hover:text-ink transition-colors"
        >
          종목 검색 →
        </Link>
      }
    >
      {isLoading ? (
        <LoadingState label="관심종목을 불러오는 중..." />
      ) : items.length === 0 ? (
        <EmptyState
          icon={<Star size={28} aria-hidden />}
          title="관심종목이 없습니다"
          hint={
            <Link href="/stocksearch" className="text-primary-400 hover:underline">
              종목 검색에서 별표로 추가하세요 →
            </Link>
          }
        />
      ) : (
        <WatchlistTable items={items} showAdded={false} />
      )}
    </Card>
  );
};

export default WatchlistCard;
