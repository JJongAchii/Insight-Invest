"use client";

import React from "react";

import { AnalyticsTrading } from "@/state/api";
import Card from "@/components/ui/Card";
import StatTile from "@/components/ui/StatTile";
import InfoTip from "@/components/ui/InfoTip";

interface TradingRealityCardProps {
  trading: AnalyticsTrading | null;
  /** 섹션이 강등된 사유 (서버 notes["trading"]). 없으면 일반 문구로 대체. */
  note?: string | null;
}

const fmtCostDrag = (v: number | null): string => (v == null ? "—" : `−${Math.abs(v).toFixed(2)}%p`);

/** 거래 현실 — 리밸 빈도·턴오버·비용 드래그 근사. 실전 비용을 넣으면 얼마나 깎이는지.
 *  판단 라벨 없음: 근사치임을 명기하고 수치만 표시 (스펙 §3). */
const TradingRealityCard: React.FC<TradingRealityCardProps> = ({ trading, note }) => {
  if (!trading) {
    return (
      <Card title="거래 현실">
        <p className="text-sm text-ink-muted">{note ?? "계산되지 않았습니다"}</p>
      </Card>
    );
  }

  return (
    <Card title="거래 현실">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatTile label="리밸 횟수" value={`${trading.n_rebals}회`} />
        <StatTile
          label="연평균 리밸"
          value={trading.rebals_per_year == null ? "—" : `${trading.rebals_per_year.toFixed(2)}회`}
        />
        <StatTile
          label={
            <span className="inline-flex items-center gap-1">
              평균 턴오버
              <InfoTip>편도 합산 — 전량 교체=2.0</InfoTip>
            </span>
          }
          value={trading.avg_turnover == null ? "—" : trading.avg_turnover.toFixed(2)}
        />
        <StatTile
          label={
            <span className="inline-flex items-center gap-1">
              비용 드래그 (근사)
              <InfoTip>턴오버·리밸 빈도에서 역산한 근사치 — 실제 체결 비용과 다를 수 있다</InfoTip>
            </span>
          }
          value={
            <span className="num text-sm font-medium leading-snug">
              10bps: 연 {fmtCostDrag(trading.cost_drag_pct_10bps)} / 30bps: 연{" "}
              {fmtCostDrag(trading.cost_drag_pct_30bps)}
            </span>
          }
        />
      </div>
    </Card>
  );
};

export default TradingRealityCard;
