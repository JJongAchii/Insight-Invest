"use client";

import { BellRing, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useEffect } from "react";

import { useFetchActionsQuery } from "@/state/api";

export default function ActionCenterSummary() {
  const { data, isLoading, error } = useFetchActionsQuery({ horizonDays: 30 });

  useEffect(() => {
    const nav = navigator as Navigator & { setAppBadge?: (count?: number) => Promise<void> };
    if (data && nav.setAppBadge) {
      nav.setAppBadge(data.counts.badge ?? data.counts.actionable).catch(() => undefined);
    }
  }, [data]);

  if (error) return null;

  const items = (data?.items ?? []).filter((item) => item.severity !== "low").slice(0, 3);

  return (
    <section className="rounded-2xl border border-edge bg-surface p-4 lg:p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <BellRing size={18} className="text-primary-400" aria-hidden />
            <h2 className="font-semibold text-ink">Action Center</h2>
            {data && data.counts.actionable > 0 && (
              <span className="rounded-full bg-primary-500 px-2 py-0.5 text-xs font-semibold text-white num">
                {data.counts.actionable}
              </span>
            )}
          </div>
          <p className="mt-1 text-sm text-ink-secondary">지금 내 판단에 영향을 주는 변화만 모았습니다.</p>
        </div>
        <Link href="/actions" className="flex items-center gap-1 text-sm font-medium text-primary-400">
          View All <ChevronRight size={15} />
        </Link>
      </div>

      {isLoading ? (
        <p className="mt-4 text-sm text-ink-muted">Action을 정리하는 중...</p>
      ) : items.length === 0 ? (
        <p className="mt-4 text-sm text-ink-muted">새로 확인할 중요 항목이 없습니다.</p>
      ) : (
        <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-3">
          {items.map((item) => (
            <Link key={item.event_id} href={item.link} className="rounded-xl border border-edge p-3 hover:bg-raised">
              <div className="flex items-center gap-2 text-xs text-ink-muted">
                <span className={`h-2 w-2 rounded-full ${item.severity === "high" ? "bg-losses" : "bg-warning"}`} />
                <span>{item.category}</span>
                {item.ticker && <span className="ml-auto num">{item.ticker}</span>}
              </div>
              <p className="mt-2 text-sm font-semibold text-ink line-clamp-2">{item.title}</p>
              <p className="mt-1 text-xs text-ink-secondary line-clamp-2">{item.detail}</p>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}
