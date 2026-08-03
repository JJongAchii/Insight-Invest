"use client";

import React from "react";

import { useFetchRebalSignalsQuery } from "@/state/api";
import Card from "@/components/ui/Card";

const ACTION_LABEL: Record<string, string> = { enter: "진입", exit: "이탈", keep: "유지" };
const ACTION_COLOR: Record<string, string> = {
  enter: "var(--gains)",
  exit: "var(--losses)",
  keep: "var(--chart-2)",
};

/** 다음 리밸런싱 신호 — 배치가 리밸 전일 저녁 엔진과 동일 계산으로 생성.
 *  active인데 신호가 없으면 아직 주기 안이라는 뜻 — 안내 문구만. */
const NextRebalCard: React.FC<{ portId: number; isActive: boolean }> = ({ portId, isActive }) => {
  const { data } = useFetchRebalSignalsQuery(undefined, { skip: !isActive });
  if (!isActive) return null;
  const sig = data?.signals.find((s) => s.port_id === portId);

  return (
    <Card title="다음 리밸런싱">
      {!sig ? (
        <p className="text-sm text-ink-muted">
          다음 리밸런싱 주기 전일 저녁에 목표 비중이 생성됩니다.
        </p>
      ) : (
        <>
          <p className="text-xs text-ink-muted mb-2">
            {sig.is_stale ? "지난 신호 — " : ""}예상 리밸일 {sig.next_rebal} · {data?.as_of} 데이터
            기준 · 최종 비중은 리밸 전일 저녁 확정
          </p>
          <div className="flex flex-col gap-1.5">
            {sig.items.map((it) => (
              <div key={it.ticker} className="flex items-baseline gap-2 text-sm">
                <span
                  className="badge-neutral shrink-0"
                  style={{ color: ACTION_COLOR[it.action] }}
                >
                  {ACTION_LABEL[it.action]}
                </span>
                <span className="text-ink w-40 truncate">{it.name}</span>
                <span className="num text-ink-secondary">
                  {(it.prev_weight * 100).toFixed(1)}% → {(it.target_weight * 100).toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </Card>
  );
};

export default NextRebalCard;
