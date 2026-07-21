"use client";

import React, { useMemo } from "react";
import { KrMacroSeries, useFetchRegimeKrQuery } from "@/state/api";
import Card from "@/components/ui/Card";
import InfoTip from "@/components/ui/InfoTip";
import StatTile from "@/components/ui/StatTile";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";
import EmptyState from "@/components/ui/EmptyState";
import TimeSeriesChart from "@/components/charts/TimeSeriesChart";

const fmt = (v: number | undefined | null, digits = 2, suffix = "") =>
  v === undefined || v === null ? "—" : `${v.toFixed(digits)}${suffix}`;

const toChartData = (series: KrMacroSeries | undefined) =>
  (series?.data ?? []).map((d) => ({ date: d.date, value: d.value }));

/** Merge multiple {date,value} series into one date-keyed dataset. */
const mergeSeries = (
  inputs: { key: string; series: KrMacroSeries | undefined }[]
) => {
  const byDate = new Map<string, { date: string; [k: string]: number | string }>();
  for (const { key, series } of inputs) {
    for (const point of series?.data ?? []) {
      const row = byDate.get(point.date) ?? { date: point.date };
      row[key] = point.value;
      byDate.set(point.date, row);
    }
  }
  return Array.from(byDate.values()).sort((a, b) =>
    String(a.date).localeCompare(String(b.date))
  );
};

/** Korea macro tab: policy/market rates, FX, inflation, and OECD CLI. */
const KoreaMacro: React.FC = () => {
  const { data, isLoading, error, refetch } = useFetchRegimeKrQuery();

  const series = data;
  const baseRate = series?.base_rate;
  const ktb3y = series?.ktb_3y;
  const ktb10y = series?.ktb_10y;
  const usdkrw = series?.usdkrw;
  const cpiYoy = series?.cpi_yoy;
  const cliKor = series?.cli_kor;

  const ratesData = useMemo(
    () =>
      mergeSeries([
        { key: "base_rate", series: baseRate },
        { key: "ktb_3y", series: ktb3y },
        { key: "ktb_10y", series: ktb10y },
      ]),
    [baseRate, ktb3y, ktb10y]
  );

  if (error) {
    return (
      <div className="card">
        <ErrorState message="Failed to load Korea macro data" onRetry={refetch} />
      </div>
    );
  }

  if (isLoading || !data) {
    return (
      <div className="card">
        <LoadingState label="Loading Korea macro data..." />
      </div>
    );
  }

  if (!series || Object.keys(series).length === 0) {
    return (
      <div className="card">
        <EmptyState
          title="No Korea macro data"
          hint="KR macro series will appear once ingested"
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* Latest snapshot */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatTile
          label={baseRate?.name ?? "기준금리"}
          value={fmt(baseRate?.latest, 2, "%")}
        />
        <StatTile
          label={ktb3y?.name ?? "국고채 3Y"}
          value={fmt(ktb3y?.latest, 2, "%")}
        />
        <StatTile
          label={usdkrw?.name ?? "USD/KRW"}
          value={fmt(usdkrw?.latest, 1)}
        />
        <StatTile
          label={cpiYoy?.name ?? "CPI YoY"}
          value={fmt(cpiYoy?.latest, 2, "%")}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card
          title={
            <span className="inline-flex items-center gap-1.5">
              금리 — 기준금리 · 국고채 3Y/10Y
              <InfoTip helpKey="kr.rates" />
            </span>
          }
        >
          <TimeSeriesChart
            data={ratesData}
            series={[
              {
                key: "base_rate",
                name: baseRate?.name ?? "기준금리",
                color: "var(--chart-1)",
              },
              {
                key: "ktb_3y",
                name: ktb3y?.name ?? "국고채 3Y",
                color: "var(--chart-2)",
              },
              {
                key: "ktb_10y",
                name: ktb10y?.name ?? "국고채 10Y",
                color: "var(--chart-3)",
              },
            ]}
            height={280}
            yFormatter={(v) => `${v.toFixed(1)}%`}
          />
        </Card>

        <Card
          title={
            <span className="inline-flex items-center gap-1.5">
              {usdkrw?.name ?? "USD/KRW"}
              <InfoTip helpKey="kr.usdkrw" />
            </span>
          }
        >
          <TimeSeriesChart
            data={toChartData(usdkrw)}
            series={[
              {
                key: "value",
                name: usdkrw?.name ?? "USD/KRW",
                color: "var(--chart-6)",
              },
            ]}
            height={280}
            yFormatter={(v) => v.toFixed(0)}
          />
        </Card>

        <Card title={cpiYoy?.name ?? "CPI YoY"}>
          <TimeSeriesChart
            data={toChartData(cpiYoy)}
            series={[
              {
                key: "value",
                name: cpiYoy?.name ?? "CPI YoY",
                color: "var(--chart-5)",
              },
            ]}
            height={280}
            yFormatter={(v) => `${v.toFixed(1)}%`}
            baseline={2}
          />
        </Card>

        <Card title={cliKor?.name ?? "OECD CLI (Korea)"}>
          <TimeSeriesChart
            data={toChartData(cliKor)}
            series={[
              {
                key: "value",
                name: cliKor?.name ?? "CLI",
                color: "var(--chart-4)",
              },
            ]}
            height={280}
            baseline={100}
          />
        </Card>
      </div>
    </div>
  );
};

export default KoreaMacro;
