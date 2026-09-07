"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
  InsightInvestor,
  InsightWindow,
  useFetchInsightFlowsTopQuery,
  useFetchMetaDataQuery,
} from "@/state/api";
import Card from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";
import { fmtEok, fmtPct, signClass } from "@/app/insight/format";

export default function FlowsTopCard() {
  const [investor, setInvestor] = useState<InsightInvestor>("frgn");
  const [window, setWindow] = useState<InsightWindow>("1w");
  const [side, setSide] = useState<"buys" | "sells">("buys");
  const {
    currentData: data,
    isFetching,
    error,
    refetch,
  } = useFetchInsightFlowsTopQuery({ window, investor });
  const { data: metaData } = useFetchMetaDataQuery({});
  const tickerToMetaId = useMemo(() => {
    const map = new Map<string, number>();
    const rows =
      (metaData as
        { ticker: string; meta_id: number; iso_code: string }[] | undefined) ??
      [];
    for (const row of rows)
      if (row.iso_code === "KR") map.set(row.ticker, row.meta_id);
    return map;
  }, [metaData]);
  const rows = (data?.[side] ?? []).slice(0, 5);

  return (
    <Card
      headingLevel={2}
      title="자금은 어디로 움직였나"
      action={
        <Link
          href="/insight?tab=settled&section=flows"
          className="text-xs text-primary-300 hover:underline"
        >
          시장 수급 전체 →
        </Link>
      }
    >
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-xs text-ink-secondary">
          투자자
          <select
            aria-label="수급 투자자"
            className="rounded-lg border border-edge bg-raised px-3 py-2 text-ink"
            value={investor}
            onChange={(event) =>
              setInvestor(event.target.value as InsightInvestor)
            }
          >
            <option value="frgn">외국인</option>
            <option value="inst">기관</option>
          </select>
        </label>
        <label className="flex items-center gap-2 text-xs text-ink-secondary">
          기간
          <select
            aria-label="수급 기간"
            className="rounded-lg border border-edge bg-raised px-3 py-2 text-ink"
            value={window}
            onChange={(event) => setWindow(event.target.value as InsightWindow)}
          >
            <option value="1d">1거래일</option>
            <option value="1w">1주</option>
            <option value="1m">1개월</option>
          </select>
        </label>
        <div className="flex gap-1" aria-label="수급 방향">
          {(
            [
              ["buys", "순매수"],
              ["sells", "순매도"],
            ] as const
          ).map(([key, label]) => (
            <button
              type="button"
              key={key}
              className="filter-chip"
              aria-pressed={side === key}
              onClick={() => setSide(key)}
            >
              {label}
            </button>
          ))}
        </div>
        {data?.as_of && (
          <span className="text-xs text-ink-muted sm:ml-auto">
            {data.as_of} 기준 · 상위 5종목
          </span>
        )}
      </div>
      {error ? (
        <ErrorState
          message="수급 데이터를 불러오지 못했습니다"
          onRetry={refetch}
        />
      ) : !data && isFetching ? (
        <LoadingState label="수급 데이터를 불러오는 중…" />
      ) : rows.length === 0 ? (
        <EmptyState title="해당 조건의 수급 데이터가 없습니다" />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <caption className="sr-only">
              {investor === "frgn" ? "외국인" : "기관"}{" "}
              {side === "buys" ? "순매수" : "순매도"} 상위 종목
            </caption>
            <thead>
              <tr className="table-header">
                <th className="px-2 py-3 text-left">종목</th>
                <th className="px-2 py-3 text-right">순매수액</th>
                <th className="px-2 py-3 text-right">등락률</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const metaId = tickerToMetaId.get(row.ticker);
                return (
                  <tr className="table-row" key={row.ticker}>
                    <td className="px-2 py-3">
                      <Link
                        className="inline-flex flex-col gap-1 hover:text-primary-300"
                        href={
                          metaId === undefined
                            ? `/stocksearch?q=${encodeURIComponent(row.ticker)}`
                            : `/stock/${metaId}`
                        }
                      >
                        <span className="font-medium">{row.name}</span>
                        <span className="text-[11px] text-ink-muted">
                          {row.ticker} · {row.market}
                        </span>
                      </Link>
                    </td>
                    <td
                      className={`whitespace-nowrap px-2 py-3 text-right num ${signClass(row.net_value)}`}
                    >
                      {fmtEok(row.net_value)}
                    </td>
                    <td
                      className={`whitespace-nowrap px-2 py-3 text-right num ${signClass(row.chg_pct)}`}
                    >
                      {fmtPct(row.chg_pct)}
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
}
