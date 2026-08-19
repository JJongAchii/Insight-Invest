"use client";

import React from "react";

import { StrategyLiveResponse } from "@/state/api";
import Card from "@/components/ui/Card";
import StatTile from "@/components/ui/StatTile";
import EmptyState from "@/components/ui/EmptyState";

const fmtPct = (v: number | null | undefined, digits = 2): string =>
  v == null || Number.isNaN(v) ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(digits)}%`;

interface LiveHeadlineProps {
  live?: StrategyLiveResponse;
}

/** 저장 후 실전 운영 헤드라인 — nav·지표에서 파생한 4개 타일(누적수익·연환산·낙폭·경과일).
 *  판단 라벨 없음: 수치와 백테스트 대응치만 표시 (스펙 §3). */
const LiveHeadline: React.FC<LiveHeadlineProps> = ({ live }) => {
  const nav = live?.nav ?? [];

  if (nav.length === 0) {
    return (
      <Card title="Live Tracking">
        <EmptyState
          title="실전 추적 준비 중"
          hint="다음 데일리 파이프라인 실행 후 표시됩니다"
        />
      </Card>
    );
  }

  const base = nav[0].value;
  const last = nav[nav.length - 1].value;
  const peak = Math.max(...nav.map((p) => p.value));
  const cumRetPct = base === 0 ? 0 : (last / base - 1) * 100;
  const ddPct = (last / peak - 1) * 100;
  // nav[0] is the saved_at anchor row, not an elapsed trading day — matches the
  // server's live_percentile n_days (= len(live_nav) - 1), so this card and
  // ExpectationCard's "{n_days}거래일" agree.
  const elapsedDays = Math.max(0, nav.length - 1);
  const annRet = live?.metrics_live?.ann_ret ?? null;
  const btAnnRet = live?.metrics_backtest?.ann_ret ?? null;
  const btMdd = live?.metrics_backtest?.mdd ?? null;
  const savedAtSub = live?.saved_at ? `저장일 ${live.saved_at}` : undefined;

  return (
    <Card
      title="Live Tracking"
      action={
        live?.as_of ? (
          <span className="text-xs text-ink-muted">as_of {live.as_of}</span>
        ) : undefined
      }
    >
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatTile
          label="누적 수익 (저장 후)"
          value={fmtPct(cumRetPct)}
          deltaType={cumRetPct >= 0 ? "gain" : "loss"}
          sub={savedAtSub}
        />
        <StatTile
          label="연환산"
          value={fmtPct(annRet)}
          deltaType={annRet == null ? "neutral" : annRet >= 0 ? "gain" : "loss"}
          sub={`백테스트 ${fmtPct(btAnnRet)}`}
        />
        <StatTile
          label="현재 낙폭"
          value={fmtPct(ddPct)}
          deltaType={ddPct < 0 ? "loss" : "neutral"}
          sub={`백테스트 MDD ${fmtPct(btMdd)}`}
        />
        <StatTile
          label="경과 거래일"
          value={`${elapsedDays}일`}
          sub={savedAtSub}
        />
      </div>
    </Card>
  );
};

export default LiveHeadline;
