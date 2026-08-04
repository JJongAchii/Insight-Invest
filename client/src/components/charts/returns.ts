import dayjs from "dayjs";

export interface NavPoint {
  trade_date: string;
  value: number;
}

export interface PeriodReturn {
  period: string;
  return: number;
}

/**
 * Compute period-over-period returns (%) from a NAV series.
 * Groups NAV by month/year end value; return = change vs previous period's end.
 * With `initialRef` supplied, the first period is also computed (change vs that
 * reference value) instead of being dropped for lack of a prior period — used by
 * the live series, which is anchored at a known reference value (the saved_at NAV).
 */
export const calculatePeriodReturns = (
  data: NavPoint[],
  period: "month" | "year",
  initialRef?: number
): PeriodReturn[] => {
  if (!data || data.length === 0) return [];

  const sortedData = [...data].sort(
    (a, b) => dayjs(a.trade_date).unix() - dayjs(b.trade_date).unix()
  );

  const groupedData = sortedData.reduce(
    (acc, { trade_date, value }) => {
      const date = dayjs(trade_date);
      const key = period === "year" ? date.format("YYYY") : date.format("YYYY-MM");

      if (!acc[key]) {
        acc[key] = { start: value, end: value };
      } else {
        acc[key].end = value;
      }
      return acc;
    },
    {} as Record<string, { start: number; end: number }>
  );

  const returnData: PeriodReturn[] = [];
  let previousEndValue: number | null = initialRef ?? null;

  for (const [key, { end }] of Object.entries(groupedData)) {
    if (previousEndValue !== null) {
      const periodReturn = ((end - previousEndValue) / previousEndValue) * 100;
      returnData.push({ period: key, return: periodReturn });
    }
    previousEndValue = end;
  }

  return returnData;
};
