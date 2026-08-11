"use client";

import React, { useEffect, useRef, useState } from "react";
import { InsightMarket, useFetchIntradayMarketQuery } from "@/state/api";
import PageHeader from "@/components/ui/PageHeader";
import IndexBreadthStrip from "./IndexBreadthStrip";
import FlowsSection from "./FlowsSection";
import SectorSection from "./SectorSection";
import FactorSection from "./FactorSection";
import ValuationSection from "./ValuationSection";
import SignalsSection from "./SignalsSection";
import BreadthHistory from "./BreadthHistory";
import IntradayTab from "./intraday/IntradayTab";

type Tab = "live" | "settled";

/** KR market insight: 장중(지연 스냅샷) | 정산(일배치) 2탭. */
const InsightPage = () => {
  const [market, setMarket] = useState<InsightMarket>("KOSPI");
  const [tab, setTab] = useState<Tab>("settled");
  const { data: intraday } = useFetchIntradayMarketQuery(undefined, {
    pollingInterval: 5 * 60 * 1000,
    skipPollingIfUnfocused: true,
  });
  const active = intraday?.active === true;

  // 첫 로드에 한해 기본 탭 결정: 장중이면 live (스펙 D4).
  const defaulted = useRef(false);
  useEffect(() => {
    if (!defaulted.current && intraday) {
      defaulted.current = true;
      if (intraday.active && intraday.is_open) setTab("live");
    }
  }, [intraday]);

  return (
    <div className="flex flex-col gap-6 pb-16">
      <PageHeader
        title="KR Market Insight"
        description="수급·시장폭·신호 — KRX 전 종목 데이터 기반"
      />

      {active && (
        <div className="flex gap-1 border-b border-edge">
          {(
            [
              ["live", intraday?.is_open ? "🔴 장중" : "오늘 마감"],
              ["settled", "정산 인사이트"],
            ] as [Tab, string][]
          ).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition-colors ${
                tab === key
                  ? "border-ink text-ink"
                  : "border-transparent text-ink-muted hover:text-ink"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      )}

      {active && tab === "live" && intraday ? (
        <IntradayTab data={intraday} />
      ) : (
        <>
          <IndexBreadthStrip market={market} onMarketChange={setMarket} />
          <FlowsSection />
          <SectorSection />
          <FactorSection />
          <ValuationSection />
          <SignalsSection />
          <BreadthHistory market={market} onMarketChange={setMarket} />
        </>
      )}
    </div>
  );
};

export default InsightPage;
