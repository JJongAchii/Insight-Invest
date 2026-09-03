"use client";

import {
  BellRing,
  BookOpen,
  CalendarDays,
  CheckCircle2,
  ChevronRight,
  Clock3,
  Database,
  Inbox,
  X,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import EmptyState from "@/components/ui/EmptyState";
import LoadingState from "@/components/ui/LoadingState";
import PageHeader from "@/components/ui/PageHeader";
import {
  ActionItem,
  AttentionSeverity,
  useFetchActionsQuery,
  useUpdateActionStateMutation,
} from "@/state/api";
import NotificationSettings from "./NotificationSettings";

type Tab = "inbox" | "calendar" | "alerts";
type Filter = "all" | "high" | "portfolio" | "research" | "events";

const SEVERITY_STYLE: Record<AttentionSeverity, string> = {
  high: "bg-losses",
  medium: "bg-warning",
  low: "bg-primary-400",
};

const SEVERITY_LABEL: Record<AttentionSeverity, string> = {
  high: "높음",
  medium: "보통",
  low: "참고",
};

const dateLabel = (value: string | null) => {
  if (!value) return "일정 미정";
  return new Intl.DateTimeFormat("ko-KR", {
    month: "short",
    day: "numeric",
    weekday: "short",
  }).format(new Date(`${value.slice(0, 10)}T00:00:00`));
};

const SOURCE_STATUS = {
  ok: { label: "정상", style: "bg-gains/15 text-gains" },
  preserved: { label: "최근 정상값", style: "bg-warning/15 text-warning" },
  configuration_required: { label: "설정 필요", style: "bg-warning/15 text-warning" },
  upgrade_required: { label: "업그레이드 필요", style: "bg-warning/15 text-warning" },
  unavailable: { label: "사용 불가", style: "bg-losses/15 text-losses" },
} as const;

const TABS: Tab[] = ["inbox", "calendar", "alerts"];
const FILTERS: Filter[] = ["all", "high", "portfolio", "research", "events"];

const replaceViewInUrl = (tab: Tab, filter: Filter) => {
  const url = new URL(window.location.href);
  url.searchParams.set("tab", tab);
  url.searchParams.set("filter", filter);
  window.history.replaceState(window.history.state, "", url);
};

function ActionCard({ item }: { item: ActionItem }) {
  const router = useRouter();
  const [updateState, { isLoading }] = useUpdateActionStateMutation();
  const externalLink = /^https?:\/\//i.test(item.link);

  const saveToJournal = () => {
    sessionStorage.setItem("ii-journal-prefill", JSON.stringify(item));
    router.push("/journal?prefill=action");
  };

  const snooze = () => {
    const until = new Date();
    until.setDate(until.getDate() + 1);
    until.setHours(9, 0, 0, 0);
    updateState({ event_id: item.event_id, state: "snoozed", snoozed_until: until.toISOString() });
  };

  return (
    <article className="group relative overflow-hidden rounded-2xl border border-edge bg-surface transition-colors hover:border-edge-strong">
      <span
        aria-hidden
        className={`absolute bottom-0 left-0 top-0 w-0.5 ${SEVERITY_STYLE[item.severity]}`}
      />
      <div className="flex items-start gap-3 p-4 pl-5 sm:p-5 sm:pl-6">
        <span
          aria-hidden
          className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${SEVERITY_STYLE[item.severity]}`}
        />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 text-xs text-ink-muted">
            <span className="badge-neutral">{item.category}</span>
            {item.market && <span className="badge-neutral">{item.market}</span>}
            {item.event_status && (
              <span className="badge-neutral capitalize">{item.event_status}</span>
            )}
            {(item.ticker || item.name) && <span>{item.ticker ?? item.name}</span>}
            {item.scheduled_for && <span>{dateLabel(item.scheduled_for)}</span>}
            <span className="font-mono text-[10px] uppercase tracking-wider">
              우선순위 {SEVERITY_LABEL[item.severity]}
            </span>
            {item.data_as_of && <span className="ml-auto font-mono text-[10px]">기준 {item.data_as_of.slice(0, 10)}</span>}
          </div>
          <h2 className="mt-2 text-[15px] font-semibold leading-6 text-ink sm:text-base">{item.title}</h2>
          <p className="mt-1 text-sm leading-6 text-ink-secondary">{item.detail}</p>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            {externalLink ? (
              <a
                href={item.link}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-primary inline-flex items-center gap-1.5"
                onClick={() => updateState({ event_id: item.event_id, state: "read" })}
              >
                상세 보기 <ChevronRight size={15} aria-hidden />
              </a>
            ) : (
              <Link
                href={item.link}
                className="btn-primary inline-flex items-center gap-1.5"
                onClick={() => updateState({ event_id: item.event_id, state: "read" })}
              >
                상세 보기 <ChevronRight size={15} aria-hidden />
              </Link>
            )}
            {item.actions.includes("journal") && (
              <button type="button" className="btn-secondary inline-flex items-center gap-1.5" onClick={saveToJournal}>
                <BookOpen size={15} aria-hidden /> 판단 기록에 남기기
              </button>
            )}
            {item.actions.includes("snooze") && (
              <button type="button" className="btn-secondary inline-flex items-center gap-1.5" onClick={snooze} disabled={isLoading}>
                <Clock3 size={15} aria-hidden /> 내일 다시 보기
              </button>
            )}
            {item.actions.includes("dismiss") && (
              <button
                type="button"
                className="ml-auto rounded-lg p-2 text-ink-muted hover:bg-raised hover:text-ink"
                aria-label="항목 닫기"
                onClick={() => updateState({ event_id: item.event_id, state: "dismissed" })}
                disabled={isLoading}
              >
                <X size={16} aria-hidden />
              </button>
            )}
          </div>
        </div>
      </div>
    </article>
  );
}

export default function ActionCenterPage() {
  // 분기 실적은 약 90일 간격이라 60일 창에서는 정상 수집된 다음 일정도 숨을 수 있다.
  const { data, isLoading, error, refetch } = useFetchActionsQuery({ horizonDays: 90 });
  const [tab, setTab] = useState<Tab>("inbox");
  const [filter, setFilter] = useState<Filter>("all");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const savedTab = params.get("tab") as Tab | null;
    const savedFilter = params.get("filter") as Filter | null;
    if (savedTab && TABS.includes(savedTab)) setTab(savedTab);
    if (savedFilter && FILTERS.includes(savedFilter)) setFilter(savedFilter);
  }, []);

  useEffect(() => {
    const nav = navigator as Navigator & { setAppBadge?: (count?: number) => Promise<void> };
    if (data && nav.setAppBadge) {
      nav.setAppBadge(data.counts.badge ?? data.counts.actionable).catch(() => undefined);
    }
  }, [data]);

  const items = useMemo(() => {
    const source = tab === "calendar" ? data?.calendar ?? [] : data?.items ?? [];
    if (filter === "high") return source.filter((item) => item.severity === "high");
    if (filter === "portfolio") return source.filter((item) => item.scope === "portfolio" || ["holding", "strategy"].includes(item.category));
    if (filter === "research") return source.filter((item) => ["watchlist", "journal", "signal"].includes(item.category));
    if (filter === "events") return source.filter((item) => item.kind === "event");
    return source;
  }, [data, filter, tab]);

  const groups = useMemo(() => {
    if (tab !== "calendar") return [] as [string, ActionItem[]][];
    const grouped = new Map<string, ActionItem[]>();
    for (const item of items) {
      const key = item.scheduled_for ?? "unscheduled";
      grouped.set(key, [...(grouped.get(key) ?? []), item]);
    }
    return [...grouped.entries()];
  }, [items, tab]);

  const selectTab = (value: Tab) => {
    setTab(value);
    replaceViewInUrl(value, filter);
  };

  const selectFilter = (value: Filter) => {
    setFilter(value);
    replaceViewInUrl(tab, value);
  };

  return (
    <div className="flex flex-col gap-6 pb-20">
      <PageHeader
        eyebrow="Review desk"
        title="검토할 일"
        description="시장 변화와 내 투자 판단에서 지금 확인할 항목을 중요도와 시점 순으로 정리합니다."
        meta={
          <>
            <span>90일 검토 창</span>
            <span>·</span>
            <span>{data?.data_as_of ? `시장 기준 ${data.data_as_of}` : "시장 기준 확인 중"}</span>
          </>
        }
      />

      <div
        className="scrollbar-hidden -mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0"
        role="group"
        aria-label="검토 현황 요약"
        tabIndex={0}
      >
        <section className="metric-strip min-w-[38rem] grid-cols-4 sm:min-w-0" aria-label="검토 현황">
        {[
          ["검토 필요", data?.counts.actionable ?? 0, BellRing],
          ["높은 우선순위", data?.counts.high ?? 0, Inbox],
          ["새 항목", data?.counts.new ?? 0, CheckCircle2],
          ["예정 일정", data?.counts.scheduled ?? 0, CalendarDays],
        ].map(([label, value, Icon]) => {
          const MetricIcon = Icon as typeof BellRing;
          return (
            <div key={String(label)} className="metric-tile p-4 sm:p-5">
              <div className="flex items-center gap-2 text-xs text-ink-muted"><MetricIcon size={15} aria-hidden />{String(label)}</div>
              <p className="num mt-2 text-2xl font-semibold text-ink">{Number(value)}</p>
            </div>
          );
        })}
        </section>
      </div>

      <div className="segmented-control self-start" aria-label="검토 보기 방식">
        {([
          ["inbox", "검토함"],
          ["calendar", "일정"],
          ["alerts", "알림 설정"],
        ] as [Tab, string][]).map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => selectTab(value)}
            aria-pressed={tab === value}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "alerts" ? (
        <div className="space-y-4">
          <NotificationSettings />
          <section className="card">
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-primary-300">Watchlist rules</p>
            <h2 className="mt-2 font-semibold text-ink">관심종목 알림 조건</h2>
            <p className="mt-1 text-sm text-ink-secondary">
              종목별 상단·하단 가격과 일간 변동 기준은 관심종목의 투자 논거 편집에서 설정합니다.
            </p>
            <Link href="/stocksearch#watchlist" className="btn-secondary mt-4 inline-flex items-center gap-1.5">
              관심종목 열기 <ChevronRight size={15} />
            </Link>
          </section>
        </div>
      ) : error ? (
        <div className="card text-center">
          <p className="text-sm text-ink-secondary">검토 항목을 불러오지 못했습니다.</p>
          <button type="button" className="btn-secondary mt-3" onClick={() => refetch()}>다시 시도</button>
        </div>
      ) : isLoading ? (
        <div className="card"><LoadingState label="검토 항목을 정리하는 중..." /></div>
      ) : (
        <>
          {tab === "calendar" && data?.sources && data.sources.length > 0 && (
            <section className="rounded-2xl border border-edge bg-surface p-4">
              <div className="flex items-center gap-2">
                <Database size={17} className="text-primary-400" aria-hidden />
                <h2 className="font-semibold text-ink">일정 데이터 상태</h2>
              </div>
              <p className="mt-1 text-xs leading-5 text-ink-muted">
                일정 제공 상태를 함께 표시합니다. 공시는 접수 후 Observed로만 추가됩니다.
              </p>
              <div className="mt-4 flex gap-3 overflow-x-auto pb-1 sm:grid sm:grid-cols-2 sm:overflow-visible xl:grid-cols-3">
                {data.sources.map((source) => {
                  const status = SOURCE_STATUS[source.status] ?? SOURCE_STATUS.unavailable;
                  return (
                    <div key={source.provider} className="min-w-64 rounded-xl border border-edge bg-raised/50 p-3 sm:min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-sm font-medium text-ink">{source.label}</span>
                        <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${status.style}`}>
                          {status.label}
                        </span>
                      </div>
                      <p className="mt-2 text-xs text-ink-secondary">
                        {source.coverage ?? source.message ?? "상태 정보 없음"}
                      </p>
                      {source.coverage && source.message && (
                        <p className="mt-1 text-[11px] leading-4 text-ink-muted">{source.message}</p>
                      )}
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          <div className="scrollbar-hidden flex items-center gap-2 overflow-x-auto" aria-label="검토 항목 필터">
            {([
              ["all", "전체"],
              ["high", "높은 우선순위"],
              ["portfolio", "포트폴리오"],
              ["research", "리서치"],
              ["events", "이벤트"],
            ] as [Filter, string][]).map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => selectFilter(value)}
                className="filter-chip"
                aria-pressed={filter === value}
              >
                {label}
              </button>
            ))}
          </div>

          {items.length === 0 ? (
            <div className="card">
              <EmptyState icon={<CheckCircle2 size={28} />} title="지금 확인할 항목이 없습니다" hint="새로운 변화나 예정된 검토가 생기면 이곳에 표시됩니다." />
            </div>
          ) : tab === "calendar" ? (
            <div className="space-y-6">
              {groups.map(([day, dayItems]) => (
                <section key={day}>
                  <h2 className="mb-3 text-sm font-semibold text-ink-secondary">{dateLabel(day)}</h2>
                  <div className="space-y-3">{dayItems.map((item) => <ActionCard key={item.event_id} item={item} />)}</div>
                </section>
              ))}
            </div>
          ) : (
            <div className="space-y-3">{items.map((item) => <ActionCard key={item.event_id} item={item} />)}</div>
          )}

          <p className="font-mono text-[10px] uppercase tracking-wider text-ink-muted">
            생성 {data?.generated_at ? new Date(data.generated_at).toLocaleString("ko-KR") : "-"}
            {data?.data_as_of ? ` · 시장 데이터 ${data.data_as_of}` : ""}
          </p>
        </>
      )}
    </div>
  );
}
