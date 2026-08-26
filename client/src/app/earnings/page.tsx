"use client";

import {
  BarChart3,
  BookOpen,
  CalendarDays,
  ChevronRight,
  Clock3,
  Database,
  ExternalLink,
  FileText,
  History,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import EmptyState from "@/components/ui/EmptyState";
import LoadingState from "@/components/ui/LoadingState";
import PageHeader from "@/components/ui/PageHeader";
import {
  EarningsEvent,
  EarningsResultSignal,
  EarningsScope,
  useFetchEarningsQuery,
} from "@/state/api";

type Tab = "overview" | "calendar" | "results";

const TABS: { value: Tab; label: string }[] = [
  { value: "overview", label: "Overview" },
  { value: "calendar", label: "Calendar" },
  { value: "results", label: "Results" },
];

const SCOPES: { value: EarningsScope; label: string }[] = [
  { value: "all", label: "All Coverage" },
  { value: "mine", label: "My Coverage" },
  { value: "leaders", label: "Market Leaders" },
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

const dateLabel = (value: string) =>
  new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "short",
    day: "numeric",
    weekday: "short",
  }).format(new Date(`${value.slice(0, 10)}T00:00:00`));

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

function MetricBlock({
  title,
  actual,
  estimate,
  surprise,
  money = false,
}: {
  title: string;
  actual: number | null;
  estimate: number | null;
  surprise: number | null;
  money?: boolean;
}) {
  const format = money ? moneyLabel : numberLabel;
  const surpriseStyle =
    surprise == null ? "text-ink-muted" : surprise > 0 ? "text-gains" : surprise < 0 ? "text-losses" : "text-ink-secondary";
  return (
    <div className="rounded-xl border border-edge bg-raised/60 p-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{title}</p>
      <div className="mt-2 grid grid-cols-3 gap-2">
        <div>
          <p className="text-[11px] text-ink-muted">Actual</p>
          <p className="mt-0.5 text-sm font-semibold text-ink num">{format(actual)}</p>
        </div>
        <div>
          <p className="text-[11px] text-ink-muted">Estimate</p>
          <p className="mt-0.5 text-sm font-medium text-ink-secondary num">{format(estimate)}</p>
        </div>
        <div>
          <p className="text-[11px] text-ink-muted">Surprise</p>
          <p className={`mt-0.5 text-sm font-semibold num ${surpriseStyle}`}>{surpriseLabel(surprise)}</p>
        </div>
      </div>
    </div>
  );
}

