"use client";

import React from "react";

import { AnalyticsDrawdowns } from "@/state/api";
import Card from "@/components/ui/Card";
import TimeSeriesChart from "@/components/charts/TimeSeriesChart";

interface DrawdownCardProps {
  drawdowns: AnalyticsDrawdowns | null;
  /** 섹션이 강등된 사유 (서버가 별도 note를 주지 않으면 일반 문구로 대체). */
  note?: string | null;
}

const fmtPct = (v: number): string => `${v.toFixed(2)}%`;
const signColor = (v: number): string => (v >= 0 ? "var(--gains)" : "var(--losses)");

/** 낙폭 — 수중곡선(underwater curve)과 상위 에피소드(깊이·회복). 회복 미확인은 "진행 중".
 *  판단 라벨 없음: 수치와 날짜만 표시 (스펙 §3). */
const DrawdownCard: React.FC<DrawdownCardProps> = ({ drawdowns, note }) => {
  if (!drawdowns) {
    return (
      <Card title="낙폭">
        <p className="text-sm text-ink-muted">
          {note ?? "이력 부족으로 계산되지 않았습니다"}
        </p>
      </Card>
    );
  }

  const chartData = drawdowns.underwater.map((p) => ({ date: p.date, dd: p.dd_pct }));

  return (
    <Card title="낙폭">
      <TimeSeriesChart
        data={chartData}
        series={[{ key: "dd", name: "낙폭", color: "var(--losses)" }]}
        height={220}
        yFormatter={(v) => `${v.toFixed(1)}%`}
        baseline={0}
      />

      {drawdowns.episodes.length === 0 ? (
        <p className="text-sm text-ink-muted mt-4">이력 부족으로 계산되지 않았습니다</p>
      ) : (
        <div className="overflow-x-auto mt-4">
          <table className="w-full text-sm">
            <thead>
              <tr className="table-header">
                <th className="py-2.5 px-4 text-right rounded-l-lg">깊이</th>
                <th className="py-2.5 px-4 text-left">고점 → 저점 → 회복</th>
                <th className="py-2.5 px-4 text-right rounded-r-lg">회복일수</th>
              </tr>
            </thead>
            <tbody>
              {drawdowns.episodes.map((e, i) => (
                <tr key={`${e.peak}-${e.trough}-${i}`} className="table-row">
                  <td className="table-cell text-right">
                    <span className="num font-medium" style={{ color: signColor(e.depth_pct) }}>
                      {fmtPct(e.depth_pct)}
                    </span>
                  </td>
                  <td className="table-cell num text-ink-secondary">
                    {e.peak ?? "—"} → {e.trough ?? "—"} → {e.recover ?? "—"}
                  </td>
                  <td className="table-cell text-right">
                    {e.days_to_recover == null ? (
                      <span className="badge-neutral">진행 중</span>
                    ) : (
                      <span className="num text-ink-secondary">{e.days_to_recover}일</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
};

export default DrawdownCard;
