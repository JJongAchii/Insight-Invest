import type { IpoPosition, IpoRow } from "@/state/api";

const wonFormat = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 0 });
const countFormat = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 4 });

const isNum = (v: number | null | undefined): v is number =>
  typeof v === "number" && Number.isFinite(v);

/** 원 단위, 천 단위 구분. */
export const fmtWon = (v: number | null | undefined): string =>
  isNum(v) ? `${wonFormat.format(v)}원` : "—";

export const fmtShares = (v: number | null | undefined): string =>
  isNum(v) ? `${countFormat.format(v)}주` : "—";

/** 분수(0.052) → "+5.20%". */
export const fmtReturn = (v: number | null | undefined): string => {
  if (!isNum(v)) return "—";
  const pct = v * 100;
  return `${pct > 0 ? "+" : ""}${pct.toFixed(2)}%`;
};

export const returnTone = (v: number | null | undefined): string =>
  !isNum(v) || v === 0 ? "text-ink-secondary" : v > 0 ? "text-gains" : "text-losses";

/** "YYYY-MM-DD" 그대로(표). */
export const fmtDay = (value: string | null | undefined): string =>
  value ? value.slice(0, 10) : "—";

/** "10월 29일 (목)" — 카드·제목용. */
export const fmtDayLabel = (value: string | null | undefined): string => {
  if (!value) return "—";
  const day = new Date(`${value.slice(0, 10)}T00:00:00`);
  if (Number.isNaN(day.getTime())) return value;
  return new Intl.DateTimeFormat("ko-KR", {
    month: "short",
    day: "numeric",
    weekday: "short",
  }).format(day);
};

// ── 일정(달력) 계산: "YYYY-MM-DD" 문자열을 UTC 자정으로 다뤄 시간대 영향 없이 더하고 뺀다.
const WEEKDAY = ["일", "월", "화", "수", "목", "금", "토"];

const toUtcDay = (iso: string): Date | null => {
  const day = new Date(`${iso.slice(0, 10)}T00:00:00Z`);
  return Number.isNaN(day.getTime()) ? null : day;
};

/** 한국 시간 기준 오늘 "YYYY-MM-DD". */
export const kstToday = (): string =>
  new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());

export const addDays = (iso: string, days: number): string => {
  const day = toUtcDay(iso);
  if (!day) return iso;
  day.setUTCDate(day.getUTCDate() + days);
  return day.toISOString().slice(0, 10);
};

/** 그 주의 월요일. */
export const mondayOf = (iso: string): string => {
  const day = toUtcDay(iso);
  if (!day) return iso;
  return addDays(iso, -((day.getUTCDay() + 6) % 7));
};

/** "10/29(수)" — 좁은 칸용. */
export const fmtShortDay = (value: string | null | undefined): string => {
  if (!value) return "—";
  const day = toUtcDay(value);
  if (!day) return value;
  return `${day.getUTCMonth() + 1}/${day.getUTCDate()}(${WEEKDAY[day.getUTCDay()]})`;
};

export const fmtShortRange = (
  start: string | null | undefined,
  end: string | null | undefined
): string => {
  if (start && end && start.slice(0, 10) !== end.slice(0, 10)) {
    return `${fmtShortDay(start)}~${fmtShortDay(end)}`;
  }
  return fmtShortDay(start ?? end);
};

export const dayParts = (iso: string) => {
  const day = toUtcDay(iso);
  return day
    ? { month: day.getUTCMonth() + 1, date: day.getUTCDate(), weekday: WEEKDAY[day.getUTCDay()] }
    : { month: 0, date: 0, weekday: "" };
};

export const fmtTimestamp = (value: string | null | undefined): string => {
  if (!value) return "—";
  const at = new Date(value);
  if (Number.isNaN(at.getTime())) return value;
  return at.toLocaleString("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const MARKET_LABEL: Record<string, string> = {
  KOSPI: "코스피",
  KOSDAQ: "코스닥",
  KONEX: "코넥스",
};

export const marketLabel = (market: string | null | undefined): string =>
  market ? MARKET_LABEL[market.toUpperCase()] ?? market : "—";

export const POSITION_META: Record<IpoPosition, { label: string; style: string }> = {
  signal: { label: "신호", style: "bg-primary-500/15 text-primary-300" },
  holding: { label: "보유", style: "bg-warning/15 text-warning" },
  sold: { label: "매도 완료", style: "bg-raised text-ink" },
  unfilled: { label: "미체결", style: "bg-raised text-ink-muted" },
  awaiting_listing_data: { label: "상장 데이터 대기", style: "bg-warning/15 text-warning" },
};

export const positionMeta = (position: IpoRow["position"]) =>
  position ? POSITION_META[position] ?? { label: position, style: "bg-raised text-ink-secondary" } : null;

/** 판단: 매수 / 패스 / 판단 불가. */
export const judgement = (
  row: IpoRow
): { label: string; style: string; reason: string | null } => {
  const reason = row.reason ?? null;
  if (row.status === "not_eligible") {
    return { label: "판단 불가", style: "bg-raised text-ink-muted", reason };
  }
  if (row.buy) {
    return { label: "매수", style: "bg-primary-500/15 text-primary-300", reason };
  }
  if (row.status === "decided") {
    return { label: "패스", style: "bg-raised text-ink-secondary", reason };
  }
  return { label: "미확인", style: "bg-raised text-ink-muted", reason };
};

/** 체결가: 사용자 입력이 있으면 그것을, 없으면 배치 추정을 쓴다. */
export const entryOf = (row: IpoRow) => {
  const user = row.user?.entry_price;
  if (isNum(user)) return { price: user, entered: true };
  return { price: row.entry_price ?? null, entered: false };
};

export const exitOf = (row: IpoRow) => {
  const user = row.user?.exit_price;
  if (isNum(user)) {
    return { price: user, date: row.user?.exit_date ?? row.exit_date ?? null, entered: true };
  }
  return { price: row.exit_price ?? null, date: row.exit_date ?? null, entered: false };
};

/** FastAPI 오류의 detail(문자열 또는 검증 오류 배열)을 사람이 읽을 문장으로. */
export const apiErrorMessage = (error: unknown, fallback: string): string => {
  if (typeof error === "object" && error !== null && "data" in error) {
    const detail = (error as { data?: { detail?: unknown } }).data?.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) =>
          typeof item === "object" && item !== null && typeof (item as { msg?: unknown }).msg === "string"
            ? (item as { msg: string }).msg
            : null
        )
        .filter((msg): msg is string => Boolean(msg));
      if (messages.length > 0) return messages.join(" · ");
    }
  }
  return fallback;
};
