"use client";

import React, { useMemo, useState } from "react";
import Searchbar, { SortKey } from "./Searchbar";
import Contents, { Strategy } from "./Contents";
import PageHeader from "@/components/ui/PageHeader";
import {
  useFetchStrategiesQuery,
  useFetchStrategyMonthlyNavQuery,
} from "@/state/api";

const StrategyList = () => {
  const { data: strategyInfo } = useFetchStrategiesQuery({});
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

  return (
    <div className="flex flex-col gap-6 pb-16">
      <PageHeader
        title="Research Lab · 전략 보관함"
        description="백테스트 성과뿐 아니라 실행 전제·기간·검증 상태를 함께 확인합니다"
      />

      <div className="rounded-xl border border-warning/30 bg-warning/5 px-4 py-3 text-xs leading-5 text-ink-secondary">
        이 목록의 수익률·변동성·샤프는 모두 연구 구간 수치이며 미검증 상태입니다.
        표본 외 검증과 데이터 누출 감사를 통과하기 전에는 실전 전략으로 간주하지 않습니다.
      </div>

      <div className="card">
        <Searchbar
          search={search}
          onSearchChange={setSearch}
          sortKey={sortKey}
          onSortChange={setSortKey}
        />
        <Contents strategyList={visibleStrategies} strategyNav={strategyNav} />
      </div>
    </div>
  );
};

export default StrategyList;
