"use client";

import {
  BarChart3,
  BookOpen,
  CalendarDays,
  ChevronRight,
  Clock3,
  Database,
  ExternalLink,
  History,
  Search,
  X,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import EmptyState from "@/components/ui/EmptyState";
import LoadingState from "@/components/ui/LoadingState";
import PageHeader from "@/components/ui/PageHeader";
import {
  EarningsEvent,
  EarningsDisplayStatus,
  EarningsResultSignal,
  EarningsScope,
  useFetchEarningsQuery,
} from "@/state/api";

type Tab = "overview" | "calendar" | "results";

const TABS: { value: Tab; label: string }[] = [
  { value: "overview", label: "한눈에 보기" },
  { value: "calendar", label: "발표 일정" },
  { value: "results", label: "발표 결과" },
];

const SCOPES: { value: EarningsScope; label: string }[] = [
  { value: "all", label: "전체" },
  { value: "mine", label: "내 종목" },
  { value: "leaders", label: "시장 대표" },
];

const CALENDAR_WINDOWS = [
  { value: 30, label: "향후 30일" },
  { value: 90, label: "향후 90일" },
  { value: 180, label: "향후 180일" },
];

const RESULT_WINDOWS = [
  { value: 120, label: "최근 120일" },
  { value: 365, label: "최근 1년" },
  { value: 1098, label: "최근 3년" },
];

const TIMING: Record<string, { label: string; hint: string }> = {
  bmo: { label: "Before Market Open", hint: "미국장 개장 전" },
  amc: { label: "After Market Close", hint: "미국장 마감 후 · 한국은 통상 다음날 새벽" },
  dmh: { label: "During Market Hours", hint: "미국장 거래 중" },
  tbd: { label: "Time TBD", hint: "발표 시각 미정" },
};

const SIGNAL: Record<Exclude<EarningsResultSignal, null>, { label: string; style: string }> = {
  beat: { label: "Beat", style: "bg-gains/15 text-gains" },
  miss: { label: "Miss", style: "bg-losses/15 text-losses" },
  mixed: { label: "Mixed", style: "bg-warning/15 text-warning" },
  in_line: { label: "In Line", style: "bg-raised text-ink-secondary" },
};

const DISPLAY_STATUS: Record<EarningsDisplayStatus, { label: string; style: string }> = {
  upcoming: { label: "Estimated", style: "bg-raised text-ink-secondary" },
  awaiting_results: { label: "Awaiting Results", style: "bg-warning/15 text-warning" },
  result_unavailable: { label: "Result Unavailable", style: "bg-losses/15 text-losses" },
  reported: { label: "Reported", style: "bg-gains/15 text-gains" },
};

const dateLabel = (value: string) =>
  new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "short",
    day: "numeric",
    weekday: "short",
  }).format(new Date(`${value.slice(0, 10)}T00:00:00`));

const dateParts = (value: string) => {
  const date = new Date(`${value.slice(0, 10)}T00:00:00`);
  return {
    month: new Intl.DateTimeFormat("ko-KR", { month: "short" }).format(date),
    day: new Intl.DateTimeFormat("ko-KR", { day: "2-digit" }).format(date),
    weekday: new Intl.DateTimeFormat("ko-KR", { weekday: "short" }).format(date),
  };
};

const numberLabel = (value: number | null, digits = 2) =>
  value == null
    ? "—"
    : new Intl.NumberFormat("en-US", { maximumFractionDigits: digits }).format(value);

