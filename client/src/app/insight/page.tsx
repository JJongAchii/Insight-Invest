"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { InsightMarket, useFetchIntradayMarketQuery } from "@/state/api";
import PageHeader from "@/components/ui/PageHeader";
import LoadingState from "@/components/ui/LoadingState";
import IndexBreadthStrip from "./IndexBreadthStrip";
import FlowsSection from "./FlowsSection";
import SectorSection from "./SectorSection";
import FactorSection from "./FactorSection";
import ValuationSection from "./ValuationSection";
import SignalsSection from "./SignalsSection";
import BreadthHistory from "./BreadthHistory";
import IntradayTab from "./intraday/IntradayTab";
import MarketReadout from "./MarketReadout";

const SECTIONS = [
  {
    id: "overview",
    label: "지수 · 시장폭",
    description: "지수 움직임에 얼마나 많은 종목이 동참하는지 확인합니다.",
  },
  {
    id: "flows",
    label: "투자자 수급",
    description:
      "외국인과 기관의 자금 흐름, 순매수·순매도 상위 종목을 비교합니다.",
  },
  {
    id: "sectors",
    label: "섹터 · 테마",
    description: "업종과 테마의 강약을 비교하고, 구성 종목에서 가격·수급의 근거를 확인합니다.",
  },
  {
    id: "factors",
    label: "팩터",
    description: "시장 수익률을 이끄는 종목 특성을 확인합니다.",
  },
  {
    id: "valuation",
    label: "밸류에이션",
    description: "현재 가격 수준을 과거 분포와 비교합니다.",
  },
  {
    id: "signals",
    label: "수급 신호",
    description: "연속 매수와 수급 강도, 가격과 수급의 엇갈림을 탐색합니다.",
  },
];

function InsightContent() {
  const params = useSearchParams();
  const { data: intraday } = useFetchIntradayMarketQuery(undefined, {
    pollingInterval: 5 * 60 * 1000,
    skipPollingIfUnfocused: true,
  });
  const market: InsightMarket =
    params.get("market") === "KOSDAQ" ? "KOSDAQ" : "KOSPI";
  const selected =
    SECTIONS.find((section) => section.id === params.get("section")) ??
    SECTIONS[0];
  const requestedTab = params.get("tab");
  const live =
    requestedTab === "intraday" ||
    requestedTab === "live" ||
    (!requestedTab &&
      !params.has("section") &&
      intraday?.active &&
      intraday.is_open);
  const showLive = Boolean(live && intraday?.active);
  const updateView = (values: Record<string, string>) => {
    const url = new URL(window.location.href);
    Object.entries(values).forEach(([key, value]) =>
      url.searchParams.set(key, value),
    );
    window.history.pushState(null, "", url);
  };
  const changeMarket = (value: InsightMarket) => updateView({ market: value });

  return (
    <div className="flex flex-col gap-6 pb-10">
      <PageHeader
        title="한국 시장"
        description="지수와 시장 참여를 먼저 보고, 관심 있는 분석으로 이동하세요."
        meta={
          <>
            <span>KRX 전 종목</span>
            <span>·</span>
            <span>장중 스냅샷과 정산 데이터를 구분합니다</span>
          </>
        }
      />
      <MarketReadout />
      <div className="flex flex-col gap-4">
        <div
          className="segmented-control self-start"
          aria-label="시장 데이터 시점"
        >
          <button
            type="button"
            aria-pressed={!showLive}
            onClick={() => updateView({ tab: "settled" })}
          >
            정산 분석
          </button>
          <button
            type="button"
            aria-pressed={showLive}
            disabled={!intraday?.active}
            onClick={() => updateView({ tab: "intraday" })}
          >
            {intraday?.is_open ? "장중 흐름 · 지연" : "최근 장중 스냅샷"}
          </button>
        </div>
        {live && intraday && !intraday.active && (
          <p className="text-xs text-ink-muted">
            장중 스냅샷이 없어 정산 데이터를 표시합니다.
          </p>
        )}
        {showLive && intraday ? (
          <IntradayTab data={intraday} />
        ) : (
          <>
            <nav className="flex flex-wrap gap-2" aria-label="시장 분석 항목">
              {SECTIONS.map((section) => (
                <button
                  type="button"
                  key={section.id}
                  className="filter-chip"
                  aria-pressed={selected.id === section.id}
                  onClick={() =>
                    updateView({ tab: "settled", section: section.id })
                  }
                >
                  {section.label}
                </button>
              ))}
            </nav>
            <section className="space-y-5" aria-label={selected.label}>
              <p className="text-sm leading-6 text-ink-secondary">
                {selected.description}
              </p>
              {selected.id === "overview" && (
                <>
                  <IndexBreadthStrip
                    market={market}
                    onMarketChange={changeMarket}
                  />
                  <BreadthHistory
                    market={market}
                    onMarketChange={changeMarket}
                  />
                </>
              )}
              {selected.id === "flows" && <FlowsSection />}
              {selected.id === "sectors" && <SectorSection />}
              {selected.id === "factors" && <FactorSection />}
              {selected.id === "valuation" && <ValuationSection />}
              {selected.id === "signals" && <SignalsSection />}
            </section>
          </>
        )}
      </div>
    </div>
  );
}

export default function InsightPage() {
  return (
    <Suspense fallback={<LoadingState label="시장 화면을 준비하는 중…" />}>
      <InsightContent />
    </Suspense>
  );
}
