"use client";

import React, { useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import {
  InsightFlowTopRow,
  useFetchInsightFlowsTopQuery,
  useFetchMetaDataQuery,
} from "@/state/api";
import Card from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";
import { fmtEok, fmtPct, MarketBadge, signClass } from "@/app/insight/format";

/** Dashboard card: foreign investors' top-5 net buys over the last week. */
const FlowsTopCard: React.FC = () => {
  const router = useRouter();
  const { data, isLoading, error, refetch } = useFetchInsightFlowsTopQuery({
    window: "1w",
    investor: "frgn",
  });

  // Insight rows only carry tickers; resolve meta_id via the cached meta list.
  const { data: metaData } = useFetchMetaDataQuery({});
  const tickerToMetaId = useMemo(() => {
    const map = new Map<string, number>();
    const rows =
      (metaData as { ticker: string; meta_id: number }[] | undefined) ?? [];
    for (const row of rows) map.set(row.ticker, row.meta_id);
    return map;
  }, [metaData]);

  const goToStock = (row: InsightFlowTopRow) => {
    const metaId = tickerToMetaId.get(row.ticker);
    if (metaId !== undefined) {
      router.push(`/stock/${metaId}`);
    } else {
      router.push(`/stocksearch?q=${encodeURIComponent(row.name)}`);
    }
  };

  const rows = (data?.buys ?? []).slice(0, 5);

  return (
    <Card
      title="외국인 순매수 Top 5"
      action={
        <div className="flex items-center gap-3">
          {data?.as_of && (
            <span className="text-xs text-ink-muted num">1W · {data.as_of}</span>
          )}
          <Link
            href="/insight"
            className="text-xs font-medium text-ink-muted hover:text-ink transition-colors"
          >
            더 보기 →
          </Link>
        </div>
      }
    >
      {error ? (
        <ErrorState message="Failed to load top flows" onRetry={refetch} />
      ) : isLoading || !data ? (
        <LoadingState label="수급 데이터를 불러오는 중..." />
      ) : rows.length === 0 ? (
        <EmptyState title="No data" />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="table-header">
                <th className="py-2.5 px-3 text-left rounded-l-lg">#</th>
                <th className="py-2.5 px-3 text-left">Name</th>
                <th className="py-2.5 px-3 text-left">Mkt</th>
                <th className="py-2.5 px-3 text-right">Net</th>
                <th className="py-2.5 px-3 text-right rounded-r-lg">Chg</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={`${row.rank}-${row.ticker}`}
                  className="table-row cursor-pointer"
                  onClick={() => goToStock(row)}
                >
                  <td className="table-cell num text-ink-muted">{row.rank}</td>
                  <td className="table-cell">
                    <span className="font-medium text-ink">{row.name}</span>
                    <span className="ml-1.5 text-xs text-ink-muted num">
                      {row.ticker}
                    </span>
                  </td>
                  <td className="table-cell">
                    <MarketBadge market={row.market} />
                  </td>
                  <td className="table-cell text-right">
                    <span className={signClass(row.net_value)}>
                      {fmtEok(row.net_value)}
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
        </div>
      )}
    </Card>
  );
};

export default FlowsTopCard;
