import React from "react";
import Link from "next/link";
import { IntradayMarketResponse } from "@/state/api";
import { fmtPct, signClass } from "@/app/insight/format";
import EmptyState from "@/components/ui/EmptyState";

/** 내 종목(관심·보유 KR) 장중 현황 — 보유·관심 통합, 중복 티커는 보유 우선,
 *  등락률 내림차순 정렬 (null chg_pct는 맨 뒤). */
const MyIntraday = ({ my }: { my: NonNullable<IntradayMarketResponse["my"]> }) => {
  const holdingTickers = new Set(my.holdings.map((r) => r.ticker));
  const rows = [
    ...my.holdings.map((r) => ({ ...r, kind: "보유" as const })),
    ...my.watchlist
      .filter((r) => !holdingTickers.has(r.ticker))
      .map((r) => ({ ...r, kind: "관심" as const })),
  ].sort((a, b) => {
    if (a.chg_pct == null && b.chg_pct == null) return 0;
    if (a.chg_pct == null) return 1;
    if (b.chg_pct == null) return -1;
    return b.chg_pct - a.chg_pct;
  });

  return (
    <div className="card">
      <h4 className="text-base font-semibold text-ink mb-4">My Stocks · Intraday</h4>
      {rows.length === 0 ? (
        <EmptyState title="KR 관심·보유 종목 없음" hint="관심 종목을 등록하면 장중 현황이 표시됩니다" />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {rows.map((r) => (
            <Link
              key={r.ticker}
              href={r.meta_id != null ? `/stock/${r.meta_id}` : `/stocksearch?q=${encodeURIComponent(r.name || r.ticker)}`}
              className="flex items-center justify-between rounded-lg border border-edge px-3 py-2 hover:bg-raised transition-colors"
            >
              <span className="text-sm text-ink truncate">
                {r.name || r.ticker}
                <span className="ml-1.5 text-[10px] text-ink-muted">{r.kind}</span>
              </span>
              <span className={`num text-sm font-semibold ${signClass(r.chg_pct)}`}>
                {fmtPct(r.chg_pct)}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
};

export default MyIntraday;
