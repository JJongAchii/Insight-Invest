import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";

export const api = createApi({
  reducerPath: "api",
  baseQuery: fetchBaseQuery({ baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL }),
  tagTypes: [], // You can define tags here for caching and invalidation
  endpoints: (builder) => ({
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
    }),
    fetchStrategyNav: builder.query({
      query: () => "/backtest/strategy/nav",
    }),
  }),
});

export const { 
  useFetchMetaDataQuery, 
  useFetchTickersQuery, 
  useFetchAlgorithmsQuery, 
  useFetchStrategiesQuery,
  useFetchStrategyNavQuery,
} = api;
