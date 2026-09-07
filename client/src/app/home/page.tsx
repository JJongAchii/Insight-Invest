"use client";

import {
  ArrowUpRight,
  CalendarDays,
  ChevronDown,
  Globe2,
  Search,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import TradingViewWidget from "@/app/(components)/TradingViewWidget";
import { useAppSelector } from "@/app/redux";
import { personalNavigation } from "@/lib/navigation";
import MarketOverview from "./MarketOverview";
import FlowsTopCard from "./FlowsTopCard";
import MarketTiles from "./MarketTiles";
import MacroSnapshot from "./MacroSnapshot";
import NewsBriefingCard from "./NewsBriefingCard";
import ResearchPreview from "./ResearchPreview";
import PortfolioCard from "./PortfolioCard";
import WatchlistCard from "./WatchlistCard";
import StrategiesCard from "./StrategiesCard";
import SpotlightLane from "./SpotlightLane";
import styles from "./marketBriefing.module.css";

export default function Home() {
  const isDarkMode = useAppSelector((state) => state.global.isDarkMode);
  const [globalOpen, setGlobalOpen] = useState(false);
  const [personalOpen, setPersonalOpen] = useState(false);
  const colorTheme = isDarkMode ? "dark" : "light";
  const tickerTapeConfig = useMemo(
    () => ({
      symbols: [
        { description: "S&P 500", proName: "VANTAGE:SP500" },
        { description: "NASDAQ 100", proName: "NASDAQ:NDX" },
        { description: "달러 인덱스", proName: "CAPITALCOM:DXY" },
        { description: "금", proName: "OANDA:XAUUSD" },
        { description: "WTI", proName: "TVC:USOIL" },
        { description: "USD/JPY", proName: "FX:USDJPY" },
        { proName: "BITSTAMP:BTCUSD", title: "Bitcoin" },
      ],
      showSymbolLogo: false,
      isTransparent: false,
      displayMode: "compact",
      colorTheme,
      locale: "kr",
      scroll: true,
    }),
    [colorTheme],
  );

  return (
    <div className={styles.page}>
      <header className={styles.masthead}>
        <div>
          <h1>시장 브리핑</h1>
          <p>지금의 시장 흐름에서 경제의 변화, 더 읽어볼 연구까지.</p>
        </div>
        <Link href="/data-trust" className={styles.textLink}>
          출처와 데이터 상태 <ArrowUpRight size={15} aria-hidden />
        </Link>
      </header>
      <nav className={styles.jumpLinks} aria-label="분석 바로가기">
        <Link href="/regime">
          <Globe2 size={15} aria-hidden />
          경제 지표
        </Link>
        <Link href="/earnings">
          <CalendarDays size={15} aria-hidden />
          실적 일정
        </Link>
        <Link href="/stocksearch">
          <Search size={15} aria-hidden />
          종목 비교
        </Link>
        <a href="#reading">
          뉴스 · 리서치 <ChevronDown size={14} aria-hidden />
        </a>
      </nav>
      <section className={styles.quoteBoard} aria-label="주요 지수와 경제 지표">
        <MarketTiles />
        <MacroSnapshot />
      </section>
      <MarketOverview />
      <section
        id="reading"
        className={styles.readingGrid}
        aria-label="경제 뉴스와 최신 리서치"
      >
        <NewsBriefingCard />
        <ResearchPreview />
      </section>
      <FlowsTopCard />
      <SpotlightLane />
      <details
        className={styles.globalTape}
        onToggle={(event) => setGlobalOpen(event.currentTarget.open)}
      >
        <summary>
          <Globe2 size={16} aria-hidden />
          글로벌 지수 · 원자재<span>TradingView 제공</span>
          <ChevronDown size={14} aria-hidden />
        </summary>
        {globalOpen && (
          <>
            <p className="px-5 pb-3 text-xs text-ink-muted">
              외부 시세로, 거래소와 종목에 따라 지연될 수 있습니다.
            </p>
            <TradingViewWidget
              key={colorTheme}
              widgetScriptUrl="https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js"
              widgetConfig={tickerTapeConfig}
            />
          </>
        )}
      </details>
      <details
        className={styles.personalTools}
        onToggle={(event) => setPersonalOpen(event.currentTarget.open)}
      >
        <summary>
          개인 투자 도구<span>포트폴리오 · 기록 · 백테스트</span>
          <ChevronDown size={14} aria-hidden />
        </summary>
        <nav aria-label="개인 투자 도구">
          {personalNavigation.map((item) => (
            <Link href={item.href} key={item.href}>
              {item.label}
            </Link>
          ))}
        </nav>
        {personalOpen && (
          <div className="space-y-5">
            <PortfolioCard />
            <WatchlistCard />
            <StrategiesCard />
          </div>
        )}
      </details>
    </div>
  );
}
