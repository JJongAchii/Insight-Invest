"use client";

import {
  CalendarDays,
  ChevronDown,
  ChevronRight,
  Globe2,
  Rocket,
  Search,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { personalNavigation } from "@/lib/navigation";
import MarketOverview from "./MarketOverview";
import MarketDesk from "./MarketDesk";
import FlowsTopCard from "./FlowsTopCard";
import MarketTiles from "./MarketTiles";
import MacroSnapshot from "./MacroSnapshot";
import ResearchPreview from "./ResearchPreview";
import PortfolioCard from "./PortfolioCard";
import WatchlistCard from "./WatchlistCard";
import StrategiesCard from "./StrategiesCard";
import SpotlightLane from "./SpotlightLane";
import styles from "./marketBriefing.module.css";
import { useFetchIpoQuery } from "@/state/api";

export default function Home() {
  const [personalOpen, setPersonalOpen] = useState(false);
  const [marketOpen, setMarketOpen] = useState(false);
  const ipo = useFetchIpoQuery();
  const status = ipo.data?.status;
  const session = status?.next_session;
  const missingDecision = status?.calendar?.some(row => row.planned_listing_date === session && row.decision_missing);
  const reliable = session && !ipo.error && !status?.stale && !status?.problems?.length && !missingDecision && ipo.data?.open;
  const signals = ipo.data?.open?.filter(row => row.position === "signal" && row.listing_date === session).length;

  return (
    <div className={styles.page}>
      <header className={styles.masthead}>
        <h1>시장 브리핑</h1>
        <Link className={styles.ipoLink} href="/ipo" data-signal={Boolean(reliable && signals)}>
          <Rocket size={16} aria-hidden /> 공모주 신호
          <strong>{reliable ? `${session.slice(5).replace("-", "/")} 매수 ${signals ? `${signals}건` : "없음"}`
            : ipo.isLoading ? "확인 중" : "산출 상태 확인"}</strong>
          <ChevronRight size={15} aria-hidden />
        </Link>
      </header>
      <MarketDesk />
      <details className={styles.marketDetails} onToggle={event => setMarketOpen(event.currentTarget.open)}>
        <summary>시장 지표와 수급 <ChevronDown size={17} aria-hidden /></summary>
        {marketOpen && <div className={styles.marketContents}>
          <section className={styles.quoteBoard} aria-label="주요 지수와 경제 지표">
            <MarketTiles />
            <MacroSnapshot />
          </section>
          <MarketOverview />
          <FlowsTopCard />
          <SpotlightLane />
          <nav className={styles.jumpLinks} aria-label="분석 바로가기">
            <Link href="/regime"><Globe2 size={15} aria-hidden /> 경제 지표</Link>
            <Link href="/earnings"><CalendarDays size={15} aria-hidden /> 실적 일정</Link>
            <Link href="/stocksearch"><Search size={15} aria-hidden /> 종목 비교</Link>
          </nav>
        </div>}
      </details>
      <section className={styles.reading} aria-label="최신 리서치">
        <ResearchPreview />
      </section>
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
