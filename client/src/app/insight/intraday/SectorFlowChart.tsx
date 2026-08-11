import React, { useMemo } from "react";
import TimeSeriesChart from "@/components/charts/TimeSeriesChart";
import { IntradaySectorRow } from "@/state/api";

// globals.css는 --chart-1~6까지만 정의한다 (7,8 없음) — 8업종을 6색으로 순환.
const COLORS = [
  "var(--chart-1)",
  "var(--chart-2)",
  "var(--chart-3)",
  "var(--chart-4)",
  "var(--chart-5)",
  "var(--chart-6)",
];

/** 당일 섹터 등락률 흐름 — 거래대금 상위 8업종 (스펙 D4). sectors는 이미
 *  value_krw 내림차순이므로 앞 8개를 취한다. */
const SectorFlowChart = ({ sectors }: { sectors: IntradaySectorRow[] }) => {
  const top = sectors.slice(0, 8);
  const { data, series } = useMemo(() => {
    const byTime = new Map<string, { date: string; [k: string]: string | number | null }>();
    for (const s of top) {
      for (const p of s.flow) {
        const row = byTime.get(p.t) ?? { date: p.t };
        row[s.name] = p.chg_pct;
        byTime.set(p.t, row);
      }
    }
    return {
      data: [...byTime.values()].sort((a, b) =>
        String(a.date).localeCompare(String(b.date))
      ),
      series: top.map((s, i) => ({
        key: s.name,
        name: s.name,
        color: COLORS[i % COLORS.length],
      })),
    };
  }, [top]);

  if (data.length < 2) return null; // 폴 1회뿐이면 라인이 무의미

  return (
    <div className="card">
      <h4 className="text-base font-semibold text-ink mb-4">
        섹터 흐름 — 거래대금 상위 8업종 (당일, %)
      </h4>
      <TimeSeriesChart
        data={data}
        series={series}
        height={320}
        yFormatter={(v: number) => `${v.toFixed(1)}%`}
      />
    </div>
  );
};

export default SectorFlowChart;