function EarningsCard({ item }: { item: EarningsEvent }) {
  const router = useRouter();
  const timing = TIMING[item.release_timing] ?? TIMING.tbd;
  const period = [item.fiscal_year, item.fiscal_quarter ? `Q${item.fiscal_quarter}` : null]
    .filter(Boolean)
    .join(" ");
  const signal = item.result_signal ? SIGNAL[item.result_signal] : null;

  const saveToJournal = () => {
    const result = item.lifecycle === "reported"
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
        event_status: item.lifecycle === "reported" ? "observed" : "projected",
        scheduled_for: item.release_date,
        available_at: item.available_at,
        data_as_of: item.data_as_of,
        source: item.source,
      })
    );
    router.push("/journal?prefill=earnings");
  };

  return (
    <article className="rounded-2xl border border-edge bg-surface p-4 sm:p-5">
      <div className="flex flex-col gap-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2 text-xs text-ink-muted">
              {item.is_market_leader && <span className="badge-neutral">Market #{item.marketcap_rank}</span>}
              {item.scope === "portfolio" && <span className="badge-neutral">Portfolio</span>}
              {item.scope === "watchlist" && <span className="badge-neutral">Watchlist</span>}
              <span className="badge-neutral">{item.lifecycle === "reported" ? "Reported" : "Estimated"}</span>
              {signal && <span className={`rounded-full px-2 py-0.5 font-semibold ${signal.style}`}>{signal.label}</span>}
            </div>
            <h2 className="mt-2 truncate text-lg font-semibold text-ink">
              {item.ticker} <span className="font-normal text-ink-secondary">{item.name}</span>
            </h2>
            <p className="mt-1 text-sm text-ink-secondary">
              {period || "Fiscal period unavailable"} · {dateLabel(item.release_date)}
            </p>
          </div>
          <CalendarDays className="mt-1 shrink-0 text-primary-400" size={22} aria-hidden />
        </div>

        <div className="flex items-start gap-2 rounded-xl bg-raised px-3 py-2.5 text-sm">
          <Clock3 size={16} className="mt-0.5 shrink-0 text-ink-muted" aria-hidden />
          <div>
            <p className="font-medium text-ink">{timing.label}</p>
            <p className="text-xs text-ink-muted">{timing.hint}</p>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <MetricBlock
            title="EPS"
            actual={item.eps_actual}
            estimate={item.eps_estimate}
            surprise={item.eps_surprise_pct}
          />
          <MetricBlock
            title="Revenue"
            actual={item.revenue_actual}
            estimate={item.revenue_estimate}
            surprise={item.revenue_surprise_pct}
            money
          />
        </div>

        <details className="rounded-xl border border-edge px-3 py-2.5">
          <summary className="cursor-pointer text-sm font-medium text-ink">Earnings Call & Sources</summary>
          <div className="mt-3 space-y-2 text-xs leading-5 text-ink-secondary">
            {item.call_time || item.webcast_url ? (
              <p>확인된 어닝콜 정보가 있습니다.</p>
            ) : (
              <p>현재 소스는 정확한 어닝콜 시각·웹캐스트·전문을 제공하지 않습니다. 발표 시각을 어닝콜 시각으로 추정하지 않습니다.</p>
            )}
            <p>일정과 컨센서스는 Finnhub, 공식 제출 문서는 SEC에서 확인합니다. 미래 일정은 회사 확정 여부를 구분할 수 없어 Estimated로 표시합니다.</p>
          </div>
        </details>

        <div className="flex flex-wrap items-center gap-2">
          <Link href={item.stock_link} className="btn-primary inline-flex items-center gap-1.5">
            Open Stock <ChevronRight size={15} aria-hidden />
          </Link>
          {item.source_url && (
            <a href={item.source_url} target="_blank" rel="noopener noreferrer" className="btn-secondary inline-flex items-center gap-1.5">
              SEC Filings <ExternalLink size={14} aria-hidden />
            </a>
          )}
          <button type="button" onClick={saveToJournal} className="btn-secondary inline-flex items-center gap-1.5">
            <BookOpen size={14} aria-hidden /> Save to Journal
          </button>
          <span className="ml-auto text-[11px] text-ink-muted">Data {item.data_as_of}</span>
        </div>
      </div>
    </article>
  );
}

function Section({ title, description, items }: { title: string; description: string; items: EarningsEvent[] }) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="section-title">{title}</h2>
        <p className="mt-1 text-sm text-ink-muted">{description}</p>
      </div>
      {items.length ? (
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
          {items.map((item) => <EarningsCard key={item.event_id} item={item} />)}
        </div>
      ) : (
        <div className="card">
          <EmptyState icon={<CalendarDays size={28} aria-hidden />} title="이 범위에는 확인된 Earnings가 없습니다" hint="범위를 All Coverage로 바꾸거나 다음 일일 업데이트 후 다시 확인해 보세요." />
        </div>
      )}
    </section>
  );
}