const moneyLabel = (value: number | null) => {
  if (value == null) return "—";
  const absolute = Math.abs(value);
  if (absolute >= 1e12) return `$${(value / 1e12).toFixed(2)}T`;
  if (absolute >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
  if (absolute >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  return `$${new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value)}`;
};

const surpriseLabel = (value: number | null) =>
  value == null ? "—" : `${value > 0 ? "+" : ""}${value.toFixed(1)}%`;

const dateTimeLabel = (value?: string | null) => {
  if (!value) return null;
  return new Intl.DateTimeFormat("ko-KR", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Seoul",
  }).format(new Date(value));
};

function MetricBlock({
  title,
  actual,
  estimate,
  surprise,
  actualNote,
  money = false,
}: {
  title: string;
  actual: number | null;
  estimate: number | null;
  surprise: number | null;
  actualNote?: string | null;
  money?: boolean;
}) {
  const format = money ? moneyLabel : numberLabel;
  const surpriseStyle =
    surprise == null ? "text-ink-muted" : surprise > 0 ? "text-gains" : surprise < 0 ? "text-losses" : "text-ink-secondary";
  return (
    <div className="grid min-w-[30rem] grid-cols-[5.5rem_repeat(3,minmax(6rem,1fr))] items-end gap-3 border-b border-edge py-3 last:border-b-0">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-ink-muted">{title}</p>
      <div>
        <p className="text-[10px] uppercase tracking-wide text-ink-muted">실제</p>
        <p className="mt-0.5 text-sm font-semibold text-ink num">{format(actual)}</p>
        {actualNote && <p className="mt-0.5 text-[10px] text-ink-muted">{actualNote}</p>}
      </div>
      <div>
        <p className="text-[10px] uppercase tracking-wide text-ink-muted">예상</p>
        <p className="mt-0.5 text-sm font-medium text-ink-secondary num">{format(estimate)}</p>
      </div>
      <div>
        <p className="text-[10px] uppercase tracking-wide text-ink-muted">차이</p>
        <p className={`mt-0.5 text-sm font-semibold num ${surpriseStyle}`}>{surpriseLabel(surprise)}</p>
      </div>
    </div>
  );
}

function EarningsCard({ item }: { item: EarningsEvent }) {
  const router = useRouter();
  const timing = TIMING[item.release_timing] ?? TIMING.tbd;
  const displayStatus = DISPLAY_STATUS[item.display_status]
    ?? DISPLAY_STATUS[item.lifecycle === "reported" ? "reported" : "upcoming"];
  const period = [item.fiscal_year, item.fiscal_quarter ? `Q${item.fiscal_quarter}` : null]
    .filter(Boolean)
    .join(" ");
  const signal = item.result_signal ? SIGNAL[item.result_signal] : null;
  const officialResultFiled = item.official_result_status === "filed";
  const officialFallback = item.actual_reconciliation_status === "official_only";
  const reconciliationDiffers = item.actual_reconciliation_status === "differs";
  const reconciliationMatched = item.actual_reconciliation_status === "matched";
  const epsActualNote = item.eps_actual_basis === "non_gaap_diluted"
    ? "Official non-GAAP"
    : item.eps_actual_basis === "gaap_diluted"
      ? "Official GAAP"
      : item.eps_actual_source === "finnhub"
        ? "Finnhub standardized"
        : null;
  const revenueActualNote = item.revenue_actual_source === "sec"
    ? "Official release"
    : item.revenue_actual_source === "finnhub"
      ? "Finnhub standardized"
      : null;
  const releaseDate = dateParts(item.release_date);
  const railStyle = item.display_status === "reported"
    ? "from-gains via-gains/60 to-transparent"
    : item.display_status === "awaiting_results" || item.display_status === "result_unavailable"
      ? "from-warning via-warning/60 to-transparent"
      : "from-primary-400 via-primary-500/60 to-transparent";
  const dotStyle = item.display_status === "reported"
    ? "border-gains shadow-[0_0_12px_rgba(52,211,153,0.55)]"
    : item.display_status === "awaiting_results" || item.display_status === "result_unavailable"
      ? "border-warning shadow-[0_0_12px_rgba(251,191,36,0.55)]"
      : "border-primary-300 shadow-[0_0_12px_rgba(155,126,255,0.65)]";

  const saveToJournal = () => {
    const result = item.display_status === "reported"
      ? `EPS ${numberLabel(item.eps_actual)} vs ${numberLabel(item.eps_estimate)}, Revenue ${moneyLabel(item.revenue_actual)} vs ${moneyLabel(item.revenue_estimate)}`
      : `EPS estimate ${numberLabel(item.eps_estimate)}, Revenue estimate ${moneyLabel(item.revenue_estimate)}`;
    sessionStorage.setItem(
      "ii-journal-prefill",
      JSON.stringify({
        event_id: item.event_id,
        kind: "event",
        category: "earnings",
        severity: "medium",
        title: `${item.ticker} ${period || "Earnings"}`,
        detail: `${dateLabel(item.release_date)} · ${timing.label} · ${result}`,
        link: item.stock_link,
        meta_id: item.meta_id,
        ticker: item.ticker,
        name: item.name,
        market: "US",
        scope: item.scope,
        event_status: item.display_status === "reported" ? "observed" : "projected",
        scheduled_for: item.release_date,
        available_at: item.available_at,
        data_as_of: item.data_as_of,
        source: officialFallback ? "sec" : item.source,
      })
    );
    router.push("/journal?prefill=earnings");
  };

  return (
    <article className="grid gap-4 px-4 py-5 sm:px-5 md:grid-cols-[7.5rem_minmax(0,1fr)] md:gap-6 md:px-6 md:py-6">
      <div className="relative min-h-14 pl-5 md:min-h-0 md:pl-0 md:pr-6">
        <span aria-hidden className={`absolute bottom-0 left-0 top-0 w-px bg-gradient-to-b md:left-auto md:right-0 ${railStyle}`} />
        <span aria-hidden className={`absolute left-[-3px] top-1 h-[7px] w-[7px] rounded-full border bg-surface md:left-auto md:right-[-3px] ${dotStyle}`} />
        <div className="flex items-baseline gap-2 md:block">
          <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-primary-300">{releaseDate.month}</p>
          <p className="num text-2xl font-semibold tracking-[-0.04em] text-ink md:mt-1 md:text-3xl">{releaseDate.day}</p>
          <p className="text-xs text-ink-muted md:mt-1">{releaseDate.weekday} · US</p>
        </div>
      </div>

      <div className="min-w-0">
        <div className="flex flex-col gap-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2 text-xs text-ink-muted">
              {item.is_market_leader && <span className="badge-neutral">Market #{item.marketcap_rank}</span>}
              {item.scope === "portfolio" && <span className="badge-neutral">Portfolio</span>}
              {item.scope === "watchlist" && <span className="badge-neutral">Watchlist</span>}
              <span className={`rounded-full px-2 py-0.5 font-medium ${displayStatus.style}`}>{displayStatus.label}</span>
              {officialResultFiled && <span className="rounded-full bg-primary-400/15 px-2 py-0.5 font-semibold text-primary-400">Official Result Filed</span>}
              {officialFallback && <span className="rounded-full bg-primary-400/15 px-2 py-0.5 font-semibold text-primary-300">Official Actual</span>}
              {reconciliationMatched && <span className="rounded-full bg-gains/15 px-2 py-0.5 font-semibold text-gains">Sources Matched</span>}
              {reconciliationDiffers && <span className="rounded-full bg-warning/15 px-2 py-0.5 font-semibold text-warning">Source Difference</span>}
              {signal && <span className={`rounded-full px-2 py-0.5 font-semibold ${signal.style}`}>{signal.label}</span>}
            </div>
            <h3 className="mt-2 truncate text-lg font-semibold tracking-[-0.02em] text-ink">
              {item.ticker} <span className="font-normal text-ink-secondary">{item.name}</span>
            </h3>
            <p className="mt-1 text-sm text-ink-secondary">
              {period || "회계 기간 미확인"} · {dateLabel(item.release_date)}
            </p>
          </div>
        </div>

        <div className="flex items-start gap-2 border-y border-edge py-3 text-sm">
          <Clock3 size={16} className="mt-0.5 shrink-0 text-ink-muted" aria-hidden />
          <div>
            <p className="font-medium text-ink">{timing.label}</p>
            <p className="text-xs text-ink-muted">
              {officialFallback
                ? "SEC 공식 발표 수치를 먼저 반영했습니다. Finnhub 표준 Actual은 도착 후 자동 대조됩니다."
                : reconciliationDiffers
                  ? "Finnhub 표준값과 공식 발표 수치에 차이가 있어 두 출처를 함께 보존하고 있습니다."
                  : item.display_status === "awaiting_results"
                    ? officialResultFiled
                      ? "SEC 공식 실적 공시는 확인됐지만 안전하게 추출 가능한 수치는 아직 없습니다."
                      : "발표 구간이 지났으며 공급자의 실제치 반영을 기다리는 중입니다."
                    : item.display_status === "result_unavailable"
                      ? officialResultFiled
                        ? "SEC 공식 실적 공시는 확인됐지만 Finnhub 표준 Actual은 아직 확인되지 않았습니다."
                        : "발표 구간은 지났지만 현재 공급자에서 실제치를 확인하지 못했습니다."
                      : timing.hint}
            </p>
          </div>
        </div>

        <div className="scrollbar-hidden overflow-x-auto">
          <MetricBlock title="EPS" actual={item.eps_actual} estimate={item.eps_estimate} surprise={item.eps_surprise_pct} actualNote={epsActualNote} />
          <MetricBlock title="Revenue" actual={item.revenue_actual} estimate={item.revenue_estimate} surprise={item.revenue_surprise_pct} actualNote={revenueActualNote} money />
        </div>

        <details className="border-t border-edge pt-3">
          <summary className="cursor-pointer text-sm font-medium text-ink">어닝콜 · 데이터 근거</summary>
          <div className="mt-3 space-y-2 text-xs leading-5 text-ink-secondary">
            {item.call_time || item.webcast_url ? (
              <p>확인된 어닝콜 정보가 있습니다.</p>
            ) : (
              <p>현재 소스는 정확한 어닝콜 시각·웹캐스트·전문을 제공하지 않습니다. 발표 시각을 어닝콜 시각으로 추정하지 않습니다.</p>
            )}
            {officialResultFiled && (
              <p>SEC {item.official_result_form ?? "filing"}에서 공식 결과 발표를 확인했습니다.</p>
            )}
            {item.official_actual_status === "extracted" && (
              <p>
                공식 발표: GAAP EPS {numberLabel(item.official_eps_gaap_actual ?? null)} · Adjusted EPS {numberLabel(item.official_eps_adjusted_actual ?? null)} · Revenue {moneyLabel(item.official_revenue_actual ?? null)}.
              </p>
            )}
            {officialFallback && <p>공식 EPS는 회계 기준을 표시하되 Finnhub 컨센서스와 직접 비교하지 않습니다. 매출은 같은 통화 기준일 때만 차이를 계산하며, 종합 Beat/Miss는 표준 Actual 도착 전까지 보류합니다.</p>}
            {reconciliationMatched && <p>Finnhub 표준 Actual과 SEC 공식 발표 수치가 허용 오차 안에서 일치합니다.</p>}
            {reconciliationDiffers && <p>Finnhub 표준 Actual과 SEC 공식 발표 수치가 허용 오차를 벗어났습니다. 화면 Actual은 Finnhub 표준값이며 공식값은 위에 함께 남깁니다.</p>}
            <p>일정·컨센서스·표준 Actual은 Finnhub, 공식 결과와 선반영 수치는 SEC 제출 문서에서 확인합니다.</p>
          </div>
        </details>

        <div className="flex flex-wrap items-center gap-2 border-t border-edge pt-3">
          <Link href={item.stock_link} className="btn-secondary inline-flex items-center gap-1.5 text-xs">
            종목 보기 <ChevronRight size={15} aria-hidden />
          </Link>
          {item.official_result_url && (
            <a href={item.official_result_url} target="_blank" rel="noopener noreferrer" className="btn-secondary inline-flex items-center gap-1.5 text-xs">
              공식 공시 <ExternalLink size={14} aria-hidden />
            </a>
          )}
          {item.official_actual_url && item.official_actual_url !== item.official_result_url && (
            <a href={item.official_actual_url} target="_blank" rel="noopener noreferrer" className="btn-secondary inline-flex items-center gap-1.5 text-xs">
              Official Release <ExternalLink size={14} aria-hidden />
            </a>
          )}
          {item.source_url && (
            <a href={item.source_url} target="_blank" rel="noopener noreferrer" className="btn-secondary inline-flex items-center gap-1.5 text-xs">
              SEC 제출 목록 <ExternalLink size={14} aria-hidden />
            </a>
          )}
          <button type="button" onClick={saveToJournal} className="btn-secondary inline-flex items-center gap-1.5 text-xs">
            <BookOpen size={14} aria-hidden /> 저널에 저장
          </button>
          <span className="ml-auto text-[11px] text-ink-muted">Data {item.data_as_of}</span>
        </div>
      </div>
      </div>
    </article>
  );
}

function Section({
  title,
  description,
  items,
  emptyTitle = "이 범위에는 확인된 Earnings가 없습니다",
  emptyHint = "범위를 All Coverage로 바꾸거나 다음 데이터 업데이트 후 다시 확인해 보세요.",
}: {
  title: string;
  description: string;
  items: EarningsEvent[];
  emptyTitle?: string;
  emptyHint?: string;
}) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="section-title">{title}</h2>
        <p className="mt-1 text-sm text-ink-muted">{description}</p>
      </div>
      {items.length ? (
        <div className="divide-y divide-edge overflow-hidden rounded-2xl border border-edge bg-surface shadow-[0_18px_60px_rgba(0,0,0,0.12)]">
          {items.map((item) => <EarningsCard key={item.event_id} item={item} />)}
        </div>
      ) : (
        <div className="card">
          <EmptyState icon={<CalendarDays size={28} aria-hidden />} title={emptyTitle} hint={emptyHint} />
        </div>
      )}
    </section>
  );
}

