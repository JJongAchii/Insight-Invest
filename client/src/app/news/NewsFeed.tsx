"use client";

import Link from "next/link";
import { ArrowRight, ChevronDown } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  useAcknowledgeDeskNewsSeenMutation,
  useFetchDeskNewsQuery,
  type DeskNewsItem,
} from "@/state/api";
import { PublicationText, Sources, checked, date, dayOf, refresh } from "../home/deskParts";
import styles from "./news.module.css";

const clock = new Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
const longDay = new Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", month: "long", day: "numeric", weekday: "long" });

const TOPICS = [
  { key: "economy", label: "경제·금융", categories: ["경제", "거시경제", "금융"] },
  { key: "industry", label: "산업·기술", categories: ["산업", "기술"] },
  { key: "trade", label: "무역·에너지", categories: ["무역", "에너지"] },
  { key: "world", label: "세계", categories: ["세계정세", "글로벌 주요사건"] },
  { key: "filing", label: "기업 공시", categories: [] },
] as const;
type Topic = (typeof TOPICS)[number]["key"];

/** 분류 없이 온 글: 공시, 금리·관세 같은 정책 발표를 설명한 데스크 글, 그 밖에는 분류를 읽지 못한 뉴스. */
const labelOf = (item: DeskNewsItem) =>
  item.category ?? (item.kind === "filing" ? "기업 공시" : item.origin === "desk" ? "정책·발표" : "뉴스");
const topicOf = (item: DeskNewsItem): Topic | null => {
  if (item.kind === "filing") return "filing";
  if (!item.category) return item.origin === "desk" ? "economy" : null;
  return TOPICS.find(topic => (topic.categories as readonly string[]).includes(item.category!))?.key ?? null;
};
const provenance = (item: DeskNewsItem) =>
  item.origin === "reporter" ? "원문을 대조한 AI 요약" : item.status === "analysis" ? "원문을 인용한 AI 해설" : "원문 제목";

function Article({ item }: { item: DeskNewsItem }) {
  return <div className={styles.article}>
    {item.body ? <PublicationText text={item.body} /> : <>
      {item.summary && <p className={styles.facts}>{item.summary}</p>}
      {item.significance && <div className={styles.reason}><h4>왜 중요한가</h4><p>{item.significance}</p></div>}
      {item.change && <div className={styles.section}><h4>달라진 점</h4><p>{item.change}</p></div>}
      {item.interpretation && <div className={styles.section}>
        <h4>{item.kind === "filing" ? "기업에 미치는 영향" : "해석"}</h4><p>{item.interpretation}</p>
      </div>}
      {item.watch && <div className={styles.section}><h4>다음 확인할 점</h4><p>{item.watch}</p></div>}
    </>}
    {item.sources.length > 0 && <Sources items={item.sources} label="근거 원문" />}
    {item.followups.length > 0 && <div className={styles.section}><h4>이후 확인된 관련 자료</h4>
      <Sources items={item.followups} label="후속 보도와 공시" />
    </div>}
    <p className={styles.note}>
      {item.licenses.map(licence => <span key={licence.url}>출처 이용 <a href={licence.url} target="_blank" rel="noopener noreferrer">{licence.name}</a> · </span>)}
      {provenance(item)} · 발행 {date(item.published_at)} KST
    </p>
  </div>;
}

function Row({ item, open, fresh, dated, target }: {
  item: DeskNewsItem; open?: boolean; fresh?: boolean; dated?: boolean; target?: React.Ref<HTMLLIElement>;
}) {
  return <li ref={target} data-urgent={item.priority === "urgent" || undefined}>
    <details className={styles.row} open={open}>
      <summary>
        {dated ? date(item.published_at) : <time dateTime={item.published_at}>{clock.format(new Date(item.published_at))}</time>}
        <span className={styles.tags}>
          {fresh && <span className={styles.fresh}><span className="sr-only">새 소식</span></span>}
          {item.priority === "urgent" && <em>긴급</em>}
          {item.update && <span className={styles.update}>후속</span>}
          <span>{labelOf(item)}</span>
          {item.publisher && <span className={styles.publisher}>{item.publisher}</span>}
        </span>
        <strong>{item.title}</strong>
        <ChevronDown size={16} aria-hidden />
      </summary>
      <Article item={item} />
    </details>
  </li>;
}

