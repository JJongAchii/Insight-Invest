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

  return (
    <div className="rounded-2xl border border-edge bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h2 className="text-sm font-semibold text-ink">KR Market Readout</h2>
        <span className="text-xs text-ink-muted">시장폭과 수급은 서로 다른 관측입니다</span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {kr.map((item) => (
          <div key={item.key} className="rounded-xl bg-raised px-3 py-2.5">
            <p className="text-sm font-semibold text-ink">{item.title}</p>
            <p className="text-xs text-ink-secondary mt-1">{item.detail}</p>
            <p className="text-[11px] text-ink-muted num mt-1.5">기준 {item.as_of}</p>
          </div>
        ))}
      </div>
      {data.conflicts.some((text) => text.includes("KR")) && (
        <p className="text-xs mt-3" style={{ color: "var(--chart-4)" }}>
          관측이 엇갈립니다. 지수 방향만으로 시장 전체 참여를 해석하지 마세요.
        </p>
      )}
      <Link href="/regime" className="inline-block text-xs text-primary-400 mt-3 hover:underline">
        글로벌 레짐과 함께 보기 →
      </Link>
    </div>
  );
};

export default MarketReadout;
