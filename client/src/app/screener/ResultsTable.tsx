"use client";

import React, { useState } from "react";
import { ScreenerStock, ScreenerSortField } from "@/state/api";

interface ResultsTableProps {
  data: ScreenerStock[];
  onSort: (sortBy: ScreenerSortField, ascending: boolean) => void;
}

const formatPercent = (value: number, includeSign = true) => {
  const formatted = value.toFixed(2);
  if (includeSign && value > 0) return `+${formatted}%`;
  return `${formatted}%`;
};

const formatPrice = (value: number) => {
  if (value >= 1000) return value.toLocaleString("en-US", { maximumFractionDigits: 0 });
  return value.toFixed(2);
};

const getColorClass = (value: number) => {
  if (value > 0) return "text-gains";
  if (value < 0) return "text-losses";
  return "text-neutral-600";
};

const ResultsTable: React.FC<ResultsTableProps> = ({ data, onSort }) => {
  const [sortField, setSortField] = useState<ScreenerSortField>("return_3m");
  const [sortAsc, setSortAsc] = useState(false);

  const handleHeaderClick = (field: ScreenerSortField) => {
    const newAsc = field === sortField ? !sortAsc : false;
    setSortField(field);
    setSortAsc(newAsc);
    onSort(field, newAsc);
  };

  const SortHeader: React.FC<{
    field: ScreenerSortField;
    label: string;
    className?: string;
  }> = ({ field, label, className = "" }) => (
    <th
      className={`table-header cursor-pointer hover:bg-neutral-100 transition-colors ${className}`}
      onClick={() => handleHeaderClick(field)}
    >
      <div className="flex items-center gap-1">
        {label}
        {sortField === field && (
          <span className="text-primary-500">{sortAsc ? "↑" : "↓"}</span>
        )}
      </div>
    </th>
  );

  if (data.length === 0) {
    return (
      <div className="card text-center py-8">
        <p className="text-neutral-500">No stocks match your criteria</p>
      </div>
    );
  }

  return (
    <div className="card overflow-hidden p-0">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1000px]">
          <thead>
            <tr>
              <th className="table-header text-left pl-4">Ticker</th>
              <th className="table-header text-left">Name</th>
              <th className="table-header text-right">Price</th>
              <SortHeader field="return_1m" label="1M" className="text-right" />
              <SortHeader field="return_3m" label="3M" className="text-right" />
              <SortHeader field="return_6m" label="6M" className="text-right" />
              <SortHeader field="return_12m" label="12M" className="text-right" />
              <SortHeader field="volatility_3m" label="Vol" className="text-right" />
              <SortHeader field="mdd_1y" label="MDD" className="text-right" />
              <SortHeader field="pct_from_high" label="vs High" className="text-right pr-4" />
            </tr>
          </thead>
          <tbody>
            {data.map((stock) => (
              <tr key={stock.meta_id} className="table-row">
                <td className="table-cell font-medium pl-4">
                  <div className="flex items-center gap-2">
                    <span className="text-neutral-900">{stock.ticker}</span>
                    {stock.iso_code && (
                      <span className="text-xs px-1.5 py-0.5 bg-neutral-100 rounded text-neutral-500">
                        {stock.iso_code}
                      </span>
                    )}
                  </div>
                </td>
                <td className="table-cell text-neutral-600 max-w-[200px] truncate">
                  {stock.name || "-"}
                </td>
                <td className="table-cell text-right font-medium">
                  ${formatPrice(stock.current_price)}
                </td>
                <td className={`table-cell text-right ${getColorClass(stock.return_1m)}`}>
                  {formatPercent(stock.return_1m)}
                </td>
                <td className={`table-cell text-right ${getColorClass(stock.return_3m)}`}>
                  {formatPercent(stock.return_3m)}
                </td>
                <td className={`table-cell text-right ${getColorClass(stock.return_6m)}`}>
                  {formatPercent(stock.return_6m)}
                </td>
                <td className={`table-cell text-right ${getColorClass(stock.return_12m)}`}>
                  {formatPercent(stock.return_12m)}
                </td>
                <td className="table-cell text-right text-neutral-600">
                  {stock.volatility_3m.toFixed(1)}%
                </td>
                <td className="table-cell text-right text-losses">
                  {formatPercent(stock.mdd_1y, false)}
                </td>
                <td className={`table-cell text-right pr-4 ${getColorClass(stock.pct_from_high)}`}>
                  {formatPercent(stock.pct_from_high)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default ResultsTable;
