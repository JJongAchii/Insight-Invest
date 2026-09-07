"use client";

import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import {
  InsightMarket,
  useFetchInsightIndexQuery,
  useFetchIntradayMarketQuery,
} from "@/state/api";
import { fmtPct, signClass } from "@/app/insight/format";
import styles from "./marketBriefing.module.css";

export default function MarketTiles() {
  const {
    data: indexData,
    isLoading,
    error,
    refetch,
  } = useFetchInsightIndexQuery({ days: 30 });
  const { data: intraday } = useFetchIntradayMarketQuery(undefined, {
    pollingInterval: 5 * 60 * 1000,
    skipPollingIfUnfocused: true,
  });

  return (
    <div className={styles.quotes}>
      {(["KOSPI", "KOSDAQ"] as InsightMarket[]).map((market) => {
        const series = (indexData?.rows ?? [])
          .filter((row) => row.index === market && Number.isFinite(row.close))
          .sort((a, b) => a.date.localeCompare(b.date));
        const last = series.at(-1);
        const previous = series.at(-2);
        const snapshot = intraday?.active
          ? intraday.indices?.find(
              (index) => index.key === market && Number.isFinite(index.level),
            )
          : undefined;
        // A delayed snapshot must not overwrite a more recent settled observation.
        const useSnapshot = Boolean(
          snapshot &&
          intraday?.trade_date &&
          (!last ||
            intraday.trade_date > last.date ||
            (intraday.trade_date === last.date && intraday.is_open)),
        );
        const value = useSnapshot ? snapshot?.level : last?.close;
        const change = useSnapshot
          ? (snapshot?.chg_pct ?? null)
          : last && previous && previous.close !== 0
            ? (last.close / previous.close - 1) * 100
            : null;
        const asOf = useSnapshot ? intraday?.as_of : last?.date;
        const label = useSnapshot
          ? intraday?.is_open
            ? "장중 · 지연 시세"
            : "마감 스냅샷"
          : "정산 종가";
        return (
          <div className={styles.quote} key={market}>
            <Link
              href={`/insight?tab=${useSnapshot ? "intraday" : "settled"}&market=${market}`}
              className={styles.quoteLabel}
            >
              {market}
              <ArrowUpRight size={14} aria-hidden />
            </Link>
            <p className={styles.quoteValue}>
              {value == null
                ? "—"
                : value.toLocaleString("ko-KR", {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: 2,
                  })}
            </p>
            <p className={`${styles.quoteChange} ${signClass(change)}`}>
              {fmtPct(change)} <small>전일 대비</small>
            </p>
            {error && value == null ? (
              <button
                type="button"
                onClick={refetch}
                className={styles.quoteDate}
              >
                불러오기 실패 · 다시 시도
              </button>
            ) : (
              <p className={styles.quoteDate}>
                {isLoading && value == null
                  ? "지수 불러오는 중…"
                  : asOf
                    ? `${asOf.replace("T", " ")} · ${label}`
                    : "관측값 미확인"}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
