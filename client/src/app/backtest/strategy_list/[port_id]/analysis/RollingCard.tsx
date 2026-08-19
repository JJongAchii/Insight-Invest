"use client";

import React, { useMemo } from "react";

import { AnalyticsRolling } from "@/state/api";
import Card from "@/components/ui/Card";
import TimeSeriesChart from "@/components/charts/TimeSeriesChart";

interface RollingCardProps {
  rolling: AnalyticsRolling | null;
  /** 섹션이 강등된 사유 (서버 notes["rolling"]). 없으면 일반 문구로 대체. */
  note?: string | null;
  /** BM 비교가 빠진 사유 (서버 notes["bm"]) — 있으면 카드 하단에 각주로 표시. */
  bmNote?: string | null;
}

type Row = { date: string; strategy: number | null; bm: number | null };

/** 두 rows 배열(전략/BM)을 날짜 기준으로 병합 — 지표 필드(roll_ret/roll_sharpe)는 호출부에서 뽑는다. */
const mergeByDate = (
  rows: { date: string; v: number }[],
  bmRows: { date: string; v: number }[] | null
): Row[] => {
  const byDate = new Map<string, Row>();
  for (const r of rows) byDate.set(r.date, { date: r.date, strategy: r.v, bm: null });
  for (const r of bmRows ?? []) {
    const existing = byDate.get(r.date);
    if (existing) existing.bm = r.v;
    else byDate.set(r.date, { date: r.date, strategy: null, bm: r.v });
  }
  return [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date));
};

/** 롤링 1년 수익률·샤프 — 기간 의존성 진단 재료. 전략 vs BM (있으면).
 *  판단 라벨 없음: 두 시계열과 창 길이만 표시 (스펙 §3). */
const RollingCard: React.FC<RollingCardProps> = ({ rolling, note, bmNote }) => {
  const hasBm = !!rolling?.bm_rows?.length;

  const { retData, sharpeData } = useMemo(() => {
    if (!rolling) return { retData: [], sharpeData: [] };
    const retRows = mergeByDate(
      rolling.rows.map((r) => ({ date: r.date, v: r.roll_ret })),
      rolling.bm_rows?.map((r) => ({ date: r.date, v: r.roll_ret })) ?? null
    );
    const sharpeRows = mergeByDate(
      rolling.rows.map((r) => ({ date: r.date, v: r.roll_sharpe })),
      rolling.bm_rows?.map((r) => ({ date: r.date, v: r.roll_sharpe })) ?? null
    );
    return { retData: retRows, sharpeData: sharpeRows };
  }, [rolling]);

  if (!rolling) {
    return (
      <Card title="Rolling Performance">
        <p className="text-sm text-ink-muted">{note ?? "계산되지 않았습니다"}</p>
      </Card>
    );
  }

  const series = [
    { key: "strategy", name: "전략", color: "var(--chart-1)" },
    ...(hasBm ? [{ key: "bm", name: "BM", color: "var(--text-muted)" }] : []),
  ];

  return (
    <Card
      title="Rolling Performance"
      action={<span className="text-xs text-ink-muted">창 {rolling.window}거래일</span>}
    >
      <div className="flex flex-col gap-6">
        <div>
          <h4 className="text-sm font-medium text-ink mb-2">Rolling 1Y Return</h4>
          <TimeSeriesChart
            data={retData}
            series={series}
            height={220}
            yFormatter={(v) => `${v.toFixed(1)}%`}
            baseline={0}
          />
        </div>
        <div>
          <h4 className="text-sm font-medium text-ink mb-2">Rolling Sharpe</h4>
          <TimeSeriesChart
            data={sharpeData}
            series={series}
            height={220}
            yFormatter={(v) => v.toFixed(2)}
            baseline={0}
          />
        </div>
      </div>
      {bmNote && (
        <p className="text-xs mt-4" style={{ color: "var(--chart-4)" }}>
          ⚠ {bmNote}
        </p>
      )}
    </Card>
  );
};

export default RollingCard;
