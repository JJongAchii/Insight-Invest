"use client";

import { ChevronDown } from "lucide-react";
import { useFetchMarketDeskQuery, type DeskBrief, type DeskLead } from "@/state/api";
import { NewsPreview } from "../news/NewsFeed";
import MarketMap from "./MarketMap";
import NoteCard from "./NoteCard";
import { PublicationText, Sources, date, dayOf, refresh } from "./deskParts";
import styles from "./marketDesk.module.css";

// 장중 노트를 홈 맨 위에 올리는 스위치. 그림자 운영 동안은 /notes에서만 본다(스펙 2026-11-27 §10).
export const NOTES_ON_HOME = false;
const newestFirst = (a: DeskBrief, b: DeskBrief) => Date.parse(b.published_at) - Date.parse(a.published_at);

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

function EntryList({ entries }: { entries: DeskBrief[] }) {
  return <ul className={styles.feedList}>{entries.map(item => <li key={item.id}>
    <details>
      <summary>{date(item.published_at)}
        <strong>{item.kind === "am" ? "아침 브리핑" : "마감 브리핑"}</strong><ChevronDown size={16} aria-hidden /></summary>
      <div className={styles.feedBody}><BriefBody entry={item} /></div>
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
  const notes = data?.notes ?? [];
  const latest = notes.at(-1);
  const today = data?.today ?? dayOf(new Date());
  // Press reports that explained today's index path stay beside the map until notes take the top of the home.
  const reports = (board?.market_reports ?? []).filter(src => dayOf(src.published_at) === today);
  return <>
    {NOTES_ON_HOME && latest ? <NoteCard note={latest} since={data?.since_note ?? null} earlier={notes.slice(0, -1)} />
      : data?.lead ? <SessionLead lead={data.lead} /> : null}
    <MarketMap map={data?.map} reports={reports} failed={!!error} loading={isLoading} retry={() => void refetch()} />
    {!!board?.briefings.length && <section className={styles.desk} aria-label="아침·마감 브리핑">
      <header className={styles.header}><h2>아침·마감 브리핑</h2></header><EntryList entries={[...board.briefings].sort(newestFirst)} />
    </section>}
    <NewsPreview />
  </>;
}