export default function EarningsPage() {
  const [tab, setTab] = useState<Tab>("overview");
  const [scope, setScope] = useState<EarningsScope>("all");
  const { data, isLoading, error, refetch } = useFetchEarningsQuery({ scope, days: 90, resultsDays: 120 });

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const initialTab = params.get("tab") as Tab | null;
    const initialScope = params.get("scope") as EarningsScope | null;
    if (initialTab && TABS.some((item) => item.value === initialTab)) setTab(initialTab);
    if (initialScope && SCOPES.some((item) => item.value === initialScope)) setScope(initialScope);
  }, []);

  useEffect(() => {
    const url = new URL(window.location.href);
    url.searchParams.set("tab", tab);
    url.searchParams.set("scope", scope);
    window.history.replaceState(window.history.state, "", url);
  }, [scope, tab]);

  const upcoming = useMemo(() => tab === "overview" ? (data?.upcoming ?? []).slice(0, 6) : data?.upcoming ?? [], [data, tab]);
  const results = useMemo(() => tab === "overview" ? (data?.recent_results ?? []).slice(0, 6) : data?.recent_results ?? [], [data, tab]);
  const sourceReady = data?.source?.status === "ok";

  return (
    <div className="flex flex-col gap-6 pb-20">
      <PageHeader
        title="Earnings Hub"
        description="주요 미국 기업과 내 종목의 실적 일정·컨센서스·발표 결과를 한곳에서 비교합니다"
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[
          ["This Week", data?.summary.this_week ?? 0, CalendarDays],
          ["Upcoming", data?.summary.upcoming ?? 0, Clock3],
          ["Recent Results", data?.summary.reported_recently ?? 0, BarChart3],
          ["My Coverage", data?.summary.my_coverage ?? 0, FileText],
        ].map(([label, value, Icon]) => {
          const MetricIcon = Icon as typeof CalendarDays;
          return (
            <div key={String(label)} className="rounded-2xl border border-edge bg-surface p-4">
              <div className="flex items-center gap-2 text-xs text-ink-muted"><MetricIcon size={15} />{String(label)}</div>
              <p className="mt-2 text-2xl font-semibold text-ink num">{Number(value)}</p>
            </div>
          );
        })}
      </div>

      <div className="flex flex-col gap-3 rounded-2xl border border-edge bg-surface p-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex gap-1 overflow-x-auto">
          {TABS.map((item) => (
            <button key={item.value} type="button" onClick={() => setTab(item.value)} className={`whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium ${tab === item.value ? "bg-primary-500 text-white" : "text-ink-secondary hover:bg-raised hover:text-ink"}`}>
              {item.label}
            </button>
          ))}
        </div>
        <div className="flex gap-1 overflow-x-auto">
          {SCOPES.map((item) => (
            <button key={item.value} type="button" onClick={() => setScope(item.value)} className={`whitespace-nowrap rounded-full border px-3 py-1.5 text-xs font-medium ${scope === item.value ? "border-primary-400 bg-primary-400/15 text-primary-400" : "border-edge text-ink-muted hover:text-ink"}`}>
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {data && (
        <div className={`rounded-xl border p-3 text-sm ${sourceReady ? "border-gains/30 bg-gains/10" : "border-warning/30 bg-warning/10"}`}>
          <div className="flex items-start gap-2">
            <Database size={17} className={sourceReady ? "text-gains" : "text-warning"} aria-hidden />
            <div className="min-w-0 flex-1">
              <p className="font-medium text-ink">{sourceReady ? "Earnings Data Ready" : "Earnings Data Needs Attention"}</p>
              <p className="mt-0.5 text-xs leading-5 text-ink-secondary">
                {data.source?.message ?? "아직 발행된 Earnings 데이터가 없습니다."}
                {data.data_as_of && ` · Data ${data.data_as_of}`}
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

      {isLoading ? (
        <div className="card"><LoadingState label="Earnings 일정과 결과를 불러오는 중..." /></div>
      ) : error ? (
        <div className="card text-center">
          <p className="text-sm text-losses">Earnings 데이터를 불러오지 못했습니다.</p>
          <button type="button" className="btn-secondary mt-3" onClick={() => refetch()}>Retry</button>
        </div>
      ) : (
        <>
          {(tab === "overview" || tab === "calendar") && (
            <Section title="Upcoming Earnings" description="향후 90일의 공급자 발표 일정입니다. Estimated는 회사 확정 일정이라는 뜻이 아닙니다." items={upcoming} />
          )}
          {(tab === "overview" || tab === "results") && (
            <Section title="Recent Results" description="최근 120일 발표치와 컨센서스 차이입니다. Beat/Miss는 EPS와 매출을 함께 비교합니다." items={results} />
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
