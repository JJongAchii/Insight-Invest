"use client";

import React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { IoBarChart } from "react-icons/io5";

import {
  useFetchStrategiesQuery,
  useFetchStrategyMonthlyNavQuery,
} from "@/state/api";
import Card from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import LoadingState from "@/components/ui/LoadingState";
import SparklineChart from "@/components/charts/SparklineChart";

interface StrategyRow {
  port_id: number;
  port_name: string;
  strategy_name: string;
  ann_ret: number;
  ann_vol: number;
  sharpe: number;
}

interface StrategyNavRow {
  port_id: number;
  trade_date: string;
  value: number;
}

/** Dashboard card listing saved strategies with key metrics + NAV sparkline. */
const StrategiesCard: React.FC = () => {
  const router = useRouter();
  const { data: strategies, isLoading } = useFetchStrategiesQuery({});
  const { data: monthlyNav } = useFetchStrategyMonthlyNavQuery({});

  const list: StrategyRow[] = strategies ?? [];
  const navRows: StrategyNavRow[] = monthlyNav ?? [];

  return (
    <Card
      title="My Strategies"
      action={
        <Link
          href="/backtest/strategy_list"
          className="text-xs font-medium text-ink-muted hover:text-ink transition-colors"
        >
          모든 전략 →
        </Link>
      }
    >
      {isLoading ? (
        <LoadingState label="전략을 불러오는 중..." />
      ) : list.length === 0 ? (
        <EmptyState
          icon={<IoBarChart className="w-7 h-7" aria-hidden />}
          title="저장된 전략이 없습니다"
          hint={
            <Link
              href="/backtest/simulation"
              className="text-primary-400 hover:underline"
            >
              백테스트를 실행하고 저장하세요 →
            </Link>
          }
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="table-header">
                <th className="py-2.5 px-3 text-left rounded-l-lg">Name</th>
                <th className="py-2.5 px-3 text-right">Ann. Ret</th>
                <th className="py-2.5 px-3 text-right">Sharpe</th>
                <th className="py-2.5 px-3 text-right rounded-r-lg">NAV</th>
              </tr>
            </thead>
            <tbody>
              {list.map((s) => {
                const navValues = navRows
                  .filter((nav) => nav.port_id === s.port_id)
                  .map((nav) => nav.value);
                return (
                  <tr
                    key={s.port_id}
                    className="table-row cursor-pointer"
                    onClick={() =>
                      router.push(`/backtest/strategy_list/${s.port_id}`)
                    }
                  >
                    <td className="table-cell">
                      <span className="font-medium text-ink">{s.port_name}</span>
                      <span className="ml-1.5 text-xs text-ink-muted">
                        {s.strategy_name}
                      </span>
                    </td>
                    <td className="table-cell text-right">
                      <span
                        className={
                          s.ann_ret >= 0 ? "metric-positive" : "metric-negative"
                        }
                      >
                        {s.ann_ret >= 0 ? "+" : ""}
                        {s.ann_ret}%
                      </span>
                    </td>
                    <td className="table-cell text-right">
                      <span className="num text-ink-secondary">{s.sharpe}</span>
                    </td>
                    <td className="table-cell">
                      <div className="flex justify-end">
                        <SparklineChart
                          data={navValues}
                          width={90}
                          height={28}
                          color="var(--chart-1)"
                        />
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
};

export default StrategiesCard;
