"use client";

import React, { useMemo } from "react";
import Link from "next/link";

import {
  AttentionItem,
  AttentionSeverity,
  useFetchAttentionQuery,
} from "@/state/api";

const SEVERITY_RANK: Record<AttentionSeverity, number> = {
  high: 0,
  medium: 1,
  low: 2,
};

// high = losses(red), medium = chart-4(amber), low = chart-2(blue)
const SEVERITY_DOT: Record<AttentionSeverity, string> = {
  high: "var(--losses)",
  medium: "var(--chart-4)",
  low: "var(--chart-2)",
};

const AttentionCard: React.FC<{ item: AttentionItem }> = ({ item }) => (
  <Link
    href={item.link}
    className="group shrink-0 w-[280px] p-4 rounded-2xl border border-edge bg-surface
               hover:border-edge-strong hover:bg-raised transition-all duration-200"
  >
    <div className="flex items-center gap-2 mb-2">
      <span
        className="w-2 h-2 rounded-full shrink-0"
        style={{ backgroundColor: SEVERITY_DOT[item.severity] }}
        aria-hidden
      />
      <span className="badge-neutral">{item.category}</span>
      {(item.ticker || item.name) && (
        <span className="ml-auto text-xs text-ink-muted num truncate">
          {item.ticker ?? item.name}
        </span>
      )}
    </div>
    <p className="text-sm font-semibold text-ink group-hover:text-ink line-clamp-2">
      {item.title}
    </p>
    <p className="text-xs text-ink-secondary mt-1 line-clamp-2">{item.detail}</p>
  </Link>
);

/** "오늘 주목" — attention items sorted high→low. Hidden on error. */
const AttentionLane: React.FC = () => {
  const { data, isLoading, error, refetch } = useFetchAttentionQuery();

  const items = useMemo(() => {
    // 매크로 국면·시장 위험도는 시간축 카드에서 한 번만 보여준다.
    const list = (data?.items ?? []).filter((item) => item.category !== "macro");
    return [...list].sort(
      (a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity]
    );
  }, [data]);

  if (error) {
    return (
      <div className="rounded-xl border border-edge px-4 py-3 flex items-center justify-between gap-3">
        <p className="text-sm text-ink-muted">내 자산 확인점을 불러오지 못했습니다.</p>
        <button onClick={refetch} className="text-xs font-semibold text-primary-400 hover:underline">
          다시 시도
        </button>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-ink-muted">
        <span
          className="w-4 h-4 rounded-full animate-spin"
          style={{
            border: "2px solid var(--border)",
            borderTopColor: "var(--primary)",
          }}
          aria-hidden
        />
        내 자산 확인점을 불러오는 중...
      </div>
    );
  }

  return (
    <div>
      <h2 className="text-sm font-semibold text-ink-secondary mb-3">
        Portfolio Attention
      </h2>
      {items.length === 0 ? (
        <p className="text-sm text-ink-muted">
          보유·관심 종목에서 새로 확인할 예외가 없습니다.
        </p>
      ) : (
        <div className="flex gap-3 overflow-x-auto pb-2 -mx-1 px-1">
          {items.map((item, i) => (
            <AttentionCard key={`${item.category}-${item.ticker ?? i}`} item={item} />
          ))}
        </div>
      )}
    </div>
  );
};

export default AttentionLane;
