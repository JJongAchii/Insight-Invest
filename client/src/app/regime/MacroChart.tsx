"use client";

import React, { useMemo } from "react";
import TimeSeriesChart, {
  TimeSeriesReferenceArea,
} from "@/components/charts/TimeSeriesChart";

interface MacroData {
  macro_id: string;
  base_date: string;
  value: number;
}

interface MacroChartProps {
  primaryData: MacroData[];
  recessionData: MacroData[];
  primaryLabel: string;
  recessionLabel: string;
  title: string;
  subtitle?: string;
  baseline?: number;
}

const MacroChart: React.FC<MacroChartProps> = ({
  primaryData,
  recessionData,
  primaryLabel,
  recessionLabel,
  title,
  subtitle,
  baseline,
}) => {
  const { chartData, recessionAreas } = useMemo(() => {
    const data = (primaryData ?? []).map((d) => ({
      date: d.base_date,
      value: d.value,
    }));

    // Map recession values onto the primary series dates, then compute
    // contiguous ranges where the recession indicator === 1.
    const recessionByDate = new Map<string, number>(
      (recessionData ?? []).map((d) => [d.base_date, d.value])
    );

    const areas: TimeSeriesReferenceArea[] = [];
    let rangeStart: string | null = null;
    let prevDate: string | null = null;

    for (const point of data) {
      const inRecession = recessionByDate.get(point.date) === 1;
      if (inRecession && rangeStart === null) {
        rangeStart = point.date;
      } else if (!inRecession && rangeStart !== null) {
        areas.push({ x1: rangeStart, x2: prevDate ?? rangeStart });
        rangeStart = null;
      }
      prevDate = point.date;
    }
    if (rangeStart !== null && prevDate !== null) {
      areas.push({ x1: rangeStart, x2: prevDate });
    }

    return { chartData: data, recessionAreas: areas };
  }, [primaryData, recessionData]);

  const latestValue = primaryData?.[primaryData.length - 1]?.value;

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h4 className="text-base font-semibold text-ink">{title}</h4>
          <p className="text-xs text-ink-muted mt-0.5">
            {subtitle ?? `${primaryLabel} · shaded: ${recessionLabel}`}
          </p>
        </div>
        {latestValue !== undefined && (
          <span className="num text-sm font-medium text-ink-secondary">
            Latest: {latestValue.toFixed(2)}
          </span>
        )}
      </div>
      <TimeSeriesChart
        data={chartData}
        series={[{ key: "value", name: primaryLabel, color: "var(--chart-1)" }]}
        height={300}
        showBrush
        referenceAreas={recessionAreas}
        baseline={baseline}
      />
    </div>
  );
};

export default MacroChart;
