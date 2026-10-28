"use client";

import { CalendarDays } from "lucide-react";
import React, { useMemo, useState } from "react";

import type {
  IpoCalendarEvent,
  IpoCalendarEventKind,
  IpoCalendarItem,
  IpoStage,
} from "@/state/api";
import {
  addDays,
  dayParts,
  fmtShortDay,
  fmtShortRange,
  fmtWon,
  marketLabel,
  mondayOf,
} from "./format";
import { EmptyLine, Pill, Section } from "./parts";

type View = "list" | "calendar";

const EMPTY_TEXT = "진행 중인 공모 일정 없음(데이터는 매일 저녁 갱신)";
const GRID_WEEKS = 5;

const STAGE_LABEL: Record<IpoStage, string> = {
  filed: "신고서 제출",
  bookbuilding: "수요예측",
  priced: "공모가 확정",
  subscription: "청약",
  paid: "납입 완료",
  listing_scheduled: "상장일 확정",
};

const STAGE_STYLE: Partial<Record<IpoStage, string>> = {
  subscription: "bg-warning/15 text-warning",
  listing_scheduled: "bg-primary-500/15 text-primary-300",
};

/** 타임라인에서 그 단계까지 진행된 마지막 칸(-1: 아직 수요예측 전). */
const STAGE_REACHED: Record<IpoStage, number> = {
  filed: -1,
  bookbuilding: 0,
  priced: 1,
  subscription: 2,
  paid: 3,
  listing_scheduled: 4,
};

const KIND_META: Record<IpoCalendarEventKind, { label: string; style: string }> = {
  bookbuild: { label: "수요예측", style: "bg-secondary-400/15 text-secondary-400" },
  price: { label: "공모가", style: "bg-secondary-400/25 text-ink" },
  subscription: { label: "청약", style: "bg-warning/15 text-warning" },
  payment: { label: "납입", style: "border border-edge bg-raised text-ink-secondary" },
  listing: { label: "상장", style: "bg-primary-500/15 text-primary-300" },
  decision: { label: "신호 계산", style: "border border-primary-400/60 text-primary-300" },
  buy: { label: "매수", style: "bg-primary-500 text-white" },
  sell: { label: "매도", style: "bg-secondary-500 text-white" },
};

const KIND_ORDER: IpoCalendarEventKind[] = [
  "bookbuild",
  "price",
  "subscription",
  "payment",
  "listing",
  "decision",
  "buy",
  "sell",
];

const kindMeta = (kind: string) =>
  KIND_META[kind as IpoCalendarEventKind] ?? { label: kind, style: "bg-raised text-ink-secondary" };

const sortKey = (item: IpoCalendarItem) =>
  item.planned_listing_date ?? item.subscription_start ?? item.bookbuild_start ?? "9999-12-31";

function StageBadge({ item }: { item: IpoCalendarItem }) {
  const stage = item.stage ?? null;
  const label = item.stage_label ?? (stage ? STAGE_LABEL[stage] ?? stage : "단계 미확인");
  const style = (stage && STAGE_STYLE[stage]) || "bg-raised text-ink-secondary";
  return <Pill className={style}>{label}</Pill>;
}