export default function EarningsPage() {
  const [tab, setTab] = useState<Tab>("overview");
  const [scope, setScope] = useState<EarningsScope>("all");
  const [calendarDays, setCalendarDays] = useState(90);
  const [resultsDays, setResultsDays] = useState(365);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const initialTab = params.get("tab") as Tab | null;
    const initialScope = params.get("scope") as EarningsScope | null;
    const initialCalendarDays = Number(params.get("days"));
    const initialResultsDays = Number(params.get("resultsDays"));
    if (initialTab && TABS.some((item) => item.value === initialTab)) setTab(initialTab);
    if (initialScope && SCOPES.some((item) => item.value === initialScope)) setScope(initialScope);
    if (CALENDAR_WINDOWS.some((item) => item.value === initialCalendarDays)) setCalendarDays(initialCalendarDays);
    if (RESULT_WINDOWS.some((item) => item.value === initialResultsDays)) setResultsDays(initialResultsDays);
    setSearch(params.get("q") ?? "");
    setHydrated(true);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebouncedSearch(search.trim()), 250);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    if (!hydrated) return;
    const url = new URL(window.location.href);
    url.searchParams.set("tab", tab);
    url.searchParams.set("scope", scope);
    url.searchParams.set("days", String(calendarDays));
    url.searchParams.set("resultsDays", String(resultsDays));
    if (search.trim()) url.searchParams.set("q", search.trim());
    else url.searchParams.delete("q");
    window.history.replaceState(window.history.state, "", url);
  }, [calendarDays, hydrated, resultsDays, scope, search, tab]);

  const { data, isLoading, isFetching, error, refetch } = useFetchEarningsQuery({
    scope,
    days: calendarDays,
    resultsDays,
    query: debouncedSearch,
  });

  const compactOverview = tab === "overview" && !debouncedSearch;
  const upcoming = useMemo(
    () => compactOverview ? (data?.upcoming ?? []).slice(0, 6) : data?.upcoming ?? [],
    [compactOverview, data],
  );
  const pending = useMemo(
    () => compactOverview ? (data?.pending_results ?? []).slice(0, 6) : data?.pending_results ?? [],
    [compactOverview, data],
  );
  const results = useMemo(
    () => compactOverview ? (data?.recent_results ?? []).slice(0, 6) : data?.recent_results ?? [],
    [compactOverview, data],
  );
  const sourceStale = data?.source?.freshness === "stale";
  const sourceReady = data?.source?.status === "ok" && !sourceStale;
  const sourceTitle = sourceStale
    ? "Earnings Data Stale"
    : sourceReady
      ? "Earnings Data Ready"
      : "Earnings Data Needs Attention";
  const sourceMessage = sourceStale
    ? `원본이 기대 기준일 ${data?.source?.expected_as_of ?? "—"}보다 오래됐습니다. 이 상태의 Actual 결측은 공급자 지연으로 해석하지 않습니다.`
    : data?.source?.message ?? "아직 발행된 Earnings 데이터가 없습니다.";
  const awaitingDescription = sourceStale
    ? "원본 갱신이 지연되어 Actual 도착 여부를 아직 판정할 수 없습니다. 배치 복구 후 자동으로 다시 분류됩니다."
    : "발표 후 Actual을 기다리는 이벤트입니다. SEC 공식 수치를 안전하게 읽으면 Results로 먼저 이동하고, 아니면 Finnhub 반영을 기다립니다.";
  const lastUpdated = dateTimeLabel(data?.source?.available_at);
  const hasVisibleEvents = tab === "calendar"
    ? upcoming.length > 0
    : tab === "results"
      ? pending.length + results.length > 0
      : upcoming.length + pending.length + results.length > 0;
  const hasActiveFilters = Boolean(search.trim()) || scope !== "all" || calendarDays !== 90 || resultsDays !== 365;
  const emptyTitle = debouncedSearch
    ? `“${debouncedSearch}” Earnings를 찾지 못했습니다`
    : "선택한 범위에는 Earnings가 없습니다";

  const resetFilters = () => {
    setSearch("");
    setScope("all");
    setCalendarDays(90);
    setResultsDays(365);
  };

  return (
    <div className="flex flex-col gap-6 pb-20">
      <PageHeader
        eyebrow="Event calendar"
        title="실적 일정"
        description="주요 미국 기업과 내 종목의 실적 일정·컨센서스·발표 결과를 한 흐름에서 비교합니다."
        meta={
          <>
            <span>예정 {data?.summary.upcoming ?? 0}건</span>
            <span>·</span>
            <span>{lastUpdated ? `마지막 반영 ${lastUpdated}` : "원본 확인 중"}</span>
          </>
        }
      />

      <div
        className="scrollbar-hidden -mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0"
        role="group"
        aria-label="실적 일정 요약"
        tabIndex={0}
      >
        <section className="metric-strip min-w-[40rem] grid-cols-4 sm:min-w-0" aria-label="실적 일정 요약">
        {[
          ["이번 주", data?.summary.this_week ?? 0, CalendarDays, "calendar"],
          ["발표 예정", data?.summary.upcoming ?? 0, Clock3, "calendar"],
          ["결과 대기", data?.summary.awaiting_results ?? 0, History, "results"],
          ["최근 결과", data?.summary.reported_recently ?? 0, BarChart3, "results"],
        ].map(([label, value, Icon, target]) => {
          const MetricIcon = Icon as typeof CalendarDays;
          return (
            <button
              key={String(label)}
              type="button"
              onClick={() => setTab(target as Tab)}
              className="metric-tile p-4 text-left transition-colors hover:bg-raised sm:p-5"
              aria-pressed={tab === target}
            >
              <div className="flex items-center gap-2 text-xs text-ink-muted"><MetricIcon size={15} />{String(label)}</div>
              <p className={`mt-2 text-2xl font-semibold num ${label === "결과 대기" && Number(value) > 0 ? "text-warning" : "text-ink"}`}>{Number(value)}</p>
            </button>
          );
        })}
        </section>
      </div>

      <div className="space-y-3 rounded-2xl border border-edge bg-surface p-3 sm:p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="segmented-control border-0 bg-transparent p-0" aria-label="실적 보기 방식">
            {TABS.map((item) => (
              <button key={item.value} type="button" onClick={() => setTab(item.value)} aria-pressed={tab === item.value}>
                {item.label}
              </button>
            ))}
          </div>
          <div className="scrollbar-hidden flex gap-1 overflow-x-auto" aria-label="실적 대상 필터">
            {SCOPES.map((item) => (
              <button key={item.value} type="button" onClick={() => setScope(item.value)} className="filter-chip" aria-pressed={scope === item.value}>
                {item.label}
              </button>
            ))}
          </div>
        </div>

        <div className="grid gap-2 border-t border-edge pt-3 md:grid-cols-[minmax(240px,1fr)_150px_150px_auto]">
          <label className="relative block">
            <span className="sr-only">Search earnings</span>
            <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" size={17} aria-hidden />
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="input h-11 pl-10 pr-10"
              placeholder="Ticker or company · 예: NVDA, Nvidia"
              autoComplete="off"
            />
            {search && (
              <button type="button" onClick={() => setSearch("")} className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg p-2 text-ink-muted hover:bg-overlay hover:text-ink" aria-label="Clear search">
                <X size={15} aria-hidden />
              </button>
            )}
          </label>
          <label>
            <span className="sr-only">Calendar window</span>
            <select className="input h-11" value={calendarDays} onChange={(event) => setCalendarDays(Number(event.target.value))}>
              {CALENDAR_WINDOWS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
          </label>
          <label>
            <span className="sr-only">Results history</span>
            <select className="input h-11" value={resultsDays} onChange={(event) => setResultsDays(Number(event.target.value))}>
              {RESULT_WINDOWS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
          </label>
          {hasActiveFilters && (
            <button type="button" className="btn-secondary h-11 whitespace-nowrap" onClick={resetFilters}>초기화</button>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink-muted">
          <span>검색 범위: Market Leaders + My Coverage</span>
          {debouncedSearch && data && <span className="text-ink-secondary">매칭 이벤트 {data.coverage.filtered_events}건</span>}
          {isFetching && !isLoading && <span className="ml-auto text-primary-400" role="status">Updating…</span>}
        </div>
      </div>

      {data && (
        <div className={`rounded-xl border p-3 text-sm ${sourceReady ? "border-gains/30 bg-gains/10" : "border-warning/30 bg-warning/10"}`}>
          <div className="flex items-start gap-2">
            <Database size={17} className={sourceReady ? "text-gains" : "text-warning"} aria-hidden />
            <div className="min-w-0 flex-1">
              <p className="font-medium text-ink">{sourceTitle}</p>
              <p className="mt-0.5 text-xs leading-5 text-ink-secondary">
                {sourceMessage}
                {lastUpdated && ` · Last updated ${lastUpdated} KST`}
              </p>
              <p className="mt-1 text-xs leading-5 text-ink-muted">
                {sourceStale
                  ? "정기 원본 갱신이 지연됐습니다. 복구 전에는 Actual 결측을 공급자 지연으로 판단하지 않습니다."
                  : "정기 원본 갱신은 09:00·19:00 KST 배치 후 반영됩니다. 공식 SEC 수치는 먼저 표시하고 Finnhub 표준값은 도착 후 자동 대조합니다."}
              </p>
              <details className="mt-2 text-xs text-ink-muted">
                <summary className="cursor-pointer">Data Coverage</summary>
                <p className="mt-2 leading-5">
                  현재 유니버스 {data.coverage.universe_total}개 · 시장 대표기업 {data.coverage.market_leaders ?? 0}개 · 선택 범위 {data.coverage.filtered_universe}개 · 이벤트 {data.coverage.filtered_events}/{data.coverage.events_total}건
                  {data.source?.reference_match_pct != null && ` · 종목 참조 매칭 ${data.source.reference_match_pct}%`}
                  {data.source?.cik_coverage_pct != null && ` · CIK ${data.source.cik_coverage_pct}%`}
                  {data.coverage.history_start && ` · 이력 ${data.coverage.history_start}부터`}
                </p>
              </details>
            </div>
          </div>
        </div>
      )}

      {data && data.summary.awaiting_results > 0 && (
        <div className="rounded-xl border border-warning/30 bg-warning/10 p-3 text-sm">
          <p className="font-medium text-ink">Awaiting Results · {data.summary.awaiting_results}건</p>
          <p className="mt-1 text-xs leading-5 text-ink-secondary">
            {sourceStale
              ? awaitingDescription
              : data.summary.official_results_available > 0
              ? `이 중 ${data.summary.official_results_available}건은 SEC 공식 결과 공시가 확인됐지만 안전하게 추출 가능한 수치가 없어 Finnhub Actual을 기다리고 있습니다.`
              : "발표 구간은 지났지만 Finnhub 실제치가 아직 도착하지 않은 이벤트입니다. Results에서 사라지지 않고 실제치가 들어오면 자동으로 Reported로 전환됩니다."}
          </p>
        </div>
      )}

      {isLoading ? (
        <div className="card"><LoadingState label="Earnings 일정과 결과를 불러오는 중..." /></div>
      ) : error ? (
        <div className="card text-center">
          <p className="text-sm text-losses">Earnings 데이터를 불러오지 못했습니다.</p>
          <button type="button" className="btn-secondary mt-3" onClick={() => refetch()}>Retry</button>
        </div>
      ) : (
        <>
          {tab === "overview" && upcoming.length > 0 && (
            <Section title="발표 예정" description={`향후 ${calendarDays}일의 공급자 발표 일정입니다. Estimated는 회사 확정 일정이라는 뜻이 아닙니다.`} items={upcoming} />
          )}
          {(tab === "overview" || tab === "results") && pending.length > 0 && (
            <Section title="결과 반영 대기" description={awaitingDescription} items={pending} />
          )}
          {tab === "overview" && results.length > 0 && (
            <Section title="최근 발표 결과" description={`최근 ${resultsDays}일 발표치와 컨센서스 차이입니다. Beat/Miss는 EPS와 매출을 함께 비교합니다.`} items={results} />
          )}
          {tab === "calendar" && (
            <Section
              title="발표 예정"
              description={`향후 ${calendarDays}일의 공급자 발표 일정입니다. Estimated는 회사 확정 일정이라는 뜻이 아닙니다.`}
              items={upcoming}
              emptyTitle={emptyTitle}
            />
          )}
          {tab === "results" && results.length > 0 && (
            <Section title="발표 결과" description={`최근 ${resultsDays}일 발표치와 컨센서스 차이입니다. Beat/Miss는 EPS와 매출을 함께 비교합니다.`} items={results} />
          )}
          {!hasVisibleEvents && tab !== "calendar" && (
            <div className="card text-center">
              <EmptyState icon={<Search size={28} aria-hidden />} title={emptyTitle} hint="티커·회사명을 확인하거나 Coverage와 기간을 넓혀 보세요." />
              {hasActiveFilters && <button type="button" className="btn-secondary -mt-8" onClick={resetFilters}>필터 초기화</button>}
            </div>
          )}
          {tab === "overview" && data && data.revisions.length > 0 && (
            <section className="card">
              <div className="flex items-center gap-2"><History size={18} className="text-ink-muted" /><h2 className="section-title">Schedule Changes</h2></div>
              <div className="mt-3 divide-y divide-edge">
                {data.revisions.slice(0, 5).map((revision) => (
                  <div key={revision.revision_id} className="flex flex-wrap items-center gap-2 py-2 text-sm">
                    <span className="font-semibold text-ink">{revision.ticker}</span>
                    <span className="text-ink-secondary">{revision.previous_release_date} → {revision.release_date}</span>
                    <span className="ml-auto text-xs text-ink-muted">확인 {revision.observed_at.slice(0, 10)}</span>
                  </div>
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
