import React from "react";
import { useRouter } from "next/navigation";
import SparklineChart from "@/components/charts/SparklineChart";
import EmptyState from "@/components/ui/EmptyState";

export interface Strategy {
  port_id: number;
  port_name: string;
  strategy_name: string;
  ann_ret: number;
  ann_vol: number;
  sharpe: number;
}

interface StrategyNav {
  port_id: number;
  trade_date: string;
  value: number;
}

const Contents = ({
  strategyList,
  strategyNav,
}: {
  strategyList: Strategy[];
  strategyNav: StrategyNav[];
}) => {
  const router = useRouter();
  const handleGridClick = (port_id: number) => {
    router.push(`/backtest/strategy_list/${port_id}`);
  };

  if (!strategyList || strategyList.length === 0) {
    return (
      <EmptyState
        title="No strategies found"
        hint="Run a backtest and save it to see it here"
      />
    );
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 mt-4">
      {strategyList?.map((strategy) => {
        const navValues =
          strategyNav
            ?.filter((nav) => nav.port_id === strategy.port_id)
            .map((nav) => nav.value) ?? [];

        return (
          <div
            key={strategy.port_id}
            className="card-interactive flex p-5"
            onClick={() => handleGridClick(strategy.port_id)}
          >
            <div className="w-1/2 pr-4">
              <div className="font-semibold text-ink mb-1">
                {strategy.port_name}
              </div>
              <div className="text-ink-muted text-xs mb-3">
                {strategy.strategy_name}
              </div>
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-ink-muted">Return</span>
                  <span
                    className={
                      strategy.ann_ret >= 0
                        ? "metric-positive text-sm"
                        : "metric-negative text-sm"
                    }
                  >
                    {strategy.ann_ret >= 0 ? "+" : ""}
                    {strategy.ann_ret}%
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-ink-muted">Volatility</span>
                  <span className="num text-sm font-medium text-ink-secondary">
                    {strategy.ann_vol}%
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-ink-muted">Sharpe</span>
                  <span className="num text-sm font-medium text-ink-secondary">
                    {strategy.sharpe}
                  </span>
                </div>
              </div>
            </div>
            <div className="w-1/2 flex items-center justify-center">
              <SparklineChart
                data={navValues}
                width={140}
                height={60}
                color="var(--chart-1)"
              />
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default Contents;
