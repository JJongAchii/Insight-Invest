"use client";

import React from "react";

import { AnalyticsMonthly } from "@/state/api";
import Card from "@/components/ui/Card";
import StatTile from "@/components/ui/StatTile";

interface MonthlyStatsCardProps {
  monthly: AnalyticsMonthly | null;
  /** 섹션이 강등된 사유 (서버가 별도 note를 주지 않으면 일반 문구로 대체). */
  note?: string | null;
  /** BM 비교가 빠진 사유 (서버 notes["bm"]) — 있으면 카드 하단에 각주로 표시. */
  bmNote?: string | null;
}

const fmtPct = (v: number | null, digits = 1): string => (v == null ? "—" : `${v.toFixed(digits)}%`);
const signColor = (v: number): string => (v >= 0 ? "var(--gains)" : "var(--losses)");

const MonthRow: React.FC<{ month: string; ret_pct: number }> = ({ month, ret_pct }) => (
  <div className="flex items-baseline justify-between text-sm">
    <span className="text-ink-secondary num">{month}</span>
    <span className="num font-medium" style={{ color: signColor(ret_pct) }}>
      {fmtPct(ret_pct, 2)}
    </span>
  </div>
);

/** 월별 승률·최고/최악 월 — 분포의 꼬리를 직접 보여준다.
 *  판단 라벨 없음: 승률·수치만 표시 (스펙 §3). */
const MonthlyStatsCard: React.FC<MonthlyStatsCardProps> = ({ monthly, note, bmNote }) => {
  if (!monthly) {
    return (
      <Card title="Monthly Statistics">
        <p className="text-sm text-ink-muted">{note ?? "계산되지 않았습니다"}</p>
      </Card>
    );
  }

  return (
    <Card title="Monthly Statistics">
      <div className="grid grid-cols-2 gap-3 mb-6">
        <StatTile label="승률" value={fmtPct(monthly.win_rate)} />
        <StatTile label="승률 (BM 대비)" value={fmtPct(monthly.win_rate_vs_bm)} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <h4 className="text-sm font-medium text-ink mb-2">Best Months</h4>
          {monthly.best.length === 0 ? (
            <p className="text-sm text-ink-muted">계산되지 않았습니다</p>
          ) : (
            <div className="flex flex-col gap-1.5">
              {monthly.best.map((m) => (
                <MonthRow key={m.month} month={m.month} ret_pct={m.ret_pct} />
              ))}
            </div>
          )}
        </div>
        <div>
          <h4 className="text-sm font-medium text-ink mb-2">Worst Months</h4>
          {monthly.worst.length === 0 ? (
            <p className="text-sm text-ink-muted">계산되지 않았습니다</p>
          ) : (
            <div className="flex flex-col gap-1.5">
              {monthly.worst.map((m) => (
                <MonthRow key={m.month} month={m.month} ret_pct={m.ret_pct} />
              ))}
            </div>
          )}
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

export default MonthlyStatsCard;
