"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { useMemo } from "react";
import {
  useFetchDeskNewsQuery,
  type DeskArticle, type DeskNewsItem, type MapMarket, type MapStock, type MarketMap as MarketMapData,
} from "@/state/api";
import { Sources, dayOf, refresh } from "./deskParts";
import styles from "./marketMap.module.css";

const NAMES = { KOSPI: "코스피", KOSDAQ: "코스닥" } as const;
const clock = new Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
const day = new Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", month: "numeric", day: "numeric" });

export const signed = (value: number, digits = 2) => `${value > 0 ? "+" : ""}${value.toFixed(digits)}`;
export const tone = (value: number | null | undefined) => (value == null || value === 0 ? undefined : value > 0 ? styles.up : styles.down);
export const collected = (stamp: string) => clock.format(new Date(stamp));
const won = (value: number) => `${Math.round(value / 1e8).toLocaleString("ko-KR")}억`;

function basis(map: MarketMapData) {
  const at = map.observed_at ? collected(map.observed_at) : "";
  if (map.state === "delayed") return `시세 수집 지연 · 마지막 KRX ${at}`;
  if (map.state === "closed") return `장 마감 · KRX ${at} 기준`;
  if (map.state === "previous") return `지난 거래일 ${map.observed_at ? day.format(new Date(map.observed_at)) : ""} 기준`;
  return `KRX ${at} 수집 · 약 20분 지연`;
}

type Mentions = Map<string, { count: number; id: string }>;

/** 그날 제목에 종목명이 나온 뉴스·공시 수와 가장 최근 글. 긴 이름부터 찾아 지우므로 '삼성전자우' 기사는 '삼성전자'로 세지 않는다. */
export function mentionsOf(items: DeskNewsItem[], names: string[], tradeDate: string): Mentions {
  const longest = [...new Set(names)].filter(name => name.length >= 2).sort((a, b) => b.length - a.length);
  const found: Mentions = new Map();
  for (const item of items) {
    if (dayOf(item.published_at) !== tradeDate) continue;
    let text = `${item.title} ${item.headline}`;
    for (const name of longest) {
      if (!text.includes(name)) continue;
      text = text.split(name).join(" ");
      const seen = found.get(name);
      // The list is newest first, so the first article found is the one to open.
      found.set(name, seen ? { ...seen, count: seen.count + 1 } : { count: 1, id: item.id });
    }
  }
  return found;
}

function Name({ stock, mentions }: { stock: MapStock; mentions: Mentions }) {
  const found = mentions.get(stock.name);
  return <span className={styles.name}>
    <span>{stock.name}</span>
    {found && <Link className={styles.mention} href={`/news?item=${encodeURIComponent(found.id)}`}
      aria-label={`${stock.name} 오늘 기사 ${found.count}건 · 최근 기사 열기`}>기사 {found.count}</Link>}
  </span>;
}

function Movers({ title, rows, mentions }: { title: string; rows: MapStock[]; mentions: Mentions }) {
  if (!rows.length) return null;
  return <div>
    <h4>{title}</h4>
    <ul className={styles.rows}>{rows.map(stock => <li key={stock.ticker}>
      <Name stock={stock} mentions={mentions} />
      <span className={tone(stock.chg_pct)}>{signed(stock.chg_pct)}%</span>
      <span className={styles.contrib}>{signed(stock.contrib_pp ?? 0)}%p</span>
    </li>)}</ul>
  </div>;
}

function Breadth({ name, market }: { name: string; market: MapMarket }) {
  const b = market.breadth;
  const limits = b.limit_up.map(s => s.name);
  return <p className={styles.breadth}>
    <b>{name}</b> 상승 {b.up.toLocaleString("ko-KR")} · 하락 {b.down.toLocaleString("ko-KR")} · 보합 {b.flat.toLocaleString("ko-KR")}
    {b.up10 > 0 && <> · +10% 이상 {b.up10}</>}{b.down10 > 0 && <> · −10% 이하 {b.down10}</>}
    {market.top10_share != null && <span className={styles.note}> · 지수 움직임의 {Math.round(market.top10_share * 100)}%가 상위 10종목</span>}
    {limits.length > 0 && <><br /><span className={styles.note}>상한가 {limits.length}: {limits.slice(0, 6).join(", ")}{limits.length > 6 ? " 외" : ""}</span></>}
  </p>;
}

