"use client";

import React from "react";

import { AnalyticsPremise } from "@/state/api";
import Card from "@/components/ui/Card";

interface PremiseCardProps {
  premise: AnalyticsPremise | null;
  /** 섹션이 강등된 사유 (서버 notes["premise"]). 없으면 일반 문구로 대체. */
  note?: string | null;
}

const dash = (v: string | null | undefined): string => v ?? "—";

interface Item {
  label: string;
  value: string;
}

/** 분석 전제 — 이 백테스트가 어떤 조건에서 나왔는지 (알고리즘·비용·유니버스·구간).
 *  판단 라벨 없음: 값과 사실 서술 경고만 (스펙 §3). */
const PremiseCard: React.FC<PremiseCardProps> = ({ premise, note }) => {
  if (!premise) {
    return (
      <Card title="Research Premise">
        <p className="text-sm text-ink-muted">{note ?? "계산되지 않았습니다"}</p>
      </Card>
    );
  }

  const items: Item[] = [
    { label: "알고리즘", value: dash(premise.algorithm) },
    { label: "리밸 주기", value: dash(premise.rebal_freq) },
    {
      label: "거래비용",
      value: premise.cost_bps == null ? "—" : `${premise.cost_bps}bps`,
    },
    { label: "통화", value: dash(premise.currency) },
    ...(premise.return_basis
      ? [{ label: "Return Basis", value: premise.return_basis }]
      : []),
    ...(premise.execution_rule
      ? [{ label: "Execution", value: premise.execution_rule }]
      : []),
    ...(premise.calculation_version
      ? [{ label: "Version", value: premise.calculation_version }]
      : []),
    { label: "유니버스", value: `${premise.universe_n}종목` },
    {
      label: "구간",
      value: `${premise.bt_start} ~ ${premise.bt_end} (${premise.bt_days}일)`,
    },
    {
      label: "리밸 횟수",
      value: premise.n_rebals == null ? "—" : `${premise.n_rebals}회`,
    },
    { label: "저장일", value: dash(premise.saved_at) },
  ];

  return (
    <Card title="Research Premise">
      {premise.cost_warning && (
        <div
          className="mb-4 px-3 py-2 rounded-lg text-sm"
          style={{
            color: "var(--chart-4)",
            backgroundColor: "color-mix(in srgb, var(--chart-4) 10%, transparent)",
          }}
        >
          ⚠ 거래비용 0으로 백테스트됨 — 수익률이 실전 대비 부풀려져 있습니다
        </div>
      )}
      <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3">
        {items.map((it) => (
          <div key={it.label} className="flex items-baseline justify-between gap-3 text-sm">
            <dt className="text-ink-muted shrink-0">{it.label}</dt>
            <dd className="text-ink font-medium num text-right truncate">{it.value}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
};

export default PremiseCard;
