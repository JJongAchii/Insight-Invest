"use client";

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
const koreanDay = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit" });
const dayOf = (stamp: string) => koreanDay.format(new Date(stamp));
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

function Sources({ items, label, timeLabel = "발표" }: { items: DeskArticle["sources"]; label: string; timeLabel?: string }) {
  return <ul className={styles.sources} aria-label={label}>{items.map(src => <li key={src.url}>
    <a href={src.url} target="_blank" rel="noopener noreferrer">{src.title} <ArrowUpRight size={13} aria-hidden /></a>
    <span>{src.publisher} · {timeLabel} {date(src.published_at)} KST
      {src.license_url && <> · <a href={src.license_url} target="_blank" rel="noopener noreferrer">{src.license_name || "출처 이용 조건"}</a></>}
    </span>
  </li>)}</ul>;
}

function IssueBody({ entry }: { entry: DeskArticle }) {
  const verified = entry.kind !== "move" || (entry.status === "analysis" && entry.sources.length > 0);
  return <>
    {!verified && <p className={styles.caution}>원인 미확인</p>}
    {entry.fact !== entry.headline && <PublicationText text={entry.fact} />}
    {verified && entry.interpretation && <div className={styles.section}><h4>{entry.kind === "filing" ? "기업에 미치는 영향" : "해석"}</h4><p>{entry.interpretation}</p></div>}
    {entry.observation && entry.observation !== entry.fact && <p className={styles.meta}>{entry.observation}</p>}
    {entry.observed_at && <p className={styles.meta}>KRX 시세 수집 {date(entry.observed_at)} KST · 원천 약 20분 지연</p>}
    {entry.watch && <div className={styles.section}><h4>다음 확인할 점</h4><p>{entry.watch}</p></div>}
    {entry.sources.length > 0 && <Sources items={entry.sources} label={verified ? "분석 근거" : "앞서 발표된 자료"} />}
    {!!entry.followups?.length && <div className={styles.section}><h4>이후 확인된 관련 자료</h4>
      <Sources items={entry.followups} label="후속 보도와 공시" />
    </div>}
  </>;
}

function EntryList({ entries }: { entries: Entry[] }) {
  return <ul className={styles.feedList}>{entries.map(item => <li key={item.id}>
    <details>
      <summary>{date(item.kind === "move" && item.observed_at ? item.observed_at : item.published_at)}
        <strong>{title(item)}</strong><ChevronDown size={16} aria-hidden /></summary>
      <div className={styles.feedBody}>
        {"body" in item ? <BriefBody entry={item} /> : <IssueBody entry={item} />}
      </div>
    </details>
  </li>)}</ul>;
}