/** 지금 시장: 지수를 움직인 종목, 오르고 내린 종목 수, 같이 움직인 테마, 평소보다 거래가 몰린 종목. 모델 없이 10분마다. */
export default function MarketMap({ map, reports, failed, loading, retry }: {
  map?: MarketMapData; reports: DeskArticle["sources"]; failed: boolean; loading: boolean; retry: () => void;
}) {
  const ready = map && map.markets && map.indices;
  const { data: news } = useFetchDeskNewsQuery(undefined, refresh);
  const mentions = useMemo(() => {
    if (!map?.markets || !map.trade_date) return new Map() as Mentions;
    const shown = [
      ...(["KOSPI", "KOSDAQ"] as const).flatMap(key => [
        ...map.markets![key].contributors.up.slice(0, 3), ...map.markets![key].contributors.down.slice(0, 2)]),
      ...(map.value_spikes ?? []),
    ];
    return mentionsOf(news?.items ?? [], shown.map(stock => stock.name), map.trade_date);
  }, [map, news]);
  return <section className={styles.card} aria-labelledby="market-map-title">
    <header className={styles.header}>
      <h2 id="market-map-title">지금 시장</h2>
      {ready && <span className={styles.meta} data-state={map.state}>{basis(map)}</span>}
      <Link className={styles.link} href="/insight?tab=intraday">장중 전체 <ArrowRight size={13} aria-hidden /></Link>
    </header>
    {!ready ? <p className={styles.empty}>
      {failed || map?.state === "unavailable" ? <>시장 지도를 불러오지 못했습니다. <button type="button" onClick={retry}>다시 불러오기</button></>
        : loading ? "시장 지도를 불러오는 중입니다."
        : "장이 열리면 KRX 시세로 지수를 움직인 종목과 시장 폭을 10분마다 보여드립니다."}
    </p> : <>
      <div className={styles.indices}>{(["KOSPI", "KOSDAQ"] as const).map(key => {
        const index = map.indices![key];
        return <div className={styles.index} key={key}>
          <span>{NAMES[key]}</span>
          <strong>{index?.level != null ? index.level.toLocaleString("ko-KR", { maximumFractionDigits: 2 }) : "—"}</strong>
          {index?.chg_pct != null && <em className={tone(index.chg_pct)}>{signed(index.chg_pct)}%</em>}
        </div>;
      })}</div>
      <div className={styles.block}>
        <h3>지수를 움직인 종목</h3>
        <div className={styles.pair}>{(["KOSPI", "KOSDAQ"] as const).map(key => {
          const contributors = map.markets![key].contributors;
          return <div key={key}>
            <Movers title={`${NAMES[key]} 끌어올린 종목`} rows={contributors.up.slice(0, 3)} mentions={mentions} />
            <Movers title={`${NAMES[key]} 끌어내린 종목`} rows={contributors.down.slice(0, 2)} mentions={mentions} />
          </div>;
        })}</div>
      </div>
      <div className={styles.block}>
        <h3>오르고 내린 종목 수</h3>
        {(["KOSPI", "KOSDAQ"] as const).map(key => <Breadth key={key} name={NAMES[key]} market={map.markets![key]} />)}
      </div>
      {!!map.groups?.length && <div className={styles.block}>
        <h3>같이 움직인 테마</h3>
        <div className={styles.chips}>{map.groups.map(group => <span className={styles.chip} key={`${group.id}-${group.direction}`}>
          <b>{group.name}</b> {group.members.length}종목 {group.direction === "up" ? "+7% 이상" : "−7% 이하"}{" "}
          <span>{group.members.slice(0, 3).map(m => `${m.name} ${signed(m.chg_pct, 1)}%`).join(" · ")}</span>
        </span>)}</div>
      </div>}
      {map.value_spikes_state === "ready" && !!map.value_spikes?.length && <div className={styles.block}>
        <h3>평소보다 거래가 몰린 종목</h3>
        <ul className={styles.rows}>{map.value_spikes.map(stock => <li key={stock.ticker}>
          <Name stock={stock} mentions={mentions} />
          <span className={tone(stock.chg_pct)}>{signed(stock.chg_pct)}%</span>
          <span className={styles.contrib}>{won(stock.value)} · 평소 하루치의 {stock.multiple?.toFixed(1)}배</span>
        </li>)}</ul>
      </div>}
      {reports.length > 0 && <div className={styles.block}>
        <h3>시황 기사</h3>
        <Sources items={reports} label="지수 흐름을 설명한 기사" timeLabel="보도" />
      </div>}
    </>}
  </section>;
}
