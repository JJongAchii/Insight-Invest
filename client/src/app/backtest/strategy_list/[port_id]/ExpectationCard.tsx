"use client";

import React from "react";

import { LiveExpectation } from "@/state/api";
import Card from "@/components/ui/Card";

const fmtPct = (v: number, digits = 2): string =>
  `${v >= 0 ? "+" : ""}${v.toFixed(digits)}%`;

/** p<50이면 "하위 p%", p>=50이면 "상위 (100-p)%" — 어느 쪽이든 원 백분위값을 괄호로
 *  병기해 숫자를 왜곡하지 않는다. 판단(좋다/나쁘다) 없이 분포 내 위치만 서술한다.
 *  보수(100-p)는 반올림된 p에서 유도하고, 표시값은 0%가 나오지 않도록 최소 1%로
 *  클램프한다(괄호 안 원 백분위값은 클램프하지 않는다). */
const percentileLabel = (p: number): string => {
  const rounded = Math.round(p);
  if (p < 50) {
    const bottomPct = Math.max(1, rounded);
    return `하위 ${bottomPct}% (백분위 ${rounded})`;
  }
  const topPct = Math.max(1, 100 - rounded);
  return `상위 ${topPct}% (백분위 ${rounded})`;
};

const PercentileStrip: React.FC<{ p: number }> = ({ p }) => {
  const clamped = Math.max(0, Math.min(100, p));
  return (
    <div className="mt-2 mb-1">
      <div className="relative h-2 rounded-full bg-raised">
        <div
          className="absolute top-1/2 h-3 w-3 -translate-y-1/2 -translate-x-1/2 rounded-full border-2 border-surface"
          style={{ left: `${clamped}%`, backgroundColor: "var(--chart-1)" }}
        />
      </div>
      <div className="flex justify-between text-[10px] text-ink-muted mt-1">
        <span>0</span>
        <span>50</span>
        <span>100</span>
      </div>
    </div>
  );
};

interface ExpectationCardProps {
  expectation?: LiveExpectation | null;
}

/** 저장 후 실전 수익·낙폭을 백테스트의 같은 길이 구간 분포 안에 위치시킨다.
 *  판단 라벨 없음: 위치 서술과 원 백분위값만 표시 (스펙 §3). */
const ExpectationCard: React.FC<ExpectationCardProps> = ({ expectation }) => {
  if (!expectation) {
    return (
      <Card title="기대 대비 위치">
        <p className="text-sm text-ink-muted">표본 부족(최소 5일·분포 60개)</p>
      </Card>
    );
  }

  const { n_days, live_ret_pct, ret_percentile, live_dd_pct, dd_percentile } =
    expectation;

  return (
    <Card title="기대 대비 위치">
      <div className="mb-5">
        <p className="text-sm text-ink">
          저장 후 {n_days}거래일 수익 {fmtPct(live_ret_pct)}는 백테스트의 모든{" "}
          {n_days}일 구간 중 {percentileLabel(ret_percentile)}
        </p>
        <PercentileStrip p={ret_percentile} />
      </div>
      <div>
        <p className="text-sm text-ink">
          현재 낙폭 {fmtPct(live_dd_pct)}는 백테스트의 모든 {n_days}일 구간
          낙폭 분포 중 {percentileLabel(dd_percentile)}
        </p>
        <PercentileStrip p={dd_percentile} />
      </div>
    </Card>
  );
};

export default ExpectationCard;
