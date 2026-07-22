"use client";

import React, { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Pencil, Trash2 } from "lucide-react";
import {
  ColumnDef,
  SortingState,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";

import { HoldingPosition } from "@/state/api";
import {
  fmtNative,
  fmtFracPct,
  fmtPctVal,
  marketLabel,
  signClassNum,
} from "./format";
import { fmtJo } from "@/app/insight/format";

interface PortfolioTableProps {
  positions: HoldingPosition[];
  onEdit: (position: HoldingPosition) => void;
  onRemove: (metaId: number) => void;
}

const SortIcon: React.FC<{ dir: false | "asc" | "desc" }> = ({ dir }) => (
  <span className="text-[10px] text-ink-muted w-3 inline-block">
    {dir === "asc" ? "▲" : dir === "desc" ? "▼" : ""}
  </span>
);

const MarketPill: React.FC<{ iso: string }> = ({ iso }) => (
  <span
    className="badge-neutral"
    style={{ color: iso === "KR" ? "var(--chart-1)" : "var(--chart-2)" }}
  >
    {marketLabel(iso)}
  </span>
);

const PortfolioTable: React.FC<PortfolioTableProps> = ({
  positions,
  onEdit,
  onRemove,
}) => {
  const router = useRouter();
  const [sorting, setSorting] = useState<SortingState>([
    { id: "weight", desc: true },
  ]);

  const columns = useMemo<ColumnDef<HoldingPosition>[]>(
    () => [
      {
        id: "name",
        accessorKey: "name",
        header: "Name",
        cell: ({ row }) => {
          const p = row.original;
          return (
            <div>
              <span className="font-medium text-ink">{p.name ?? p.ticker}</span>
              <span className="ml-1.5 text-xs text-ink-muted num">
                {p.ticker}
              </span>
            </div>
          );
        },
      },
      {
        id: "market",
        accessorKey: "iso_code",
        header: "Mkt",
        cell: ({ row }) => <MarketPill iso={row.original.iso_code} />,
      },
      {
        id: "shares",
        accessorKey: "shares",
        header: "수량",
        cell: ({ row }) => (
          <span className="num text-ink">
            {row.original.shares.toLocaleString()}
          </span>
        ),
      },
      {
        id: "avg_cost",
        accessorKey: "avg_cost",
        header: "평단",
        cell: ({ row }) => (
          <span className="num text-ink-secondary">
            {fmtNative(row.original.avg_cost, row.original.currency)}
          </span>
        ),
      },
      {
        id: "latest_price",
        accessorKey: "latest_price",
        header: "현재가",
        cell: ({ row }) => {
          const p = row.original;
          return (
            <div className="flex flex-col items-end">
              <span className="num text-ink">
                {fmtNative(p.latest_price, p.currency)}
              </span>
              {p.day_chg_pct !== null && (
                <span className={`text-xs ${signClassNum(p.day_chg_pct)}`}>
                  {fmtPctVal(p.day_chg_pct)}
                </span>
              )}
            </div>
          );
        },
      },
      {
        id: "market_value",
        accessorKey: "market_value_krw",
        header: "평가액",
        cell: ({ row }) => {
          const p = row.original;
          return (
            <div className="flex flex-col items-end">
              <span className="num text-ink">
                {fmtNative(p.market_value_native, p.currency)}
              </span>
              <span className="num text-xs text-ink-muted">
                {fmtJo(p.market_value_krw)}
              </span>
            </div>
          );
        },
      },
      {
        id: "pnl",
        accessorKey: "unrealized_pnl_native",
        header: "손익",
        cell: ({ row }) => {
          const p = row.original;
          const sign = p.unrealized_pnl_native > 0 ? "+" : "";
          return (
            <div className="flex flex-col items-end">
              <span className={signClassNum(p.unrealized_pnl_native)}>
                {p.unrealized_pnl_native === 0
                  ? fmtNative(0, p.currency)
                  : `${sign}${fmtNative(p.unrealized_pnl_native, p.currency)}`}
              </span>
              <span className={`text-xs ${signClassNum(p.unrealized_pnl_pct)}`}>
                {fmtFracPct(p.unrealized_pnl_pct)}
              </span>
            </div>
          );
        },
      },
      {
        id: "weight",
        accessorKey: "weight",
        header: "비중",
        cell: ({ row }) => {
          const pct = row.original.weight * 100;
          return (
            <div className="flex flex-col items-end gap-1 min-w-[64px]">
              <span className="num text-sm font-semibold text-ink-secondary">
                {pct.toFixed(1)}%
              </span>
              <div className="w-full h-1.5 bg-raised rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${Math.max(0, Math.min(100, pct))}%`,
                    backgroundColor: "var(--chart-1)",
                    opacity: 0.9,
                  }}
                />
              </div>
            </div>
          );
        },
      },
      {
        id: "actions",
        header: "",
        enableSorting: false,
        cell: ({ row }) => {
          const p = row.original;
          return (
            <div className="flex items-center justify-end gap-1">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onEdit(p);
                }}
                aria-label={`${p.name ?? p.ticker} 보유 수정`}
                className="p-1.5 rounded-lg text-ink-muted hover:text-ink hover:bg-overlay transition-colors"
              >
                <Pencil size={14} aria-hidden />
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onRemove(p.meta_id);
                }}
                aria-label={`${p.name ?? p.ticker} 보유 제거`}
                className="p-1.5 rounded-lg text-ink-muted hover:text-losses hover:bg-overlay transition-colors"
              >
                <Trash2 size={14} aria-hidden />
              </button>
            </div>
          );
        },
      },
    ],
    [onEdit, onRemove]
  );

  const table = useReactTable({
    data: positions,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  const alignRight = new Set([
    "shares",
    "avg_cost",
    "latest_price",
    "market_value",
    "pnl",
    "weight",
    "actions",
  ]);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id} className="table-header">
              {hg.headers.map((header) => (
                <th
                  key={header.id}
                  className={`py-2.5 px-4 whitespace-nowrap first:rounded-l-lg last:rounded-r-lg ${
                    alignRight.has(header.column.id) ? "text-right" : "text-left"
                  } ${
                    header.column.getCanSort()
                      ? "cursor-pointer select-none"
                      : ""
                  }`}
                  onClick={header.column.getToggleSortingHandler()}
                >
                  <span
                    className={`inline-flex items-center gap-1 ${
                      alignRight.has(header.column.id) ? "justify-end" : ""
                    }`}
                  >
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
          {table.getRowModel().rows.map((row) => (
            <tr
              key={row.id}
              className="table-row cursor-pointer"
              onClick={() => router.push(`/stock/${row.original.meta_id}`)}
            >
              {row.getVisibleCells().map((cell) => (
                <td
                  key={cell.id}
                  className={`table-cell whitespace-nowrap ${
                    alignRight.has(cell.column.id) ? "text-right" : ""
                  }`}
                >
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default PortfolioTable;
