"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import {
  InsightInvestor,
  InsightSignalRow,
  InsightSignalType,
  useFetchInsightSignalsQuery,
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

  const goToStock = (row: InsightSignalRow) => {
    router.push(`/stocksearch?q=${encodeURIComponent(row.name)}`);
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