function Timeline({ item }: { item: IpoCalendarItem }) {
  const reached = item.stage ? STAGE_REACHED[item.stage] ?? -1 : -1;
  // 기간은 "~" 뒤에서 줄을 바꿀 수 있게 해 좁은 칸에서 옆 칸을 침범하지 않게 한다.
  const range = (start?: string | null, end?: string | null): React.ReactNode =>
    fmtShortRange(start, end)
      .split("~")
      .flatMap((part, i) => (i === 0 ? [part] : ["~", <wbr key={i} />, part]));
  const steps: [string, React.ReactNode][] = [
    ["수요예측", range(item.bookbuild_start, item.bookbuild_end)],
    ["공모가 확정", fmtShortDay(item.price_announce_date)],
    ["청약", range(item.subscription_start, item.subscription_end)],
    ["납입", fmtShortDay(item.payment_date)],
    ["상장", item.planned_listing_date ? fmtShortDay(item.planned_listing_date) : "공시 전"],
  ];
  return (
    <ol className="mt-4 grid gap-2 sm:grid-cols-5 sm:gap-3" aria-label="공모 일정">
      {steps.map(([label, date], index) => {
        const state = index < reached ? "done" : index === reached ? "current" : "next";
        const bar =
          state === "done"
            ? "bg-primary-400/60"
            : state === "current"
              ? "bg-primary-400 shadow-[0_0_10px_rgba(124,91,255,0.45)]"
              : "bg-edge";
        return (
          <li
            key={label}
            className="flex items-center gap-2.5 sm:flex-col sm:items-stretch sm:gap-1.5"
            aria-current={state === "current" ? "step" : undefined}
          >
            <span aria-hidden className={`h-2 w-2 shrink-0 rounded-full sm:h-1 sm:w-full ${bar}`} />
            <div className="flex min-w-0 flex-1 items-baseline justify-between gap-2 sm:block">
              <span
                className={`block text-[11px] ${state === "current" ? "font-semibold text-ink" : "text-ink-muted"}`}
              >
                {label}
              </span>
              <span
                className={`num block text-xs ${state === "next" ? "text-ink-secondary" : "text-ink"}`}
              >
                {date}
              </span>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function TradePlan({ item }: { item: IpoCalendarItem }) {
  if (!item.planned_listing_date) {
    return (
      <p className="mt-4 text-xs leading-5 text-ink-muted">상장일 공시 전(보통 상장 약 6일 전 공시)</p>
    );
  }
  return (
    <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-primary-400/30 bg-primary-500/10 px-3 py-2.5 text-sm text-ink">
      <span>
        신호 계산 <strong className="num font-semibold">{fmtShortDay(item.decision_night)}</strong> 밤
      </span>
      <span aria-hidden className="text-ink-muted">·</span>
      <span>
        매수 <strong className="num font-semibold">{fmtShortDay(item.buy_session)}</strong> 08:30~09:00
      </span>
      <span aria-hidden className="text-ink-muted">·</span>
      <span>
        매도 <strong className="num font-semibold">{fmtShortDay(item.sell_session)}</strong> 종가
      </span>
    </div>
  );
}

function ScheduleCard({ item }: { item: IpoCalendarItem }) {
  const band =
    item.band_low != null || item.band_high != null
      ? `${fmtWon(item.band_low)} ~ ${fmtWon(item.band_high)}`
      : null;
  return (
    <article className="rounded-xl border border-edge bg-raised/40 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="truncate text-[15px] font-semibold text-ink">{item.corp_name ?? item.event_id}</h3>
        <span className="badge-neutral">{marketLabel(item.market)}</span>
        <StageBadge item={item} />
        {item.decided && <Pill className="bg-primary-500/15 text-primary-300">신호 계산됨</Pill>}
      </div>
      <p className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-secondary">
        <span>
          희망 밴드 <span className="num text-ink">{band ?? "—"}</span>
        </span>
        <span>
          확정 공모가 <span className="num font-semibold text-ink">{fmtWon(item.final_price)}</span>
        </span>
      </p>
      <Timeline item={item} />
      <TradePlan item={item} />
    </article>
  );
}

function Legend() {
  return (
    <div className="mb-3 flex flex-wrap gap-1.5" aria-label="일정 종류">
      {KIND_ORDER.map((kind) => (
        <span key={kind} className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${KIND_META[kind].style}`}>
          {KIND_META[kind].label}
        </span>
      ))}
    </div>
  );
}

function EventChip({ event }: { event: IpoCalendarEvent }) {
  const meta = kindMeta(event.kind);
  const name = event.corp_name ?? event.event_id;
  return (
    <span
      title={event.label ?? `${meta.label} · ${name}`}
      className={`block truncate rounded px-1.5 py-0.5 text-[10px] font-medium leading-4 ${meta.style}`}
    >
      {meta.label} {name}
    </span>
  );
}

function CalendarView({ events, today }: { events: IpoCalendarEvent[]; today: string }) {
  const byDate = useMemo(() => {
    const grouped = new Map<string, IpoCalendarEvent[]>();
    for (const event of events) {
      if (!event.date) continue;
      const key = event.date.slice(0, 10);
      grouped.set(key, [...(grouped.get(key) ?? []), event]);
    }
    for (const list of grouped.values()) {
      list.sort((a, b) => KIND_ORDER.indexOf(a.kind) - KIND_ORDER.indexOf(b.kind));
    }
    return grouped;
  }, [events]);

  const start = mondayOf(today);
  const end = addDays(start, GRID_WEEKS * 7 - 1);
  const days = Array.from({ length: GRID_WEEKS * 7 }, (_, index) => addDays(start, index));
  const later = events.filter((event) => event.date && event.date.slice(0, 10) > end).length;
  const agenda = [...byDate.keys()].filter((day) => day >= today).sort();

  return (
    <div>
      <Legend />

      {/* 데스크톱: 이번 주 월요일부터 5주 */}
      <div className="hidden md:block">
        <div className="grid grid-cols-[repeat(5,minmax(0,1fr))_repeat(2,minmax(0,0.6fr))] gap-px pb-1 text-center text-[11px] text-ink-muted">
          {["월", "화", "수", "목", "금", "토", "일"].map((label) => (
            <span key={label}>{label}</span>
          ))}
        </div>
        <div className="grid grid-cols-[repeat(5,minmax(0,1fr))_repeat(2,minmax(0,0.6fr))] gap-px overflow-hidden rounded-xl border border-edge bg-edge">
          {days.map((day, index) => {
            const { month, date } = dayParts(day);
            const isToday = day === today;
            const past = day < today;
            const dayEvents = byDate.get(day) ?? [];
            return (
              <div
                key={day}
                className={`min-h-[92px] min-w-0 p-1.5 ${isToday ? "bg-primary-500/10 ring-2 ring-inset ring-primary-400" : "bg-surface"}`}
                aria-label={`${month}월 ${date}일${isToday ? " 오늘" : ""} 일정 ${dayEvents.length}건`}
              >
                <div className="mb-1 flex items-center justify-between gap-1">
                  <span className={`num text-[11px] ${isToday ? "font-semibold text-ink" : past ? "text-ink-muted/60" : "text-ink-secondary"}`}>
                    {index === 0 || date === 1 ? `${month}/${date}` : date}
                  </span>
                  {isToday && <span className="text-[10px] font-semibold text-primary-300">오늘</span>}
                </div>
                <div className={`space-y-1 ${past ? "opacity-55" : ""}`}>
                  {dayEvents.map((event, i) => (
                    <EventChip key={`${event.event_id}-${event.kind}-${i}`} event={event} />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
        {later > 0 && (
          <p className="mt-2 text-[11px] text-ink-muted">
            {fmtShortDay(end)} 이후 일정 {later}건은 목록 보기에서 확인할 수 있습니다.
          </p>
        )}
      </div>

      {/* 모바일: 오늘부터 날짜별 목록 */}
      <div className="md:hidden">
        {agenda.length === 0 ? (
          <EmptyLine>{EMPTY_TEXT}</EmptyLine>
        ) : (
          <ol className="divide-y divide-edge border-y border-edge">
            {agenda.map((day) => {
              const { month, date, weekday } = dayParts(day);
              const isToday = day === today;
              return (
                <li key={day} className="flex gap-3 py-3">
                  <div className="w-12 shrink-0 text-center">
                    <p className="num text-[11px] text-ink-muted">{month}월</p>
                    <p className={`num text-lg font-semibold leading-6 ${isToday ? "text-primary-300" : "text-ink"}`}>
                      {date}
                    </p>
                    <p className={`text-[10px] ${isToday ? "font-semibold text-primary-300" : "text-ink-muted"}`}>
                      {isToday ? "오늘" : weekday}
                    </p>
                  </div>
                  <ul className="min-w-0 flex-1 space-y-1.5">
                    {(byDate.get(day) ?? []).map((event, i) => {
                      const meta = kindMeta(event.kind);
                      return (
                        <li key={`${event.event_id}-${event.kind}-${i}`} className="flex min-w-0 items-center gap-2">
                          <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium ${meta.style}`}>
                            {meta.label}
                          </span>
                          <span className="min-w-0 truncate text-sm text-ink">
                            {event.corp_name ?? event.event_id}
                            {event.label && (
                              <span className="ml-1.5 text-xs text-ink-muted">{event.label}</span>
                            )}
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </div>
  );
}

/** 상장 일정: 공모주별 진행(목록)과 날짜별 일정(달력). */
export default function IpoSchedule({
  calendar,
  events,
  today,
}: {
  calendar: IpoCalendarItem[];
  events: IpoCalendarEvent[];
  today: string;
}) {
  const [view, setView] = useState<View>("list");
  const items = useMemo(
    () => [...calendar].sort((a, b) => sortKey(a).localeCompare(sortKey(b))),
    [calendar]
  );
  const empty = items.length === 0 && events.length === 0;

  return (
    <Section
      icon={CalendarDays}
      title="상장 일정"
      className="border-primary-400/30"
      meta={
        <div className="segmented-control" role="group" aria-label="상장 일정 보기 방식">
          {([
            ["list", "목록"],
            ["calendar", "달력"],
          ] as [View, string][]).map(([value, label]) => (
            <button key={value} type="button" aria-pressed={view === value} onClick={() => setView(value)}>
              {label}
            </button>
          ))}
        </div>
      }
    >
      {empty ? (
        <EmptyLine>{EMPTY_TEXT}</EmptyLine>
      ) : view === "calendar" ? (
        <CalendarView events={events} today={today} />
      ) : items.length === 0 ? (
        <EmptyLine>{EMPTY_TEXT}</EmptyLine>
      ) : (
        <div className="grid gap-3 xl:grid-cols-2">
          {items.map((item) => (
            <ScheduleCard key={item.event_id} item={item} />
          ))}
        </div>
      )}
    </Section>
  );
}
