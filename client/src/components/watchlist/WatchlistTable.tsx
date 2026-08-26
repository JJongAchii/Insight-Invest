"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { Pencil, X } from "lucide-react";

import {
  useRemoveFromWatchlistMutation,
  WatchlistItem,
} from "@/state/api";
import { fmtEok, fmtPct, signClass } from "@/app/insight/format";
import { formatDate, formatPrice } from "@/lib/market";
import WatchlistThesisEditor from "./WatchlistThesisEditor";

interface WatchlistTableProps {
  items: WatchlistItem[];
  /** Show the "Added" date column (default true). */
  showAdded?: boolean;
  /**
   * KR 장중 등락률 오버라이드 — meta_id → intraday chg_pct. 값이 있는 KR 행에
   * 한해 Chg 셀을 🔴 접두 장중 값으로 교체한다 (홈 대시보드 전용, 스펙 D4).
   */
  liveChg?: Map<number, number>;
}

/**
 * Shared watchlist table (rows → /stock/{meta_id}, remove button).
 * Used by the stock search page and the home dashboard.
 */
const WatchlistTable: React.FC<WatchlistTableProps> = ({
  items,
  showAdded = true,
  liveChg,
}) => {
  const router = useRouter();
  const [editing, setEditing] = useState<WatchlistItem | null>(null);
  const [removeFromWatchlist] = useRemoveFromWatchlistMutation();

  const handleRemove = (e: React.MouseEvent, item: WatchlistItem) => {
    e.stopPropagation();
    removeFromWatchlist(item.meta_id);
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="table-header">
            <th className="py-2.5 px-3 text-left rounded-l-lg">종목·논거</th>
            <th className="py-2.5 px-3 text-right">가격</th>
            <th className="py-2.5 px-3 text-right">등락</th>
            <th className="py-2.5 px-3 text-right">외국인 20D</th>
            <th className="py-2.5 px-3 text-right">기관 20D</th>
            {showAdded && <th className="py-2.5 px-3 text-right">추가일</th>}
            <th className="py-2.5 px-3 text-right rounded-r-lg" />
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const isKr = item.iso_code === "KR";
            const isKrEtf = isKr && item.security_type?.toUpperCase() === "ETF";
            const live = isKr ? liveChg?.get(item.meta_id) : undefined;
            return (
              <tr
                key={item.meta_id}
                className="table-row cursor-pointer"
                onClick={() => router.push(`/stock/${item.meta_id}`)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    router.push(`/stock/${item.meta_id}`);
                  }
                }}
                tabIndex={0}
                role="button"
              >
                <td className="table-cell">
                  <span className="font-medium text-ink">
                    {item.name ?? item.ticker}
                  </span>
                  <span className="ml-1.5 text-xs text-ink-muted num">
                    {item.ticker}
                  </span>
                  <p className="mt-1 max-w-[260px] truncate text-xs text-ink-secondary">
                    {item.thesis || "관심 논거를 기록해 두세요"}
                  </p>
                  {item.review_date && (
                    <p className="mt-1 text-xs text-ink-muted">검토 {formatDate(item.review_date)}</p>
                  )}
                </td>
                <td className="table-cell text-right">
                  <span className="num text-ink">
                    {formatPrice(item.latest_price, item.iso_code)}
                  </span>
                </td>
                <td className="table-cell text-right">
                  <span className={signClass(live ?? item.chg_pct)}>
                    {live != null ? `🔴 ${fmtPct(live)}` : fmtPct(item.chg_pct)}
                  </span>
                </td>
                <td className="table-cell text-right">
                  <span
                    className={isKrEtf ? "text-ink-muted" : signClass(item.frgn_net_20d)}
                    title={isKrEtf ? "KR ETF에는 외국인 20일 수급 데이터가 제공되지 않습니다." : undefined}
                  >
                    {isKrEtf ? "N/A" : fmtEok(item.frgn_net_20d)}
                  </span>
                </td>
                <td className="table-cell text-right">
                  <span
                    className={isKrEtf ? "text-ink-muted" : signClass(item.inst_net_20d)}
                    title={isKrEtf ? "KR ETF에는 기관 20일 수급 데이터가 제공되지 않습니다." : undefined}
                  >
                    {isKrEtf ? "N/A" : fmtEok(item.inst_net_20d)}
                  </span>
                </td>
                {showAdded && (
                  <td className="table-cell text-right">
                    <span className="num text-ink-muted text-xs">
                      {formatDate(item.added_at)}
                    </span>
                  </td>
                )}
                <td className="table-cell text-right">
                  <div className="flex justify-end gap-1">
                    <button
                      onClick={(event) => { event.stopPropagation(); setEditing(item); }}
                      aria-label={`${item.name ?? item.ticker} 관심 논거 편집`}
                      className="p-1.5 rounded-lg text-ink-muted hover:text-primary-400 hover:bg-raised"
                    >
                      <Pencil size={14} aria-hidden />
                    </button>
                    <button
                      onClick={(e) => handleRemove(e, item)}
                      aria-label={`${item.name ?? item.ticker} 관심종목에서 제거`}
                      className="p-1.5 rounded-lg text-ink-muted hover:text-losses hover:bg-raised transition-colors"
                    >
                      <X size={14} aria-hidden />
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {editing && <WatchlistThesisEditor item={editing} onClose={() => setEditing(null)} />}
    </div>
  );
};

export default WatchlistTable;
