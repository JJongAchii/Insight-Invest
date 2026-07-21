"use client";

import React from "react";
import { Star } from "lucide-react";
import {
  useAddToWatchlistMutation,
  useFetchWatchlistQuery,
  useRemoveFromWatchlistMutation,
} from "@/state/api";

interface WatchlistStarProps {
  metaId: number;
  /** Icon size in px; defaults to 20. */
  size?: number;
  className?: string;
}

/**
 * Watchlist toggle star. Membership is derived from the cached /watchlist
 * query ("Watchlist" tag), so every star on screen stays in sync after a
 * POST/DELETE invalidation.
 */
const WatchlistStar: React.FC<WatchlistStarProps> = ({
  metaId,
  size = 20,
  className = "",
}) => {
  const { data: watchlist } = useFetchWatchlistQuery();
  const [addToWatchlist, { isLoading: adding }] = useAddToWatchlistMutation();
  const [removeFromWatchlist, { isLoading: removing }] =
    useRemoveFromWatchlistMutation();

  const inWatchlist =
    watchlist?.items?.some((item) => item.meta_id === metaId) ?? false;
  const busy = adding || removing;

  const handleToggle = (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    if (busy) return;
    if (inWatchlist) {
      removeFromWatchlist(metaId);
    } else {
      addToWatchlist({ meta_id: metaId });
    }
  };

  return (
    <button
      type="button"
      onClick={handleToggle}
      disabled={busy}
      aria-pressed={inWatchlist}
      aria-label={inWatchlist ? "관심종목에서 제거" : "관심종목에 추가"}
      title={inWatchlist ? "관심종목에서 제거" : "관심종목에 추가"}
      className={`p-2 rounded-lg hover:bg-raised transition-colors disabled:opacity-50 ${
        inWatchlist ? "text-amber-400" : "text-ink-muted hover:text-amber-400"
      } ${className}`.trim()}
    >
      <Star
        size={size}
        fill={inWatchlist ? "currentColor" : "none"}
        aria-hidden
      />
    </button>
  );
};

export default WatchlistStar;
