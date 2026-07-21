"use client";

import React, { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  InsightFlowTopRow,
  InsightInvestor,
  InsightWindow,
  useFetchInsightFlowsMarketQuery,
  useFetchInsightFlowsTopQuery,
} from "@/state/api";
import Card from "@/components/ui/Card";
import InfoTip from "@/components/ui/InfoTip";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";
import EmptyState from "@/components/ui/EmptyState";
import TimeSeriesChart from "@/components/charts/TimeSeriesChart";
import {
  fmtEok,
  fmtEokAxis,
  fmtPct,
  MarketBadge,
  Segmented,
  signClass,
} from "./format";

const INVESTOR_OPTIONS: { id: InsightInvestor; label: string }[] = [
  { id: "frgn", label: "Foreign" },
  { id: "inst", label: "Institution" },
];

const WINDOW_OPTIONS: { id: InsightWindow; label: string }[] = [
  { id: "1d", label: "1D" },
  { id: "1w", label: "1W" },
  { id: "1m", label: "1M" },
];

/** One side of the top buys/sells pair. */
const FlowsTopTable: React.FC<{
  title: string;
  rows: InsightFlowTopRow[];
  onRowClick: (row: InsightFlowTopRow) => void;
}> = ({ title, rows, onRowClick }) => (
  <div>
    <p className="text-sm font-medium text-ink-secondary mb-2">{title}</p>
    {rows.length === 0 ? (
      <EmptyState title="No data" />
    ) : (
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="table-header">
              <th className="py-2.5 px-3 text-left rounded-l-lg">#</th>
              <th className="py-2.5 px-3 text-left">Name</th>
              <th className="py-2.5 px-3 text-left">Mkt</th>
              <th className="py-2.5 px-3 text-right">Net</th>
              <th className="py-2.5 px-3 text-right rounded-r-lg">Chg</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={`${row.rank}-${row.ticker}`}
                className="table-row cursor-pointer"
                onClick={() => onRowClick(row)}
              >
                <td className="table-cell num text-ink-muted">{row.rank}</td>
                <td className="table-cell">
                  <span className="font-medium text-ink">{row.name}</span>
                  <span className="ml-1.5 text-xs text-ink-muted num">
                    {row.ticker}
                  </span>
                </td>
                <td className="table-cell">
                  <MarketBadge market={row.market} />
                </td>
                <td className="table-cell text-right">
                  <span className={signClass(row.net_value)}>
                    {fmtEok(row.net_value)}
                  </span>
                </td>
                <td className="table-cell text-right">
                  <span className={signClass(row.chg_pct)}>
                    {fmtPct(row.chg_pct)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )}
  </div>
);

/** Foreign/institution flows: 12M cumulative net value + top buys/sells tables. */
const FlowsSection: React.FC = () => {
  const router = useRouter();
  const [investor, setInvestor] = useState<InsightInvestor>("frgn");
  const [flowWindow, setFlowWindow] = useState<InsightWindow>("1d");

  const {
    data: marketData,
    isLoading: marketLoading,
    error: marketError,
    refetch: refetchMarket,
  } = useFetchInsightFlowsMarketQuery({ days: 365 });
  const {
    data: topData,
    isLoading: topLoading,
    error: topError,
    refetch: refetchTop,
  } = useFetchInsightFlowsTopQuery({ window: flowWindow, investor });

  const investorLabel =
    INVESTOR_OPTIONS.find((o) => o.id === investor)?.label ?? investor;

  // Cumulative net value (억) per market for the selected investor.
  const cumulativeData = useMemo(() => {
    const rows = (marketData?.rows ?? []).filter(
      (r) => r.investor === investor && r.market !== "ALL"
    );
    if (rows.length === 0) return [];
    const byDate = new Map<string, { KOSPI: number; KOSDAQ: number }>();
    for (const r of rows) {
      const g = byDate.get(r.date) ?? { KOSPI: 0, KOSDAQ: 0 };
      if (r.market === "KOSPI" || r.market === "KOSDAQ") {
        g[r.market] += r.net_value;
      }
      byDate.set(r.date, g);
    }
    let cumKospi = 0;
    let cumKosdaq = 0;
    return Array.from(byDate.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, g]) => {
        cumKospi += g.KOSPI;
        cumKosdaq += g.KOSDAQ;
        return {
          date,
          KOSPI: cumKospi / 1e8,
          KOSDAQ: cumKosdaq / 1e8,
        };
      });
  }, [marketData, investor]);

  const goToStock = (row: InsightFlowTopRow) => {
    router.push(`/stocksearch?q=${encodeURIComponent(row.name)}`);
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-semibold text-ink">Investor Flows</h2>
        <Segmented
          options={INVESTOR_OPTIONS}
          value={investor}
          onChange={setInvestor}
        />
      </div>

      <Card
        title={
          <span className="inline-flex items-center gap-1.5">
            {`Cumulative Net Buying — ${investorLabel}`}
            <InfoTip helpKey="flows.cumulative" />
          </span>
        }
        action={
          <span className="text-xs text-ink-muted">12M · KOSPI vs KOSDAQ</span>
        }
      >
        {marketError ? (
          <ErrorState
            message="Failed to load market flows"
            onRetry={refetchMarket}
          />
        ) : marketLoading || !marketData ? (
          <LoadingState label="Loading market flows..." />
        ) : cumulativeData.length === 0 ? (
          <EmptyState title="No market flow data" />
        ) : (
          <TimeSeriesChart
            data={cumulativeData}
            series={[
              { key: "KOSPI", color: "var(--chart-1)" },
              { key: "KOSDAQ", color: "var(--chart-2)" },
            ]}
            height={280}
            yFormatter={fmtEokAxis}
            baseline={0}
          />
        )}
      </Card>

      <Card
        title={
          <span className="inline-flex items-center gap-1.5">
            {`Top Net Buys / Sells — ${investorLabel}`}
            <InfoTip helpKey="flows.top" />
          </span>
        }
        action={
          <div className="flex items-center gap-3">
            {topData?.as_of && (
              <span className="text-xs text-ink-muted num">
                as of {topData.as_of}
              </span>
            )}
            <Segmented
              options={WINDOW_OPTIONS}
              value={flowWindow}
              onChange={setFlowWindow}
            />
          </div>
        }
      >
        {topError ? (
          <ErrorState message="Failed to load top flows" onRetry={refetchTop} />
        ) : topLoading || !topData ? (
          <LoadingState label="Loading top flows..." />
        ) : (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <FlowsTopTable
              title="Top Buys"
              rows={topData.buys}
              onRowClick={goToStock}
            />
            <FlowsTopTable
              title="Top Sells"
              rows={topData.sells}
              onRowClick={goToStock}
            />
          </div>
        )}
      </Card>
    </div>
  );
};

export default FlowsSection;
