"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  ColumnDef,
  RowSelectionState,
  PaginationState,
  SortingState,
  Updater,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";

import { useFetchSparklinesQuery } from "@/state/api";
import { MetaRow, FilterState, CAP_THRESHOLDS } from "./types";
import SparklineChart from "@/components/charts/SparklineChart";
import { formatMarketCap } from "@/lib/market";
import { Search } from "lucide-react";

interface MetaTableProps {
  data: MetaRow[];
  filters: FilterState;
  selectedIds: number[];
  onSelectionChange: (selectedIds: number[]) => void;
  onRowClick: (row: MetaRow) => void;
  /** Applied once as the quick filter (e.g. from ?q= URL param). */
  initialQuickFilter?: string;
}

const PAGE_SIZE_OPTIONS = [10, 25, 50, 100];

const sizeOf = (row: MetaRow): number | null => {
  if (row.security_type?.toLowerCase() !== "etf") {
    return row.marketcap ?? null;
  }
  // During a rolling deploy the old API omits fund_size entirely. Preserve
  // its former market-cap display, but do not turn a new explicit null into AUM.
  return row.fund_size === undefined ? (row.marketcap ?? null) : row.fund_size;
};

/** AND across whitespace-separated terms; a term matches ticker/name/sector/market. */
const matchesQuickFilter = (row: MetaRow, query: string): boolean => {
  const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (terms.length === 0) return true;
  const haystack = [
    row.ticker,
    row.name,
    row.sector ?? "",
    row.iso_code,
    row.security_subtype ?? "",
  ]
    .join(" ")
    .toLowerCase();
  return terms.every((term) => haystack.includes(term));
};

/** Sort direction indicator for clickable headers. */
const SortIcon: React.FC<{ dir: false | "asc" | "desc" }> = ({ dir }) => (
  <span className="text-[10px] text-ink-muted w-3 inline-block">
    {dir === "asc" ? "▲" : dir === "desc" ? "▼" : ""}
  </span>
);

