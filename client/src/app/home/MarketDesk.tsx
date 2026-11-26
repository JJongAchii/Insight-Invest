"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight, ArrowUpRight, ChevronDown } from "lucide-react";
import { useFetchMarketDeskQuery, type DeskArticle, type DeskBrief } from "@/state/api";
import styles from "./marketDesk.module.css";

const formatTime = new Intl.DateTimeFormat("ko-KR", {
  timeZone: "Asia/Seoul", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
});
type Entry = DeskArticle | DeskBrief;
const refresh = { pollingInterval: 120_000, skipPollingIfUnfocused: true, refetchOnFocus: true };
const newestFirst = (a: Entry, b: Entry) => Date.parse(b.published_at) - Date.parse(a.published_at);
const reports = (issues: DeskArticle[]) => issues.filter(item => item.origin === "reporter").sort(newestFirst);
const date = (stamp: string) => <time dateTime={stamp}>{formatTime.format(new Date(stamp))}</time>;
const checked = (stamp: string, delayed: boolean) => <span className={styles.meta}>
  {delayed ? "갱신 지연 · 마지막 확인 " : "마지막 확인 "}{date(stamp)} KST
</span>;
const edition = (item: Entry) => {
  if (item.kind === "am") return "아침 브리핑";
  if (item.kind === "pm") return "마감 브리핑";
  if (item.kind === "filing") return "기업 공시";
  if (item.kind === "move") return "시세 변화";
  return "주요 뉴스";
};
const title = (item: Entry) => "headline" in item ? item.headline : edition(item);
const decode = (s: string) => s.replaceAll("&lt;", "<").replaceAll("&gt;", ">").replaceAll("&amp;", "&");

function PublicationText({ text }: { text: string }) {
  // Slack's published format contains labelled links and single-asterisk emphasis. Keep text escaped by React.
  return <div className={styles.prose}>{text.split(/(<https?:\/\/[^<>\s|]+(?:\|[^<>]*)?>|\*[^*\n]+\*)/g).map((part, i) => {
    if (part.startsWith("<http") && part.endsWith(">")) {
      const [href, label] = part.slice(1, -1).split("|", 2);
      return <a key={i} href={decode(href)} target="_blank" rel="noopener noreferrer">{decode(label || href)}</a>;
    }
    if (part.startsWith("*") && part.endsWith("*")) return <strong key={i}>{decode(part.slice(1, -1))}</strong>;
    return decode(part);
  })}</div>;
}

function BriefBody({ entry }: { entry: DeskBrief }) {
  const paragraphs = entry.body.trim().split(/\n\s*\n/);
  return <>
    <p className={styles.meta}>자료 기준 {date(entry.as_of)} KST</p>
    <PublicationText text={paragraphs.slice(0, 2).join("\n\n")} />
    {paragraphs.length > 2 && <details className={styles.more}>
      <summary>브리핑 전문 읽기</summary>
      <PublicationText text={paragraphs.slice(2).join("\n\n")} />
    </details>}
  </>;
}

function Sources({ items, label }: { items: DeskArticle["sources"]; label: string }) {
  return <ul className={styles.sources} aria-label={label}>{items.map(src => <li key={src.url}>
    <a href={src.url} target="_blank" rel="noopener noreferrer">{src.title} <ArrowUpRight size={13} aria-hidden /></a>
    <span>{src.publisher} · 발표 {date(src.published_at)} KST
      {src.license_url && <> · <a href={src.license_url} target="_blank" rel="noopener noreferrer">{src.license_name || "출처 이용 조건"}</a></>}
    </span>
  </li>)}</ul>;
}

function IssueBody({ entry }: { entry: DeskArticle }) {
  return <>
    {entry.status === "unconfirmed" && <p className={styles.caution}>원인 미확인</p>}
    {entry.fact !== entry.headline && <PublicationText text={entry.fact} />}
    {entry.interpretation && <div className={styles.section}><h4>{entry.kind === "filing" ? "기업에 미치는 영향" : "시장에 미치는 영향"}</h4><p>{entry.interpretation}</p></div>}
    {entry.observation && entry.observation !== entry.fact && <p className={styles.meta}>{entry.observation}</p>}
    {entry.observed_at && <p className={styles.meta}>KRX 시세 수집 {date(entry.observed_at)} KST · 원천 약 20분 지연</p>}
    {entry.watch && <div className={styles.section}><h4>다음 확인할 점</h4><p>{entry.watch}</p></div>}
    {entry.sources.length > 0 && <Sources items={entry.sources} label="분석 근거" />}
    {!!entry.followups?.length && <div className={styles.section}><h4>이후 확인된 관련 자료</h4>
      <Sources items={entry.followups} label="후속 보도와 공시" />
    </div>}
  </>;
}

