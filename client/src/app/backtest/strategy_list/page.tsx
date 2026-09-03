"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import { Plus, ShieldAlert } from "lucide-react";
import Searchbar, { SortKey } from "./Searchbar";
import Contents, { Strategy } from "./Contents";
import PageHeader from "@/components/ui/PageHeader";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";
import {
  useFetchStrategiesQuery,
  useFetchStrategyMonthlyNavQuery,
} from "@/state/api";

const StrategyList = () => {
  const {
    data: strategyInfo,
    isLoading,
    isError,
    refetch,
  } = useFetchStrategiesQuery({});
  const { data: strategyNav } = useFetchStrategyMonthlyNavQuery({});

  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("name");

  const visibleStrategies = useMemo(() => {
    const list: Strategy[] = strategyInfo ? [...strategyInfo] : [];

    const query = search.trim().toLowerCase();
    const filtered = query
      ? list.filter(
          (s) =>
            s.port_name?.toLowerCase().includes(query) ||
            s.strategy_name?.toLowerCase().includes(query)
        )
      : list;

    return filtered.sort((a, b) => {
      switch (sortKey) {
        case "return":
          return b.ann_ret - a.ann_ret;
        case "sharpe":
          return b.sharpe - a.sharpe;
        case "name":
        default:
          return (a.port_name ?? "").localeCompare(b.port_name ?? "");
      }
    });
  }, [strategyInfo, search, sortKey]);

  const totalCount = strategyInfo?.length ?? 0;
  const trackingCount = strategyInfo?.filter(
    (strategy: Strategy) => strategy.status === "active"
  ).length ?? 0;

  return (
    <div className="flex flex-col gap-6 pb-16">
      <PageHeader
        eyebrow="Backtest results"
        title="저장된 백테스트"
        description="저장한 백테스트의 성과, 실행 조건, 추적 상태를 한곳에서 비교하고 상세 결과를 확인합니다."
        meta={
          <>
            <span>{totalCount} records</span>
            <span>·</span>
            <span>{trackingCount} tracking</span>
            <span>·</span>
            <span>0 verified</span>
          </>
        }
        actions={
          <Link href="/backtest/simulation" className="btn-primary inline-flex items-center gap-2 text-sm">
            <Plus size={16} aria-hidden />
            새 백테스트
          </Link>
        }
      />

      <aside className="relative overflow-hidden rounded-2xl border border-warning/25 bg-warning/5 px-5 py-4">
        <span aria-hidden className="absolute inset-y-0 left-0 w-px bg-warning" />
        <div className="flex items-start gap-3">
          <ShieldAlert size={18} className="mt-0.5 shrink-0 text-warning" aria-hidden />
          <div>
            <p className="text-sm font-semibold text-ink">현재 저장된 결과는 전부 연구 단계입니다</p>
            <p className="mt-1 max-w-4xl text-xs leading-5 text-ink-secondary">
              수익률·변동성·샤프는 연구 구간의 관측치입니다. 표본 외 검증과 데이터 누출 감사를 통과하기 전에는 실전 성과로 해석하지 않습니다.
            </p>
          </div>
        </div>
      </aside>

      <section className="overflow-hidden rounded-2xl border border-edge bg-surface shadow-[0_18px_60px_rgba(0,0,0,0.12)]" aria-labelledby="strategy-index-title">
        <div className="flex flex-wrap items-end justify-between gap-3 px-5 pt-5 md:px-6 md:pt-6">
          <div>
            <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.18em] text-primary-300">Result index</p>
            <h2 id="strategy-index-title" className="mt-1 text-lg font-semibold tracking-[-0.02em] text-ink">백테스트 결과</h2>
          </div>
          <p className="text-xs text-ink-muted">선택하면 실행 조건 → 백테스트 결과 → 운영 추적 순서로 열립니다</p>
        </div>
        <Searchbar
          search={search}
          onSearchChange={setSearch}
          sortKey={sortKey}
          onSortChange={setSortKey}
        />
        {isError ? (
          <ErrorState message="저장된 백테스트를 불러오지 못했습니다" onRetry={refetch} />
        ) : isLoading ? (
          <LoadingState label="저장된 백테스트를 불러오는 중..." />
        ) : (
          <Contents strategyList={visibleStrategies} strategyNav={strategyNav} />
        )}
      </section>
    </div>
  );
};

export default StrategyList;
