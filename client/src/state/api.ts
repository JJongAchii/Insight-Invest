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
  // News hooks
  useFetchNewsQuery,
  useLazyFetchNewsQuery,
  useFetchNewsSourcesQuery,
  // Mutation hooks
  useRunBacktestMutation,
  useSaveStrategyMutation,
  useClearStrategyMutation,
} = api;
