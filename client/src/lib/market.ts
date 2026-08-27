export type SupportedMarket = "KR" | "US";

export const marketOf = (isoCode?: string | null): SupportedMarket =>
  isoCode === "KR" ? "KR" : "US";

export const formatPrice = (
  value: number | null | undefined,
  isoCode?: string | null
): string => {
  if (typeof value !== "number" || Number.isNaN(value)) return "—";
  const market = marketOf(isoCode);
  return new Intl.NumberFormat(market === "KR" ? "ko-KR" : "en-US", {
    style: "currency",
    currency: market === "KR" ? "KRW" : "USD",
    maximumFractionDigits: market === "KR" ? 0 : 2,
  }).format(value);
};

export const formatMarketCap = (
  value: number | null | undefined,
  isoCode?: string | null
): string => {
  if (typeof value !== "number" || Number.isNaN(value)) return "—";
  if (marketOf(isoCode) === "KR") {
    if (value >= 1e12) return `${(value / 1e12).toFixed(1)}조원`;
    if (value >= 1e8) return `${(value / 1e8).toFixed(0)}억원`;
    return `${Math.round(value).toLocaleString("ko-KR")}원`;
  }
  if (value >= 1e12) return `$${(value / 1e12).toFixed(1)}T`;
  if (value >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
  if (value >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  return `$${value.toLocaleString("en-US")}`;
};

export const formatShares = (value: number | null | undefined): string => {
  if (typeof value !== "number" || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 2,
  }).format(value);
};

const REFERENCE_SOURCE_LABELS: Record<string, string> = {
  krx_stock_master: "KRX Stock Master",
  krx_etf_meta: "KRX ETF Meta",
  krx_reported_aum: "KRX Reported AUM",
  massive_ticker_details: "Massive Ticker Details",
  massive_close_x_weighted_shares: "Massive Close × Weighted Shares",
  estimate_close_x_share_class_shares:
    "Massive Close × Share-class Shares (estimate)",
};

export const formatReferenceSource = (value?: string | null): string => {
  if (!value) return "—";
  return REFERENCE_SOURCE_LABELS[value] ?? value.replaceAll("_", " ");
};

export const formatDate = (value?: string | null): string => {
  if (!value) return "—";
  const dateOnly = value.slice(0, 10);
  const date = new Date(`${dateOnly}T00:00:00`);
  if (Number.isNaN(date.getTime())) return dateOnly;
  return new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
};

export const formatChartDate = (value?: string | null): string => {
  if (!value) return "";
  const date = value.slice(0, 10);
  return date.length === 10 ? `${date.slice(5, 7)}.${date.slice(8, 10)}` : date;
};
