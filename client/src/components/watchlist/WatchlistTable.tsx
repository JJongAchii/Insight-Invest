"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { X } from "lucide-react";

import {
  useRemoveFromWatchlistMutation,
  WatchlistItem,
} from "@/state/api";
import { fmtEok, fmtPct, signClass } from "@/app/insight/format";

const fmtPrice = (value: number | null, isKr: boolean): string => {
  if (value === null || Number.isNaN(value)) return "—";
  if (isKr) return `${Math.round(value).toLocaleString()}원`;
  return `$${value.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
};

const fmtAddedAt = (value: string | null): string => {
  if (!value) return "—";
  return value.split("T")[0];
};

interface WatchlistTableProps {
  items: WatchlistItem[];
  /** Show the "Added" date column (default true). */
  showAdded?: boolean;
}

/**
 * Shared watchlist table (rows → /stock/{meta_id}, remove button).
 * Used by the stock search page and the home dashboard.
 */
const WatchlistTable: React.FC<WatchlistTableProps> = ({
  items,
  showAdded = true,
}) => {
  const router = useRouter();
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
            <th className="py-2.5 px-3 text-left rounded-l-lg">Name</th>
            <th className="py-2.5 px-3 text-right">Price</th>
            <th className="py-2.5 px-3 text-right">Chg</th>
            <th className="py-2.5 px-3 text-right">외국인 20D</th>
            <th className="py-2.5 px-3 text-right">기관 20D</th>
            {showAdded && <th className="py-2.5 px-3 text-right">Added</th>}
            <th className="py-2.5 px-3 text-right rounded-r-lg" />
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const isKr = item.iso_code === "KR";
            return (
              <tr
                key={item.meta_id}
                className="table-row cursor-pointer"
                onClick={() => router.push(`/stock/${item.meta_id}`)}
              >
                <td className="table-cell">
                  <span className="font-medium text-ink">
                    {item.name ?? item.ticker}
                  </span>
                  <span className="ml-1.5 text-xs text-ink-muted num">
                    {item.ticker}
                  </span>
                </td>
                <td className="table-cell text-right">
                  <span className="num text-ink">
                    {fmtPrice(item.latest_price, isKr)}
                  </span>
                </td>
                <td className="table-cell text-right">
                  <span className={signClass(item.chg_pct)}>
                    {fmtPct(item.chg_pct)}
                  </span>
                </td>
                <td className="table-cell text-right">
                  <span className={signClass(item.frgn_net_20d)}>
                    {fmtEok(item.frgn_net_20d)}
                  </span>
                </td>
                <td className="table-cell text-right">
                  <span className={signClass(item.inst_net_20d)}>
                    {fmtEok(item.inst_net_20d)}
                  </span>
                </td>
                {showAdded && (
                  <td className="table-cell text-right">
                    <span className="num text-ink-muted text-xs">
                      {fmtAddedAt(item.added_at)}
                    </span>
                  </td>
                )}
                <td className="table-cell text-right">
                  <button
                    onClick={(e) => handleRemove(e, item)}
                    aria-label={`${item.name ?? item.ticker} 관심종목에서 제거`}
                    className="p-1.5 rounded-lg text-ink-muted hover:text-losses
                               hover:bg-raised transition-colors"
                  >
                    <X size={14} aria-hidden />
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export default WatchlistTable;
