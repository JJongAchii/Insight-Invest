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
    title="SEC 핵심 재무"
    action={asOf ? <span className="text-xs text-ink-muted num">제출 {asOf}</span> : undefined}
  >
    {isLoading ? (
      <LoadingState label="SEC 재무를 불러오는 중..." />
    ) : !facts || facts.length === 0 ? (
      <p className="text-sm text-ink-muted">{note ?? "표시할 연간 재무가 없습니다."}</p>
    ) : (
      <div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {facts.map((fact) => (
            <div key={fact.key} className="rounded-xl border border-edge p-3">
              <p className="text-xs text-ink-muted">{LABELS[fact.key]}</p>
              <p className="text-lg font-semibold text-ink num mt-1">{fmtUsd(fact.value)}</p>
              <p className="text-xs text-ink-secondary num mt-1">
                {fact.yoy_pct == null ? "전년 비교 없음" : `YoY ${fact.yoy_pct >= 0 ? "+" : ""}${fact.yoy_pct.toFixed(1)}%`}
              </p>
              <p className="text-[10px] text-ink-muted num mt-1">기간 {fact.period}</p>
            </div>
          ))}
        </div>
        <p className="text-xs text-ink-muted mt-3">
          {note} 정정 제출은 현재 시점에 공개된 최신 filed 값을 사용합니다.
        </p>
      </div>
    )}
  </Card>
);

export default FundamentalsCard;
