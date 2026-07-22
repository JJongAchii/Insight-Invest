"use client";

import React, { useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { IoBriefcase } from "react-icons/io5";

import { useFetchHoldingsQuery } from "@/state/api";
import Card from "@/components/ui/Card";
import EmptyState from "@/components/ui/EmptyState";
import LoadingState from "@/components/ui/LoadingState";
import { fmtJo } from "@/app/insight/format";
import {
  fmtFracPct,
  fmtSignedJo,
  signClassNum,
} from "@/app/portfolio/format";

/** Dashboard "My Portfolio" summary: totals + top-3 positions by weight. */
const PortfolioCard: React.FC = () => {
  const router = useRouter();
  const { data, isLoading } = useFetchHoldingsQuery();

  const positions = data?.positions ?? [];
  const summary = data?.summary;

  const top3 = useMemo(() => {
    const list = data?.positions ?? [];
    return [...list].sort((a, b) => b.weight - a.weight).slice(0, 3);
  }, [data]);

  return (
    <Card
      title={
        <span className="inline-flex items-center gap-2">
          <IoBriefcase className="w-4 h-4 text-primary-400" aria-hidden />
          My Portfolio
        </span>
      }
      action={
        <Link
          href="/portfolio"
          className="text-xs font-medium text-ink-muted hover:text-ink transition-colors"
        >
          전체 보기 →
        </Link>
      }
    >
      {isLoading ? (
        <LoadingState label="포트폴리오를 불러오는 중..." />
      ) : !summary || positions.length === 0 ? (
        <EmptyState
          icon={<IoBriefcase className="w-7 h-7" aria-hidden />}
          title="보유 종목이 없습니다"
          hint={
            <Link href="/portfolio" className="text-primary-400 hover:underline">
              포트폴리오에서 추가하세요 →
            </Link>
          }
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Totals */}
          <div>
            <p className="metric-label mb-1">총 평가액</p>
            <p className="metric-value">{fmtJo(summary.total_value_krw)}</p>
            <div className="flex gap-6 mt-4">
              <div>
                <p className="metric-label mb-0.5">총 손익</p>
                <p className="flex items-baseline gap-1.5">
                  <span className={signClassNum(summary.total_pnl_krw)}>
                    {fmtSignedJo(summary.total_pnl_krw)}
                  </span>
                  <span className={`text-xs ${signClassNum(summary.total_pnl_krw)}`}>
                    {fmtFracPct(summary.total_pnl_pct)}
                  </span>
                </p>
              </div>
              <div>
                <p className="metric-label mb-0.5">일간 손익</p>
                <p className={signClassNum(summary.day_pnl_krw)}>
                  {fmtSignedJo(summary.day_pnl_krw)}
                </p>
              </div>
            </div>
          </div>

          {/* Top 3 positions */}
          <div>
            <p className="metric-label mb-2">상위 비중 종목</p>
            <div className="space-y-1">
              {top3.map((p) => (
                <button
                  key={p.meta_id}
                  onClick={() => router.push(`/stock/${p.meta_id}`)}
                  className="w-full flex items-center justify-between gap-2 px-2.5 py-2
                             rounded-lg hover:bg-raised transition-colors text-left"
                >
                  <span className="min-w-0">
                    <span className="text-sm font-medium text-ink truncate">
                      {p.name ?? p.ticker}
                    </span>
                    <span className="ml-1.5 text-xs text-ink-muted num">
                      {(p.weight * 100).toFixed(1)}%
                    </span>
                  </span>
                  <span className={`text-sm shrink-0 ${signClassNum(p.unrealized_pnl_pct)}`}>
                    {fmtFracPct(p.unrealized_pnl_pct)}
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </Card>
  );
};

export default PortfolioCard;
