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
 */
export const calculatePeriodReturns = (
  data: NavPoint[],
  period: "month" | "year"
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
  let previousEndValue: number | null = null;

  for (const [key, { end }] of Object.entries(groupedData)) {
    if (previousEndValue !== null) {
      const periodReturn = ((end - previousEndValue) / previousEndValue) * 100;
      returnData.push({ period: key, return: periodReturn });
    }
    previousEndValue = end;
  }

  return returnData;
};
