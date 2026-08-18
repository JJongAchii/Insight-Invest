"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Clock3 } from "lucide-react";

import { useFetchOverviewQuery } from "@/state/api";
import { formatDate } from "@/lib/market";

const STORAGE_KEY = "insight-invest:last-overview-visit";

export default function SinceLastVisit() {
  const { data } = useFetchOverviewQuery();
  const [previousVisit, setPreviousVisit] = useState<string | null | undefined>(undefined);

  useEffect(() => {
    setPreviousVisit(window.localStorage.getItem(STORAGE_KEY));
  }, []);

  useEffect(() => {
    if (!data || previousVisit === undefined) return;
    window.localStorage.setItem(STORAGE_KEY, data.generated_at);
  }, [data, previousVisit]);

  const changes = useMemo(() => {
    if (!data || previousVisit === undefined) return [];
    const priorDay = previousVisit?.slice(0, 10);
    return data.evidence.filter(
      (item) => item.changed && (!priorDay || !item.as_of || item.as_of.slice(0, 10) > priorDay)
    );
  }, [data, previousVisit]);

  if (!data || previousVisit === undefined) return null;

  return (
    <section className="rounded-2xl border border-edge bg-surface p-4" aria-labelledby="since-title">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <Clock3 size={18} className="text-primary-400" aria-hidden />
          <h2 id="since-title" className="text-sm font-semibold text-ink">지난 방문 이후</h2>
        </div>
        {previousVisit && <span className="text-xs text-ink-muted">이전 방문 {formatDate(previousVisit)}</span>}
      </div>
      {!previousVisit ? (
        <p className="mt-2 text-sm text-ink-secondary">
          첫 방문입니다. 다음 방문부터 새로 전환되거나 임계치를 넘은 근거만 이곳에 모읍니다.
        </p>
      ) : changes.length === 0 ? (
        <p className="mt-2 text-sm text-ink-secondary">새로 확인할 주요 근거 변화가 없습니다.</p>
      ) : (
        <div className="mt-3 flex gap-3 overflow-x-auto pb-1">
          {changes.map((item) => (
            <Link key={item.key} href={item.link} className="min-w-[240px] rounded-xl bg-raised p-3 hover:bg-overlay">
              <p className="text-sm font-medium text-ink">{item.title}</p>
              <p className="mt-1 text-xs text-ink-secondary">{item.detail}</p>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}