/** 뉴스 화면: 날짜별 전체 목록. 화면을 열면 여기까지 본 것으로 기록한다. */
export default function NewsFeed({ itemId }: { itemId?: string }) {
  const { data, error, isLoading, refetch, fulfilledTimeStamp } = useFetchDeskNewsQuery(undefined, refresh);
  const [acknowledge] = useAcknowledgeDeskNewsSeenMutation();
  const recorded = useRef<string | undefined>(undefined);
  const [topic, setTopic] = useState<Topic | "all">("all");
  // What was unseen when this visit began stays marked while it is being read.
  const [seenAtEntry, setSeenAtEntry] = useState<string | null | undefined>(undefined);
  if (data && seenAtEntry === undefined) setSeenAtEntry(data.seen_through);
  const selected = useRef<HTMLLIElement>(null);
  const items = data?.items ?? [];
  const newest = items[0]?.published_at;
  const seenThrough = data?.seen_through;
  const found = Boolean(itemId && items.some(item => item.id === itemId));

  // Record the visit once per newest article. A failed record is tried again when the list is next read.
  useEffect(() => {
    if (!newest || recorded.current === newest) return;
    if (seenThrough && Date.parse(newest) <= Date.parse(seenThrough)) return;
    recorded.current = newest;
    acknowledge({ through: newest }).unwrap().catch(() => { recorded.current = undefined; });
    const nav = navigator as Navigator & { clearAppBadge?: () => Promise<void> };
    nav.clearAppBadge?.().catch(() => undefined);
  }, [acknowledge, newest, seenThrough, fulfilledTimeStamp]);
  useEffect(() => {
    if (found) selected.current?.scrollIntoView({ block: "start" });
  }, [found]);

  const counts = TOPICS.map(entry => ({ ...entry, count: items.filter(item => topicOf(item) === entry.key).length }))
    .filter(entry => entry.count > 0);
  // A topic whose last article has aged out of the list falls back to everything.
  const active = counts.some(entry => entry.key === topic) ? topic : "all";
  const shown = active === "all" ? items : items.filter(item => topicOf(item) === active);
  const fresh = (item: DeskNewsItem) => seenAtEntry !== undefined &&
    (seenAtEntry === null || Date.parse(item.published_at) > Date.parse(seenAtEntry));
  const unseen = items.filter(fresh).length;
  const today = dayOf(new Date());
  const yesterday = dayOf(new Date(Date.parse(`${today}T00:00:00+09:00`) - 12 * 60 * 60_000));
  const days = [...new Set(shown.map(item => dayOf(item.published_at)))];

  return <section className={styles.feed} aria-label="뉴스 목록">
    {data && <header className={styles.header}>
      <p className={styles.total}>최근 뉴스 {items.length}건{unseen > 0 && <span className={styles.count}>새 소식 {unseen}건</span>}</p>
      {data.checked_at && checked(data.checked_at, !!error || data.state === "stale")}
    </header>}
    {(counts.length > 1 || active !== "all") && <div className={styles.topics} role="group" aria-label="뉴스 분야">
      <button type="button" className="filter-chip" aria-pressed={active === "all"} onClick={() => setTopic("all")}>전체 {items.length}</button>
      {counts.map(entry => <button type="button" className="filter-chip" key={entry.key}
        aria-pressed={active === entry.key} onClick={() => setTopic(entry.key)}>{entry.label} {entry.count}</button>)}
    </div>}
    {itemId && data && !found && <p className={styles.empty}>선택한 뉴스는 최근 목록에서 지나갔습니다.</p>}
    {items.length ? days.map(day => {
      const rows = shown.filter(item => dayOf(item.published_at) === day);
      return <section key={day} aria-labelledby={`news-day-${day}`}>
        <h2 className={styles.day} id={`news-day-${day}`}>
          {day === today ? "오늘 · " : day === yesterday ? "어제 · " : ""}{longDay.format(new Date(rows[0].published_at))}
          <span>{rows.length}건</span>
        </h2>
        <ul className={styles.list}>{rows.map(item => <Row key={item.id} item={item} fresh={fresh(item)}
          open={item.id === itemId} target={item.id === itemId ? selected : undefined} />)}</ul>
      </section>;
    }) : <p className={styles.empty}>
      {error ? <>뉴스를 불러오지 못했습니다. <button type="button" onClick={() => refetch()}>다시 불러오기</button></>
        : isLoading ? "뉴스를 불러오는 중입니다."
        : "최근 발행된 뉴스가 없습니다. 원문 확인을 마친 소식이 올라오면 여기에 표시됩니다."}
    </p>}
  </section>;
}

/** 홈: 최신 뉴스 몇 건. 미리보기는 본 것으로 기록하지 않는다. */
export function NewsPreview({ limit = 5 }: { limit?: number }) {
  const { data, error, isLoading, refetch } = useFetchDeskNewsQuery(undefined, refresh);
  const items = data?.items ?? [];
  return <section className={styles.feed} aria-labelledby="news-preview-title">
    <header className={styles.header}>
      <h2 id="news-preview-title">주요 뉴스</h2>
      <Link className={styles.all} href="/news">
        {data && data.unseen > 0 ? `새 소식 ${data.unseen}건 · 전체 보기` : "전체 보기"} <ArrowRight size={14} aria-hidden />
      </Link>
    </header>
    {items.length ? <ul className={`${styles.list} ${styles.dated}`}>
      {items.slice(0, limit).map(item => <Row key={item.id} item={item} dated />)}
    </ul> : <p className={styles.empty}>
      {error ? <>뉴스를 불러오지 못했습니다. <button type="button" onClick={() => refetch()}>다시 불러오기</button></>
        : isLoading ? "뉴스를 불러오는 중입니다." : "최근 발행된 뉴스가 없습니다."}
    </p>}
  </section>;
}
