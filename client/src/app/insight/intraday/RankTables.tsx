"use client";

import React, { useMemo } from "react";
import Link from "next/link";
import { IntradayStockRow, useFetchMetaDataQuery } from "@/state/api";
import { fmtPct, signClass } from "@/app/insight/format";

const fmtValue = (v?: number | null) =>
  v == null ? "—" : `${(v / 1e8).toLocaleString(undefined, { maximumFractionDigits: 0 })}억`;

const StockTable = ({
  title,
  rows,
  tickerToMetaId,
}: {
  title: string;
  rows: IntradayStockRow[];
  tickerToMetaId: Map<string, number>;
}) => (
  <div className="card">
    <h4 className="text-base font-semibold text-ink mb-4">{title}</h4>
    <table className="w-full text-sm">
      <thead>
        <tr className="table-header">
          <th className="py-2 px-3 text-left rounded-l-lg">종목</th>
          <th className="py-2 px-3 text-right">현재가</th>
          <th className="py-2 px-3 text-right">등락률</th>
          <th className="py-2 px-3 text-right rounded-r-lg">거래대금</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => {
          // top_value/top_movers 행은 ticker만 갖는다 — 메타 목록에서 meta_id를
          // 찾지 못하면 종목 검색으로 폴백한다 (FlowsTopCard/SignalsSection과 동일 규약).
          const metaId = tickerToMetaId.get(r.ticker);
          const href =
            metaId !== undefined
              ? `/stock/${metaId}`
              : `/stocksearch?q=${encodeURIComponent(r.name || r.ticker)}`;
          return (
            <tr key={r.ticker} className="table-row">
              <td className="table-cell">
                <Link href={href} className="hover:underline">
                  {r.name || r.ticker}
                </Link>
              </td>
              <td className="table-cell text-right num">
                {r.close == null ? "—" : r.close.toLocaleString()}
              </td>
              <td className={`table-cell text-right num ${signClass(r.chg_pct)}`}>
                {fmtPct(r.chg_pct)}
              </td>
              <td className="table-cell text-right num text-ink-muted">{fmtValue(r.value)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  </div>
);

/** 거래대금·급등락 순위 블록. */
const RankTables = ({
  topValue,
  up,
  down,
}: {
  topValue: IntradayStockRow[];
  up: IntradayStockRow[];
  down: IntradayStockRow[];
}) => {
  // Insight 순위 행은 ticker만 갖는다 — 메타 목록에서 meta_id를 조회한다.
  const { data: metaData } = useFetchMetaDataQuery({});
  const tickerToMetaId = useMemo(() => {
    const map = new Map<string, number>();
    const metaRows =
      (metaData as { ticker: string; meta_id: number }[] | undefined) ?? [];
    for (const row of metaRows) map.set(row.ticker, row.meta_id);
    return map;
  }, [metaData]);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <StockTable title="거래대금 TOP 10" rows={topValue} tickerToMetaId={tickerToMetaId} />
      <StockTable title="급등 TOP 10" rows={up} tickerToMetaId={tickerToMetaId} />
      <StockTable title="급락 TOP 10" rows={down} tickerToMetaId={tickerToMetaId} />
    </div>
  );
};

export default RankTables;
