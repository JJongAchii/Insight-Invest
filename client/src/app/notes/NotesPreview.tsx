"use client";

import { useFetchMarketDeskQuery } from "@/state/api";
import NoteCard from "../home/NoteCard";
import { refresh } from "../home/deskParts";
import styles from "../home/marketMap.module.css";

/** 오늘 쓴 노트를 최신부터. 맨 위 노트에만 노트 이후 변화를 붙인다. */
export default function NotesPreview() {
  const { data, error, isLoading, refetch } = useFetchMarketDeskQuery(undefined, refresh);
  const notes = [...(data?.notes ?? [])].reverse();
  if (!notes.length) return <section className={styles.card} aria-label="장중 노트">
    <p className={styles.empty}>
      {error ? <>노트를 불러오지 못했습니다. <button type="button" onClick={() => refetch()}>다시 불러오기</button></>
        : isLoading ? "노트를 불러오는 중입니다." : "오늘 쓴 장중 노트가 아직 없습니다."}
    </p>
  </section>;
  return <>{notes.map((note, i) => <NoteCard key={note.id} note={note} since={i === 0 ? data?.since_note ?? null : null} />)}</>;
}
