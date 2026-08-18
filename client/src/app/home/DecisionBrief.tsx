"use client";

import Link from "next/link";
import React from "react";

import Card from "@/components/ui/Card";
import ErrorState from "@/components/ui/ErrorState";
import LoadingState from "@/components/ui/LoadingState";
import {
  DataHealthLevel,
  EvidenceTone,
  OverviewTone,
  useFetchHoldingsQuery,
  useFetchOverviewQuery,
} from "@/state/api";

const TONE_STYLE: Record<OverviewTone, { color: string; bg: string }> = {
  risk_on: { color: "var(--gains)", bg: "color-mix(in srgb, var(--gains) 10%, transparent)" },
  risk_off: { color: "var(--losses)", bg: "color-mix(in srgb, var(--losses) 10%, transparent)" },
  mixed: { color: "var(--chart-4)", bg: "color-mix(in srgb, var(--chart-4) 12%, transparent)" },
};

const EVIDENCE_DOT: Record<EvidenceTone, string> = {
  positive: "var(--gains)",
  negative: "var(--losses)",
  neutral: "var(--ink-muted)",
};

const HEALTH_DOT: Record<DataHealthLevel, string> = {
  ok: "var(--gains)",
  warn: "var(--chart-4)",
  error: "var(--losses)",
  unknown: "var(--ink-muted)",
};

/** Current market synthesis plus explicit checks against the user's holdings. */
const DecisionBrief: React.FC = () => {
  const { data, isLoading, error, refetch } = useFetchOverviewQuery();
  const { data: holdings } = useFetchHoldingsQuery();

  if (error) {
    return <ErrorState message="판단 요약을 불러오지 못했습니다" onRetry={refetch} />;
  }
  if (isLoading || !data) return <LoadingState label="시장 판단 근거를 정리하는 중..." />;

  const summary = holdings?.summary;
  const portfolioChecks: string[] = [];
  if (summary?.top_weight != null && summary.top_weight >= 0.25) {
    portfolioChecks.push(`최대 종목 비중 ${(summary.top_weight * 100).toFixed(1)}%`);
  }
  if (summary?.hhi != null && summary.hhi >= 0.18) {
    portfolioChecks.push(`집중도 HHI ${summary.hhi.toFixed(2)}`);
  }
  const largestDrift = [...(holdings?.positions ?? [])]
    .filter((position) => position.drift_pp != null)
    .sort((a, b) => Math.abs(b.drift_pp ?? 0) - Math.abs(a.drift_pp ?? 0))[0];
  if (largestDrift?.drift_pp != null && Math.abs(largestDrift.drift_pp) >= 5) {
    portfolioChecks.push(
      `${largestDrift.name ?? largestDrift.ticker} 목표 괴리 ${largestDrift.drift_pp >= 0 ? "+" : ""}${largestDrift.drift_pp.toFixed(1)}%p`
    );
  }
  if (summary && summary.n_positions > 0 && portfolioChecks.length === 0) {
    portfolioChecks.push("설정 기준(단일 25%·HHI 0.18) 이상의 집중 없음");
  }

  const toneStyle = TONE_STYLE[data.tone];
  const unhealthy = data.data_status.filter((item) => item.level !== "ok");

  return (
    <Card
      title="오늘의 판단 프레임"
      action={
        <span className="text-xs text-ink-muted">
          처방이 아닌 관측 방향의 일치 여부
        </span>
      }
    >
      <div className="space-y-5">
        <div className="flex flex-wrap items-center gap-3">
          <span
            className="px-3 py-1.5 rounded-lg text-sm font-semibold"
            style={{ color: toneStyle.color, backgroundColor: toneStyle.bg }}
          >
            {data.tone_label}
          </span>
          <span className="text-xs text-ink-muted">{data.method}</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
          {data.evidence.map((item) => (
            <Link
              key={item.key}
              href={item.link}
              className="rounded-xl border border-edge p-3 hover:bg-raised transition-colors"
            >
              <div className="flex items-center gap-2">
                <span
                  className="h-2 w-2 rounded-full shrink-0"
                  style={{ backgroundColor: EVIDENCE_DOT[item.tone] }}
                  aria-hidden
                />
                <p className="text-sm font-semibold text-ink truncate">{item.title}</p>
                {item.changed && <span className="badge-neutral ml-auto">변화</span>}
              </div>
              <p className="mt-1.5 text-xs text-ink-secondary line-clamp-2">{item.detail}</p>
              {item.as_of && (
                <p className="mt-2 text-[11px] text-ink-muted num">기준 {item.as_of}</p>
              )}
            </Link>
          ))}
        </div>

        {(data.conflicts.length > 0 || portfolioChecks.length > 0) && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {data.conflicts.length > 0 && (
              <div className="rounded-xl bg-raised p-3">
                <p className="text-xs font-semibold text-ink-secondary mb-1">엇갈리는 신호</p>
                {data.conflicts.map((text) => (
                  <p key={text} className="text-sm text-ink">{text}</p>
                ))}
              </div>
            )}
            {portfolioChecks.length > 0 && (
              <Link href="/portfolio" className="rounded-xl bg-raised p-3 hover:bg-surface transition-colors">
                <p className="text-xs font-semibold text-ink-secondary mb-1">내 포트폴리오 확인점</p>
                <p className="text-sm text-ink">{portfolioChecks.join(" · ")}</p>
              </Link>
            )}
          </div>
        )}

        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-edge pt-3">
          <span className="text-xs font-semibold text-ink-secondary">데이터 상태</span>
          {data.data_status.length === 0 ? (
            <span className="text-xs text-ink-muted">배치 상태표 미발행</span>
          ) : (
            data.data_status.map((item) => (
              <span key={item.dataset} className="inline-flex items-center gap-1.5 text-xs text-ink-muted">
                <span
                  className="w-1.5 h-1.5 rounded-full"
                  style={{ backgroundColor: HEALTH_DOT[item.level] }}
                  aria-hidden
                />
                {item.label} {item.as_of ?? item.detail}
              </span>
            ))
          )}
          {unhealthy.length > 0 && (
            <span className="text-xs text-losses">{unhealthy.length}개 확인 필요</span>
          )}
        </div>
      </div>
    </Card>
  );
};

export default DecisionBrief;
