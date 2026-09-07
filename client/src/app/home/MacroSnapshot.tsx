"use client";

import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { useFetchRegimeKrQuery } from "@/state/api";
import styles from "./marketBriefing.module.css";

const indicators = [
  { key: "usdkrw", label: "달러 / 원", unit: "원", digits: 1 },
  { key: "base_rate", label: "한국 기준금리", unit: "%", digits: 2 },
];

export default function MacroSnapshot() {
  const { data, isLoading, error, refetch } = useFetchRegimeKrQuery(undefined, {
    pollingInterval: 300_000,
    refetchOnMountOrArgChange: 300,
    refetchOnFocus: true,
    refetchOnReconnect: true,
  });
  return (
    <div className={styles.quotes}>
      {indicators.map((indicator) => {
        const series = data?.[indicator.key];
        const latest = series?.latest;
        return (
          <div className={styles.quote} key={indicator.key}>
            <Link href="/regime?country=kr" className={styles.quoteLabel}>
              {indicator.label}
              <ArrowUpRight size={14} aria-hidden />
            </Link>
            <p className={styles.quoteValue}>
              {latest != null && Number.isFinite(latest)
                ? latest.toLocaleString("ko-KR", {
                    minimumFractionDigits: indicator.digits,
                    maximumFractionDigits: indicator.digits,
                  })
                : "—"}
              <span>{indicator.unit}</span>
            </p>
            {error ? (
              <button
                type="button"
                onClick={refetch}
                className={styles.quoteDate}
              >
                불러오기 실패 · 다시 시도
              </button>
            ) : (
              <p className={styles.quoteDate}>
                {isLoading
                  ? "관측값 불러오는 중…"
                  : latest == null
                    ? "관측값 미확인"
                    : `${series?.as_of ? `${series.as_of} 관측` : "기준일 미확인"} · ECOS`}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
