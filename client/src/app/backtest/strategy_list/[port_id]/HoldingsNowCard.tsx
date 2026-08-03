"use client";

import React from "react";

import { LiveWeightRow } from "@/state/api";
import Card from "@/components/ui/Card";
import WeightBar from "@/components/charts/WeightBar";

interface HoldingsNowCardProps {
  weights?: LiveWeightRow[] | null;
}

/** 현재 보유 비중 — 어제 종가 기준, 드리프트 반영(리밸런싱 재계산치 아님).
 *  판단 라벨 없음: 비중 수치만 표시 (스펙 §3). "백테스트 최종 배분과 다름" 안내는
 *  MetricSummary 쪽 라벨이 담당한다(Task 4). */
const HoldingsNowCard: React.FC<HoldingsNowCardProps> = ({ weights }) => {
  if (!weights || weights.length === 0) {
    return (
      <Card title="현재 보유 비중 (어제 종가 기준, 드리프트 반영)">
        <p className="text-sm text-ink-muted">다음 배치부터 집계됩니다</p>
      </Card>
    );
  }

  const tradeDate = weights.reduce(
    (latest, w) => (w.trade_date > latest ? w.trade_date : latest),
    weights[0].trade_date
  );
  const sorted = [...weights].sort((a, b) => b.weight - a.weight);

  return (
    <Card
      title="현재 보유 비중 (어제 종가 기준, 드리프트 반영)"
      action={<span className="text-xs text-ink-muted">{tradeDate}</span>}
    >
      <WeightBar
        items={sorted.map((w) => ({ label: w.ticker, value: w.weight }))}
      />
    </Card>
  );
};

export default HoldingsNowCard;
