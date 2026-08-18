import React from "react";
import { useRouter } from "next/navigation";
import SparklineChart from "@/components/charts/SparklineChart";
import EmptyState from "@/components/ui/EmptyState";
import LiveBadge from "@/components/LiveBadge";
import { formatDate } from "@/lib/market";

export interface Strategy {
  port_id: number;
  port_name: string;
  strategy_name: string;
  ann_ret: number;
  ann_vol: number;
  sharpe: number;
  status?: string;
  created_at?: string | null;
  bt_start?: string | null;
  bt_end?: string | null;
  benchmark?: string | null;
  currency?: string | null;
  cost_bps?: number | null;
  audit_status?: "unverified" | string | null;
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
        title="저장된 연구 전략이 없습니다"
        hint="백테스트를 실행하고 저장하면 이곳에서 전제와 기간을 함께 비교할 수 있습니다"
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
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                handleGridClick(strategy.port_id);
              }
            }}
            role="link"
            tabIndex={0}
          >
            <div className="w-3/5 pr-4">
              <div className="flex items-center gap-2 mb-1">
                <div className="font-semibold text-ink">
                  {strategy.port_name}
                </div>
                {strategy.status === "active" && (
                  <span className="badge-neutral" style={{ color: "var(--gains)" }}>
                    ACTIVE
                  </span>
                )}
                <span className="badge-neutral text-[10px]">미검증</span>
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
              <dl className="mt-3 space-y-1 border-t border-edge pt-3 text-[11px] text-ink-muted">
                <div className="flex justify-between gap-2">
                  <dt>실험 구간</dt>
                  <dd className="text-right num text-ink-secondary">
                    {strategy.bt_start ?? "—"} ~ {strategy.bt_end ?? "—"}
                  </dd>
                </div>
                <div className="flex justify-between gap-2">
                  <dt>전제</dt>
                  <dd className="text-right text-ink-secondary">
                    {strategy.benchmark ?? "BM 미기록"} · {strategy.currency ?? "통화 미기록"} · 비용 {strategy.cost_bps ?? "—"}bps
                  </dd>
                </div>
                <div className="flex justify-between gap-2">
                  <dt>저장일</dt>
                  <dd className="text-right text-ink-secondary">
                    {formatDate(strategy.created_at)}
                  </dd>
                </div>
              </dl>
            </div>
            <div className="w-2/5 flex flex-col items-center justify-center gap-1.5">
              <SparklineChart
                data={navValues}
                width={140}
                height={60}
                color="var(--chart-1)"
              />
              {/* Live (post-save) track — hidden until tracking data exists */}
              <LiveBadge
                portId={strategy.port_id}
                showSparkline
                sparkWidth={70}
                sparkHeight={20}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default Contents;
