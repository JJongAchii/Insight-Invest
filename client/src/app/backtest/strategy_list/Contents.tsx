import React from "react";
import Link from "next/link";
import { ArrowUpRight, CalendarRange, FlaskConical } from "lucide-react";
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
  strategyNav?: StrategyNav[];
}) => {
  if (!strategyList || strategyList.length === 0) {
    return (
      <div className="px-5 md:px-6">
        <EmptyState
          icon={<FlaskConical size={28} aria-hidden />}
          title="조건에 맞는 백테스트가 없습니다"
          hint="검색어를 지우거나 새 백테스트를 저장해 보세요"
        />
      </div>
    );
  }

  return (
    <div>
      <div className="hidden grid-cols-[minmax(220px,1.3fr)_minmax(260px,1fr)_170px_minmax(260px,1fr)_28px] gap-5 border-b border-edge bg-raised/60 px-6 py-3 font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-muted xl:grid">
        <span>Strategy record</span>
        <span>Research evidence</span>
        <span>Track</span>
        <span>Test contract</span>
        <span aria-hidden />
      </div>
      {strategyList?.map((strategy) => {
        const navValues =
          strategyNav
            ?.filter((nav) => nav.port_id === strategy.port_id)
            .map((nav) => nav.value) ?? [];

        return (
          <Link
            key={strategy.port_id}
            href={`/backtest/strategy_list/${strategy.port_id}`}
            className="group relative grid gap-5 border-b border-edge px-5 py-5 transition-colors last:border-b-0 hover:bg-raised/55 md:px-6 xl:grid-cols-[minmax(220px,1.3fr)_minmax(260px,1fr)_170px_minmax(260px,1fr)_28px] xl:items-center"
          >
            <span
              aria-hidden
              className="absolute bottom-3 left-0 top-3 w-px origin-center scale-y-0 bg-gradient-to-b from-primary-400 to-secondary-400 transition-transform group-hover:scale-y-100"
            />
            <div className="min-w-0">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <span className="font-semibold tracking-[-0.015em] text-ink">
                  {strategy.port_name}
                </span>
                {strategy.status === "active" && (
                  <span className="badge-success font-mono text-[9px] tracking-[0.1em]">
                    TRACKING
                  </span>
                )}
                <span className="badge-neutral font-mono text-[9px] tracking-[0.08em] text-warning">
                  UNVERIFIED
                </span>
              </div>
              <p className="truncate text-xs text-ink-muted">
                {strategy.strategy_name}
              </p>
              <p className="mt-3 flex items-center gap-1.5 font-mono text-[10px] text-ink-muted">
                <CalendarRange size={12} aria-hidden />
                저장 {formatDate(strategy.created_at)}
              </p>
            </div>

            <dl className="grid grid-cols-3 overflow-hidden rounded-xl border border-edge bg-canvas/25">
              <div className="border-r border-edge px-3 py-3">
                <dt className="text-[10px] uppercase tracking-wider text-ink-muted">CAGR</dt>
                <dd
                  className={
                    strategy.ann_ret >= 0
                      ? "metric-positive mt-1 text-sm"
                      : "metric-negative mt-1 text-sm"
                  }
                >
                    {strategy.ann_ret >= 0 ? "+" : ""}
                    {strategy.ann_ret}%
                </dd>
              </div>
              <div className="border-r border-edge px-3 py-3">
                <dt className="text-[10px] uppercase tracking-wider text-ink-muted">Vol</dt>
                <dd className="num mt-1 text-sm font-medium text-ink-secondary">{strategy.ann_vol}%</dd>
              </div>
              <div className="px-3 py-3">
                <dt className="text-[10px] uppercase tracking-wider text-ink-muted">Sharpe</dt>
                <dd className="num mt-1 text-sm font-medium text-ink-secondary">{strategy.sharpe}</dd>
              </div>
            </dl>

            <div className="flex min-h-16 items-center gap-3 xl:flex-col xl:justify-center xl:gap-1">
              <SparklineChart
                data={navValues}
                width={132}
                height={48}
                color="var(--chart-1)"
              />
              <LiveBadge
                portId={strategy.port_id}
                showSparkline
                sparkWidth={70}
                sparkHeight={20}
              />
            </div>

            <dl className="grid gap-2 text-[11px] sm:grid-cols-2 xl:grid-cols-1">
              <div className="flex justify-between gap-3">
                <dt className="text-ink-muted">백테스트 구간</dt>
                <dd className="num text-right text-ink-secondary">
                  {strategy.bt_start ?? "—"} → {strategy.bt_end ?? "—"}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-ink-muted">산출 전제</dt>
                <dd className="text-right text-ink-secondary">
                  {strategy.benchmark ?? "BM 미기록"} · {strategy.currency ?? "통화 미기록"} · {strategy.cost_bps ?? "—"}bps
                </dd>
              </div>
            </dl>

            <ArrowUpRight
              size={18}
              aria-hidden
              className="hidden text-ink-muted transition-all group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-primary-300 xl:block"
            />
          </Link>
        );
      })}
    </div>
  );
};

export default Contents;
