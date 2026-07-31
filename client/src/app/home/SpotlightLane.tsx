"use client";

import React from "react";
import Link from "next/link";

import {
  SpotlightGroup,
  SpotlightItem,
  useFetchSpotlightQuery,
} from "@/state/api";

const MINE_LABEL: Record<string, string> = {
  holding: "보유",
  watchlist: "관심",
};

// 그룹별 대표 지표 한 줄 — 그 그룹에 의미 있는 컬럼만 고른다
const metricLine = (signalType: string, item: SpotlightItem): string => {
  if (signalType === "near_52w_high_hold") {
    return [
      item.hold_days != null ? `${item.hold_days}일째 유지` : "",
      item.dist_pct != null ? `고점 대비 ${item.dist_pct.toFixed(1)}%` : "",
    ]
      .filter(Boolean)
      .join(" · ");
  }
  if (signalType === "frgn_streak10") {
    return [
      item.streak != null ? `${item.streak}일 연속 순매수` : "",
      item.intensity_20d != null ? `강도 ${item.intensity_20d.toFixed(1)}%` : "",
    ]
      .filter(Boolean)
      .join(" · ");
  }
  return [
    item.intensity_20d != null ? `강도 ${item.intensity_20d.toFixed(1)}%` : "",
    item.ret_20d != null ? `20일 ${item.ret_20d.toFixed(1)}%` : "",
  ]
    .filter(Boolean)
    .join(" · ");
};

const SpotlightCard: React.FC<{ group: SpotlightGroup; item: SpotlightItem }> = ({
  group,
  item,
}) => {
  const body = (
    <>
      <div className="flex items-center gap-2 mb-1">
        <span className="text-sm font-semibold text-ink truncate">{item.name}</span>
        {item.mine && <span className="badge-neutral">{MINE_LABEL[item.mine]}</span>}
        {item.also_in.length > 0 && <span className="badge-neutral">복합</span>}
        <span
          className="ml-auto text-xs num shrink-0"
          style={{
            color: (item.chg_pct ?? 0) >= 0 ? "var(--gains)" : "var(--losses)",
          }}
        >
          {item.chg_pct != null
            ? `${item.chg_pct > 0 ? "+" : ""}${item.chg_pct.toFixed(1)}%`
            : ""}
        </span>
      </div>
      <p className="text-xs text-ink-secondary">{metricLine(group.signal_type, item)}</p>
    </>
  );
  const cls =
    "group shrink-0 w-[240px] p-4 rounded-2xl border border-edge bg-surface " +
    "hover:border-edge-strong hover:bg-raised transition-all duration-200";
  return item.link ? (
    <Link href={item.link} className={cls}>
      {body}
    </Link>
  ) : (
    <div className={cls}>{body}</div>
  );
};

/** "오늘의 신호 종목" — 전시장 신호 스캔 (attention의 내 종목 트리아지와 별개).
 *  그룹 순서는 서버가 기준선 대비 우위 내림차순으로 준다. 에러·빈 데이터면
 *  레인 자체를 렌더하지 않는다 (AttentionLane 관례). */
const SpotlightLane: React.FC = () => {
  const { data, isLoading, error } = useFetchSpotlightQuery();
  if (error || isLoading) return null;
  const groups = (data?.groups ?? []).filter((g) => g.items.length > 0);
  if (groups.length === 0) return null;

  return (
    <div>
      <h2 className="text-sm font-semibold text-ink-secondary mb-3">
        오늘의 신호 종목
      </h2>
      <div className="flex flex-col gap-4">
        {groups.map((g) => (
          <div key={g.signal_type}>
            <div className="flex flex-wrap items-baseline gap-x-2 mb-2">
              <span className="text-sm font-medium text-ink">{g.title}</span>
              {g.evidence && (
                <span className="text-xs text-ink-muted">{g.evidence}</span>
              )}
            </div>
            <div className="flex gap-3 overflow-x-auto pb-2 -mx-1 px-1">
              {g.items.map((item) => (
                <SpotlightCard
                  key={`${g.signal_type}-${item.ticker}`}
                  group={g}
                  item={item}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default SpotlightLane;
