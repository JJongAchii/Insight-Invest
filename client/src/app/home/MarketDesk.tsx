"use client";

import { ArrowUpRight, ChevronDown } from "lucide-react";
import { useFetchMarketDeskQuery, type DeskArticle, type DeskBrief, type DeskLead } from "@/state/api";
import { NewsPreview } from "../news/NewsFeed";
import { PublicationText, Sources, checked, date, dayOf, refresh } from "./deskParts";
import styles from "./marketDesk.module.css";

// 이 화면의 글은 지수·업종 변동 해설과 아침·마감 브리핑이다. 뉴스와 공시는 주요 뉴스 목록이 맡는다.
type Entry = DeskArticle | DeskBrief;
const newestFirst = (a: Entry, b: Entry) => Date.parse(b.published_at) - Date.parse(a.published_at);
const title = (item: Entry) => "headline" in item ? item.headline : item.kind === "am" ? "아침 브리핑" : "마감 브리핑";

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

function IssueBody({ entry }: { entry: DeskArticle }) {
  const verified = entry.status === "analysis" && entry.sources.length > 0;
  return <>
    {!verified && <p className={styles.caution}>원인 미확인</p>}
    {entry.fact !== entry.headline && <PublicationText text={entry.fact} />}
    {verified && entry.interpretation && <div className={styles.section}><h4>해석</h4><p>{entry.interpretation}</p></div>}
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

function SessionLead({ lead }: { lead: DeskLead }) {
  const closed = lead.phase === "close";
  const comparison = lead.comparison;
  const originals = [...new Map([...lead.reading.sources, ...lead.qualification.sources].map(src => [src.url, src])).values()];
  return <section className={styles.desk} aria-labelledby="lead-title">
    <header className={styles.header}>
      <h2 id="lead-title">{closed ? "한국 증시 마감 해설" : "한국 증시 장중 해설"}</h2>
      <span className={styles.meta}>{date(lead.as_of)} KST 시황 보도 기준</span>
    </header>
    <article className={styles.lead}>
      <h3>{lead.headline}</h3>
      {comparison && <div className={styles.comparison}>
        <strong>{comparison.share_pct.toLocaleString("ko-KR", { maximumFractionDigits: 1 })}%</strong>
        <span>{comparison.index}가 전날 {comparison.previous_points < 0 ? "낙폭에서 되찾은 비율" : "상승분에서 반납한 비율"}
          <small>전날 {Math.abs(comparison.previous_points).toLocaleString("ko-KR")}포인트 {comparison.previous_points < 0 ? "하락" : "상승"}
          {" · "}오늘 {Math.abs(comparison.current_points).toLocaleString("ko-KR")}포인트 {comparison.current_points > 0 ? "상승" : "하락"}</small>
        </span>
      </div>}
      <div className={styles.argument}>{[lead.reading, lead.qualification].map((passage, i) => <p key={i}>{passage.text}{" "}
        {passage.sources.map(src => <sup key={src.url}><a href={src.url} target="_blank" rel="noopener noreferrer"
          aria-label={`${src.publisher} 원문 · ${src.title}`}>[{originals.findIndex(ref => ref.url === src.url) + 1}]</a></sup>)}
      </p>)}</div>
      <div className={styles.nextCheck}><h4>{closed ? "다음 거래일에 볼 것" : "남은 장에서 볼 것"}</h4><p>{lead.watch}</p></div>
      <details className={styles.more}>
        <summary>근거 원문 {originals.length}건</summary>
        <Sources items={originals} label="시장 해설의 근거 원문" timeLabel="보도" />
        <p className={styles.meta}>작성 자료 마감 {date(lead.cutoff)} · 발행 {date(lead.published_at)} KST</p>
      </details>
    </article>
  </section>;
}

export default function MarketDesk() {
  const { data, error, isLoading, refetch } = useFetchMarketDeskQuery(undefined, refresh);
  const board = data?.board;
  const moves = (board?.issues ?? []).filter((item): item is DeskArticle & { observed_at: string } =>
    item.origin !== "reporter" && item.kind === "move" && !!item.observed_at).sort(newestFirst);
  const today = data?.today ?? dayOf(new Date());
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
  const policy = session ? data?.policy_coverage ?? [] : [];
  const observationsSection = <section className={styles.desk} aria-labelledby="desk-title">
    <header className={styles.header}>
      <h2 id="desk-title">장중 시장 해설</h2>
      {session && <span className={styles.meta}>
        {data?.session_state === "previous" ? "지난 거래일 기록 · " : data?.session_state === "delayed" ? "수집 지연 · " : ""}
        KRX 수집 {date(session.observed_at)} KST · 시세 약 20분 지연
      </span>}
    </header>
    <div className={policy.length ? styles.readingGrid : undefined}><div>
    {session && <article className={styles.article}>
      <h3>{session.headline}</h3>
      <p className={styles.prose}>{session.market}</p>
      {marketReports.length > 0 && <div className={styles.section}>
        <h4>언론이 짚은 장중 배경</h4>
        <Sources items={marketReports} label="당일 지수 흐름을 설명한 보도" timeLabel="보도" />
      </div>}
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
    {policy.length > 0 && <aside className={styles.coverage} aria-label="정책·경제 보도">
      <div className={styles.background}>
      <h3>같은 날 나온 정책·경제 보도</h3>
      <ul>{policy.map(({ headline, source }) => <li key={source.url + headline}>
        <a href={source.url} target="_blank" rel="noopener noreferrer">{headline} <ArrowUpRight size={13} aria-hidden /></a>
        <span className={styles.meta}>{source.publisher} · 보도 {date(source.published_at)} KST
          {source.license_url && <> · <a href={source.license_url} target="_blank" rel="noopener noreferrer">{source.license_name || "출처 이용 조건"}</a></>}
        </span>
      </li>)}</ul>
      </div>
    </aside>}
    </div>
    {observations.length > 0 && <div className={styles.records}><h3>시간대별 변동 기록</h3><EntryList entries={observations} /></div>}
    {board && <footer className={styles.footer}>
      {checked(board.checked_at, !!error || data.state === "stale")}
      <span>DART 확인 {board.filings_at ? date(board.filings_at) : "최근 조회 없음"}{board.monitoring && (!board.filings_at || Date.parse(board.checked_at) - Date.parse(board.filings_at) > 15 * 60_000) && " · 지연"}</span>
    </footer>}
  </section>;
  return <>
    {data?.lead ? <>
      <SessionLead lead={data.lead} />
      <details className={styles.observations}><summary>장중 시세와 관련 보도 <ChevronDown size={16} aria-hidden /></summary>
        {observationsSection}
      </details>
    </> : observationsSection}
    {!!board?.briefings.length && <section className={styles.desk} aria-label="아침·마감 브리핑">
      <header className={styles.header}><h2>아침·마감 브리핑</h2></header><EntryList entries={[...board.briefings].sort(newestFirst)} />
    </section>}
    <NewsPreview />
    {previous.length > 0 && <section className={styles.desk} aria-label="지난 장중 해설">
      <header className={styles.header}><h2>지난 장중 해설</h2></header><EntryList entries={previous} />
    </section>}
  </>;
}
