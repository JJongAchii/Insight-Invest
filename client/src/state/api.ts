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

export interface PriceSummaryFlows {
  /** 20-day cumulative foreign net buying, KRW. */
  frgn_net_20d: number;
  /** 20-day cumulative institution net buying, KRW. */
  inst_net_20d: number;
}

export interface PriceSummaryResponse {
  meta_id: number;
  ticker: string;
  name: string | null;
  metrics: StockMetrics;
  latest_price: number | null;
  latest_date: string | null;
  /** Latest daily traded value, KRW (KR only). */
  value: number | null;
  /** Market cap, KRW (KR only). */
  mktcap: number | null;
  per: number | null;
  pbr: number | null;
  /** Dividend yield, %. */
  div: number | null;
  flows_recent: PriceSummaryFlows | null;
}

export interface SparklineResponse {
  sparklines: Record<string, number[]>;
}

// Types for stock detail / watchlist operations
export interface StockDetailMeta {
  meta_id: number;
  ticker: string;
  name: string | null;
  sector: string | null;
  iso_code: string;
  security_type: string | null;
  marketcap: number | null;
}

export interface StockDetailResponse {
  meta: StockDetailMeta;
  summary: PriceSummaryResponse;
  in_watchlist: boolean;
}

export interface WatchlistItem {
  meta_id: number;
  ticker: string;
  name: string | null;
  iso_code: string;
  security_type: string | null;
  added_at: string | null;
  note: string | null;
  latest_price: number | null;
  chg_pct: number | null;
  frgn_net_20d: number | null;
  inst_net_20d: number | null;
}

export interface WatchlistResponse {
  items: WatchlistItem[];
}

