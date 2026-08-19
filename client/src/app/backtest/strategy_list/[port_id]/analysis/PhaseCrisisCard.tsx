"use client";

import React from "react";

import { AnalyticsCrisisRow, AnalyticsPhaseRow } from "@/state/api";
import Card from "@/components/ui/Card";

interface PhaseCrisisCardProps {
  phases: { rows: AnalyticsPhaseRow[] } | null;
  crisis: AnalyticsCrisisRow[];
  /** phases 섹션이 강등된 사유 (서버 notes["phases"]). 없으면 일반 문구로 대체. */
  phasesNote?: string | null;
  /** BM 비교가 빠진 사유 (서버 notes["bm"]) — 있으면 카드 하단에 각주로 표시. */
  bmNote?: string | null;
}

/** 알려진 위기 구간 → 표시 라벨. 모르는 key는 key 그대로 (스펙 §3). */
const CRISIS_LABEL: Record<string, string> = {
  covid_2020: "코로나 급락 (2020-02~03)",
};

const fmtPct = (v: number | null): string => (v == null ? "—" : `${v.toFixed(2)}%`);
const signColor = (v: number | null): string | undefined =>
  v == null ? undefined : v >= 0 ? "var(--gains)" : "var(--losses)";

/** 국면별 월평균 수익(전략 vs BM) + 고정 위기 구간 수익. 현재 국면 강조는 하지 않는다.
 *  판단 라벨 없음: 수치·n·사유만 표시 (스펙 §3). */
const PhaseCrisisCard: React.FC<PhaseCrisisCardProps> = ({
  phases,
  crisis,
  phasesNote,
  bmNote,
}) => {
  return (
    <Card title="Regimes & Crisis Periods">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div>
          <h4 className="text-sm font-medium text-ink mb-2">Monthly Return by Regime</h4>
          {!phases || phases.rows.length === 0 ? (
            <p className="text-sm text-ink-muted">{phasesNote ?? "계산되지 않았습니다"}</p>
          ) : (
            <div className="flex flex-col gap-1.5">
              {phases.rows.map((r) => (
                <div key={r.phase} className="flex items-baseline gap-2 text-sm">
                  <span className="text-ink w-24 shrink-0 truncate">{r.phase}</span>
                  <span className="num font-medium" style={{ color: signColor(r.mean_ret_pct) }}>
                    {fmtPct(r.mean_ret_pct)}
                  </span>
                  <span className="text-xs text-ink-muted">n={r.n_months}</span>
                  {r.bm_mean_ret_pct != null && (
                    <span className="text-xs text-ink-muted num ml-auto">
                      BM {fmtPct(r.bm_mean_ret_pct)}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div>
          <h4 className="text-sm font-medium text-ink mb-2">Crisis Periods</h4>
          {crisis.length === 0 ? (
            <p className="text-sm text-ink-muted">계산되지 않았습니다</p>
          ) : (
            <div className="flex flex-col gap-1.5">
              {crisis.map((c) => (
                <div key={c.key} className="flex items-baseline gap-2 text-sm">
                  <span className="text-ink-secondary flex-1 truncate">
                    {CRISIS_LABEL[c.key] ?? c.key}
                  </span>
                  {c.ret_pct == null ? (
                    <span className="text-xs text-ink-muted">{c.note ?? "계산되지 않았습니다"}</span>
                  ) : (
                    <span className="num font-medium" style={{ color: signColor(c.ret_pct) }}>
                      {fmtPct(c.ret_pct)}
                    </span>
                  )}
                </div>
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

export default PhaseCrisisCard;