const MetaTable: React.FC<MetaTableProps> = ({
  data,
  filters,
  selectedIds,
  onSelectionChange,
  onRowClick,
  initialQuickFilter,
}) => {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [pagination, setPagination] = useState<PaginationState>({
    pageIndex: 0,
    pageSize: 25,
  });
  const [sparklineCache, setSparklineCache] = useState<
    Record<string, number[]>
  >({});
  const [quickFilterInput, setQuickFilterInput] = useState(
    initialQuickFilter ?? ""
  );
  const [globalFilter, setGlobalFilter] = useState(initialQuickFilter ?? "");

  // Debounce the quick-filter input before it hits the table.
  useEffect(() => {
    const t = setTimeout(() => setGlobalFilter(quickFilterInput), 300);
    return () => clearTimeout(t);
  }, [quickFilterInput]);

  // 상단 검색에서 같은 페이지의 ?q= 값만 바뀌어도 표 검색어를 동기화한다.
  useEffect(() => {
    const next = initialQuickFilter ?? "";
    setQuickFilterInput(next);
    setGlobalFilter(next);
  }, [initialQuickFilter]);

  // Structured filters (market/sector/cap/type) are applied before the table.
  const filteredData = useMemo(() => {
    return data.filter((row) => {
      if (filters.market !== "all" && row.iso_code !== filters.market) {
        return false;
      }
      if (filters.sector && row.sector !== filters.sector) {
        return false;
      }
      if (
        filters.type !== "all" &&
        (row.security_type ?? "").toLowerCase() !== filters.type
      ) {
        return false;
      }
      if (filters.cap !== "all") {
        const cap = sizeOf(row);
        if (!cap) return false;
        const thresholds = CAP_THRESHOLDS[row.iso_code === "KR" ? "KR" : "US"];
        if (filters.cap === "large" && cap < thresholds.large) return false;
        if (
          filters.cap === "mid" &&
          (cap >= thresholds.large || cap < thresholds.mid)
        )
          return false;
        if (filters.cap === "small" && cap >= thresholds.mid) return false;
      }
      return true;
    });
  }, [data, filters]);

  const columns = useMemo<ColumnDef<MetaRow>[]>(
    () => [
      {
        id: "select",
        enableSorting: false,
        header: "비교",
        cell: ({ row }) => (
          <input
            type="checkbox"
            className="accent-primary-500 cursor-pointer"
            checked={row.getIsSelected()}
            disabled={!row.getIsSelected() && selectedIds.length >= 5}
            onChange={row.getToggleSelectedHandler()}
            onClick={(e) => e.stopPropagation()}
            aria-label={`${row.original.ticker} 비교 ${row.getIsSelected() ? "해제" : "추가"}`}
          />
        ),
      },
      {
        accessorKey: "ticker",
        header: "Ticker",
        cell: ({ getValue, row }) => (
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              onRowClick(row.original);
            }}
            className="num font-medium text-ink underline-offset-4 hover:text-primary-300 hover:underline"
            aria-label={`${row.original.name || getValue<string>()} 요약 열기`}
          >
            {getValue<string>()}
          </button>
        ),
      },
      {
        accessorKey: "name",
        header: "Name",
        cell: ({ getValue }) => getValue<string>() || "—",
      },
      {
        accessorKey: "sector",
        header: "Sector",
        cell: ({ getValue }) => getValue<string | null>() || "—",
      },
      {
        accessorKey: "iso_code",
        header: "Market",
      },
      {
        id: "size",
        accessorFn: sizeOf,
        header: "Size",
        sortUndefined: "last",
        cell: ({ getValue, row }) => (
          <span className="num">
            {formatMarketCap(getValue<number | null>(), row.original.iso_code)}
          </span>
        ),
      },
      {
        id: "sparkline",
        header: "30D Trend",
        enableSorting: false,
        cell: ({ row }) => {
          const sparkline =
            sparklineCache[String(row.original.meta_id)] || [];
          return <SparklineChart data={sparkline} />;
        },
      },
      {
        accessorKey: "security_type",
        header: "Type",
        cell: ({ getValue, row }) => {
          const type = getValue<string>() ?? "";
          const subtype = row.original.security_subtype;
          if (type.toLowerCase() === "etf") {
            return (
              <span
                className="badge font-semibold"
                style={{
                  color: "var(--secondary)",
                  backgroundColor:
                    "color-mix(in srgb, var(--secondary) 12%, transparent)",
                }}
              >
                {subtype && subtype !== "ETF" ? `ETF · ${subtype}` : "ETF"}
              </span>
            );
          }
          return (
            <span className="text-ink-secondary">
              {subtype && subtype.toUpperCase() !== type.toUpperCase()
                ? `${type} · ${subtype}`
                : type || "—"}
            </span>
          );
        },
      },
    ],
    [onRowClick, selectedIds.length, sparklineCache]
  );

  // Bridge the parent's number[] selection to TanStack's RowSelectionState.
  const rowSelection = useMemo<RowSelectionState>(() => {
    const sel: RowSelectionState = {};
    for (const id of selectedIds) sel[String(id)] = true;
    return sel;
  }, [selectedIds]);

  const handleRowSelectionChange = (updater: Updater<RowSelectionState>) => {
    const next = typeof updater === "function" ? updater(rowSelection) : updater;
    const ids = Object.keys(next)
      .filter((key) => next[key])
      .map(Number);
    onSelectionChange(ids.slice(0, 5));
  };

  const table = useReactTable({
    data: filteredData,
    columns,
    getRowId: (row) => String(row.meta_id),
    state: { sorting, globalFilter, rowSelection, pagination },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    onRowSelectionChange: handleRowSelectionChange,
    onPaginationChange: setPagination,
    globalFilterFn: (row, _columnId, filterValue) =>
      matchesQuickFilter(row.original, String(filterValue ?? "")),
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    enableRowSelection: true,
  });

  // 표 전체(최대 1만여 종목)가 아니라 정렬·필터 후 현재 페이지의 ID만 요청한다.
  const visibleMetaIds = table
    .getRowModel()
    .rows.map((row) => row.original.meta_id)
    .join(",");
  const { data: visibleSparklineData } = useFetchSparklinesQuery(visibleMetaIds, {
    skip: !visibleMetaIds,
  });

  useEffect(() => {
    if (!visibleSparklineData?.sparklines) return;
    setSparklineCache((current) => ({
      ...current,
      ...visibleSparklineData.sparklines,
    }));
  }, [visibleSparklineData]);

  useEffect(() => {
    setPagination((current) => ({ ...current, pageIndex: 0 }));
  }, [filters, globalFilter]);

  const { pageIndex, pageSize } = table.getState().pagination;
  const totalRows = table.getFilteredRowModel().rows.length;
  const firstRow = totalRows === 0 ? 0 : pageIndex * pageSize + 1;
  const lastRow = Math.min((pageIndex + 1) * pageSize, totalRows);

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4 px-5 py-5 md:px-6">
        <div>
          <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-ink-muted">Registry result</p>
          <p className="mt-1 text-sm text-ink-secondary">
            {totalRows.toLocaleString()}개 종목
            {totalRows !== data.length &&
              ` (전체 ${data.length.toLocaleString()}개에서 필터)`}
          </p>
        </div>
        <label className="w-full sm:w-80">
          <span className="sr-only">종목 빠른 검색</span>
          <span className="relative block">
            <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" aria-hidden />
            <input
              type="search"
              value={quickFilterInput}
              onChange={(e) => setQuickFilterInput(e.target.value)}
              placeholder="티커 · 종목명 · 섹터"
              className="input h-11 pl-10"
            />
          </span>
        </label>
      </div>

      <div className="overflow-x-auto border-y border-edge">
        <table className="w-full min-w-[940px] text-sm" aria-label="종목 유니버스">
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id} className="table-header">
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    className="whitespace-nowrap px-4 py-3 text-left first:pl-5 last:pr-5 md:first:pl-6 md:last:pr-6"
                    aria-sort={
                      header.column.getIsSorted() === "asc"
                        ? "ascending"
                        : header.column.getIsSorted() === "desc"
                          ? "descending"
                          : undefined
                    }
                  >
                    {header.column.getCanSort() ? (
                      <button
                        type="button"
                        onClick={header.column.getToggleSortingHandler()}
                        className="inline-flex items-center gap-1 rounded text-left hover:text-ink"
                      >
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        <SortIcon dir={header.column.getIsSorted()} />
                      </button>
                    ) : (
                      <span>{flexRender(header.column.columnDef.header, header.getContext())}</span>
                    )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="py-12 text-center text-ink-muted"
                >
                  현재 조건에 맞는 종목이 없습니다
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  className="table-row cursor-pointer"
                  onClick={() => onRowClick(row.original)}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="table-cell whitespace-nowrap first:pl-5 last:pr-5 md:first:pl-6 md:last:pr-6">
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination footer */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 md:px-6">
        <div className="flex items-center gap-2 text-sm text-ink-secondary">
          <span>페이지당 행</span>
          <select
            value={pageSize}
            onChange={(e) => table.setPageSize(Number(e.target.value))}
            className="px-2 py-1 text-sm border border-edge rounded-lg bg-surface
                       focus:outline-none focus:border-primary-400"
            aria-label="페이지당 행 수"
          >
            {PAGE_SIZE_OPTIONS.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-ink-muted num">
            {firstRow.toLocaleString()}–{lastRow.toLocaleString()} /{" "}
            {totalRows.toLocaleString()}
          </span>
          <button
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
            className="px-3 py-1.5 text-sm rounded-lg bg-raised border border-edge
                       hover:bg-overlay disabled:opacity-40 disabled:cursor-not-allowed"
            aria-label="이전 페이지"
          >
            ←
          </button>
          <button
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
            className="px-3 py-1.5 text-sm rounded-lg bg-raised border border-edge
                       hover:bg-overlay disabled:opacity-40 disabled:cursor-not-allowed"
            aria-label="다음 페이지"
          >
            →
          </button>
        </div>
      </div>
    </div>
  );
};

export default MetaTable;
