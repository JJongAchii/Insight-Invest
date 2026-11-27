"use client";

import type { DeskArticle, DeskNote, EvidenceLabel, SinceNote } from "@/state/api";
import { Sources } from "./deskParts";
import { collected, signed, tone } from "./MarketMap";
import styles from "./marketMap.module.css";

const INDEX = { KOSPI: "코스피", KOSDAQ: "코스닥" } as Record<string, string>;
const SLOT = { open: "개장", morning: "오전", afternoon: "오후", preclose: "마감 전", close: "마감" } as const;

function Evidence({ label, sources }: { label: EvidenceLabel; sources: DeskArticle["sources"] }) {
  return <>
    <span className={styles.label} data-label={label}>{label}</span>
    {sources.slice(0, 2).map(src => <a className={styles.cite} key={src.url} href={src.url} target="_blank" rel="noopener noreferrer"
      aria-label={`${src.publisher} 원문 · ${src.title}`}>{src.publisher}</a>)}
  </>;
}

/** 노트 이후 달라진 것 — 10분마다 KRX 지도에서 자동 계산(모델 없음). */
export function SinceNoteStrip({ since }: { since: SinceNote | null }) {
  if (!since) return null;
  const moves = Object.entries(since.indices).filter(([, v]) => Math.abs(v.delta) >= 0.3)
    .map(([key, v]) => `${INDEX[key] ?? key} ${signed(v.from)}% → ${signed(v.to)}%`);
  const names = [
    since.new_limit_up.length ? `새 상한가 ${since.new_limit_up.map(s => s.name).join(", ")}` : "",
    since.new_limit_down.length ? `새 하한가 ${since.new_limit_down.map(s => s.name).join(", ")}` : "",
    since.new_spikes.length ? `거래 급증 ${since.new_spikes.map(s => s.name).join(", ")}` : "",
  ].filter(Boolean);
  return <p className={styles.after}>
    <b>노트 이후 · KRX {collected(since.to)}</b>{[...moves, ...names].join(" · ")}
  </p>;
}

function NoteBody({ note }: { note: DeskNote }) {
  return <div className={styles.note}>
    <h3>{note.headline}</h3>
    <h4>움직이는 이유</h4>
    <ol className={styles.claims}>{note.drivers.map((claim, i) => <li key={i}>
      <span>{claim.text} <Evidence label={claim.label} sources={claim.sources} /></span>
    </li>)}</ol>
    {note.stocks.length > 0 && <>
      <h4>주요 종목</h4>
      <ul className={styles.stockList}>{note.stocks.map(stock => <li key={stock.name}>
        <b>{stock.name}</b>
        {stock.chg_pct != null && <span className={`${styles.figure} ${tone(stock.chg_pct) ?? ""}`}>{signed(stock.chg_pct)}%</span>}
        {stock.reason} <Evidence label={stock.label} sources={stock.sources} />
      </li>)}</ul>
    </>}
    {note.since_last && <p className={styles.since}><b>지난 노트 이후</b>{note.since_last}</p>}
    {note.watch.length > 0 && <>
      <h4>{note.slot === "close" ? "다음 거래일에 볼 것" : "남은 장에서 볼 것"}</h4>
      <ul className={styles.watch}>{note.watch.map(item => <li key={item}>{item}</li>)}</ul>
    </>}
    {note.sources.length > 0 && <details className={styles.more}>
      <summary>근거 원문 {note.sources.length}건</summary>
      <Sources items={note.sources} label="노트의 근거 원문" timeLabel="보도" />
    </details>}
  </div>;
}

/** 장중 노트 한 편과, 그 뒤 달라진 것, 같은 날 앞선 노트. */
export default function NoteCard({ note, since, earlier = [] }: { note: DeskNote; since: SinceNote | null; earlier?: DeskNote[] }) {
  const title = note.kind === "urgent" ? "급변 노트" : `장중 노트${note.slot ? ` · ${SLOT[note.slot]}` : ""}`;
  return <section className={styles.card} aria-labelledby={`note-${note.id}`}>
    <header className={styles.header}>
      <h2 id={`note-${note.id}`}>{title}</h2>
      <span className={styles.meta}>{collected(note.published_at)} 작성 · KRX {collected(note.observed_at)} 기준</span>
    </header>
    <NoteBody note={note} />
    <SinceNoteStrip since={since} />
    {earlier.length > 0 && <details className={styles.earlier}>
      <summary>오늘 앞선 노트 {earlier.length}</summary>
      <ul>{[...earlier].reverse().map(item => <li key={item.id}>
        <details>
          <summary><time dateTime={item.published_at}>{collected(item.published_at)}</time>{item.headline}</summary>
          <NoteBody note={item} />
        </details>
      </li>)}</ul>
    </details>}
  </section>;
}
