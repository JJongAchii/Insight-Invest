"use client";

import { ArrowUpRight, CalendarClock } from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";

import { fmtJo } from "@/app/insight/format";
import {
  fmtFracPct,
  fmtPctVal,
  fmtSignedJo,
  signClassNum,
} from "@/app/portfolio/format";
import EmptyState from "@/components/ui/EmptyState";
import LoadingState from "@/components/ui/LoadingState";
import { useFetchHoldingsQuery, useFetchIntradayMarketQuery } from "@/state/api";

/** 브리핑 직후 총액보다 노출·괴리·다음 검토를 먼저 보여주는 포트폴리오 영향 패널. */
export default function PortfolioCard() {
  const { data, isLoading } = useFetchHoldingsQuery();
  const { data: intraday } = useFetchIntradayMarketQuery(undefined, {
    pollingInterval: 5 * 60 * 1000,
    skipPollingIfUnfocused: true,
  });

  const positions = useMemo(() => data?.positions ?? [], [data?.positions]);
  const summary = data?.summary;

  const topPositions = useMemo(
    () =>
      [...positions]
        .filter((position) => position.weight != null)
        .sort((a, b) => (b.weight ?? 0) - (a.weight ?? 0))
        .slice(0, 3),
    [positions]
  );

  const nextReview = useMemo(
    () =>
      [...positions]
        .filter((position) => position.review_date)
        .sort((a, b) =>
          (a.review_date ?? "").localeCompare(b.review_date ?? "")
        )[0],
    [positions]
  );

  const largestDrift = useMemo(
    () =>
      [...positions]
        .filter((position) => position.drift_pp != null)
        .sort(
          (a, b) => Math.abs(b.drift_pp ?? 0) - Math.abs(a.drift_pp ?? 0)
        )[0],
    [positions]
  );

  const liveChanges = useMemo(() => {
    if (!intraday?.active) return new Map<number, number>();
    const values = new Map<number, number>();
    for (const row of intraday.my?.holdings ?? []) {
      if (row.meta_id != null && row.chg_pct != null) {
        values.set(row.meta_id, row.chg_pct);
      }
    }
    return values;
  }, [intraday]);

  const reviewDate = nextReview?.review_date?.split("-");

  return (
    <section className="mb-8" aria-labelledby="portfolio-impact-title">
      <header className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h2
            id="portfolio-impact-title"
            className="text-lg font-semibold tracking-[-0.02em] text-ink"
          >
            내 포트폴리오 영향
          </h2>
          <p className="mt-1 text-xs text-ink-muted">
            시장 정보보다 내 노출과 목표 예외를 먼저 봅니다.
          </p>
        </div>
        <Link
          href="/portfolio"
          className="flex shrink-0 items-center gap-1 text-xs font-medium text-[color:var(--primary)] transition-colors hover:text-ink"
        >
          포트폴리오 열기 <ArrowUpRight size={13} aria-hidden />
        </Link>
      </header>

      <div className="overflow-hidden rounded-2xl border border-primary-400/20 bg-gradient-to-br from-raised/90 to-surface/85 shadow-[0_18px_50px_rgba(3,5,14,0.20),inset_0_1px_0_rgba(255,255,255,0.03)]">
        {isLoading ? (
          <LoadingState label="포트폴리오 영향을 계산하는 중..." />
        ) : !summary || positions.length === 0 ? (
          <EmptyState
            title="연결된 보유 자산이 없습니다"
            hint={
              <Link href="/portfolio" className="text-[color:var(--primary)] hover:underline">
                포트폴리오에서 자산을 추가하세요 →
              </Link>
            }
          />
        ) : (
          <div className="grid lg:grid-cols-[0.82fr_1.35fr_0.78fr]">
            <div className="p-5 lg:p-6">
              <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-ink-muted">
                {summary.valuation_complete ? "확인된 평가액" : "가격 확인분"}
              </p>
              <div className="mt-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <strong className="font-mono text-2xl font-medium tracking-[-0.035em] text-ink">
                  {summary.priced_positions > 0
                    ? fmtJo(summary.total_value_krw)
                    : "—"}
                </strong>
                <span className={`text-xs ${signClassNum(summary.total_pnl_pct)}`}>
                  {summary.priced_positions > 0
                    ? fmtFracPct(summary.total_pnl_pct)
                    : "—"}
                </span>
              </div>
              <div className="mt-4 flex gap-6 border-t border-edge pt-3 text-xs">
                <div>
                  <span className="block text-[10px] text-ink-muted">누적 손익</span>
                  <strong className={signClassNum(summary.total_pnl_krw)}>
                    {fmtSignedJo(summary.total_pnl_krw)}
                  </strong>
                </div>
                <div>
                  <span className="block text-[10px] text-ink-muted">일간 손익</span>
                  <strong className={signClassNum(summary.day_pnl_krw)}>
                    {fmtSignedJo(summary.day_pnl_krw)}
                  </strong>
                </div>
              </div>
              {!summary.valuation_complete && (
                <p className="mt-3 text-[10px] leading-relaxed text-warning">
                  가격 미확인 {summary.unpriced_positions}개는 합계에서 제외했습니다.
                </p>
              )}
            </div>

            <div className="border-t border-edge p-5 lg:border-l lg:border-t-0 lg:p-6">
              <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-ink-muted">
                상위 노출
              </p>
              <div className="mt-4 space-y-3">
                {topPositions.map((position) => {
                  const weight = (position.weight ?? 0) * 100;
                  const dayChange =
                    liveChanges.get(position.meta_id) ?? position.day_chg_pct;

                  return (
                    <Link
                      key={position.meta_id}
                      href={`/stock/${position.meta_id}`}
                      className="grid grid-cols-[minmax(6.5rem,1fr)_minmax(6rem,1.25fr)_auto] items-center gap-3 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-400"
                    >
                      <span className="min-w-0 truncate text-xs text-ink-secondary">
                        <strong className="font-medium text-ink">
                          {position.name ?? position.ticker}
                        </strong>
                        <span className={`ml-2 text-[10px] ${signClassNum(dayChange)}`}>
                          {fmtPctVal(dayChange)}
                        </span>
                      </span>
                      <span className="h-1 overflow-hidden rounded-full bg-overlay">
                        <span
                          className="block h-full rounded-full bg-gradient-to-r from-secondary-400 to-primary-400 shadow-[0_0_10px_rgba(124,91,255,0.28)]"
                          style={{ width: `${Math.min(Math.max(weight, 0), 100)}%` }}
                        />
                      </span>
                      <strong className="font-mono text-[10px] font-medium text-ink-secondary">
                        {weight.toFixed(1)}%
                      </strong>
                    </Link>
                  );
                })}
              </div>
            </div>

            <div className="border-t border-edge p-5 lg:border-l lg:border-t-0 lg:p-6">
              <p className="font-mono text-[9px] uppercase tracking-[0.14em] text-ink-muted">
                다음 점검
              </p>
              {nextReview && reviewDate ? (
                <Link
                  href={`/stock/${nextReview.meta_id}`}
                  className="mt-4 flex items-center gap-3 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-400"
                >
                  <span className="min-w-12 border-r border-edge pr-3 text-center font-mono">
                    <strong className="block text-xl font-medium text-ink">
                      {reviewDate[2]}
                    </strong>
                    <span className="text-[9px] text-ink-muted">{reviewDate[1]}월</span>
                  </span>
                  <span className="min-w-0">
                    <strong className="block truncate text-xs font-semibold text-ink">
                      {nextReview.name ?? nextReview.ticker}
                    </strong>
                    <span className="mt-1 block text-[10px] text-ink-muted">
                      논거와 무효화 조건 재검토
                    </span>
                  </span>
                </Link>
              ) : (
                <Link
                  href="/portfolio"
                  className="mt-4 flex items-start gap-2 text-xs leading-relaxed text-ink-muted hover:text-ink-secondary"
                >
                  <CalendarClock size={16} className="mt-0.5 shrink-0" aria-hidden />
                  검토일을 등록하면 가장 가까운 일정을 표시합니다.
                </Link>
              )}

              {largestDrift?.drift_pp != null && (
                <div className="mt-4 border-t border-edge pt-3">
                  <span className="text-[10px] text-ink-muted">가장 큰 목표 괴리</span>
                  <p className="mt-1 text-xs text-ink-secondary">
                    <strong className="font-medium text-ink">
                      {largestDrift.name ?? largestDrift.ticker}
                    </strong>{" "}
                    <span className={signClassNum(largestDrift.drift_pp)}>
                      {largestDrift.drift_pp > 0 ? "+" : ""}
                      {largestDrift.drift_pp.toFixed(1)}%p
                    </span>
                  </p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
