"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ArrowUpRight, ChevronLeft, ChevronRight, Search } from "lucide-react";
import { MarketGroupMember, MarketGroupSummary } from "@/state/api";
import { fmtEok, fmtJo, fmtPct, signClass } from "./format";
import { fmtPp, plainPct, updateGroupView } from "./groupView";

type View = "price" | "flows" | "valuation";
const VIEWS: { id: View; label: string }[] = [
  { id: "price", label: "가격·기여도" }, { id: "flows", label: "수급" },
  { id: "valuation", label: "밸류에이션" },
];
const SORTS = [
  { id: "weight_pct", label: "시총 비중" }, { id: "return_pct", label: "기간 수익률" },
  { id: "contribution_1d_pp", label: "당일 기여도" }, { id: "value", label: "거래대금" },
  { id: "frgn_net", label: "외국인 순매수" }, { id: "inst_net", label: "기관 순매수" },
  { id: "per", label: "PER" }, { id: "pbr", label: "PBR" }, { id: "div", label: "배당수익률" },
] as const;
const number = (value: number | null, suffix = "") => value == null ? "—" : `${value.toFixed(2)}${suffix}`;
const columns: Record<View, { key: keyof MarketGroupMember; label: string; format: (n: number | null) => string; signed?: boolean }[]> = {
  price: [
    { key: "return_pct", label: "기간 수익률", format: fmtPct, signed: true },
    { key: "contribution_1d_pp", label: "당일 기여도", format: fmtPp, signed: true },
    { key: "value", label: "당일 거래대금", format: fmtJo },
    { key: "relative_value20", label: "평소 대비 거래대금", format: (n) => number(n, "배") },
  ],
  flows: [
    { key: "return_pct", label: "기간 수익률", format: fmtPct, signed: true },
    { key: "frgn_net", label: "외국인 순매수", format: fmtEok, signed: true },
    { key: "inst_net", label: "기관 순매수", format: fmtEok, signed: true },
  ],
  valuation: [
    { key: "per", label: "PER", format: (n) => number(n, "배") },
    { key: "pbr", label: "PBR", format: (n) => number(n, "배") },
    { key: "div", label: "배당수익률", format: (n) => number(n, "%") },
  ],
};

function MemberName({ row }: { row: MarketGroupMember }) {
  return <div className="min-w-0">
    {row.meta_id != null ? <Link prefetch={false} href={`/stock/${row.meta_id}`} className="inline-flex max-w-full items-center gap-1 font-medium text-ink underline-offset-4 hover:text-primary-300 hover:underline"><span className="break-keep">{row.name}</span><ArrowUpRight className="shrink-0 text-ink-muted" size={12} /></Link> : <span className="font-medium text-ink">{row.name}</span>}
    <p className="mt-1 text-[10px] text-ink-muted"><span className="num">{row.ticker}</span> · {row.market ?? "시장 미확인"}{row.sector ? ` · ${row.sector}` : ""}</p>
    {row.close == null && <p className="mt-1 text-[10px] text-warning">최근 가격 없음</p>}
  </div>;
}

