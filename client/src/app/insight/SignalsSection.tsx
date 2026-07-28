"use client";

import React, { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  InsightInvestor,
  InsightSignalRow,
  InsightSignalType,
  SignalStudyRow,
  SignalStudyType,
  useFetchInsightSignalsQuery,
  useFetchInsightSignalStudyQuery,
  useFetchMetaDataQuery,
} from "@/state/api";
import Card from "@/components/ui/Card";
import InfoTip from "@/components/ui/InfoTip";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";
import EmptyState from "@/components/ui/EmptyState";
import {
  fmtEok,
  fmtJo,
  fmtPct,
  MarketBadge,
  Segmented,
  signClass,
} from "./format";

const MAX_ROWS = 30;

const TYPE_OPTIONS: { id: InsightSignalType; label: string }[] = [
  { id: "streak", label: "Streak" },
  { id: "intensity", label: "Intensity" },
  { id: "divergence", label: "Divergence" },
];

const INVESTOR_OPTIONS: { id: InsightInvestor; label: string }[] = [
  { id: "frgn", label: "Foreign" },
  { id: "inst", label: "Institution" },
];

const HELP_KEYS: Record<InsightSignalType, string> = {
  streak: "signal.streak",
  intensity: "signal.intensity",
  divergence: "signal.divergence",
};

const CAPTIONS: Record<InsightSignalType, string> = {
  streak: "동일 투자자가 여러 거래일 연속으로 순매수/순매도 중인 종목",
  intensity: "최근 20일 순매수 금액을 시가총액으로 나눈 수급 강도 상위 종목",
  divergence:
    "매집형: 주가는 내렸지만 수급이 유입 · 이탈형: 주가는 올랐지만 수급이 이탈",
};

/** Signal-tab → event-study signal_type. */
const STUDY_TYPE: Record<InsightSignalType, SignalStudyType> = {
  streak: "frgn_streak10",
  intensity: "high_intensity",
  divergence: "bull_divergence",
};

const STUDY_HORIZONS: (5 | 20 | 60)[] = [5, 20, 60];

/**
 * Honest historical track record: forward excess return vs the equal-weight
 * cross-sectional mean at 5/20/60d. The absolute medians are negative even for
 * the unconditional baseline (the benchmark is a mean, returns are right-skewed),
 * so the only readable number is the delta vs baseline — that's what's emphasized.
 */
const TrackRecordStrip: React.FC<{
  rows: SignalStudyRow[];
  baseline: SignalStudyRow[];
}> = ({ rows, baseline }) => {
  const byHorizon = new Map(rows.map((r) => [r.horizon, r]));
  const baseByHorizon = new Map(baseline.map((r) => [r.horizon, r]));
  const h20 = byHorizon.get(20);
  const b20 = baseByHorizon.get(20);
  // baseline 행이 없는 구 parquet에서는 경고를 띄우지 않는다 — 비교 근거가 없다.
  const showWarning =
    h20 !== undefined &&
    b20 !== undefined &&
    h20.median_excess < b20.median_excess;
  // 경고 트리거(median_excess)와 배지에 보여줄 근거를 일치시킨다 — hit_rate만
  // 보여주면 median은 기준선보다 낮은데 hit_rate는 높은 경우 경고 문구가
  // 스스로 모순될 수 있다.
  const delta20 =
    h20 !== undefined && b20 !== undefined
      ? h20.median_excess - b20.median_excess
      : null;

  return (
    <div className="rounded-xl border border-edge bg-raised p-3 flex flex-col gap-2.5">
      <div className="flex items-center gap-1.5">
        <span className="text-xs font-semibold text-ink-secondary">
          역사적 성과 ·{" "}
          {b20 ? "동일가중 평균 대비" : "구 벤치마크 기준 · 집계 갱신 대기"}{" "}
          (2016~)
        </span>
        <InfoTip helpKey="signal.study" />
      </div>
      <div className="grid grid-cols-3 gap-2">
        {STUDY_HORIZONS.map((h) => {
          const r = byHorizon.get(h);
          const b = baseByHorizon.get(h);
          const delta =
            r !== undefined && b !== undefined
              ? r.median_excess - b.median_excess
              : null;
          return (
            <div
              key={h}
              className="rounded-lg border border-edge bg-surface px-3 py-2"
            >
              <p className="text-[11px] text-ink-muted">{h}일 후 초과수익</p>
              {r ? (
                <>
                  {delta !== null && (
                    <p className="mt-0.5">
                      <span className="text-[11px] text-ink-muted">
                        기준선 대비{" "}
                      </span>
                      <span className={`${signClass(delta)} font-semibold num`}>
                        {delta >= 0 ? "+" : ""}
                        {delta.toFixed(2)}%p
                      </span>
                    </p>
                  )}
                  <p className="text-[11px] text-ink-muted num mt-0.5">
                    중앙값 {fmtPct(r.median_excess)} · 히트율{" "}
                    {r.hit_rate.toFixed(0)}%
                  </p>
                  <p className="text-[11px] text-ink-muted num mt-0.5">
                    N={r.n_events.toLocaleString()}건
                  </p>
                </>
              ) : (
                <p className="mt-0.5 num text-ink-muted">—</p>
              )}
            </div>
          );
        })}
      </div>
      {showWarning && h20 && b20 && delta20 !== null && (
        <p className="text-[11px] text-losses">
          ⚠ 이 신호는 아무 종목이나 골랐을 때보다 20일 성과가 낮았습니다 —
          중앙값 기준선 대비 {delta20 >= 0 ? "+" : ""}
          {delta20.toFixed(2)}%p, 승률 {h20.hit_rate.toFixed(1)}% vs 기준선{" "}
          {b20.hit_rate.toFixed(1)}%.
        </p>
      )}
    </div>
  );
};