export default function MarketDesk() {
  const { data, error, isLoading, refetch } = useFetchMarketDeskQuery(undefined, refresh);
  const [chosen, choose] = useState<string | null>(null);
  const board = data?.board;
  const entries = board ? [...board.issues.filter(item => item.origin !== "reporter"), ...board.briefings].sort(newestFirst) : [];
  const latestReport = board && reports(board.issues)[0];
  const selected = entries.find(item => item.id === chosen) ?? entries[0];
  return <section className={styles.desk} aria-labelledby="desk-title">
    <header className={styles.header}>
      <h2 id="desk-title">장중 시장 해설</h2>
      {board && checked(board.checked_at, !!error || data.state === "stale")}
    </header>
    {latestReport && <Link className={styles.flash} href={`/feed?item=${encodeURIComponent(latestReport.id)}`}>
      <span>최근 속보</span><strong>{latestReport.headline}</strong>{date(latestReport.published_at)}<ArrowRight size={15} aria-hidden />
    </Link>}
    {selected ? <div className={styles.layout}>
      {entries.length > 1 && <nav className={styles.editions} aria-label="최근 해설과 브리핑">
        <h3>최근 해설과 브리핑</h3>
        <select className={styles.chooser} aria-label="읽을 글 선택" value={selected.id} onChange={event => choose(event.target.value)}>
          {entries.map(item => <option key={item.id} value={item.id}>{formatTime.format(new Date(item.published_at))} · {title(item)}</option>)}
        </select>
        {entries.map(item => <button className={styles.edition} key={item.id} type="button" aria-pressed={item.id === selected.id} onClick={() => choose(item.id)}>
          <span>{"headline" in item && `${edition(item)} · `}{date(item.published_at)}</span>{title(item)}
        </button>)}
      </nav>}
      <article key={selected.id} className={styles.article}>
        <div className={styles.byline}>{edition(selected)} <span>발행 {date(selected.published_at)} KST</span></div>
        <h3>{title(selected)}</h3>
        {"body" in selected ? <BriefBody entry={selected} /> : <IssueBody entry={selected} />}
      </article>
    </div> : <div className={styles.empty}>
      {error ? <>발행글을 불러오지 못했습니다. <button type="button" onClick={() => refetch()}>다시 불러오기</button></>
        : isLoading ? "최근 발행글을 불러오는 중입니다."
        : <>{board ? "아직 발행된 해설이 없습니다." : "첫 시장 해설 발행을 기다리고 있습니다."} <a href="#reading">경제 뉴스 보기</a></>}
    </div>}
    {board && <footer className={styles.footer}>
      <span>KRX 수집 {board.market_at ? date(board.market_at) : "확인 전"}{board.monitoring && (!board.market_at || Date.parse(board.checked_at) - Date.parse(board.market_at) > 25 * 60_000) && " · 지연"}</span>
      <span>DART 확인 {board.filings_at ? date(board.filings_at) : "최근 조회 없음"}{board.monitoring && (!board.filings_at || Date.parse(board.checked_at) - Date.parse(board.filings_at) > 15 * 60_000) && " · 지연"}</span>
    </footer>}
  </section>;
}

export function ReporterFeed({ itemId }: { itemId?: string }) {
  const { data, error, isLoading, refetch } = useFetchMarketDeskQuery(undefined, refresh);
  const board = data?.board;
  const entries = board ? reports(board.issues) : [];
  return <section className={styles.desk} aria-labelledby="feed-title">
    <header className={styles.header}>
      <h2 id="feed-title">Slack 발송 속보</h2>
      {board && checked(board.checked_at, !!error || data.state === "stale")}
    </header>
    {entries.length ? <>
      {itemId && !entries.some(item => item.id === itemId) && <p className={styles.empty}>선택한 속보가 최근 발송 목록에서 만료됐습니다.</p>}
      <ul className={styles.feedList}>{entries.map(item => <li key={item.id}>
        <details open={item.id === itemId}>
          <summary>{date(item.published_at)}<strong>{item.headline}</strong><ChevronDown size={16} aria-hidden /></summary>
          <div className={styles.feedBody}><IssueBody entry={item} /></div>
        </details>
      </li>)}</ul>
    </> : <div className={styles.empty}>
      {error ? <>속보를 불러오지 못했습니다. <button type="button" onClick={() => refetch()}>다시 불러오기</button></>
        : isLoading ? "최근 속보를 불러오는 중입니다."
        : <>최근 발송된 속보가 없습니다. <Link href="/home#reading">경제 뉴스 보기</Link></>}
    </div>}
  </section>;
}