export default function GroupMembersTable({ members, summary }: { members: MarketGroupMember[]; summary: MarketGroupSummary }) {
  const params = useSearchParams();
  const view = VIEWS.find((item) => item.id === params.get("group_table"))?.id ?? "price";
  const sort = SORTS.find((item) => item.id === params.get("group_sort"))?.id ?? "weight_pct";
  const asc = params.get("group_order") === "asc";
  const query = params.get("group_q") ?? "";
  const terms = query.toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
  const filtered = members.filter((row) => terms.every((term) => `${row.name} ${row.ticker} ${row.sector ?? ""}`.toLocaleLowerCase().includes(term))).sort((a, b) => {
    const av = a[sort], bv = b[sort];
    if (av == null) return bv == null ? a.ticker.localeCompare(b.ticker) : 1;
    if (bv == null) return -1;
    return (asc ? av - bv : bv - av) || a.ticker.localeCompare(b.ticker);
  });
  const count = Math.max(1, Math.ceil(filtered.length / 25));
  const requestedPage = Number(params.get("group_page") ?? 1);
  const page = Number.isFinite(requestedPage) ? Math.min(count, Math.max(1, Math.floor(requestedPage))) : 1;
  const visible = filtered.slice((page - 1) * 25, page * 25);
  const activeColumns = columns[view];
  const update = (values: Record<string, string | null>, replace = false) => updateGroupView({ ...values, group_page: null }, replace);
  const cell = (row: MarketGroupMember, column: typeof activeColumns[number]) => {
    const value = row[column.key] as number | null;
    const days = column.key === "frgn_net" ? row.frgn_days : column.key === "inst_net" ? row.inst_days : null;
    return <><span className={column.signed ? signClass(value) : "num text-ink"}>{column.format(value)}</span>
      {view === "flows" && days != null && <span className="mt-1 block text-[10px] text-ink-muted">{days}/{summary.flow_days}일 확인</span>}</>;
  };

  return <section className="min-w-0 overflow-hidden rounded-2xl border border-edge bg-surface" aria-label="구성 종목">
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-edge px-5 py-4">
      <div><h3 className="font-semibold">{summary.name} 구성 종목 <span className="num ml-1 text-sm font-normal text-ink-muted">{summary.member_count}</span></h3>
        <p className="mt-1 text-xs text-ink-muted">{summary.kind === "theme" ? "공개자료 기반 대표 종목 · " : ""}종목명을 누르면 상세 분석으로 이동합니다.</p></div>
      <div className="segmented-control flex flex-wrap" aria-label="종목 비교 항목">
        {VIEWS.map((item) => <button key={item.id} aria-pressed={view === item.id} onClick={() => update({ group_table: item.id })}>{item.label}</button>)}
      </div>
    </header>
    <div className="flex flex-wrap items-center gap-3 border-b border-edge bg-raised/25 px-5 py-3">
      <label className="flex min-w-0 flex-1 items-center gap-2 rounded-lg border border-edge bg-surface px-3 py-2 text-ink-muted"><Search size={14} className="shrink-0" />
        <input type="search" aria-label="구성 종목 검색" placeholder="종목명·코드·업종 검색" value={query} onChange={(event) => update({ group_q: event.target.value || null }, true)} className="min-w-0 flex-1 bg-transparent text-xs text-ink outline-none" />
      </label>
      <div className="flex items-center gap-2 text-xs">
        <select aria-label="구성 종목 정렬 기준" className="max-w-[145px] rounded-lg border border-edge bg-surface px-2 py-2 text-ink" value={sort} onChange={(e) => update({ group_sort: e.target.value })}>{SORTS.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select>
        <button className="btn-secondary px-2 py-2 text-xs" onClick={() => update({ group_order: asc ? "desc" : "asc" })} aria-label={asc ? "내림차순으로 정렬" : "오름차순으로 정렬"}>{asc ? "낮은 순 ↑" : "높은 순 ↓"}</button>
      </div>
    </div>
    <p className="px-5 py-3 text-[11px] leading-5 text-ink-muted">{view === "price" ? `기간 수익률 ${summary.start_date ?? "시작 가격 미확인"} → ${summary.as_of} · 기여도는 ${summary.as_of} 당일 · 평소 거래대금은 직전 20거래일 평균` : view === "flows" ? `${summary.flow_days}거래일의 순매수 합계입니다. 하루라도 자료가 없으면 합계를 표시하지 않고 확인 일수를 보여줍니다.` : "PER·PBR이 산출되지 않은 종목은 —로 표시합니다. 종목별 관측일을 함께 확인하세요."}</p>
    {visible.length === 0 ? <p className="px-5 py-12 text-center text-sm text-ink-muted">일치하는 종목이 없습니다. 검색어를 바꿔보세요.</p> : <>
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full text-sm">
          <thead className="border-y border-edge bg-raised/35 text-[11px] text-ink-secondary"><tr>
            <th className="px-5 py-3 text-left font-medium">종목</th><th className="whitespace-nowrap px-3 py-3 text-right font-medium">시총 비중</th>
            {activeColumns.map((column) => <th key={column.key} className="whitespace-nowrap px-3 py-3 text-right font-medium">{column.label}</th>)}
            {view === "valuation" && <th className="px-5 py-3 text-right font-medium">관측일</th>}
          </tr></thead>
          <tbody className="divide-y divide-edge">{visible.map((row) => <tr key={row.ticker} className="hover:bg-raised/35">
            <td className="max-w-[280px] px-5 py-4"><MemberName row={row} /></td><td className="num px-3 py-4 text-right text-ink-secondary">{plainPct(row.weight_pct)}</td>
            {activeColumns.map((column) => <td key={column.key} className="whitespace-nowrap px-3 py-4 text-right">{cell(row, column)}</td>)}
            {view === "valuation" && <td className="num whitespace-nowrap px-5 py-4 text-right text-xs text-ink-muted">{row.valuation_as_of ?? "미확인"}</td>}
          </tr>)}</tbody>
        </table>
      </div>
      <div className="divide-y divide-edge border-t border-edge md:hidden">{visible.map((row) => <article key={row.ticker} className="px-5 py-4">
        <div className="flex items-start justify-between gap-3"><MemberName row={row} /><span className="num shrink-0 text-xs text-ink-secondary">비중 {plainPct(row.weight_pct)}</span></div>
        <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3">{activeColumns.map((column) => <div key={column.key}><dt className="text-[10px] text-ink-muted">{column.label}</dt><dd className="mt-1 text-sm">{cell(row, column)}</dd></div>)}</dl>
        {view === "valuation" && <p className="mt-3 text-[10px] text-ink-muted">관측일 {row.valuation_as_of ?? "미확인"}</p>}
      </article>)}</div>
    </>}
    <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-edge px-5 py-3 text-xs text-ink-muted">
      <span>검색 결과 {filtered.length}종목 · {page}/{count}페이지</span>
      <div className="flex gap-2"><button className="btn-secondary p-2 disabled:opacity-40" aria-label="구성 종목 이전 페이지" disabled={page <= 1} onClick={() => updateGroupView({ group_page: String(page - 1) })}><ChevronLeft size={15} /></button><button className="btn-secondary p-2 disabled:opacity-40" aria-label="구성 종목 다음 페이지" disabled={page >= count} onClick={() => updateGroupView({ group_page: String(page + 1) })}><ChevronRight size={15} /></button></div>
    </footer>
  </section>;
}
