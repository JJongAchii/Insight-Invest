"use client";

import React from "react";

import Card from "@/components/ui/Card";
import LoadingState from "@/components/ui/LoadingState";
import { StockFundamentalFact } from "@/state/api";

const LABELS: Record<StockFundamentalFact["key"], string> = {
  revenue: "매출",
  net_income: "순이익",
  assets: "자산",
  equity: "자본",
  operating_cash_flow: "영업현금흐름",
};

const fmtUsd = (value: number): string => {
  const sign = value < 0 ? "−" : "";
  const abs = Math.abs(value);
  if (abs >= 1e12) return `${sign}$${(abs / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `${sign}$${(abs / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(1)}M`;
  return `${sign}$${abs.toLocaleString()}`;
};

const FundamentalsCard: React.FC<{
  facts?: StockFundamentalFact[];
  asOf?: string;
  note?: string;
  isLoading: boolean;
}> = ({ facts, asOf, note, isLoading }) => (
  <Card
    title="연간 재무 원장 · SEC 10-K"
    action={asOf ? <span className="text-xs text-ink-muted num">최근 제출 {asOf}</span> : undefined}
  >
    {isLoading ? (
      <LoadingState label="SEC 재무를 불러오는 중..." />
    ) : !facts || facts.length === 0 ? (
      <p className="text-sm text-ink-muted">{note ?? "표시할 연간 재무가 없습니다."}</p>
    ) : (
      <div>
        <div className="scrollbar-hidden -mx-5 overflow-x-auto px-5 md:-mx-6 md:px-6">
          <div className="metric-strip min-w-[43rem] grid-cols-5 md:min-w-0">
          {facts.map((fact) => (
            <div key={fact.key} className="metric-tile min-w-0 p-4">
              <p className="metric-label">{LABELS[fact.key]}</p>
              <p className="mt-2 text-lg font-semibold text-ink num">{fmtUsd(fact.value)}</p>
              <p className={`mt-1 text-xs num ${fact.yoy_pct == null ? "text-ink-muted" : fact.yoy_pct >= 0 ? "text-gains" : "text-losses"}`}>
                {fact.yoy_pct == null ? "전년 비교 없음" : `전년 대비 ${fact.yoy_pct >= 0 ? "+" : ""}${fact.yoy_pct.toFixed(1)}%`}
              </p>
              <p className="mt-2 text-[10px] text-ink-muted num">기간 {fact.period}</p>
            </div>
          ))}
          </div>
        </div>
        <p className="mt-4 border-t border-edge pt-3 text-xs leading-5 text-ink-muted">
          {note} 현재 연간 10-K만 제공하며 분기 10-Q는 포함하지 않습니다. 정정 제출은 현재
          시점에 공개된 최신 filed 값을 사용합니다.
        </p>
      </div>
    )}
  </Card>
);

export default FundamentalsCard;
