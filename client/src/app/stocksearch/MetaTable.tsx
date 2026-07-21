"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  ColumnDef,
  RowSelectionState,
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

const formatMarketCap = (value: number | null): string => {
  if (typeof value !== "number" || Number.isNaN(value)) return "—";
  if (value >= 1e12) return `$${(value / 1e12).toFixed(1)}T`;
  if (value >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
  if (value >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  return `$${value.toLocaleString()}`;
};

/** AND across whitespace-separated terms; a term matches ticker/name/sector/market. */
const matchesQuickFilter = (row: MetaRow, query: string): boolean => {
  const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (terms.length === 0) return true;
  const haystack = [row.ticker, row.name, row.sector ?? "", row.iso_code]
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
  const [quickFilterInput, setQuickFilterInput] = useState(
    initialQuickFilter ?? ""
  );
  const [globalFilter, setGlobalFilter] = useState(initialQuickFilter ?? "");

  // Debounce the quick-filter input before it hits the table.
  useEffect(() => {
    const t = setTimeout(() => setGlobalFilter(quickFilterInput), 300);
    return () => clearTimeout(t);
  }, [quickFilterInput]);

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
      if (filters.cap !== "all" && row.marketcap) {
        const cap = row.marketcap;
        if (filters.cap === "large" && cap < CAP_THRESHOLDS.large) return false;
        if (
          filters.cap === "mid" &&
          (cap >= CAP_THRESHOLDS.large || cap < CAP_THRESHOLDS.mid)
        )
          return false;
        if (filters.cap === "small" && cap >= CAP_THRESHOLDS.mid) return false;
      }
      return true;
    });
  }, [data, filters]);

  // Fetch sparklines for the visible (filtered) stocks.
  const metaIds = useMemo(() => {
    return filteredData.map((row) => row.meta_id).join(",");
  }, [filteredData]);
  const { data: sparklineData } = useFetchSparklinesQuery(metaIds, {
    skip: !metaIds,
  });

  const columns = useMemo<ColumnDef<MetaRow>[]>(
    () => [
      {
        id: "select",
        enableSorting: false,
        header: ({ table }) => (
          <input
            type="checkbox"
            className="accent-primary-500 cursor-pointer"
            checked={table.getIsAllPageRowsSelected()}
            ref={(el) => {
              if (el) el.indeterminate = table.getIsSomePageRowsSelected();
            }}
            onChange={table.getToggleAllPageRowsSelectedHandler()}
            aria-label="Select all rows on page"
          />
        ),
        cell: ({ row }) => (
          <input
            type="checkbox"
            className="accent-primary-500 cursor-pointer"
            checked={row.getIsSelected()}
            onChange={row.getToggleSelectedHandler()}
            onClick={(e) => e.stopPropagation()}
            aria-label={`Select ${row.original.ticker}`}
          />
        ),
      },
      {
        accessorKey: "ticker",
        header: "Ticker",
        cell: ({ getValue }) => (
          <span className="num font-medium">{getValue<string>()}</span>
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
        accessorKey: "marketcap",
        header: "Cap",
        sortUndefined: "last",
        cell: ({ getValue }) => (
          <span className="num">
            {formatMarketCap(getValue<number | null>())}
          </span>
        ),
      },
      {
        id: "sparkline",
        header: "30D Trend",
        enableSorting: false,
        cell: ({ row }) => {
          const sparkline =
            sparklineData?.sparklines?.[String(row.original.meta_id)] || [];
          return <SparklineChart data={sparkline} />;
        },
      },
      {
        accessorKey: "security_type",
        header: "Type",
        cell: ({ getValue }) => {
          const type = getValue<string>() ?? "";
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
                ETF
              </span>
            );
          }
          return <span className="text-ink-secondary">{type || "—"}</span>;
        },
      },
    ],
    [sparklineData]
  );

  // Bridge the parent's number[] selection to TanStack's RowSelectionState.
  const rowSelection = useMemo<RowSelectionState>(() => {
    const sel: RowSelectionState = {};
    for (const id of selectedIds) sel[String(id)] = true;
    return sel;
  }, [selectedIds]);

  const handleRowSelectionChange = (updater: Updater<RowSelectionState>) => {
    const next = typeof updater === "function" ? updater(rowSelection) : updater;
    onSelectionChange(
      Object.keys(next)
        .filter((key) => next[key])
        .map(Number)
    );
  };

  const table = useReactTable({
    data: filteredData,
    columns,
    getRowId: (row) => String(row.meta_id),
    state: { sorting, globalFilter, rowSelection },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    onRowSelectionChange: handleRowSelectionChange,
    globalFilterFn: (row, _columnId, filterValue) =>
      matchesQuickFilter(row.original, String(filterValue ?? "")),
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 25 } },
    enableRowSelection: true,
  });

  const { pageIndex, pageSize } = table.getState().pagination;
  const totalRows = table.getFilteredRowModel().rows.length;
  const firstRow = totalRows === 0 ? 0 : pageIndex * pageSize + 1;
  const lastRow = Math.min((pageIndex + 1) * pageSize, totalRows);

  return (
    <div className="card">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
        <div>
          <h3 className="text-base font-semibold text-ink">Stock Metadata</h3>
          <p className="text-sm text-ink-muted mt-0.5">
            {totalRows.toLocaleString()} securities
            {totalRows !== data.length &&
              ` (filtered from ${data.length.toLocaleString()})`}
          </p>
        </div>
        <input
          type="search"
          value={quickFilterInput}
          onChange={(e) => setQuickFilterInput(e.target.value)}
          placeholder="Search ticker, name, sector..."
          className="input w-64"
          aria-label="Quick filter"
        />
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id} className="table-header">
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    className={`py-2.5 px-4 text-left whitespace-nowrap first:rounded-l-lg last:rounded-r-lg ${
                      header.column.getCanSort()
                        ? "cursor-pointer select-none"
                        : ""
                    }`}
                    onClick={header.column.getToggleSortingHandler()}
                  >
                    <span className="inline-flex items-center gap-1">
                      {flexRender(
                        header.column.columnDef.header,
                        header.getContext()
                      )}
                      {header.column.getCanSort() && (
                        <SortIcon dir={header.column.getIsSorted()} />
                      )}
                    </span>
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
                  No securities match the current filters
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
                    <td key={cell.id} className="table-cell whitespace-nowrap">
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
      <div className="flex flex-wrap items-center justify-between gap-3 pt-4">
        <div className="flex items-center gap-2 text-sm text-ink-secondary">
          <span>Rows per page</span>
          <select
            value={pageSize}
            onChange={(e) => table.setPageSize(Number(e.target.value))}
            className="px-2 py-1 text-sm border border-edge rounded-lg bg-surface
                       focus:outline-none focus:border-primary-400"
            aria-label="Rows per page"
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
            {firstRow.toLocaleString()}–{lastRow.toLocaleString()} of{" "}
            {totalRows.toLocaleString()}
          </span>
          <button
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
            className="px-3 py-1.5 text-sm rounded-lg bg-raised border border-edge
                       hover:bg-overlay disabled:opacity-40 disabled:cursor-not-allowed"
            aria-label="Previous page"
          >
            ←
          </button>
          <button
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
            className="px-3 py-1.5 text-sm rounded-lg bg-raised border border-edge
                       hover:bg-overlay disabled:opacity-40 disabled:cursor-not-allowed"
            aria-label="Next page"
          >
            →
          </button>
        </div>
      </div>
    </div>
  );
};

export default MetaTable;
