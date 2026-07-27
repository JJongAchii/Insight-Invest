"use client";

import React, { useMemo } from "react";
import { FactorName, useFetchInsightFactorsQuery } from "@/state/api";
import Card from "@/components/ui/Card";
import InfoTip from "@/components/ui/InfoTip";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";
import EmptyState from "@/components/ui/EmptyState";
import TimeSeriesChart, {
  TimeSeriesSeries,
} from "@/components/charts/TimeSeriesChart";
import { FACTOR_COLORS, FACTOR_NAMES_KR, FACTOR_ORDER } from "@/content/factors";
import { fmtPct, signClass } from "./format";

/** Long-short factor spread lens: current returns table + rebased rotation chart. */
const FactorSection: React.FC = () => {
  const { data, isLoading, error, refetch } = useFetchInsightFactorsQuery();

  const byFactor = useMemo(
    () => new Map((data?.current ?? []).map((c) => [c.factor, c])),
    [data]
  );

  // Pivot history to {date, [factor]: cum_index rebased to 100 at window start}.
  const chartData = useMemo(() => {
    const hist = data?.history ?? [];
    if (hist.length === 0) return [];
    const base = new Map<FactorName, number>();
    const byDate = new Map<string, Record<string, number | null>>();
    const sorted = hist.slice().sort((a, b) => a.date.localeCompare(b.date));
    for (const r of sorted) {
      if (!base.has(r.factor) && r.cum_index) base.set(r.factor, r.cum_index);
      const b = base.get(r.factor);
      if (!b) continue;
      const g = byDate.get(r.date) ?? {};
      g[r.factor] = (r.cum_index / b) * 100;
      byDate.set(r.date, g);
    }
    return Array.from(byDate.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, g]) => ({ date, ...g }));
  }, [data]);

  const series: TimeSeriesSeries[] = FACTOR_ORDER.map((f) => ({
    key: f,
    name: FACTOR_NAMES_KR[f],
    color: FACTOR_COLORS[f],
  }));

  // Korean-market character read off the YTD factor spreads.
  const captions = useMemo(() => {
    const out: string[] = [];
    const mom = byFactor.get("momentum");
    const size = byFactor.get("size");
    const lowvol = byFactor.get("lowvol");
    if (mom && mom.ret_ytd < 0) out.push("국내 시장은 모멘텀 역전 특성");
    if (size && size.ret_ytd > 0) out.push("소형주 프리미엄 우위");
    if (lowvol && lowvol.ret_ytd > 0) out.push("저변동 프리미엄 우위");
    return out;
  }, [byFactor]);

  return (
    <Card
      title={
        <span className="inline-flex items-center gap-1.5">
          팩터 렌즈
          <InfoTip helpKey="factor.lens" />
        </span>
      }
      action={
        data?.as_of && (
          <span className="text-xs text-ink-muted num">as of {data.as_of}</span>
        )
      }
    >
      {error ? (
        <ErrorState message="Failed to load factor data" onRetry={refetch} />
      ) : isLoading || !data ? (
        <LoadingState label="Loading factor lens..." />
      ) : data.current.length === 0 ? (
        <EmptyState title="팩터 데이터 수집 중" />
      ) : (
        <div className="flex flex-col gap-6">
          {/* Current factor spread returns */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="table-header">
                  <th className="py-2.5 px-3 text-left rounded-l-lg">팩터</th>
                  <th className="py-2.5 px-3 text-right">1D</th>
                  <th className="py-2.5 px-3 text-right">1W</th>
                  <th className="py-2.5 px-3 text-right">1M</th>
                  <th className="py-2.5 px-3 text-right rounded-r-lg">YTD</th>
                </tr>
              </thead>
              <tbody>
                {FACTOR_ORDER.map((factor) => {
                  const row = byFactor.get(factor);
                  if (!row) return null;
                  return (
                    <tr key={factor} className="table-row">
                      <td className="table-cell">
                        <span className="inline-flex items-center gap-2">
                          <span
                            className="w-2.5 h-2.5 rounded-full shrink-0"
                            style={{ backgroundColor: FACTOR_COLORS[factor] }}
                            aria-hidden
                          />
                          <span className="font-medium text-ink">
                            {FACTOR_NAMES_KR[factor]}
                          </span>
                        </span>
                      </td>
                      <td className="table-cell text-right">
                        <span className={signClass(row.ret_1d)}>
                          {fmtPct(row.ret_1d)}
                        </span>
                      </td>
                      <td className="table-cell text-right">
                        <span className={signClass(row.ret_1w)}>
                          {fmtPct(row.ret_1w)}
                        </span>
                      </td>
                      <td className="table-cell text-right">
                        <span className={signClass(row.ret_1m)}>
                          {fmtPct(row.ret_1m)}
                        </span>
                      </td>
                      <td className="table-cell text-right">
                        <span className={signClass(row.ret_ytd)}>
                          {fmtPct(row.ret_ytd)}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {captions.length > 0 && (
            <p className="text-xs text-ink-muted">{captions.join(" · ")}</p>
          )}

          {/* Factor rotation: rebased cumulative spread index */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm font-medium text-ink-secondary inline-flex items-center gap-1.5">
                팩터 로테이션
                <InfoTip helpKey="factor.rotation" />
              </p>
              <span className="text-xs text-ink-muted">3Y · indexed to 100</span>
            </div>
            {chartData.length === 0 ? (
              <EmptyState title="No factor history" />
            ) : (
              <TimeSeriesChart
                data={chartData}
                series={series}
                height={320}
                yFormatter={(v) => v.toFixed(0)}
                baseline={100}
                showBrush
              />
            )}
          </div>
        </div>
      )}
    </Card>
  );
};

export default FactorSection;
