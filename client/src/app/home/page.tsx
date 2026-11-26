"use client";

import {
  ArrowUpRight,
  CalendarDays,
  ChevronDown,
  Globe2,
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
import NewsBriefingCard from "./NewsBriefingCard";
import ResearchPreview from "./ResearchPreview";
import PortfolioCard from "./PortfolioCard";
import WatchlistCard from "./WatchlistCard";
import StrategiesCard from "./StrategiesCard";
import SpotlightLane from "./SpotlightLane";
import styles from "./marketBriefing.module.css";
import { useFetchIpoQuery } from "@/state/api";

export default function Home() {
  const [personalOpen, setPersonalOpen] = useState(false);
  const ipo = useFetchIpoQuery();
  const session = ipo.data?.status?.next_session;
  const reliable = session && !ipo.error && !ipo.data?.status?.stale && !ipo.data?.status?.problems?.length && ipo.data?.open;
  const signals = ipo.data?.open?.filter(row => row.position === "signal" && row.listing_date === session).length;

  return (
    <div className={styles.page}>
      <header className={styles.masthead}>
        <div>
          <h1>시장 브리핑</h1>
          <Link className={styles.ipoLink} href="/ipo">
            공모주 신호
            {reliable ? <span>{session.slice(5).replace("-", "/")} 매수 {signals ? `${signals}건` : "없음"}</span>
              : <span>{ipo.isLoading ? "확인 중" : "산출 상태 확인"}</span>}
            <ArrowUpRight size={14} aria-hidden />
          </Link>
        </div>
        <Link href="/data-trust" className={styles.textLink}>
          출처와 데이터 상태 <ArrowUpRight size={15} aria-hidden />
        </Link>
      </header>
      <MarketDesk />
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
