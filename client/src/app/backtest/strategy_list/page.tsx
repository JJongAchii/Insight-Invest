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
        title="Strategy Library"
        description="Explore and manage your saved backtest strategies"
      />

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
