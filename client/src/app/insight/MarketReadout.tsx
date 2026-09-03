"use client";

import Link from "next/link";
import React from "react";

import { useFetchOverviewQuery } from "@/state/api";

/** KR insight page's compact interpretation layer; raw sections remain the evidence drill-down. */
const MarketReadout: React.FC = () => {
  const { data } = useFetchOverviewQuery();
  if (!data) return null;

  const kr = data.evidence.filter((item) => item.key === "breadth" || item.key === "flow");
  if (kr.length === 0) return null;
  const positive = kr.filter((item) => item.tone === "positive").length;
  const negative = kr.filter((item) => item.tone === "negative").length;
  const reading =
    positive === kr.length
      ? "시장 참여 개선"
      : negative === kr.length
        ? "시장 참여 위축"
        : "수급과 시장폭 엇갈림";
  const toneLabel = {
    positive: "우호",
    neutral: "중립",
    negative: "경계",
  } as const;
  const toneColor = {
    positive: "var(--gains)",
    neutral: "var(--text-muted)",
    negative: "var(--losses)",
  } as const;
  const conflict = data.conflicts.some((text) => text.includes("KR"));

  return (
    <section className="relative overflow-hidden rounded-2xl border border-edge bg-surface">
      <span className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-primary-400 via-primary-500 to-secondary-400" aria-hidden />
      <div className="grid lg:grid-cols-[minmax(0,1fr)_15rem]">
        <div className="p-5 sm:p-6">
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-primary-300">Market participation</p>
              <h2 className="mt-2 text-lg font-semibold tracking-[-0.02em] text-ink">{reading}</h2>
            </div>
            <span className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${conflict ? "border-warning/30 bg-warning/10 text-warning" : "border-gains/30 bg-gains/10 text-gains"}`}>
              {conflict ? "근거 재확인" : "근거 일치"}
            </span>
          </div>
          <div className="divide-y divide-edge border-y border-edge">
            {kr.map((item) => (
              <article key={item.key} className="grid gap-2 py-4 sm:grid-cols-[5.5rem_minmax(0,1fr)_4.5rem] sm:items-start sm:gap-4">
                <div>
                  <p className="text-xs font-semibold text-ink">{item.key === "breadth" ? "시장폭" : "수급"}</p>
                  <p className="num mt-1 text-[10px] text-ink-muted">{item.as_of}</p>
                </div>
                <div>
                  <p className="text-sm font-semibold text-ink">{item.title}</p>
                  <p className="mt-1 text-xs leading-5 text-ink-secondary">{item.detail}</p>
                </div>
                <div className="flex items-center gap-1.5 text-xs sm:justify-end" style={{ color: toneColor[item.tone] }}>
                  <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
                  {toneLabel[item.tone]}
                </div>
              </article>
            ))}
          </div>
        </div>
        <aside className="border-t border-edge bg-raised/30 p-5 lg:border-l lg:border-t-0">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-ink-muted">Reading rule</p>
          <p className="mt-3 text-sm leading-6 text-ink-secondary">
            지수가 올라도 상승 종목이 줄거나 수급이 약하면 시장 전체의 회복으로 해석하지 않습니다.
          </p>
          {conflict && (
            <p className="mt-3 text-xs leading-5 text-warning">현재 관측이 엇갈립니다. 각 데이터의 기준일을 함께 확인하세요.</p>
          )}
          <Link href="/regime" className="mt-5 inline-flex text-xs font-medium text-primary-300 hover:text-primary-200">
            글로벌 국면과 비교하기 →
          </Link>
        </aside>
      </div>
    </section>
  );
};

export default MarketReadout;
