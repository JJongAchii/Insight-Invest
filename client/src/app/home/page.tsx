"use client";

import { ChartNoAxesCombined, ChevronDown, FlaskConical } from "lucide-react";
import { useMemo, useState } from "react";

import TradingViewWidget from "@/app/(components)/TradingViewWidget";
import { useAppSelector } from "@/app/redux";
import DecisionBrief from "./DecisionBrief";
import FlowsTopCard from "./FlowsTopCard";
import MarketTiles from "./MarketTiles";
import NewsBriefingCard from "./NewsBriefingCard";
import PortfolioCard from "./PortfolioCard";
import SpotlightLane from "./SpotlightLane";
import StrategiesCard from "./StrategiesCard";
import WatchlistCard from "./WatchlistCard";

export default function Home() {
  const isDarkMode = useAppSelector((state) => state.global.isDarkMode);
  const [marketToolsOpen, setMarketToolsOpen] = useState(false);
  const [researchToolsOpen, setResearchToolsOpen] = useState(false);
  const colorTheme = isDarkMode ? "dark" : "light";
  const tickerTapeUrl =
    "https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js";
  const tickerTapeConfig = useMemo(
    () => ({
      symbols: [
        { proName: "BITSTAMP:BTCUSD", title: "Bitcoin" },
        { description: "NASDAQ 100 Index", proName: "NASDAQ:NDX" },
        { description: "U.S. Dollar Index", proName: "CAPITALCOM:DXY" },
        { description: "S&P 500 Index", proName: "VANTAGE:SP500" },
        { description: "GOLD", proName: "OANDA:XAUUSD" },
        { description: "WTI CRUDE OIL", proName: "TVC:USOIL" },
        { description: "USD/KRW", proName: "FX_IDC:USDKRW" },
        { description: "USD/JPY", proName: "FX:USDJPY" },
        { description: "USD/CNY", proName: "FX_IDC:USDCNY" },
      ],
      showSymbolLogo: true,
      isTransparent: false,
      displayMode: "compact",
      colorTheme,
      locale: "en",
      scroll: true,
    }),
    [colorTheme]
  );

  return (
    <div className="pb-10">
      <DecisionBrief />
      <PortfolioCard />

      <section className="mb-8" aria-labelledby="connected-change-title">
        <header className="mb-4">
          <h2
            id="connected-change-title"
            className="text-lg font-semibold tracking-[-0.02em] text-ink"
          >
            판단과 연결된 변화
          </h2>
          <p className="mt-1 text-xs text-ink-muted">
            보유·관심 자산과 연결된 가격 변화와 소식만 먼저 봅니다.
          </p>
        </header>
        <div className="grid grid-cols-1 items-start gap-5 xl:grid-cols-2">
          <WatchlistCard />
          <NewsBriefingCard />
        </div>
      </section>

      <div className="space-y-4">
        <details
          className="group overflow-hidden rounded-2xl border border-edge bg-surface/60"
          onToggle={(event) => setMarketToolsOpen(event.currentTarget.open)}
        >
          <summary className="flex cursor-pointer list-none items-center gap-3 px-5 py-4 text-sm font-semibold text-ink transition-colors hover:bg-raised/60 [&::-webkit-details-marker]:hidden">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-edge bg-raised text-secondary-400">
              <ChartNoAxesCombined size={16} aria-hidden />
            </span>
            시장 데이터 더 보기
            <span className="ml-1 text-xs font-normal text-ink-muted">
              지수 · 수급 · 글로벌 티커
            </span>
            <ChevronDown
              size={16}
              className="ml-auto text-ink-muted transition-transform group-open:rotate-180"
              aria-hidden
            />
          </summary>
          {marketToolsOpen && (
            <div className="space-y-5 border-t border-edge p-5">
              <MarketTiles />
              <FlowsTopCard />
              <div className="overflow-hidden rounded-xl border border-edge">
                <TradingViewWidget
                  key={`tape-${colorTheme}`}
                  widgetScriptUrl={tickerTapeUrl}
                  widgetConfig={tickerTapeConfig}
                />
              </div>
            </div>
          )}
        </details>

        <details
          className="group overflow-hidden rounded-2xl border border-edge bg-surface/60"
          onToggle={(event) => setResearchToolsOpen(event.currentTarget.open)}
        >
          <summary className="flex cursor-pointer list-none items-center gap-3 px-5 py-4 text-sm font-semibold text-ink transition-colors hover:bg-raised/60 [&::-webkit-details-marker]:hidden">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-edge bg-raised text-[color:var(--primary)]">
              <FlaskConical size={16} aria-hidden />
            </span>
            리서치 도구 열기
            <span className="ml-1 text-xs font-normal text-ink-muted">
              후보 탐색 · 저장 전략
            </span>
            <ChevronDown
              size={16}
              className="ml-auto text-ink-muted transition-transform group-open:rotate-180"
              aria-hidden
            />
          </summary>
          {researchToolsOpen && (
            <div className="space-y-5 border-t border-edge p-5">
              <SpotlightLane />
              <StrategiesCard />
            </div>
          )}
        </details>
      </div>
    </div>
  );
}
