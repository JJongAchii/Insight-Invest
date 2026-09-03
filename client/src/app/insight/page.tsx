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
import MarketReadout from "./MarketReadout";

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
        eyebrow="Market tape"
        title="한국 시장"
        description="지수 방향과 시장 참여를 분리해 보고, 수급·섹터·팩터·밸류에이션 근거를 순서대로 확인합니다."
        meta={
          <>
            <span>KRX 전 종목</span>
            <span>·</span>
            <span>{intraday?.as_of ? `장중 기준 ${intraday.as_of}` : "정산 데이터"}</span>
          </>
        }
      />

      <MarketReadout />

      {active && (
        <div className="segmented-control self-start" aria-label="시장 데이터 시점">
          {(
            [
              ["live", intraday?.is_open ? "장중 흐름" : "오늘 종가"],
              ["settled", "정산 인사이트"],
            ] as [Tab, string][]
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key)}
              aria-pressed={tab === key}
            >
              <span className="inline-flex items-center gap-2">
                {key === "live" && intraday?.is_open && (
                  <span className="h-1.5 w-1.5 rounded-full bg-losses shadow-[0_0_8px_var(--losses)]" aria-hidden />
                )}
                {label}
              </span>
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