export default function MarketDesk() {
  const { data, error, isLoading, refetch } = useFetchMarketDeskQuery(undefined, refresh);
  const board = data?.board;
  const editions = (board?.issues ?? []).filter(item => item.origin !== "reporter").sort(newestFirst);
  const moves = editions.filter((item): item is DeskArticle & { observed_at: string } => item.kind === "move" && !!item.observed_at);
  const today = data?.today ?? koreanDay.format(new Date());
  // A new day's verified observation takes precedence over a previous session's saved overview.
  const session = data?.session && (dayOf(data.session.observed_at) === today ||
    !moves.some(item => dayOf(item.observed_at) === today)) ? data.session : null;
  const day = session ? dayOf(session.observed_at) : today;
  const sameSession = moves.filter(item => dayOf(item.observed_at) === day)
    .sort((a, b) => Date.parse(b.observed_at) - Date.parse(a.observed_at));
  const explained = sameSession.filter(item => item.status === "analysis" && item.sources.length > 0);
  const observations = sameSession.filter(item => !explained.includes(item));
  const marketReports = (board?.market_reports ?? []).filter(src => session && dayOf(src.published_at) === day &&
    Date.parse(src.published_at) <= Date.parse(session.observed_at) - 20 * 60_000);
  const previous = moves.filter(item => dayOf(item.observed_at) !== day);
  const companyNews = editions.filter(item => item.kind !== "move");
  const latestReport = board && reports(board.issues)[0];
  const policy = session ? data?.policy_coverage ?? [] : [];
  const hasCoverage = marketReports.length > 0 || policy.length > 0;
  return <><section className={styles.desk} aria-labelledby="desk-title">
    <header className={styles.header}>
      <h2 id="desk-title">장중 시장 해설</h2>
      {session && <span className={styles.meta}>
        {data?.session_state === "previous" ? "지난 거래일 기록 · " : data?.session_state === "delayed" ? "수집 지연 · " : ""}
        KRX 수집 {date(session.observed_at)} KST · 시세 약 20분 지연
      </span>}
    </header>
    <div className={hasCoverage ? styles.readingGrid : undefined}><div>
    {session && <article className={styles.article}>
      <h3>{session.headline}</h3>
      <p className={styles.prose}>{session.market}</p>
      {session.sectors && <div className={styles.section}><h4>어느 업종에서 갈렸나</h4><p>{session.sectors}</p></div>}
      {session.watch && <div className={styles.section}><h4>다음 확인할 점</h4><p>{session.watch}</p></div>}
    </article>}
    {explained.length > 0 && <div className={styles.eventBlock}>
      <h3>보도·공시로 확인한 변동 배경</h3>
      <article className={styles.eventArticle}>
        <div className={styles.byline}>변동 관측 {date(explained[0].observed_at)} KST</div>
        <h4>{explained[0].headline}</h4><IssueBody entry={explained[0]} />
      </article>
      {explained.length > 1 && <EntryList entries={explained.slice(1)} />}
    </div>}
    {!session && !explained.length && <p className={styles.empty}>{error || data?.session_state === "unavailable"
      ? <>시장 관측을 불러오지 못했습니다. <button type="button" onClick={() => refetch()}>다시 불러오기</button></>
      : isLoading ? "시장 관측을 불러오는 중입니다."
      : "코스피·코스닥을 같은 시각에 수집한 장중 시황을 기다리고 있습니다."}</p>}
    {(session || sameSession.length > 0) && !explained.length && <p className={styles.cause}>
      <strong>변동 배경</strong> {error || data?.state === "unavailable" ? <>관련 보도·공시를 불러오지 못했습니다. <button onClick={() => refetch()}>다시 불러오기</button></>
        : board ? "최근 관측 구간의 움직임을 직접 설명하는 근거는 아직 확인되지 않았습니다."
        : "관련 보도·공시의 첫 발행본을 기다리고 있습니다."}
    </p>}
    </div>
    {hasCoverage && <aside className={styles.coverage} aria-label="시황 관련 보도">
    {!!marketReports.length && <div className={styles.background}>
      <h3>언론이 짚은 장중 배경</h3>
      <Sources items={marketReports} label="당일 지수 흐름을 설명한 보도" timeLabel="보도" />
    </div>}
    {policy.length > 0 && <div className={styles.background}>
      <h3>같은 날 나온 정책·경제 보도</h3>
      <ul>{policy.map(({ headline, source }) => <li key={source.url + headline}>
        <a href={source.url} target="_blank" rel="noopener noreferrer">{headline} <ArrowUpRight size={13} aria-hidden /></a>
        <span className={styles.meta}>{source.publisher} · 보도 {date(source.published_at)} KST
          {source.license_url && <> · <a href={source.license_url} target="_blank" rel="noopener noreferrer">{source.license_name || "출처 이용 조건"}</a></>}
        </span>
      </li>)}</ul>
    </div>}</aside>}
    </div>
    {observations.length > 0 && <div className={styles.records}><h3>시간대별 변동 기록</h3><EntryList entries={observations} /></div>}
    {board && <footer className={styles.footer}>
      {checked(board.checked_at, !!error || data.state === "stale")}
      <span>DART 확인 {board.filings_at ? date(board.filings_at) : "최근 조회 없음"}{board.monitoring && (!board.filings_at || Date.parse(board.checked_at) - Date.parse(board.filings_at) > 15 * 60_000) && " · 지연"}</span>
    </footer>}
  </section>
    {latestReport && <div className={styles.desk}><Link className={styles.flash} href={`/feed?item=${encodeURIComponent(latestReport.id)}`}>
      <span>최근 속보</span><strong>{latestReport.headline}</strong>{date(latestReport.published_at)}<ArrowRight size={15} aria-hidden />
    </Link></div>}
    {!!board?.briefings.length && <section className={styles.desk} aria-label="아침·마감 브리핑">
      <header className={styles.header}><h2>아침·마감 브리핑</h2></header><EntryList entries={[...board.briefings].sort(newestFirst)} />
    </section>}
    {companyNews.length > 0 && <section className={styles.desk} aria-label="기업 공시·주요 뉴스">
      <header className={styles.header}><h2>기업 공시·주요 뉴스</h2></header><EntryList entries={companyNews} />
    </section>}
    {previous.length > 0 && <section className={styles.desk} aria-label="지난 장중 해설">
      <header className={styles.header}><h2>지난 장중 해설</h2></header><EntryList entries={previous} />
    </section>}
  </>;
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
      {error || data?.state === "unavailable" ? <>속보를 불러오지 못했습니다. <button type="button" onClick={() => refetch()}>다시 불러오기</button></>
        : isLoading ? "최근 속보를 불러오는 중입니다."
        : <>최근 발송된 속보가 없습니다. <Link href="/home#reading">경제 뉴스 보기</Link></>}
    </div>}
  </section>;
}
