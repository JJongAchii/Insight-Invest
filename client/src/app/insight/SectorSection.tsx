"use client";

import React, { useEffect, useMemo, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { ArrowDownUp, ExternalLink, Grid2X2, Layers3, RefreshCw } from "lucide-react";
import {
  InsightSectorPeriod, MarketGroupKind, MarketGroupMarket, MarketGroupSummary,
  useFetchMarketGroupDetailQuery, useFetchMarketGroupsQuery,
} from "@/state/api";
import TimeSeriesChart from "@/components/charts/TimeSeriesChart";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";
import EmptyState from "@/components/ui/EmptyState";
import GroupMembersTable from "./GroupMembersTable";
import { fmtEok, fmtJo, fmtPct, signClass } from "./format";
import { fmtPp, plainPct, updateGroupView } from "./groupView";

const PERIODS: { id: InsightSectorPeriod; label: string }[] = [
  { id: "1d", label: "1일" }, { id: "1w", label: "1주" }, { id: "1m", label: "1개월" },
  { id: "3m", label: "3개월" }, { id: "ytd", label: "연초 이후" },
];
const METRICS = [
  { id: "return_pct", label: "수익률" }, { id: "excess_pp", label: "시장 대비" },
  { id: "advancing_pct", label: "상승 종목 비율" }, { id: "frgn_net", label: "외국인 순매수" },
  { id: "inst_net", label: "기관 순매수" },
] as const;
type Metric = typeof METRICS[number]["id"];
const metricValue = (value: number | null, metric: Metric) => {
  if (metric === "frgn_net" || metric === "inst_net") return fmtEok(value);
  if (metric === "excess_pp") return fmtPp(value);
  return metric === "advancing_pct" ? plainPct(value) : fmtPct(value);
};
const score = (row: MarketGroupSummary, metric: Metric) => {
  const value = row[metric];
  return value == null ? null : metric === "advancing_pct" ? value - 50 : value;
};

function GroupFacts({ summary: s }: { summary: MarketGroupSummary }) {
  const total = s.period_covered_count;
  const segments = [
    { n: s.advancing_count, color: "var(--gains)" },
    { n: s.unchanged_count, color: "var(--text-muted)" },
    { n: s.declining_count, color: "var(--losses)" },
  ];
  const concentrated = s.return_pct != null && s.return_pct > 0 && s.advancing_pct != null && s.advancing_pct < 50;
  return <div className="space-y-4 border-t border-edge pt-4">
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <span className="text-ink-secondary">상승 종목 비율 <strong className="num ml-1 text-ink">{plainPct(s.advancing_pct)}</strong></span>
        <span className="text-ink-muted">기간 등락 확인 {total}/{s.member_count}종목</span>
      </div>
      <div className="flex h-2 overflow-hidden rounded-full bg-raised" aria-hidden>
        {segments.map(({ n, color }, index) => <span key={index} style={{ width: `${total ? n / total * 100 : 0}%`, backgroundColor: color }} />)}
      </div>
      <p className="text-[11px] text-ink-muted">상승 {s.advancing_count} · 보합 {s.unchanged_count} · 하락 {s.declining_count}</p>
    </div>
    {concentrated && <p className="rounded-lg bg-raised px-3 py-2 text-xs leading-5 text-ink-secondary">그룹 수익률은 올랐지만 상승 종목은 절반 미만입니다. 종목별 기여도를 함께 확인하세요.</p>}
    <div className="grid grid-cols-2 gap-x-5 gap-y-3 text-xs">
      <div><p className="text-ink-muted">종목 수익률 중앙값</p><p className={`mt-1 text-base ${signClass(s.median_return_pct)}`}>{fmtPct(s.median_return_pct)}</p></div>
      <div><p className="text-ink-muted">상위 3종목 시총 비중</p><p className="num mt-1 text-base text-ink">{plainPct(s.top3_weight_pct)}</p></div>
      {(["frgn", "inst"] as const).map((investor) => <div key={investor}>
        <p className="text-ink-muted">{investor === "frgn" ? "외국인" : "기관"} 순매수 · 선택 기간</p>
        <p className={`mt-1 text-base ${signClass(s[`${investor}_net`])}`}>{fmtEok(s[`${investor}_net`])}</p>
        <p className="mt-1 text-[10px] text-ink-muted">{s.flow_days}거래일 모두 확인 {s[`${investor}_covered_count`]}/{s.member_count}종목</p>
      </div>)}
    </div>
  </div>;
}

export default function SectorSection() {
  const params = useSearchParams();
  const kind: MarketGroupKind = params.get("kind") === "theme" ? "theme" : "sector";
  const requestedMarket = params.get("market");
  const market: MarketGroupMarket = requestedMarket === "KOSDAQ" ? "KOSDAQ"
    : requestedMarket === "KOSPI" ? "KOSPI" : kind === "theme" ? "ALL" : "KOSPI";
  const period = PERIODS.find((item) => item.id === params.get("period"))?.id ?? "1m";
  const metric = METRICS.find((item) => item.id === params.get("metric"))?.id ?? "return_pct";
  const list = params.get("group_view") === "list";
  const detailRef = useRef<HTMLDivElement>(null);
  const args = { kind, market, period };
  const { currentData: data, isFetching, error, refetch } = useFetchMarketGroupsQuery(args, { refetchOnMountOrArgChange: 120 });
  const rows = useMemo(() => [...(data?.rows ?? [])].sort((a, b) => {
    const av = a[metric], bv = b[metric];
    if (av == null) return bv == null ? a.name.localeCompare(b.name, "ko") : 1;
    if (bv == null) return -1;
    return bv - av || a.name.localeCompare(b.name, "ko");
  }), [data, metric]);
  const requestedGroup = params.get("group");
  // Invalid bookmarks must not show a different group's members silently.
  const selected = requestedGroup ? rows.find((row) => row.id === requestedGroup) : rows[0];
  const { currentData: detail, isFetching: detailFetching, error: detailError, refetch: refetchDetail } = useFetchMarketGroupDetailQuery(
    { ...args, group: selected?.id ?? "" }, { skip: !selected, refetchOnMountOrArgChange: 120 },
  );
  const summary = selected ? detail?.summary ?? selected : undefined;
  useEffect(() => {
    if (selected && !requestedGroup) updateGroupView({ group: selected.id }, true);
  }, [selected, requestedGroup]);
  useEffect(() => {
    if (!detail?.summary || !data?.as_of || detail.summary.as_of === data.as_of) return;
    // Each query can hold an older cached response across a daily publication.
    // Refresh the older side; repeatedly refreshing the newer list cannot fix it.
    if (detail.summary.as_of < data.as_of) {
      if (!detailFetching && !detailError) void refetchDetail();
    } else if (!isFetching && !error) void refetch();
  }, [detail, data?.as_of, detailFetching, detailError, isFetching, error, refetch, refetchDetail]);
  const scale = Math.max(...rows.map((row) => Math.abs(score(row, metric) ?? 0)), 1);
  const selectGroup = (id: string) => {
    updateGroupView({ group: id, group_page: null, group_q: null });
    if (window.matchMedia("(max-width: 767px)").matches) {
      requestAnimationFrame(() => {
        detailRef.current?.focus({ preventScroll: true });
        detailRef.current?.scrollIntoView({ block: "start", behavior: "instant" });
      });
    }
  };
  const changeScope = (values: Record<string, string>) => updateGroupView({ ...values, group: null, group_page: null, group_q: null });

  return <div className="min-w-0 space-y-5" data-testid="market-groups">
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <div className="segmented-control inline-flex" aria-label="분류 기준">
          <button aria-pressed={kind === "sector"} onClick={() => changeScope({ kind: "sector", market: market === "ALL" ? "KOSPI" : market })}>업종별 섹터</button>
          <button aria-pressed={kind === "theme"} onClick={() => changeScope({ kind: "theme", market: "ALL" })}>대표 테마</button>
        </div>
        <p className="mt-2 text-xs text-ink-muted">{kind === "theme" ? "공개자료에서 선정한 대표 종목군 · 테마 간 중복 포함" : "KRX 업종 분류 · 같은 시장 안에서 강약과 참여 폭 비교"}</p>
      </div>
      <div className="flex items-center gap-2 text-xs text-ink-muted">
        <span>정산 가격 {data?.as_of ?? "미확인"}</span>
        <button className="btn-ghost p-2" aria-label="섹터·테마 새로고침" disabled={isFetching} onClick={() => { void refetch(); if (selected) void refetchDetail(); }}><RefreshCw size={14} /></button>
      </div>
    </div>
    <div className="flex flex-wrap gap-3 rounded-xl border border-edge bg-surface px-4 py-3">
      <label className="flex items-center gap-2 text-xs text-ink-secondary">시장
        <select aria-label="섹터·테마 시장" className="rounded-lg border border-edge bg-raised px-2 py-2 text-ink" value={market} onChange={(e) => changeScope({ market: e.target.value })}>
          {kind === "theme" && <option value="ALL">한국 전체</option>}
          <option value="KOSPI">KOSPI</option><option value="KOSDAQ">KOSDAQ</option>
        </select>
      </label>
      <label className="flex items-center gap-2 text-xs text-ink-secondary">기간
        <select aria-label="섹터·테마 기간" className="rounded-lg border border-edge bg-raised px-2 py-2 text-ink" value={period} onChange={(e) => updateGroupView({ period: e.target.value, group_page: null })}>
          {PERIODS.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
        </select>
      </label>
      <label className="flex items-center gap-2 text-xs text-ink-secondary">지도 표시
        <select aria-label="지도 표시 지표" className="max-w-[155px] rounded-lg border border-edge bg-raised px-2 py-2 text-ink" value={metric} onChange={(e) => updateGroupView({ metric: e.target.value })}>
          {METRICS.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
        </select>
      </label>
    </div>
    {error ? <ErrorState message="섹터·테마 데이터를 불러오지 못했습니다" onRetry={refetch} />
      : !data && isFetching ? <LoadingState label="섹터·테마를 불러오는 중..." />
      : rows.length === 0 ? <EmptyState title="이 시장의 분석 자료가 아직 없습니다" hint="다른 시장을 선택하거나 정산 데이터 갱신 후 다시 확인하세요." />
      : <>
        <div className="grid min-w-0 gap-5 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <section className="min-w-0 self-start overflow-hidden rounded-2xl border border-edge bg-surface" aria-label="섹터·테마 지도">
            <div className="flex items-center justify-between gap-2 border-b border-edge px-4 py-4">
              <h3 className="flex items-center gap-2 font-semibold"><Layers3 size={16} className="text-primary-300" />{kind === "theme" ? "테마 탐색" : "섹터 탐색"}<span className="num text-xs font-normal text-ink-muted">{rows.length}</span></h3>
              <div className="flex gap-1">
                <button className="filter-chip inline-flex items-center gap-1.5" aria-pressed={!list} onClick={() => updateGroupView({ group_view: "map" })}><Grid2X2 size={12} />지도</button>
                <button className="filter-chip inline-flex items-center gap-1.5" aria-pressed={list} onClick={() => updateGroupView({ group_view: "list" })}><ArrowDownUp size={12} />순위</button>
              </div>
            </div>
            <div className={`max-h-[320px] overflow-y-auto p-3 sm:max-h-[490px] ${list ? "space-y-1" : "grid grid-cols-2 gap-2 xl:grid-cols-3"}`}>
              {rows.map((row, index) => {
                const signed = score(row, metric);
                const hue = signed == null || signed === 0 ? "var(--text-muted)" : signed > 0 ? "var(--gains)" : "var(--losses)";
                const intensity = signed == null ? 0 : 5 + Math.abs(signed) / scale * 24;
                return <button key={row.id} aria-label={`${row.name} 분석 보기`} aria-pressed={selected?.id === row.id} onClick={() => selectGroup(row.id)}
                  className={`min-w-0 rounded-xl border text-left transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-300 ${list ? "flex w-full items-center justify-between gap-3 px-3 py-3" : "flex min-h-[110px] flex-col justify-between gap-3 p-3"} ${selected?.id === row.id ? "border-primary-400 ring-1 ring-primary-400/50" : "border-transparent hover:border-edge-strong"}`}
                  style={{ backgroundColor: `color-mix(in srgb, ${hue} ${intensity}%, var(--surface-raised))` }}>
                  <span className="min-w-0"><span className="block break-keep text-xs font-semibold leading-5">{list && <span className="num mr-2 text-ink-muted">{index + 1}</span>}{row.name}</span><span className="mt-1 block text-[10px] text-ink-muted">{row.member_count}종목 · 시총 {plainPct(row.market_weight_pct)}</span></span>
                  <span className={list ? "shrink-0 text-right" : "w-full"}>
                    <span className={`block text-base ${signClass(signed)}`}>{metricValue(row[metric], metric)}</span>
                    {metric === "frgn_net" || metric === "inst_net" ? <span className="mt-1 block text-[10px] text-ink-muted">확인 {metric === "frgn_net" ? row.frgn_covered_count : row.inst_covered_count}/{row.member_count}</span>
                      : <span className="mt-1.5 flex h-1 overflow-hidden rounded bg-canvas/40" aria-hidden><span style={{ width: `${row.advancing_pct ?? 0}%`, backgroundColor: "var(--gains)", opacity: .65 }} /></span>}
                  </span>
                </button>;
              })}
            </div>
            <p className="border-t border-edge px-4 py-3 text-[10px] leading-5 text-ink-muted">{METRICS.find((item) => item.id === metric)?.label} 순 정렬 · 색 농도는 현재 목록 안의 상대 크기{metric !== "frgn_net" && metric !== "inst_net" ? " · 작은 막대는 상승 종목 비율" : " · 기간 수급이 모두 확인된 종목만 합산"}. 타일 면적은 동일합니다.</p>
          </section>
          <section ref={detailRef} tabIndex={-1} className="min-w-0 scroll-mt-24 rounded-2xl border border-edge bg-surface p-5" aria-label="선택 그룹 분석" aria-busy={detailFetching}>
            {!selected ? <EmptyState title="선택한 분류가 이 시장에 없습니다" hint="지도에서 섹터나 테마를 선택하세요." />
              : detailError ? <ErrorState message="구성 종목과 추이를 불러오지 못했습니다" onRetry={refetchDetail} />
              : summary && <>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div><p className="text-[10px] text-ink-muted">{kind === "theme" ? "대표 테마" : market} · {summary.member_count}종목</p><h3 className="mt-1 text-xl font-semibold tracking-tight">{summary.name}</h3></div>
                  <div className="text-right"><p className={`text-2xl ${signClass(summary.return_pct)}`}>{fmtPct(summary.return_pct)}</p><p className={`mt-1 text-xs ${signClass(summary.excess_pp)}`}>{summary.benchmark_name} 대비 {fmtPp(summary.excess_pp)}</p></div>
                </div>
                <p className="mt-2 text-xs leading-5 text-ink-secondary">{summary.description}</p>
                <p className="mt-2 text-[10px] text-ink-muted">{summary.start_date ?? "시작 가격 미확인"} → {summary.as_of} · 가격수익률{kind === "theme" ? " · 현재 대표종목 재구성" : " · 당시 업종 분류"}</p>
                <div className="my-4 min-w-0">
                  {detailFetching && !detail ? <div className="flex h-[220px] items-center justify-center"><LoadingState label="추이를 불러오는 중..." /></div>
                    : detail?.history.length ? <TimeSeriesChart height={220} data={detail.history} series={[
                      { key: "group_pct", name: summary.name, color: "var(--primary)", strokeWidth: 2.5 },
                      { key: "benchmark_pct", name: summary.benchmark_name, color: "var(--secondary)", opacity: .7 },
                    ]} yFormatter={(value) => `${value.toFixed(1)}%`} baseline={0} />
                      : <div className="py-12 text-center text-xs text-ink-muted">선택 기간의 추이를 계산할 가격이 부족합니다.</div>}
                </div>
                <GroupFacts summary={summary} />
              </>}
          </section>
        </div>
        {selected && detail?.summary && !detailError && <GroupMembersTable members={detail.members} summary={detail.summary} />}
        {summary && <details className="rounded-xl border border-edge bg-surface px-5 py-4 text-xs text-ink-secondary">
          <summary className="cursor-pointer font-medium text-ink">계산 기준 · 구성 근거와 출처</summary>
          <div className="mt-4 grid gap-5 leading-6 md:grid-cols-2">
            <div><p>그룹 수익률은 전일 시총으로 가중한 일별 가격 변화입니다. 현금배당은 포함하지 않습니다. 종목별 기여도는 선택 기간과 별개로 <strong>당일 %p</strong>입니다.</p>
              <p className="mt-2">가격 확인 {summary.price_covered_count}/{summary.member_count}종목 · 당일 등락 확인 {summary.daily_covered_count}/{summary.member_count}종목 · 시총 {fmtJo(summary.market_cap)}</p>
              <p>가격 {summary.as_of} · 수급 {summary.flows_as_of ?? "미확인"} · 밸류에이션 {summary.fundamentals_as_of ?? "미확인"}</p>
              <p>기간 수급이 모두 확인된 종목만 합산합니다. 자료 없음은 0원 또는 0%가 아닙니다.</p>
            </div>
            <div>{kind === "theme" ? <><p>공개자료를 참고해 선정한 일부 대표 종목입니다. 전체 테마 종목이나 현재 ETF의 보유종목·운용비중을 뜻하지 않습니다. 한 종목이 여러 테마에 포함될 수 있습니다.</p><p className="mt-2">구성 검토 {summary.reviewed_at} · 참고자료 기준 {summary.source_as_of}</p><p>구성표는 수동으로 검토하며, 가격·수급은 매일 갱신합니다. 과거 추이는 현재 대표종목으로 재구성합니다.</p></> : <><p>KRX 업종 분류와 현행 종목 마스터를 사용합니다. 과거 추이는 당시 분류를 따르므로 현재 구성 종목과 다를 수 있습니다.</p><p>구성 기준 {summary.classification_as_of} · 소수 종목 업종도 포함</p></>}
              <div className="mt-3 flex flex-col items-start gap-2">{summary.sources.map((source) => <a key={source.url} href={source.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 text-primary-300 underline-offset-4 hover:underline">{source.label}<ExternalLink size={12} /></a>)}</div>
            </div>
          </div>
        </details>}
      </>}
  </div>;
}