const NameCell: React.FC<{ row: InsightSignalRow }> = ({ row }) => (
  <td className="table-cell">
    <span className="font-medium text-ink">{row.name}</span>
    <span className="ml-1.5 text-xs text-ink-muted num">{row.ticker}</span>
  </td>
);

/** Flow signal tables: consecutive-day streaks, 20d intensity, price/flow divergence. */
const SignalsSection: React.FC = () => {
  const router = useRouter();
  const [type, setType] = useState<InsightSignalType>("streak");
  const [investor, setInvestor] = useState<InsightInvestor>("frgn");

  const { data, isLoading, error, refetch } = useFetchInsightSignalsQuery({
    type,
    investor,
  });

  const rows = (
    type === "divergence"
      ? (data?.rows ?? []).filter((r) => r.divergence !== null)
      : (data?.rows ?? [])
  ).slice(0, MAX_ROWS);

  // Event-study track record for the active signal tab (one fetch, all types).
  const { data: studyData } = useFetchInsightSignalStudyQuery();
  const studyRows = useMemo(
    () =>
      (studyData?.rows ?? []).filter(
        (r) => r.signal_type === STUDY_TYPE[type]
      ),
    [studyData, type]
  );
  // 비교 기준 — 조건 없는 유동성 전 종목-일. 구 parquet에는 없을 수 있다.
  const baselineRows = useMemo(
    () => (studyData?.rows ?? []).filter((r) => r.signal_type === "baseline"),
    [studyData]
  );

  // Signal rows only carry tickers; resolve meta_id via the cached meta list.
  const { data: metaData } = useFetchMetaDataQuery({});
  const tickerToMetaId = useMemo(() => {
    const map = new Map<string, number>();
    const metaRows =
      (metaData as { ticker: string; meta_id: number }[] | undefined) ?? [];
    for (const row of metaRows) map.set(row.ticker, row.meta_id);
    return map;
  }, [metaData]);

  const goToStock = (row: InsightSignalRow) => {
    const metaId = tickerToMetaId.get(row.ticker);
    if (metaId !== undefined) {
      router.push(`/stock/${metaId}`);
    } else {
      router.push(`/stocksearch?q=${encodeURIComponent(row.name)}`);
    }
  };

  return (
    <Card
      title="Flow Signals"
      action={
        <div className="flex flex-wrap items-center gap-3">
          {data?.as_of && (
            <span className="text-xs text-ink-muted num">
              as of {data.as_of}
            </span>
          )}
          <Segmented
            options={INVESTOR_OPTIONS}
            value={investor}
            onChange={setInvestor}
          />
          <Segmented options={TYPE_OPTIONS} value={type} onChange={setType} />
        </div>
      }
    >
      {error ? (
        <ErrorState message="Failed to load flow signals" onRetry={refetch} />
      ) : isLoading || !data ? (
        <LoadingState label="Loading flow signals..." />
      ) : rows.length === 0 ? (
        <EmptyState
          title="No signals"
          hint="조건을 충족하는 종목이 없습니다"
        />
      ) : (
        <div className="flex flex-col gap-3">
          {investor === "frgn" && studyRows.length > 0 && (
            <TrackRecordStrip rows={studyRows} baseline={baselineRows} />
          )}
          <p className="text-xs text-ink-muted flex items-center gap-1.5">
            <span>{CAPTIONS[type]}</span>
            <InfoTip helpKey={HELP_KEYS[type]} />
          </p>
          <div className="overflow-x-auto">
            {type === "streak" && (
              <table className="w-full text-sm">
                <thead>
                  <tr className="table-header">
                    <th className="py-2.5 px-3 text-left rounded-l-lg">Name</th>
                    <th className="py-2.5 px-3 text-left">Mkt</th>
                    <th className="py-2.5 px-3 text-right">Streak</th>
                    <th className="py-2.5 px-3 text-right">Net 20D</th>
                    <th className="py-2.5 px-3 text-right rounded-r-lg">Chg</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr
                      key={row.ticker}
                      className="table-row cursor-pointer"
                      onClick={() => goToStock(row)}
                    >
                      <NameCell row={row} />
                      <td className="table-cell">
                        <MarketBadge market={row.market} />
                      </td>
                      <td className="table-cell text-right">
                        <span className={signClass(row.streak)}>
                          {row.streak > 0
                            ? `+${row.streak}일 연속 순매수`
                            : `${row.streak}일 연속 순매도`}
                        </span>
                      </td>
                      <td className="table-cell text-right">
                        <span className={signClass(row.net_20d)}>
                          {fmtEok(row.net_20d)}
                        </span>
                      </td>
                      <td className="table-cell text-right">
                        <span className={signClass(row.chg_pct)}>
                          {fmtPct(row.chg_pct)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {type === "intensity" && (
              <table className="w-full text-sm">
                <thead>
                  <tr className="table-header">
                    <th className="py-2.5 px-3 text-left rounded-l-lg">Name</th>
                    <th className="py-2.5 px-3 text-left">Mkt</th>
                    <th className="py-2.5 px-3 text-right">Intensity 20D</th>
                    <th className="py-2.5 px-3 text-right">Net 20D</th>
                    <th className="py-2.5 px-3 text-right">Mktcap</th>
                    <th className="py-2.5 px-3 text-right rounded-r-lg">Chg</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr
                      key={row.ticker}
                      className="table-row cursor-pointer"
                      onClick={() => goToStock(row)}
                    >
                      <NameCell row={row} />
                      <td className="table-cell">
                        <MarketBadge market={row.market} />
                      </td>
                      <td className="table-cell text-right">
                        <span className={signClass(row.intensity_20d)}>
                          {fmtPct(row.intensity_20d)}
                        </span>
                      </td>
                      <td className="table-cell text-right">
                        <span className={signClass(row.net_20d)}>
                          {fmtEok(row.net_20d)}
                        </span>
                      </td>
                      <td className="table-cell text-right">
                        <span className="num text-ink-secondary">
                          {fmtJo(row.mktcap)}
                        </span>
                      </td>
                      <td className="table-cell text-right">
                        <span className={signClass(row.chg_pct)}>
                          {fmtPct(row.chg_pct)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {type === "divergence" && (
              <table className="w-full text-sm">
                <thead>
                  <tr className="table-header">
                    <th className="py-2.5 px-3 text-left rounded-l-lg">Name</th>
                    <th className="py-2.5 px-3 text-left">Mkt</th>
                    <th className="py-2.5 px-3 text-left">Signal</th>
                    <th className="py-2.5 px-3 text-right">Ret 20D</th>
                    <th className="py-2.5 px-3 text-right">Intensity 20D</th>
                    <th className="py-2.5 px-3 text-right rounded-r-lg">
                      Net 20D
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr
                      key={row.ticker}
                      className="table-row cursor-pointer"
                      onClick={() => goToStock(row)}
                    >
                      <NameCell row={row} />
                      <td className="table-cell">
                        <MarketBadge market={row.market} />
                      </td>
                      <td className="table-cell">
                        {row.divergence === "bull" ? (
                          <span className="badge-success">매집형</span>
                        ) : (
                          <span className="badge-danger">이탈형</span>
                        )}
                      </td>
                      <td className="table-cell text-right">
                        <span className={signClass(row.ret_20d)}>
                          {fmtPct(row.ret_20d)}
                        </span>
                      </td>
                      <td className="table-cell text-right">
                        <span className={signClass(row.intensity_20d)}>
                          {fmtPct(row.intensity_20d)}
                        </span>
                      </td>
                      <td className="table-cell text-right">
                        <span className={signClass(row.net_20d)}>
                          {fmtEok(row.net_20d)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </Card>
  );
};

export default SignalsSection;