export interface WatchlistMutationResponse {
  count: number;
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

// Types for backtest operations (API v2)
export type RebalFreq = "M" | "Q" | "Y";
export type BenchmarkName = "SPY" | "KOSPI" | "KOSDAQ" | "60_40";
export type BacktestCurrency = "USD" | "KRW";

export type BacktestParams =
  | { top_n?: number; lookback_months?: number }
  | { weights: Record<string, number> };

export interface BacktestPayload {
  strategy_name: string;
  meta_id: number[];
  algorithm: string | undefined;
  startDate: string;
  endDate: string;
  rebal_freq?: RebalFreq;
  cost_bps?: number;
  benchmark?: BenchmarkName;
  currency?: BacktestCurrency;
  params?: BacktestParams;
}

export interface FromWeightsPayload {
  strategy_name: string;
  weights: Record<string, number>;
  startDate: string;
  endDate: string;
  rebal_freq?: RebalFreq;
  cost_bps?: number;
  benchmark?: BenchmarkName;
  currency?: BacktestCurrency;
}

export interface NavPoint {
  date: string;
  value: number;
}

export interface WeightPoint {
  date: string;
  ticker: string;
  weight: number;
}

export interface MetricSet {
  ann_ret: number | null;
  ann_vol: number | null;
  sharpe: number | null;
  sortino: number | null;
  calmar: number | null;
  omega: number | null;
  mdd: number | null;
  skew: number | null;
  kurt: number | null;
  var: number | null;
  cvar: number | null;
}

export interface PeriodReturnPoint {
  label: string;
  strategy: number | null;
  benchmark: number | null;
}

export interface ContributionPoint {
  ticker: string;
  value: number;
}

export interface CrisisWindow {
  name: string;
  start: string;
  end: string;
  ret: number;
  mdd: number;
  recovery_days: number | null;
}

export interface BacktestAnalytics {
  /** Drawdown series in % (negative values). */
  drawdown: NavPoint[];
  rolling_sharpe: NavPoint[];
  /** Period returns in %. */
  yearly_returns: PeriodReturnPoint[];
  monthly_returns: PeriodReturnPoint[];
  /** Per-ticker contribution in %. */
  contribution: ContributionPoint[];
  crisis: CrisisWindow[];
}

export interface BacktestRunResult {
  result_token: string;
  strategy_name: string;
  nav: NavPoint[];
  benchmark: { name: string; nav: NavPoint[] };
  weights: WeightPoint[];
  metrics: {
    strategy: MetricSet;
    benchmark: Partial<MetricSet>;
  };
  analytics: BacktestAnalytics;
}

// 저장은 실행 응답의 result_token을 반드시 동반한다 (Lambda 컨테이너 간 상태 공유 불가)
export type SaveStrategyPayload = BacktestPayload & { result_token: string };

export interface SaveStrategyResponse {
  message: string;
}

// Types for regime operations
export type RegimePhaseName =
  | "Goldilocks"
  | "Reflation"
  | "Stagflation"
  | "Deflation";

export interface RegimePhaseCurrent {
  phase: RegimePhaseName;
  growth_dir: string;
  inflation_dir: string;
  as_of: string;
  cli: number;
  cli_delta: number;
  cpi_yoy: number;
  cpi_yoy_delta: number;
}

export interface RegimePhaseHistoryPoint {
  month: string; // "YYYY-MM"
  phase: RegimePhaseName;
  cli: number;
  cli_delta: number;
  cpi_yoy: number;
  cpi_yoy_delta: number;
}

export interface RegimePhaseResponse {
  current: RegimePhaseCurrent;
  history: RegimePhaseHistoryPoint[];
}

export interface RegimeGaugeComponent {
  name: string;
  value: number;
  percentile: number;
  score: number;
  weight: number;
}

export interface RegimeGaugeResponse {
  /** 0-100, higher = risk-off */
  score: number;
  as_of: string;
  components: RegimeGaugeComponent[];
}

export interface KrMacroPoint {
  date: string;
  value: number;
}

export interface KrMacroSeries {
  name: string;
  data: KrMacroPoint[];
  latest: number;
}

export type RegimeKrResponse = Record<string, KrMacroSeries | undefined>

export interface PhasePerformanceRow {
  ticker: string;
  mean_monthly_ret: number;
  ann_ret: number;
  hit_rate: number;
  n_months: number;
}

export interface RegimePhasePerformanceResponse {
  phases: Record<string, PhasePerformanceRow[]>;
  as_of: string;
}

// Types for optimization operations
export interface OptimizationPayload {
  meta_id: number[];
  start_date?: string;
  end_date?: string;
  lookback_period?: number;
  risk_free_rate?: number;
  min_weight?: number;
  max_weight?: number;
  n_points?: number;
}

export interface OptimizedPortfolio {
  weights: Record<string, number>;
  expected_return: number;
  volatility: number;
  sharpe_ratio: number;
  risk_contributions: Record<string, number>;
}

export interface FrontierPoint {
  return: number;
  volatility: number;
  sharpe_ratio: number;
  weights: Record<string, number>;
}

export interface AssetStats {
  expected_return: number;
  volatility: number;
}

export interface EfficientFrontierResponse {
  frontier_points: FrontierPoint[];
  max_sharpe: OptimizedPortfolio;
  min_volatility: OptimizedPortfolio;
  asset_stats: Record<string, AssetStats>;
}

// Types for correlation analysis
export interface CorrelationPayload {
  meta_id: number[];
  lookback_days?: number;
  /** [meta_id_a, meta_id_b] for the rolling correlation series. */
  rolling_pair?: number[];
}

export interface CorrelationRollingPoint {
  date: string;
  value: number;
}

export interface CorrelationRolling {
  pair: [string, string];
  series: CorrelationRollingPoint[];
}

export interface CorrelationResponse {
  tickers: string[];
  matrix: (number | null)[][];
  rolling: CorrelationRolling | null;
  as_of: string;
}

// Types for KR insight operations (수급·시장폭·신호)
export type InsightWindow = "1d" | "1w" | "1m";
export type InsightInvestor = "frgn" | "inst";
export type InsightMarket = "KOSPI" | "KOSDAQ";
export type InsightSignalType = "streak" | "intensity" | "divergence";

export interface InsightFlowTopRow {
  rank: number;
  ticker: string;
  name: string;
  market: string;
  /** Net traded value in KRW (display as 억 = /1e8). */
  net_value: number;
  net_volume: number;
  close: number;
  chg_pct: number;
  mktcap: number;
}

export interface InsightFlowsTopResponse {
  window: InsightWindow;
  investor: InsightInvestor;
  as_of: string;
  buys: InsightFlowTopRow[];
  sells: InsightFlowTopRow[];
}

export interface InsightMarketFlowRow {
  date: string;
  market: InsightMarket | "ALL";
  investor: InsightInvestor | "indiv";
  net_value: number;
}

export interface InsightFlowsMarketResponse {
  as_of: string;
  rows: InsightMarketFlowRow[];
}

export interface InsightTickerFlowRow {
  date: string;
  frgn_net: number;
  inst_net: number;
  indiv_net: number;
}

export interface InsightFlowsTickerResponse {
  ticker: string;
  as_of: string;
  rows: InsightTickerFlowRow[];
}

export interface InsightBreadthRow {
  date: string;
  advances: number;
  declines: number;
  unchanged: number;
  new_high_52w: number;
  new_low_52w: number;
  limit_up: number;
  limit_down: number;
  pct_above_ma20: number;
  total_value: number;
}

export interface InsightBreadthResponse {
  as_of: string;
  rows: InsightBreadthRow[];
}

export interface InsightSignalRow {
  ticker: string;
  name: string;
  market: string;
  close: number;
  chg_pct: number;
  mktcap: number;
  investor: InsightInvestor;
  /** Consecutive net-buy (+) / net-sell (−) days. */
  streak: number;
  net_1d: number;
  net_20d: number;
  /** 20d net value / mktcap, in %. */
  intensity_20d: number;
  ret_20d: number;
  divergence: "bull" | "bear" | null;
}

export interface InsightSignalsResponse {
  as_of: string;
  rows: InsightSignalRow[];
}

export type InsightSectorPeriod = "1d" | "1w" | "1m" | "3m" | "ytd";

export interface InsightSectorHeatmapRow {
  market: InsightMarket;
  sector: string;
  ret_1d: number | null;
  ret_1w: number | null;
  ret_1m: number | null;
  ret_3m: number | null;
  ret_ytd: number | null;
  n_stocks: number;
  /** Sector's share of market cap within its market (0–1). */
  mktcap_weight: number;
}

export interface InsightSectorHeatmapResponse {
  as_of: string;
  rows: InsightSectorHeatmapRow[];
}

export interface InsightSectorRotationRow {
  date: string;
  market: InsightMarket;
  sector: string;
  index_value: number;
}

export interface InsightSectorRotationResponse {
  as_of: string;
  rows: InsightSectorRotationRow[];
}

export interface InsightValuationRow {
  date: string;
  per: number | null;
  pbr: number | null;
  div: number | null;
}

export interface InsightValuationCurrent {
  per: number | null;
  pbr: number | null;
  div: number | null;
  /** Historical percentile rank, 0–100 (lower = cheaper). */
  pct_rank_per: number | null;
  pct_rank_pbr: number | null;
}

export interface InsightValuationResponse {
  as_of: string;
  rows: InsightValuationRow[];
  current: InsightValuationCurrent | null;
}

export interface InsightIndexRow {
  date: string;
  index: InsightMarket;
  close: number;
}

export interface InsightIndexResponse {
  rows: InsightIndexRow[];
}

export const api = createApi({
  reducerPath: "api",
  baseQuery: fetchBaseQuery({
    baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL,
    prepareHeaders: (headers) => {
      // Lambda Function URL 보호용 앱 토큰 (main.py 미들웨어와 쌍)
      const apiKey = process.env.NEXT_PUBLIC_API_KEY;
      if (apiKey) headers.set("X-API-Key", apiKey);
      return headers;
    },
  }),
  tagTypes: ["Strategy", "Portfolio", "News", "Watchlist"],
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
    fetchRegimePhase: builder.query<RegimePhaseResponse, void>({
      query: () => "/regime/phase",
    }),
    fetchRegimeGauge: builder.query<RegimeGaugeResponse, void>({
      query: () => "/regime/gauge",
    }),
    fetchRegimeKr: builder.query<RegimeKrResponse, void>({
      query: () => "/regime/kr",
    }),
    fetchRegimePhasePerformance: builder.query<
      RegimePhasePerformanceResponse,
      void
    >({
      query: () => "/regime/phase/performance",
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

    // Stock detail / watchlist endpoints
    fetchStockDetail: builder.query<StockDetailResponse, number>({
      query: (metaId) => `/stock/${metaId}`,
      // in_watchlist must refresh when the watchlist mutates
      providesTags: ["Watchlist"],
    }),
    fetchWatchlist: builder.query<WatchlistResponse, void>({
      query: () => "/watchlist",
      providesTags: ["Watchlist"],
    }),
    addToWatchlist: builder.mutation<
      WatchlistMutationResponse,
      { meta_id: number; note?: string }
    >({
      query: (body) => ({
        url: "/watchlist",
        method: "POST",
        body,
      }),
      invalidatesTags: ["Watchlist"],
    }),
    removeFromWatchlist: builder.mutation<WatchlistMutationResponse, number>({
      query: (metaId) => ({
        url: `/watchlist/${metaId}`,
        method: "DELETE",
      }),
      invalidatesTags: ["Watchlist"],
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

    // KR insight endpoints (수급·시장폭·신호)
    fetchInsightFlowsTop: builder.query<
      InsightFlowsTopResponse,
      { window: InsightWindow; investor: InsightInvestor }
    >({
      query: ({ window, investor }) =>
        `/insight/flows/top?window=${window}&investor=${investor}`,
    }),
    fetchInsightFlowsMarket: builder.query<
      InsightFlowsMarketResponse,
      { days?: number }
    >({
      query: ({ days = 365 }) => `/insight/flows/market?days=${days}`,
    }),
    fetchInsightFlowsTicker: builder.query<
      InsightFlowsTickerResponse,
      { ticker: string; months?: number }
    >({
      query: ({ ticker, months = 6 }) =>
        `/insight/flows/ticker/${ticker}?months=${months}`,
    }),
    fetchInsightBreadth: builder.query<
      InsightBreadthResponse,
      { days?: number; market: InsightMarket }
    >({
      query: ({ days = 365, market }) =>
        `/insight/breadth?days=${days}&market=${market}`,
    }),
    fetchInsightSignals: builder.query<
      InsightSignalsResponse,
      { type: InsightSignalType; investor: InsightInvestor }
    >({
      query: ({ type, investor }) =>
        `/insight/flows/signals?type=${type}&investor=${investor}`,
    }),
    fetchInsightIndex: builder.query<InsightIndexResponse, { days?: number }>({
      query: ({ days = 365 }) => `/insight/index?days=${days}`,
    }),
    fetchInsightSectorHeatmap: builder.query<InsightSectorHeatmapResponse, void>(
      {
        query: () => "/insight/sector/heatmap",
      }
    ),
    fetchInsightSectorRotation: builder.query<
      InsightSectorRotationResponse,
      { months?: number }
    >({
      query: ({ months = 12 }) => `/insight/sector/rotation?months=${months}`,
    }),
    fetchInsightValuation: builder.query<
      InsightValuationResponse,
      { market: InsightMarket }
    >({
      query: ({ market }) => `/insight/valuation?market=${market}`,
    }),

    // Mutation endpoints
    runBacktest: builder.mutation<BacktestRunResult, BacktestPayload>({
      query: (payload) => ({
        url: "/backtest",
        method: "POST",
        body: payload,
      }),
    }),
    runBacktestFromWeights: builder.mutation<BacktestRunResult, FromWeightsPayload>({
      query: (payload) => ({
        url: "/backtest/from-weights",
        method: "POST",
        body: payload,
      }),
    }),
    saveStrategy: builder.mutation<SaveStrategyResponse, SaveStrategyPayload>({
      query: (payload) => ({
        url: "/backtest/savestrategy",
        method: "POST",
        body: payload,
      }),
      invalidatesTags: ["Strategy", "Portfolio"],
    }),

    // Optimization endpoints
    calculateEfficientFrontier: builder.mutation<EfficientFrontierResponse, OptimizationPayload>({
      query: (payload) => ({
        url: "/optimization/efficient-frontier",
        method: "POST",
        body: payload,
      }),
    }),
    calculateRiskParity: builder.mutation<OptimizedPortfolio, OptimizationPayload>({
      query: (payload) => ({
        url: "/optimization/risk-parity",
        method: "POST",
        body: payload,
      }),
    }),
    calculateCorrelation: builder.mutation<CorrelationResponse, CorrelationPayload>({
      query: (payload) => ({
        url: "/optimization/correlation",
        method: "POST",
        body: payload,
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
  useFetchRegimePhaseQuery,
  useFetchRegimeGaugeQuery,
  useFetchRegimeKrQuery,
  useFetchRegimePhasePerformanceQuery,
  // Price/Stock search hooks
  useFetchSparklinesQuery,
  useFetchPriceHistoryQuery,
  useFetchPriceSummaryQuery,
  useFetchCompareDataQuery,
  // Stock detail / watchlist hooks
  useFetchStockDetailQuery,
  useFetchWatchlistQuery,
  useAddToWatchlistMutation,
  useRemoveFromWatchlistMutation,
  // News hooks
  useFetchNewsQuery,
  // KR insight hooks
  useFetchInsightFlowsTopQuery,
  useFetchInsightFlowsMarketQuery,
  useFetchInsightFlowsTickerQuery,
  useFetchInsightBreadthQuery,
  useFetchInsightSignalsQuery,
  useFetchInsightIndexQuery,
  useFetchInsightSectorHeatmapQuery,
  useFetchInsightSectorRotationQuery,
  useFetchInsightValuationQuery,
  // Mutation hooks
  useRunBacktestMutation,
  useRunBacktestFromWeightsMutation,
  useSaveStrategyMutation,
  // Optimization hooks
  useCalculateEfficientFrontierMutation,
  useCalculateRiskParityMutation,
  useCalculateCorrelationMutation,
} = api;
