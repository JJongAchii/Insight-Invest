import React, { useMemo } from "react";
import TimeSeriesChart, {
  TimeSeriesReferenceLineX,
} from "@/components/charts/TimeSeriesChart";
import InfoTip from "@/components/ui/InfoTip";
import { NavPoint } from "@/state/api";

interface NavData {
  trade_date: string;
  value: number;
}

interface BmNavData {
  /** pandas to_json 직렬화라 epoch ms(숫자)로 온다 — 전략 nav의 ISO 문자열과 다르다. */
  trade_date: string | number;
  bm_name: string;
  value: number;
}

/** 날짜 키 정규화(YYYY-MM-DD) — bm(epoch ms)·전략(ISO)·live(date-only)가 서로 다른
 *  포맷이라, 원형 그대로 Map 키로 쓰면 벤치마크가 영원히 매칭되지 않는다. */
const toDay = (d: string | number): string =>
  typeof d === "number" ? new Date(d).toISOString().slice(0, 10) : d.slice(0, 10);

const LineChart = ({
  strategyName,
  strategyNav,
  bmNav,
  liveNav,
  savedAt,
  bmLiveNav,
  bmLabel,
}: {
  strategyName: string;
  strategyNav: NavData[];
  bmNav: string;
  /** Live (post-save) NAV, ~1000-based at savedAt. */
  liveNav?: NavPoint[];
  savedAt?: string | null;
  /** 저장 후 벤치마크 NAV (첫 관측=1000) — 백테스트 BM 끝값에 이어 그린다. */
  bmLiveNav?: NavPoint[];
  /** 벤치마크 실체 표시명 (예: "Benchmark (SPY)"). */
  bmLabel?: string;
}) => {
  const { chartData, series, referenceLinesX, hasLive } = useMemo(() => {
    const bmNavData: BmNavData[] = bmNav ? JSON.parse(bmNav) : [];
    const bmByDate = new Map<string, number>(
      bmNavData.map((nav) => [toDay(nav.trade_date), nav.value])
    );

    type Row = {
      date: string;
      strategy: number | null;
      benchmark: number | null;
      live: number | null;
    };

    const rowByDate = new Map<string, Row>();
    for (const nav of strategyNav ?? []) {
      const day = toDay(nav.trade_date);
      rowByDate.set(day, {
        date: day,
        strategy: nav.value,
        benchmark: bmByDate.get(day) ?? null,
        live: null,
      });
    }

    // Rescale the 1000-based live NAV so it visually continues from the
    // stored backtest NAV's last value (saved_at == stored NAV end).
    const storedLast =
      strategyNav && strategyNav.length > 0
        ? strategyNav[strategyNav.length - 1].value
        : null;
    const live = liveNav ?? [];
    const hasLive = live.length > 0 && storedLast !== null;
    if (hasLive) {
      const scale = storedLast / 1000;
      for (const p of live) {
        const day = toDay(p.date);
        const existing = rowByDate.get(day);
        if (existing) {
          existing.live = p.value * scale;
        } else {
          rowByDate.set(day, {
            date: day,
            strategy: null,
            benchmark: bmByDate.get(day) ?? null,
            live: p.value * scale,
          });
        }
      }
      // Anchor the live segment to the backtest endpoint for continuity.
      const lastStored = strategyNav[strategyNav.length - 1];
      const boundary = rowByDate.get(toDay(lastStored.trade_date));
      if (boundary && boundary.live === null) boundary.live = storedLast;
    }

    // 저장 후 벤치마크 연장 — 라이브 라인과 같은 규약: 백테스트 BM 의 마지막
    // 값을 앵커로 1000-기준 시계열을 이어 붙인다.
    const bmLive = bmLiveNav ?? [];
    if (bmLive.length > 0 && bmNavData.length > 0) {
      const bmLast = bmNavData[bmNavData.length - 1].value;
      const bmScale = bmLast / 1000;
      for (const p of bmLive) {
        const day = toDay(p.date);
        const existing = rowByDate.get(day);
        const v = p.value * bmScale;
        if (existing) {
          existing.benchmark = v;
        } else {
          rowByDate.set(day, { date: day, strategy: null, benchmark: v, live: null });
        }
      }
    }

    const chartData = [...rowByDate.values()].sort((a, b) =>
      a.date.localeCompare(b.date)
    );

    const series = [
      { key: "strategy", name: strategyName, color: "var(--chart-1)" },
      { key: "benchmark", name: bmLabel ?? "Benchmark", color: "var(--text-muted)" },
      ...(hasLive
        ? [{ key: "live", name: "Live (저장 후)", color: "var(--chart-4)" }]
        : []),
    ];

    const referenceLinesX: TimeSeriesReferenceLineX[] | undefined =
      hasLive && savedAt
        ? [{ x: toDay(savedAt), label: "저장", color: "var(--chart-4)" }]
        : undefined;

    return { chartData, series, referenceLinesX, hasLive };
  }, [strategyName, strategyNav, bmNav, liveNav, savedAt, bmLiveNav, bmLabel]);

  return (
    <div className="card">
      <h4 className="text-base font-semibold text-ink mb-4">
        <span className="inline-flex items-center gap-1.5">
          {hasLive ? "Backtest vs Live" : "Cumulative Performance"}
          {hasLive && <InfoTip helpKey="bt.live" />}
        </span>
      </h4>
      <TimeSeriesChart
        data={chartData}
        series={series}
        height={400}
        yFormatter={(v) => v.toFixed(2)}
        referenceLinesX={referenceLinesX}
      />
    </div>
  );
};

export default LineChart;
