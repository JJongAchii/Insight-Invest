import { ArrowUpRight } from "lucide-react";
import type { DeskArticle } from "@/state/api";
import styles from "./marketDesk.module.css";

const formatTime = new Intl.DateTimeFormat("ko-KR", {
  timeZone: "Asia/Seoul", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
});
const koreanDay = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Seoul", year: "numeric", month: "2-digit", day: "2-digit" });

export const refresh = { pollingInterval: 120_000, skipPollingIfUnfocused: true, refetchOnFocus: true };
export const date = (stamp: string) => <time dateTime={stamp}>{formatTime.format(new Date(stamp))}</time>;
/** 한국 날짜(YYYY-MM-DD). 같은 거래일·같은 날의 글을 묶을 때 쓴다. */
export const dayOf = (stamp: string | Date) => koreanDay.format(new Date(stamp));
export const checked = (stamp: string, delayed: boolean) => <span className={styles.meta}>
  {delayed ? "갱신 지연 · 마지막 확인 " : "마지막 확인 "}{date(stamp)} KST
</span>;

const decode = (s: string) => s.replaceAll("&lt;", "<").replaceAll("&gt;", ">").replaceAll("&amp;", "&");

export function PublicationText({ text }: { text: string }) {
  // Published editions may carry labelled links and single-asterisk emphasis. Keep text escaped by React.
  return <div className={styles.prose}>{text.split(/(<https?:\/\/[^<>\s|]+(?:\|[^<>]*)?>|\*[^*\n]+\*)/g).map((part, i) => {
    if (part.startsWith("<http") && part.endsWith(">")) {
      const [href, label] = part.slice(1, -1).split("|", 2);
      return <a key={i} href={decode(href)} target="_blank" rel="noopener noreferrer">{decode(label || href)}</a>;
    }
    if (part.startsWith("*") && part.endsWith("*")) return <strong key={i}>{decode(part.slice(1, -1))}</strong>;
    return decode(part);
  })}</div>;
}

export function Sources({ items, label, timeLabel = "발표" }: { items: DeskArticle["sources"]; label: string; timeLabel?: string }) {
  return <ul className={styles.sources} aria-label={label}>{items.map(src => <li key={src.url}>
    <a href={src.url} target="_blank" rel="noopener noreferrer">{src.title || `${src.publisher} 원문`} <ArrowUpRight size={13} aria-hidden /></a>
    <span>{src.publisher} · {timeLabel} {date(src.published_at)} KST
      {src.license_url && <> · <a href={src.license_url} target="_blank" rel="noopener noreferrer">{src.license_name || "출처 이용 조건"}</a></>}
    </span>
  </li>)}</ul>;
}
