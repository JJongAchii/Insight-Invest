import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";

// Types for news operations
export type NewsCategory =
  | "topnews"  // Top news headlines (default)
  | "economy"  // World economy, macro
  | "policy"   // Central bank, Fed, interest rates
  | "trade"    // International trade, tariffs
  | "energy"   // Oil, gas, energy markets
  | "tech";    // Tech industry news

export type NewsRegion = "us" | "asia" | "europe" | "global" | "all";

export interface NewsArticle {
  id: string;
  title: string;
  summary: string | null;
  url: string;
  source: string;
  published_at: string | null;
  category: string;
  region: string;
  image_url: string | null;
  sentiment: string | null;
}

export interface NewsResponse {
  articles: NewsArticle[];
  total_count: number;
  cached: boolean;
  fetched_at: string;
}

export interface NewsQueryParams {
  category?: NewsCategory;
  region?: NewsRegion;
  limit?: number;
  search_query?: string;
}

export interface NewsSource {
  id: string;
  name: string;
  region: string;
}

// Types for price/stock search operations
export interface StockMetrics {
  ytd_return: number | null;
  return_1y: number | null;
  return_3m: number | null;
  volatility: number | null;
  sharpe: number | null;
  mdd: number | null;
}

export interface PricePoint {
  trade_date: string;
  adj_close: number | null;
  gross_return: number | null;
}

export interface StockMeta {
  meta_id: number;
  ticker: string;
  name: string | null;
  sector: string | null;
  iso_code: string;
  marketcap: number | null;
}

export interface PriceHistoryResponse {
  prices: PricePoint[];
  meta: StockMeta;
}

export interface PriceSummaryResponse {
  meta_id: number;
  ticker: string;
  name: string | null;
  metrics: StockMetrics;
  latest_price: number | null;
  latest_date: string | null;
}

export interface SparklineResponse {
  sparklines: Record<string, number[]>;
}

export interface CompareStock {
  meta_id: number;
  ticker: string;
  name: string | null;
  sector: string | null;
  iso_code: string;
  metrics: StockMetrics;
}

export interface NormalizedPricePoint {
  date: string;
  [ticker: string]: string | number; // ticker -> normalized price
}

export interface CompareResponse {
  stocks: CompareStock[];
  normalized_prices: NormalizedPricePoint[];
}

// Types for backtest operations
export interface BacktestPayload {
  strategy_name: string;
  meta_id: string[];
  algorithm: string | undefined;
  startDate: string;
  endDate: string;
}

export interface BacktestResult {
  weights: string;
  nav: string;
  metrics: string;
}

export interface SaveStrategyResponse {
  message: string;
}

export interface ClearStrategyResponse {
  message: string;
}

export const api = createApi({
  reducerPath: "api",
  baseQuery: fetchBaseQuery({ baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL }),
  tagTypes: ["Strategy", "Portfolio", "News"],
  endpoints: (builder) => ({
    // Query endpoints
    fetchMetaData: builder.query({
      query: () => "/meta",
    }),
    fetchTickers: builder.query({
      query: () => "/meta/tickers",
    }),
    fetchAlgorithms: builder.query({
      query: () => "/backtest/algorithm",
    }),
    fetchStrategies: builder.query({
      query: () => "/backtest/strategy",
      providesTags: ["Strategy"],
    }),
    fetchStrategyMonthlyNav: builder.query({
      query: () => "/backtest/strategy/monthlynav",
      providesTags: ["Portfolio"],
    }),
    fetchStrategyById: builder.query({
      query: (port_id) => `backtest/strategy/${port_id}`,
      providesTags: ["Strategy"],
    }),
    fetchStNavById: builder.query({
      query: (port_id) => `backtest/strategy/nav/${port_id}`,
      providesTags: ["Portfolio"],
    }),
    fetchStRebalById: builder.query({
      query: (port_id) => `backtest/strategy/rebal/${port_id}`,
      providesTags: ["Portfolio"],
    }),
    fetchBmById: builder.query({
      query: (port_id) => `backtest/strategy/bm/${port_id}`,
    }),
    fetchMacroInfo: builder.query({
      query: () => "/regime/info",
    }),
    fetchMacroData: builder.query({
      query: () => "/regime/data",
    }),

    // Price endpoints for stock search
    fetchSparklines: builder.query<SparklineResponse, string>({
      query: (metaIds) => `/price/sparklines?meta_ids=${metaIds}`,
    }),
    fetchPriceHistory: builder.query<
      PriceHistoryResponse,
      { metaId: number; startDate?: string; endDate?: string }
    >({
      query: ({ metaId, startDate, endDate }) => {
        const params = new URLSearchParams();
        if (startDate) params.append("start_date", startDate);
        if (endDate) params.append("end_date", endDate);
        const queryString = params.toString();
        return `/price/${metaId}${queryString ? `?${queryString}` : ""}`;
      },
    }),
    fetchPriceSummary: builder.query<PriceSummaryResponse, number>({
      query: (metaId) => `/price/${metaId}/summary`,
    }),
    fetchCompareData: builder.query<CompareResponse, { metaIds: string; period?: string }>({
      query: ({ metaIds, period = "1y" }) =>
        `/price/compare?meta_ids=${metaIds}&period=${period}`,
    }),

    // News endpoints
    fetchNews: builder.query<NewsResponse, NewsQueryParams>({
      query: (params) => ({
        url: "/news",
        params: {
          category: params.category || "topnews",
          region: params.region || "all",
          limit: params.limit,  // Let backend decide default (10 for recent, 5 for others)
          search_query: params.search_query,
        },
      }),
      providesTags: ["News"],
    }),
    fetchNewsSources: builder.query<{ sources: NewsSource[] }, void>({
      query: () => "/news/sources",
    }),

    // Mutation endpoints
    runBacktest: builder.mutation<BacktestResult, BacktestPayload>({
      query: (payload) => ({
        url: "/backtest",
        method: "POST",
        body: payload,
      }),
    }),
    saveStrategy: builder.mutation<SaveStrategyResponse, BacktestPayload>({
      query: (payload) => ({
        url: "/backtest/savestrategy",
        method: "POST",
        body: payload,
      }),
      invalidatesTags: ["Strategy", "Portfolio"],
    }),
    clearStrategy: builder.mutation<ClearStrategyResponse, void>({
      query: () => ({
        url: "/backtest/clearstrategy",
        method: "POST",
      }),
    }),
  }),
});

export const {
  // Query hooks
  useFetchMetaDataQuery,
  useFetchTickersQuery,
  useFetchAlgorithmsQuery,
  useFetchStrategiesQuery,
  useFetchStrategyMonthlyNavQuery,
  useFetchStrategyByIdQuery,
  useFetchStNavByIdQuery,
  useFetchStRebalByIdQuery,
  useFetchBmByIdQuery,
  useFetchMacroInfoQuery,
  useFetchMacroDataQuery,
  // Price/Stock search hooks
  useFetchSparklinesQuery,
  useFetchPriceHistoryQuery,
  useFetchPriceSummaryQuery,
  useFetchCompareDataQuery,
  // News hooks
  useFetchNewsQuery,
  useLazyFetchNewsQuery,
  useFetchNewsSourcesQuery,
  // Mutation hooks
  useRunBacktestMutation,
  useSaveStrategyMutation,
  useClearStrategyMutation,
} = api;
