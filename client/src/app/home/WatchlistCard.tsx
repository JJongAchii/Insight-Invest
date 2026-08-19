"use client";

import React, { useMemo } from "react";
import Link from "next/link";
import { Star } from "lucide-react";

import { useFetchIntradayMarketQuery, useFetchWatchlistQuery } from "@/state/api";
import Card from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import LoadingState from "@/components/ui/LoadingState";
import WatchlistTable from "@/components/watchlist/WatchlistTable";

/** Dashboard watchlist card — shared table, non-collapsible. */
const WatchlistCard: React.FC = () => {
  const { data, isLoading } = useFetchWatchlistQuery();
  const { data: intraday } = useFetchIntradayMarketQuery(undefined, {
    pollingInterval: 5 * 60 * 1000,
    skipPollingIfUnfocused: true,
  });
  const items = data?.items ?? [];

  // KR 장중 등락률 오버라이드 — meta_id → chg_pct (스펙 D4, active일 때만).
  const liveChg = useMemo(() => {
    if (!intraday?.active) return undefined;
    const out = new Map<number, number>();
    for (const row of intraday.my?.watchlist ?? []) {
      if (row.meta_id != null && row.chg_pct != null) {
        out.set(row.meta_id, row.chg_pct);
      }
    }
    return out;
  }, [intraday]);

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
          Search Stocks →
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
        <WatchlistTable items={items} showAdded={false} liveChg={liveChg} />
      )}
    </Card>
  );
};

export default WatchlistCard;
