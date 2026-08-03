"use client";

import React from "react";

import {
  RiskCorr,
  useFetchHoldingsRiskQuery,
} from "@/state/api";
import Card from "@/components/ui/Card";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";
import InfoTip from "@/components/ui/InfoTip";

const fmtPct = (v: number | null | undefined, digits = 1): string =>
  v == null ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(digits)}%`;

const signColor = (v: number | null | undefined) =>
  v == null ? undefined : v >= 0 ? "var(--gains)" : "var(--losses)";

const Tile: React.FC<{ label: React.ReactNode; value: string; sub?: string }> = ({
  label,
  value,
  sub,
}) => (
  <div className="flex-1 min-w-[140px] p-3 rounded-xl border border-edge bg-surface">
    <div className="text-xs text-ink-muted mb-1">{label}</div>
    <div className="text-lg font-semibold text-ink num">{value}</div>
    {sub && <div className="text-xs text-ink-muted mt-0.5">{sub}</div>}
  </div>
);

const CorrHeatmap: React.FC<{ corr: RiskCorr }> = ({ corr }) => (
  <div className="overflow-x-auto">
    <table className="text-xs num">
      <thead>
        <tr>
          <th />
          {corr.names.map((n) => (
            <th key={n} className="px-1.5 py-1 font-normal text-ink-muted max-w-[72px] truncate">
              {n}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {corr.names.map((rowName, i) => (
          <tr key={rowName}>
            <td className="pr-2 py-1 text-ink-muted max-w-[96px] truncate">{rowName}</td>
            {corr.values[i].map((v, j) => (
              <td
                key={j}
                className="px-1.5 py-1 text-center text-ink"
                style={{
                  backgroundColor:
                    v == null || i === j
                      ? "transparent"
                      : `color-mix(in srgb, var(--chart-1) ${Math.round(
                          Math.abs(v) * 55
                        )}%, transparent)`,
                }}
              >
                {i === j ? "·" : v == null ? "—" : v.toFixed(2)}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

/** 위험 요약 — 현재 비중을 과거에 고정 적용했다면의 반사실 수치.
 *  판단 라벨 없음: 수치·전제·데이터 경고만 (스펙 §3). */
const RiskCard: React.FC = () => {
  const { data, isLoading, error, refetch } = useFetchHoldingsRiskQuery();

  if (error)
    return (
      <Card title="위험 요약">
        <ErrorState message="위험 정보를 불러오지 못했습니다" onRetry={refetch} />
      </Card>
    );
  if (isLoading || !data)
    return (
      <Card title="위험 요약">
        <LoadingState label="위험 지표 계산 중..." />
      </Card>
    );
  if (data.empty) return null;
  if (data.insufficient)
    return (
      <Card title="위험 요약">
        <p className="text-sm text-ink-muted">
          공통 가격 이력이 {data.overlap_days}일뿐이라 위험 지표를 계산하지 않습니다 (최소 60일).
        </p>
      </Card>
    );

  return (
    <Card title="위험 요약">
      <p className="text-xs text-ink-muted mb-4">
        현재 비중 고정 가정 · {data.basis?.window.start} ~ {data.basis?.window.end}
      </p>
      <div className="flex flex-wrap gap-3">
        <Tile label="연환산 변동성" value={fmtPct(data.ann_vol)} />
        <Tile
          label="최대 낙폭"
          value={fmtPct(data.max_drawdown)}
          sub={`${data.mdd_from} ~ ${data.mdd_to}`}
        />
        <Tile
          label={
            <span className="inline-flex items-center gap-1">
              평균 상관
              <InfoTip>
                보유 종목 일수익률 상관의 평균 — 1에 가까울수록 같이 움직여 분산 효과가 없다
              </InfoTip>
            </span>
          }
          value={data.avg_pair_corr == null ? "—" : data.avg_pair_corr.toFixed(2)}
        />
      </div>

      <div className="mt-4">
        <h4 className="text-sm font-medium text-ink mb-2">
          시나리오 <span className="text-xs text-ink-muted">(현재 비중을 각 구간에 적용했다면)</span>
        </h4>
        <div className="flex flex-col gap-1.5">
          {(data.scenarios ?? []).map((s) => (
            <div key={s.key} className="flex items-baseline gap-2 text-sm">
              <span className="text-ink-secondary w-56 shrink-0">{s.label}</span>
              <span className="num font-medium" style={{ color: signColor(s.ret_pct) }}>
                {fmtPct(s.ret_pct)}
              </span>
              <span className="text-xs text-ink-muted truncate">
                {s.note ?? (s.start && s.end ? `${s.start} ~ ${s.end}` : "")}
              </span>
            </div>
          ))}
        </div>
      </div>

      {data.corr && (
        <div className="mt-4">
          <h4 className="text-sm font-medium text-ink mb-2">상관 히트맵</h4>
          <CorrHeatmap corr={data.corr} />
        </div>
      )}

      {(data.warnings ?? []).length > 0 && (
        <div className="mt-4 flex flex-col gap-1">
          {(data.warnings ?? []).map((w, i) => (
            <p key={i} className="text-xs" style={{ color: "var(--chart-4)" }}>
              ⚠ {w.ticker ? `${w.ticker} — ` : ""}{w.detail}
            </p>
          ))}
        </div>
      )}
    </Card>
  );
};

export default RiskCard;
