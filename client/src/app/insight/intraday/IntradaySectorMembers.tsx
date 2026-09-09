"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, ChevronLeft, ChevronRight, Search } from "lucide-react";
import { IntradaySectorDetail, useFetchMetaDataQuery } from "@/state/api";
import { fmtJo, fmtPct, signClass } from "../format";

const SORTS = [
  { id: "value", label: "거래대금" },
  { id: "chg_pct", label: "등락률" },
  { id: "close", label: "가격" },
] as const;
type Member = IntradaySectorDetail["members"][number];
const price = (n: number | null) => n == null ? "—" : `${n.toLocaleString("ko-KR")}원`;

export default function IntradaySectorMembers({ detail, asOf }: {
  detail: IntradaySectorDetail;
  asOf?: string;
}) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<typeof SORTS[number]["id"]>("value");
  const [asc, setAsc] = useState(false);
  const [requestedPage, setPage] = useState(1);
  // This cached metadata only enables links; never filter snapshot members by it.
  const { data: metaData } = useFetchMetaDataQuery({});
  const tickerToMetaId = useMemo(() => {
    const map = new Map<string, number>();
    const rows = (metaData ?? []) as { ticker: string; meta_id: number; iso_code: string }[];
    for (const row of rows) if (row.iso_code === "KR") map.set(row.ticker, row.meta_id);
    return map;
  }, [metaData]);
  const terms = query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  const filtered = detail.members.filter((row) => terms.every((term) =>
    `${row.name} ${row.ticker} ${row.market}`.toLocaleLowerCase().includes(term),
  )).sort((a, b) => {
    const av = a[sort], bv = b[sort];
    if (av == null) return bv == null ? a.ticker.localeCompare(b.ticker) : 1;
    if (bv == null) return -1;
    return (asc ? av - bv : bv - av) || a.ticker.localeCompare(b.ticker);
  });
  const pages = Math.max(1, Math.ceil(filtered.length / 25));
  const page = Math.min(requestedPage, pages);
  const visible = filtered.slice((page - 1) * 25, page * 25);
  const name = (row: Member) => {
    const metaId = tickerToMetaId.get(row.ticker);
    const href = metaId == null ? `/stocksearch?q=${encodeURIComponent(row.name || row.ticker)}` : `/stock/${metaId}`;
    return <div className="min-w-0">
      <Link prefetch={false} href={href} className="inline-flex max-w-full items-center gap-1 font-medium text-ink underline-offset-4 hover:underline">
        <span className="break-words">{row.name || row.ticker}</span><ArrowUpRight size={12} className="shrink-0 text-ink-muted" />
      </Link>
      <p className="mt-1 text-[10px] text-ink-muted"><span className="num">{row.ticker}</span> · {row.market}</p>
    </div>;
  };

  return <>
    <p className="px-5 pb-4 text-xs leading-5 text-ink-muted">
      {asOf ?? "시각 미확인"} 기준 · {detail.members.length}종목 · 지연 시세<br />
      이 스냅샷에 가격이 있는 종목입니다. 거래정지·가격 미형성 종목은 제외됩니다.
      종목명을 누르면 상세 분석으로 이동합니다.
    </p>
    {detail.members.length === 0 ? <p className="px-5 py-8 text-sm text-ink-muted" role="status">이 스냅샷에서 선택한 섹터의 종목을 찾지 못했습니다. 위에서 다른 섹터를 선택해 주세요.</p> : <>
      <div className="flex flex-wrap items-center gap-3 border-y border-edge bg-raised/25 px-5 py-3">
        <label className="flex min-w-0 flex-1 items-center gap-2 rounded-lg border border-edge bg-surface px-3 py-2 text-ink-muted">
          <Search size={14} className="shrink-0" />
          <input type="search" aria-label="장중 구성 종목 검색" placeholder="종목명·코드·시장 검색" value={query}
            onChange={(e) => { setQuery(e.target.value); setPage(1); }} className="min-w-0 flex-1 bg-transparent text-xs text-ink outline-none" />
        </label>
        <div className="flex items-center gap-2 text-xs">
          <select aria-label="장중 구성 종목 정렬 기준" value={sort} onChange={(e) => { setSort(e.target.value as typeof sort); setPage(1); }} className="rounded-lg border border-edge bg-surface px-2 py-2 text-ink">
            {SORTS.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
          <button type="button" className="btn-secondary px-2 py-2 text-xs" aria-label={asc ? "내림차순으로 정렬" : "오름차순으로 정렬"} onClick={() => { setAsc(!asc); setPage(1); }}>{asc ? "낮은 순 ↑" : "높은 순 ↓"}</button>
        </div>
      </div>
      {visible.length === 0 ? <p className="px-5 py-10 text-center text-sm text-ink-muted" role="status">일치하는 종목이 없습니다. 검색어를 바꿔보세요.</p> : <>
        <div className="hidden md:block">
          <table className="w-full text-sm" aria-label={`${detail.name} 장중 구성 종목`}>
            <thead className="border-b border-edge text-[11px] text-ink-secondary"><tr>
              <th scope="col" className="px-5 py-3 text-left font-medium">종목</th>
              <th scope="col" className="px-5 py-3 text-right font-medium">스냅샷 가격</th>
              <th scope="col" className="px-5 py-3 text-right font-medium">전일 대비</th>
              <th scope="col" className="px-5 py-3 text-right font-medium">누적 거래대금</th>
            </tr></thead>
            <tbody className="divide-y divide-edge">{visible.map((row) => <tr key={row.ticker} className="hover:bg-raised/35">
              <td className="max-w-[280px] px-5 py-4">{name(row)}</td>
              <td className="num whitespace-nowrap px-5 py-4 text-right">{price(row.close)}</td>
              <td className={`whitespace-nowrap px-5 py-4 text-right ${signClass(row.chg_pct)}`}>{fmtPct(row.chg_pct)}</td>
              <td className="num whitespace-nowrap px-5 py-4 text-right text-ink-secondary">{fmtJo(row.value)}</td>
            </tr>)}</tbody>
          </table>
        </div>
        <div className="divide-y divide-edge md:hidden">{visible.map((row) => <article key={row.ticker} className="px-5 py-4">
          {name(row)}
          <dl className="mt-3 grid grid-cols-2 gap-3 text-sm">
            <div><dt className="text-[10px] text-ink-muted">스냅샷 가격</dt><dd className="num mt-1">{price(row.close)}</dd></div>
            <div><dt className="text-[10px] text-ink-muted">전일 대비</dt><dd className={`mt-1 ${signClass(row.chg_pct)}`}>{fmtPct(row.chg_pct)}</dd></div>
            <div className="col-span-2 flex items-center justify-between gap-2"><dt className="text-[10px] text-ink-muted">누적 거래대금</dt><dd className="num text-ink-secondary">{fmtJo(row.value)}</dd></div>
          </dl>
        </article>)}</div>
      </>}
      <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-edge px-5 py-3 text-xs text-ink-muted">
        <span aria-live="polite">검색 결과 {filtered.length}종목 · {page}/{pages}페이지</span>
        <div className="flex gap-2">
          <button type="button" className="btn-secondary p-2 disabled:opacity-40" aria-label="장중 구성 종목 이전 페이지" disabled={page <= 1} onClick={() => setPage(page - 1)}><ChevronLeft size={15} /></button>
          <button type="button" className="btn-secondary p-2 disabled:opacity-40" aria-label="장중 구성 종목 다음 페이지" disabled={page >= pages} onClick={() => setPage(page + 1)}><ChevronRight size={15} /></button>
        </div>
      </footer>
    </>}
  </>;
}
