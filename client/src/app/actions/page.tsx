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

const dateLabel = (value: string | null) => {
  if (!value) return "일정 미정";
  return new Intl.DateTimeFormat("ko-KR", {
    month: "short",
    day: "numeric",
    weekday: "short",
  }).format(new Date(`${value.slice(0, 10)}T00:00:00`));
};

const SOURCE_STATUS = {
  ok: { label: "Ready", style: "bg-gains/15 text-gains" },
  preserved: { label: "Last good", style: "bg-warning/15 text-warning" },
  configuration_required: { label: "Setup required", style: "bg-warning/15 text-warning" },
  upgrade_required: { label: "Upgrade required", style: "bg-warning/15 text-warning" },
  unavailable: { label: "Unavailable", style: "bg-losses/15 text-losses" },
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
    <article className="rounded-2xl border border-edge bg-surface p-4">
      <div className="flex items-start gap-3">
        <span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${SEVERITY_STYLE[item.severity]}`} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 text-xs text-ink-muted">
            <span className="badge-neutral">{item.category}</span>
            {item.market && <span className="badge-neutral">{item.market}</span>}
            {item.event_status && (
              <span className="badge-neutral capitalize">{item.event_status}</span>
            )}
            {(item.ticker || item.name) && <span>{item.ticker ?? item.name}</span>}
            {item.scheduled_for && <span>{dateLabel(item.scheduled_for)}</span>}
            {item.data_as_of && <span className="ml-auto">Data {item.data_as_of.slice(0, 10)}</span>}
          </div>
          <h2 className="mt-2 font-semibold text-ink">{item.title}</h2>
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
                Open <ChevronRight size={15} aria-hidden />
              </a>
            ) : (
              <Link
                href={item.link}
                className="btn-primary inline-flex items-center gap-1.5"
                onClick={() => updateState({ event_id: item.event_id, state: "read" })}
              >
                Open <ChevronRight size={15} aria-hidden />
              </Link>
            )}
            {item.actions.includes("journal") && (
              <button type="button" className="btn-secondary inline-flex items-center gap-1.5" onClick={saveToJournal}>
                <BookOpen size={15} aria-hidden /> Save to Journal
              </button>
            )}
            {item.actions.includes("snooze") && (
              <button type="button" className="btn-secondary inline-flex items-center gap-1.5" onClick={snooze} disabled={isLoading}>
                <Clock3 size={15} aria-hidden /> Tomorrow
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
        title="Action Center"
        description="시장 변화와 내 투자 판단에서 지금 확인할 항목을 우선순위로 정리합니다"
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[
          ["Actionable", data?.counts.actionable ?? 0, BellRing],
          ["High Priority", data?.counts.high ?? 0, Inbox],
          ["New", data?.counts.new ?? 0, CheckCircle2],
          ["Scheduled", data?.counts.scheduled ?? 0, CalendarDays],
        ].map(([label, value, Icon]) => {
          const MetricIcon = Icon as typeof BellRing;
          return (
            <div key={String(label)} className="rounded-2xl border border-edge bg-surface p-4">
              <div className="flex items-center gap-2 text-xs text-ink-muted"><MetricIcon size={15} />{String(label)}</div>
              <p className="mt-2 text-2xl font-semibold text-ink num">{Number(value)}</p>
            </div>
          );
        })}
      </div>

      <div className="flex gap-1 overflow-x-auto rounded-xl border border-edge bg-surface p-1">
        {([
          ["inbox", "Inbox"],
          ["calendar", "Calendar"],
          ["alerts", "Alerts"],
        ] as [Tab, string][]).map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => selectTab(value)}
            className={`min-w-24 rounded-lg px-4 py-2 text-sm font-medium ${tab === value ? "bg-primary-500 text-white" : "text-ink-secondary hover:bg-raised"}`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "alerts" ? (
        <div className="space-y-4">
          <NotificationSettings />
          <section className="card">
            <h2 className="font-semibold text-ink">Watchlist Rules</h2>
            <p className="mt-1 text-sm text-ink-secondary">
              종목별 상단·하단 가격과 일간 변동 기준은 Watchlist의 Thesis Editor에서 설정합니다.
            </p>
            <Link href="/stocksearch#watchlist" className="btn-secondary mt-4 inline-flex items-center gap-1.5">
              Open Watchlist <ChevronRight size={15} />
            </Link>
          </section>
        </div>
      ) : error ? (
        <div className="card text-center">
          <p className="text-sm text-ink-secondary">Action을 불러오지 못했습니다.</p>
          <button type="button" className="btn-secondary mt-3" onClick={() => refetch()}>Retry</button>
        </div>
      ) : isLoading ? (
        <div className="card"><LoadingState label="Action을 정리하는 중..." /></div>
      ) : (
        <>
          {tab === "calendar" && data?.sources && data.sources.length > 0 && (
            <section className="rounded-2xl border border-edge bg-surface p-4">
              <div className="flex items-center gap-2">
                <Database size={17} className="text-primary-400" aria-hidden />
                <h2 className="font-semibold text-ink">External Sources</h2>
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

          <div className="flex gap-2 overflow-x-auto">
            {([
              ["all", "All"],
              ["high", "High"],
              ["portfolio", "Portfolio"],
              ["research", "Research"],
              ["events", "Events"],
            ] as [Filter, string][]).map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => selectFilter(value)}
                className={`rounded-full border px-3 py-1.5 text-xs font-medium ${filter === value ? "border-primary-400 bg-primary-500/15 text-primary-400" : "border-edge text-ink-muted"}`}
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

          <p className="text-xs text-ink-muted">
            Generated {data?.generated_at ? new Date(data.generated_at).toLocaleString("ko-KR") : "-"}
            {data?.data_as_of ? ` · Market data ${data.data_as_of}` : ""}
          </p>
        </>
      )}
    </div>
  );
}
