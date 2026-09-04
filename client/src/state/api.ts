import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";

// Types for news operations
export type NewsCategory =
  | "topnews"  // Top news headlines (default)
  | "economy"  // World economy, macro
  | "policy"   // Central bank, Fed, interest rates
  | "trade"    // International trade, tariffs
  | "energy"   // Oil, gas, energy markets
  | "tech";    // Tech industry news

export type NewsRegion = "us" | "asia" | "europe" | "global" | "all" | "kr";

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

export interface NewsBriefingItem {
  title: string;
  url: string;
  source: string;
  published_at: string | null;
  cluster_count: number;
  sources: string[];
  why?: string;
  related_assets?: {
    meta_id: number;
    ticker: string;
    name: string;
    relation: "보유" | "관심";
  }[];
  related_topics?: string[];
}

export interface NewsBriefingResponse {
  active: boolean;
  as_of?: string;
  edition?: "morning" | "evening";
  curated?: boolean;
  sections?: { general: NewsBriefingItem[]; economy: NewsBriefingItem[] };
  relevance_method?: string;
  relevance_warning?: string;
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
  /** Canonical series value for display; use this instead of the compatibility adj_close alias. */
  value?: number | null;
  adj_close: number | null;
  gross_return: number | null;
}

export interface PriceSeriesContract {
  series_type: "raw_close" | "split_adjusted_price" | "krx_reference_price_adjusted" | "total_return_index";
  label: "Raw Price" | "Adjusted Price" | "KRX Adjusted Price" | "Total Return";
  return_basis: string;
  capital_actions: string;
  cash_distributions: "included" | "excluded" | "implicit_in_reference_price";
  calculation_version: string;
  warning: string | null;
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
  series_contract?: PriceSeriesContract;
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
  series_contract?: PriceSeriesContract;
  valuation?: {
    status: "ok" | "unavailable" | "not_applicable";
    as_of: string | null;
    price_as_of: string | null;
    fundamental_as_of: string | null;
    source: string;
    calculation_version: string;
    per_status: string;
    pbr_status: string;
    dividend_yield_status: string;
    missing_reasons: string[];
    inputs: Record<string, number | null> | null;
    checks: Record<string, number | null> | null;
  } | null;
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
  security_subtype?: string | null;
  marketcap: number | null;
  marketcap_source?: string | null;
  marketcap_as_of?: string | null;
  shares_outstanding?: number | null;
  weighted_shares_outstanding?: number | null;
  fund_size?: number | null;
  fund_size_source?: string | null;
  fund_size_as_of?: string | null;
  reference_as_of?: string | null;
}

/** Current holding attached to a stock detail response (null when not held). */
export interface StockHolding {
  shares: number;
  avg_cost: number;
  currency: string;
  latest_price?: number | null;
  market_value_native?: number;
  cost_value_native?: number;
  unrealized_pnl_native?: number;
  /** Fraction, e.g. 0.12 = +12%. */
  unrealized_pnl_pct?: number | null;
}

export interface StockDetailResponse {
  meta: StockDetailMeta;
  summary: PriceSummaryResponse;
  in_watchlist: boolean;
  /** Current position for this stock, or null when not held. */
  holding: StockHolding | null;
}

export interface StockFundamentalFact {
  key: "revenue" | "net_income" | "assets" | "equity" | "operating_cash_flow";
  value: number;
  yoy_pct: number | null;
  period: string;
  filed: string;
  unit: string;
  tag: string;
}

export interface StockFundamentalsResponse {
  available: boolean;
  ticker?: string;
  cik?: number;
  as_of?: string;
  facts?: StockFundamentalFact[];
  note: string;
}

export interface WatchlistItem {
  meta_id: number;
  ticker: string;
  name: string | null;
  iso_code: string;
  security_type: string | null;
  added_at: string | null;
  note: string | null;
  thesis: string | null;
  catalyst: string | null;
  invalidation: string | null;
  review_date: string | null;
  latest_price: number | null;
  previous_price: number | null;
  chg_pct: number | null;
  price_as_of: string | null;
  frgn_net_20d: number | null;
  inst_net_20d: number | null;
  alerts_enabled: boolean;
  alert_price_above: number | null;
  alert_price_below: number | null;
  alert_change_pct: number | null;
}

export interface WatchlistResponse {
  items: WatchlistItem[];
}

export interface WatchlistMutationResponse {
  count: number;
}

export interface UpdateWatchlistPayload {
  meta_id: number;
  note?: string;
  thesis?: string;
  catalyst?: string;
  invalidation?: string;
  review_date?: string | null;
  alerts_enabled?: boolean;
  alert_price_above?: number | null;
  alert_price_below?: number | null;
  alert_change_pct?: number | null;
}

// Types for holdings (real positions) operations
export interface HoldingPosition {
  meta_id: number;
  ticker: string;
  name: string | null;
  iso_code: string;
  security_type: string | null;
  sector: string | null;
  shares: number;
  avg_cost: number;
  currency: string;
  latest_price: number | null;
  /** Day change, %. */
  day_chg_pct: number | null;
  market_value_native: number | null;
  cost_value_native: number;
  unrealized_pnl_native: number | null;
  /** Fraction, e.g. 0.12 = +12%. */
  unrealized_pnl_pct: number | null;
  market_value_krw: number | null;
  /** Fraction of total portfolio value (0..1). */
  weight: number | null;
  /** Optional target within invested assets, fraction (0..1). */
  target_weight: number | null;
  /** Actual minus target, percentage points. */
  drift_pp: number | null;
  thesis: string;
  invalidation: string;
  review_date: string | null;
}

export interface HoldingsSectorAlloc {
  sector: string;
  /** Fraction (0..1). */
  weight: number;
}

export interface HoldingsMarketAlloc {
  label: string;
  /** Fraction (0..1). */
  weight: number;
}

export interface HoldingsSummary {
  total_value_krw: number;
  total_cost_krw: number;
  total_pnl_krw: number;
  /** Fraction, e.g. 0.12 = +12%. */
  total_pnl_pct: number | null;
  day_pnl_krw: number;
  n_positions: number;
  priced_positions: number;
  unpriced_positions: number;
  valuation_complete: boolean;
  sector_alloc: HoldingsSectorAlloc[];
  market_alloc: HoldingsMarketAlloc[];
  asset_alloc: HoldingsMarketAlloc[];
  /** Largest single-position weight, fraction (0..1). */
  top_weight: number | null;
  /** Sum of the three largest priced positions, fraction (0..1). */
  top3_weight: number | null;
  /** Herfindahl index Σ(weight²), 0..1. */
  hhi: number | null;
  /** 1 / HHI; equally weighted equivalent number of positions. */
  effective_positions: number | null;
  /** Sum of configured target weights; null when no targets are set. */
  target_total: number | null;
}

export interface HoldingsResponse {
  positions: HoldingPosition[];
  summary: HoldingsSummary;
}

export type LedgerEventType = "BUY" | "SELL" | "DEPOSIT" | "WITHDRAW" | "DIVIDEND" | "FEE" | "FX";

export interface LedgerEvent {
  event_id: string;
  occurred_at: string;
  created_at: string;
  event_type: LedgerEventType;
  meta_id: number | null;
  ticker: string | null;
  name: string | null;
  shares: number | null;
  price: number | null;
  currency: "KRW" | "USD";
  amount: number | null;
  fees: number;
  counter_currency: "KRW" | "USD" | null;
  counter_amount: number | null;
  realized_pnl_native: number | null;
  note: string;
}

export interface LedgerSummary {
  events_count: number;
  started_at: string | null;
  cash_balances: Record<string, number>;
  cash_value_krw: number | null;
  realized_pnl: Record<string, number>;
  opening_positions: number;
  twr: number | null;
  twr_as_of: string | null;
  twr_periods: number;
  twr_note: string;
  cost_basis: string;
}

export interface PortfolioLedgerResponse {
  events: LedgerEvent[];
  summary: LedgerSummary;
}

export interface AddLedgerEventPayload {
  idempotency_key: string;
  event_type: LedgerEventType;
  occurred_at: string;
  meta_id?: number;
  shares?: number;
  price?: number;
  currency: "KRW" | "USD";
  amount?: number;
  fees?: number;
  counter_currency?: "KRW" | "USD";
  counter_amount?: number;
  note?: string;
  thesis?: string;
  invalidation?: string;
  review_date?: string;
}

export interface AddHoldingPayload {
  meta_id: number;
  shares: number;
  avg_cost: number;
  currency?: string;
  note?: string;
  target_weight?: number | null;
  thesis?: string;
  invalidation?: string;
  review_date?: string | null;
}

export interface UpdateHoldingMetadataPayload {
  meta_id: number;
  note?: string;
  target_weight?: number | null;
  thesis: string;
  invalidation: string;
  review_date?: string | null;
}

export interface HoldingMutationResponse {
  n_positions: number;
}

// Types for the portfolio risk card (GET /holdings/risk)
export interface RiskScenario {
  key: string;
  label: string;
  ret_pct: number | null;
  start: string | null;
  end: string | null;
  note: string | null;
}

export interface RiskWarning {
  kind: string;
  ticker: string | null;
  detail: string;
}

export interface RiskCorr {
  tickers: string[];
  names: string[];
  values: (number | null)[][];
}

export interface RiskContribution {
  ticker: string;
  name: string;
  /** Current portfolio weight, fraction. */
  weight: number;
  /** Standalone annualized volatility, %. */
  asset_ann_vol: number;
  /** Component variance divided by portfolio variance, fraction. */
  risk_share: number;
  /** Contribution to annualized portfolio volatility, percentage points. */
  risk_contribution_pct: number;
}

export interface HoldingsRiskResponse {
  empty?: boolean;
  reason?: string;
  insufficient?: boolean;
  overlap_days?: number;
  ann_vol?: number | null;
  max_drawdown?: number | null;
  mdd_from?: string;
  mdd_to?: string;
  avg_pair_corr?: number | null;
  diversification_ratio?: number | null;
  risk_contributions?: RiskContribution[];
  corr?: RiskCorr | null;
  scenarios?: RiskScenario[];
  warnings?: RiskWarning[];
  coverage?: {
    n_assets: number;
    total_assets: number;
    weight: number;
  };
  basis?: {
    n_assets: number;
    total_assets: number;
    coverage_weight: number;
    weights_as_of: string;
    overlap_days: number;
    window: { start: string; end: string };
    return_basis: "split_adjusted_price_return_ex_cash_distributions_krw";
  };
}

// Types for the home decision overview (GET /overview)
export type OverviewTone = "risk_on" | "risk_off" | "mixed";
export type EvidenceTone = "positive" | "negative" | "neutral";
export type DataHealthLevel = "ok" | "warn" | "error" | "unknown";

export interface OverviewEvidence {
  key: string;
  tone: EvidenceTone;
  title: string;
  detail: string;
  as_of: string | null;
  link: string;
  changed: boolean;
}

export interface DataHealthItem {
  dataset: string;
  label: string;
  level: DataHealthLevel;
  as_of: string | null;
  age_days: number | null;
  market_sessions_old: number | null;
  detail: string;
  built_at: string | null;
  row_count: number | null;
  message: string | null;
  build_version: string | null;
  expected_lag_sessions: number;
}

export interface CalculationContract {
  key: string;
  label: string;
  version: string;
  basis: string;
  execution: string | null;
  coverage: string;
  detail: string;
}

export interface OverviewHorizon {
  key: "intraday" | "tactical" | "structural";
  label: string;
  window: string;
  tone: EvidenceTone;
  summary: string;
  evidence: OverviewEvidence[];
}

export interface OverviewResponse {
  generated_at: string;
  tone: OverviewTone;
  tone_label: string;
  horizons: OverviewHorizon[];
  evidence: OverviewEvidence[];
  conflicts: string[];
  data_status: DataHealthItem[];
  calculation_contracts: CalculationContract[];
  method: string;
}

export type DecisionHorizon = "intraday" | "tactical" | "structural";

export interface JournalEntry {
  entry_id: string;
  created_at: string;
  observation: string;
  interpretation: string;
  decision: string;
  horizon: DecisionHorizon;
  confidence: number;
  counter_evidence: string;
  invalidation: string;
  review_date: string;
  evidence_snapshot: Partial<OverviewResponse> & { source_event?: Partial<ActionItem> };
  reviewed_at: string | null;
  outcome: string | null;
  lesson: string | null;
}

export interface JournalResponse {
  items: JournalEntry[];
  count: number;
}

export interface CreateJournalPayload {
  observation: string;
  interpretation: string;
  decision: string;
  horizon: DecisionHorizon;
  confidence: number;
  counter_evidence?: string;
  invalidation?: string;
  review_date: string;
  source_event_id?: string;
  source_event?: Partial<ActionItem>;
}

// Types for the "오늘 주목" attention lane
export type AttentionSeverity = "high" | "medium" | "low";

export interface AttentionItem {
  severity: AttentionSeverity;
  category: string;
  ticker?: string;
  name?: string;
  meta_id?: number;
  title: string;
  detail: string;
  link: string;
}

export interface AttentionResponse {
  as_of: string;
  items: AttentionItem[];
}

export type ActionState = "new" | "read" | "snoozed" | "dismissed";
export type ActionKind = "attention" | "alert" | "review" | "rebalance" | "data" | "system" | "event";

export interface ActionItem {
  event_id: string;
  kind: ActionKind;
  category: string;
  severity: AttentionSeverity;
  title: string;
  detail: string;
  link: string;
  meta_id: number | null;
  ticker: string | null;
  name: string | null;
  market: string | null;
  scope: "market" | "portfolio" | "watchlist" | null;
  event_status: "confirmed" | "projected" | "observed" | null;
  occurred_at: string | null;
  available_at: string;
  data_as_of: string | null;
  scheduled_for: string | null;
  source: string;
  actions: string[];
  state: ActionState;
  snoozed_until: string | null;
}

export interface ExternalEventSource {
  provider: string;
  label: string;
  status: "ok" | "preserved" | "configuration_required" | "upgrade_required" | "unavailable";
  data_as_of: string | null;
  available_at: string;
  coverage: string | null;
  message: string | null;
}

export interface ActionCenterResponse {
  generated_at: string;
  data_as_of: string | null;
  items: ActionItem[];
  calendar: ActionItem[];
  sources: ExternalEventSource[];
  counts: {
    total: number;
    actionable: number;
    high: number;
    new: number;
    badge: number;
    scheduled: number;
    external: number;
  };
}

export type ResearchEvidenceDimension = "method" | "data" | "validation" | "result";

export interface ResearchEntry {
  entry_id: string;
  source_id: string;
  source_name: string;
  title: string;
  summary: string;
  authors: string[];
  url: string;
  published_at: string;
  discovered_at: string;
  record_schema_version: 1 | 2 | 3;
  quality_profile: string;
  research_lane: "core" | "discovery" | "context";
  relevance_reason: string;
  relevance_terms: string[];
  notification_eligible: boolean;
  item_type?: "evidence_update";
  content_provenance?: "release_detail" | "full_body";
  evidence_dimensions?: ResearchEvidenceDimension[];
  evidence_excerpts?: Partial<Record<ResearchEvidenceDimension, string[]>>;
  source_digest?: string;
  resolution_status?:
    | "maintainer_published"
    | "maintainer_confirmed"
    | "commit_linked"
    | "unresolved";
  quality_gates?: Record<"transport" | "content" | "topic" | "evidence" | "notification", boolean>;
  is_read: boolean;
  is_saved: boolean;
}

export interface ResearchSource {
  source_id: string;
  source_name: string;
  count: number;
}

export interface ResearchFeedResponse {
  schema_version: 1;
  generated_at: string | null;
  total: number;
  unread: number;
  read: number;
  saved: number;
  view: ResearchView;
  lane: ResearchLane;
  lane_counts: Record<"core" | "discovery" | "context" | "all", number>;
  query: string;
  offset: number;
  limit: number;
  sources: ResearchSource[];
  items: ResearchEntry[];
}

export interface ResearchStatusResponse {
  schema_version: 1;
  initialized: boolean;
  unseen: number;
  generated_at: string | null;
  seen_through: string | null;
}

export type ResearchView = "all" | "unread" | "read" | "saved";
export type ResearchLane = "core" | "discovery" | "all";

export interface ResearchFeedParams {
  sourceId?: string;
  view?: ResearchView;
  lane?: ResearchLane;
  query?: string;
  entryId?: string;
  offset?: number;
  limit?: number;
}

export type EarningsScope = "all" | "mine" | "portfolio" | "watchlist" | "leaders";
export type EarningsResultSignal = "beat" | "miss" | "mixed" | "in_line" | null;
export type EarningsDisplayStatus =
  | "upcoming"
  | "awaiting_results"
  | "result_unavailable"
  | "reported";

export interface EarningsEvent {
  event_id: string;
  identity_quality: "fiscal_period" | "release_date";
  meta_id: number;
  ticker: string;
  name: string | null;
  cik: string | null;
  scope: "market" | "portfolio" | "watchlist";
  is_market_leader: boolean;
  marketcap_rank: number;
  fiscal_year: number | null;
  fiscal_quarter: number | null;
  release_date: string;
  release_timing: "bmo" | "amc" | "dmh" | "tbd" | string;
  schedule_status: "estimated";
  lifecycle: "scheduled" | "reported";
  eps_actual: number | null;
  eps_estimate: number | null;
  eps_surprise_pct: number | null;
  revenue_actual: number | null;
  revenue_estimate: number | null;
  revenue_surprise_pct: number | null;
  result_signal: EarningsResultSignal;
  official_result_status: "filed" | null;
  official_result_source: "sec" | null;
  official_result_form: string | null;
  official_result_url: string | null;
  official_result_filed_at: string | null;
  official_result_detected_at: string | null;
  official_actual_status?: "extracted" | "not_found" | "ambiguous" | "unsupported" | "fetch_failed" | null;
  official_actual_url?: string | null;
  official_actual_extracted_at?: string | null;
  official_eps_gaap_actual?: number | null;
  official_eps_adjusted_actual?: number | null;
  official_revenue_actual?: number | null;
  eps_actual_source?: "finnhub" | "sec" | null;
  eps_actual_basis?: "provider_standardized" | "non_gaap_diluted" | "gaap_diluted" | null;
  revenue_actual_source?: "finnhub" | "sec" | null;
  actual_reconciliation_status?: "standardized" | "official_only" | "matched" | "differs" | null;
  source: "finnhub";
  source_url: string | null;
  stock_link: string;
  call_time: string | null;
  webcast_url: string | null;
  transcript_status: "not_available" | "available";
  release_window_at: string;
  display_status: EarningsDisplayStatus;
  first_seen_at: string;
  available_at: string;
  data_as_of: string;
  universe_as_of: string;
}

export interface EarningsRevision {
  revision_id: string;
  event_id: string;
  ticker: string;
  fiscal_year: number | null;
  fiscal_quarter: number | null;
  previous_release_date: string;
  release_date: string;
  observed_at: string;
  source: string;
}

export interface EarningsResponse {
  generated_at: string;
  data_as_of: string | null;
  scope: EarningsScope;
  query: string;
  summary: {
    this_week: number;
    upcoming: number;
    awaiting_results: number;
    official_results_available: number;
    reported_recently: number;
    my_coverage: number;
  };
  coverage: {
    universe_total: number;
    market_leaders?: number;
    filtered_universe: number;
    events_total: number;
    filtered_events: number;
    invalid_release_dates?: number;
    history_start: string | null;
    forward_days?: number;
    results_days?: number;
  };
  upcoming: EarningsEvent[];
  pending_results: EarningsEvent[];
  recent_results: EarningsEvent[];
  revisions: EarningsRevision[];
  source: {
    provider: string;
    label?: string;
    status: "ok" | "preserved" | "configuration_required" | "unavailable";
    freshness?: "ready" | "stale" | "attention";
    expected_as_of?: string | null;
    age_sessions?: number | null;
    data_as_of?: string | null;
    available_at?: string;
    message?: string | null;
    universe_total?: number;
    market_leaders?: number;
    tracked_us?: number;
    matched_tracked_us?: number;
    reference_match_pct?: number;
    cik_coverage_pct?: number;
  } | null;
}

export interface NotificationConfigResponse {
  enabled: boolean;
  public_key: string | null;
  subscriptions: number;
}

export interface PushSubscriptionPayload {
  endpoint: string;
  keys: { p256dh: string; auth: string };
  user_agent: string;
}

// Types for the "오늘의 신호 종목" market spotlight lane
export interface SpotlightItem {
  ticker: string;
  name: string;
  market: string;
  close: number | null;
  chg_pct: number | null;
  streak: number | null;
  intensity_20d: number | null;
  ret_20d: number | null;
  hold_days: number | null;
  dist_pct: number | null;
  also_in: string[];
  meta_id: number | null;
  link: string | null;
  mine: "holding" | "watchlist" | null;
}

export interface SpotlightGroup {
  signal_type: string;
  title: string;
  evidence: string | null;
  items: SpotlightItem[];
}

export interface SpotlightResponse {
  as_of: string | null;
  groups: SpotlightGroup[];
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

export interface PriceCoverageAsset {
  meta_id: number;
  ticker: string | null;
  iso_code: string | null;
  start: string | null;
  end: string | null;
  rows: number;
}

export interface PriceCoverageResponse {
  assets: PriceCoverageAsset[];
  effective_start: string | null;
  effective_end: string | null;
  complete: boolean;
  price_field: "adj_close";
  note: string;
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
  signal_date?: string | null;
  execution_date?: string;
  execution_price?: "close";
  ticker: string;
  weight: number;
}

export interface BacktestCalculationContract {
  calculation_version: string;
  return_basis: string;
  signal_rule: string;
  execution_rule: string;
  execution_price: "close";
  cash_distributions: "included" | "not_exactly_included";
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
  calculation_contract?: BacktestCalculationContract;
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

/** 실전 추적(라이브) 응답 — 저장일 이후 out-of-sample NAV와 지표. */
export interface StrategyLiveResponse {
  port_id: number;
  /** 전략 저장일 (YYYY-MM-DD). 추적 미시작이면 null. */
  saved_at: string | null;
  /** 라이브 지표 계산 기준일. */
  as_of: string | null;
  /** 저장일 ~1000 기준 NAV. 추적 데이터가 없으면 []. */
  nav: NavPoint[];
  metrics_live: Partial<MetricSet>;
  metrics_backtest: Partial<MetricSet>;
  weights?: LiveWeightRow[] | null;
  expectation?: LiveExpectation | null;
  /** 저장 후 구간 벤치마크(SPY) — 라이브 nav 와 같은 규약(첫 관측=1000). 실패 시 null. */
  bm_live?: { name: string; nav: NavPoint[]; metrics?: Partial<MetricSet> } | null;
}

// Types for analytics operations (Phase 1)
export interface AnalyticsPremise {
  algorithm: string | null;
  rebal_freq: string | null;
  cost_bps: number | null;
  currency: string | null;
  return_basis?: string | null;
  execution_rule?: string | null;
  calculation_version?: string | null;
  universe_n: number;
  saved_at: string | null;
  bt_start: string;
  bt_end: string;
  bt_days: number;
  n_rebals: number | null;
  cost_warning: boolean;
}

export interface AnalyticsRollingRow {
  date: string;
  roll_ret: number;
  roll_sharpe: number;
}

export interface AnalyticsRolling {
  window: number;
  rows: AnalyticsRollingRow[];
  bm_rows: AnalyticsRollingRow[] | null;
}

export interface DrawdownEpisode {
  depth_pct: number;
  peak: string;
  trough: string;
  recover: string | null;
  days_to_recover: number | null;
}

export interface AnalyticsDrawdowns {
  underwater: { date: string; dd_pct: number }[];
  episodes: DrawdownEpisode[];
}

export interface AnalyticsPhaseRow {
  phase: string;
  mean_ret_pct: number;
  n_months: number;
  bm_mean_ret_pct: number | null;
}

export interface AnalyticsCrisisRow {
  key: string;
  ret_pct: number | null;
  note: string | null;
}

export interface AnalyticsMonthly {
  win_rate: number | null;
  win_rate_vs_bm: number | null;
  best: { month: string; ret_pct: number }[];
  worst: { month: string; ret_pct: number }[];
}

export interface AnalyticsTrading {
  n_rebals: number;
  rebals_per_year: number | null;
  avg_turnover: number | null;
  cost_drag_pct_10bps: number | null;
  cost_drag_pct_30bps: number | null;
}

export interface StrategyAnalyticsResponse {
  empty?: boolean;
  premise?: AnalyticsPremise | null;
  rolling?: AnalyticsRolling | null;
  drawdowns?: AnalyticsDrawdowns | null;
  phases?: { rows: AnalyticsPhaseRow[] } | null;
  crisis?: AnalyticsCrisisRow[];
  monthly?: AnalyticsMonthly | null;
  trading?: AnalyticsTrading | null;
  notes?: Record<string, string>;
  as_of?: string | null;
}

export interface LiveExpectation {
  n_days: number;
  live_ret_pct: number;
  ret_percentile: number;
  live_dd_pct: number;
  dd_percentile: number;
}

export interface LiveWeightRow {
  trade_date: string;
  ticker: string;
  weight: number;
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
  methodology?: {
    release_lag: string;
    vintage: "latest";
    warning: string;
  };
}

export interface RegimeGaugeComponent {
  name: string;
  value: number;
  value_label?: string;
  unit?: string;
  signal?: string;
  signal_value?: number;
  percentile: number;
  score: number;
  weight: number;
  /** Latest observation used by this component. */
  as_of: string;
}

export interface RegimeGaugeResponse {
  /** 0-100, higher = risk-off */
  score: number;
  as_of: string;
  complete_as_of?: string;
  calculated_at?: string;
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
  n_stocks: number | null;
  fundamental_name_coverage_pct: number | null;
  fundamental_mktcap_coverage_pct: number | null;
  per_name_coverage_pct: number | null;
  per_mktcap_coverage_pct: number | null;
  pbr_name_coverage_pct: number | null;
  pbr_mktcap_coverage_pct: number | null;
  earnings_name_coverage_pct: number | null;
  earnings_mktcap_coverage_pct: number | null;
  non_positive_eps_name_pct: number | null;
  aggregate_earnings_yield_pct: number | null;
}

export interface InsightValuationResponse {
  as_of: string;
  rows: InsightValuationRow[];
  current: InsightValuationCurrent | null;
  calculation_version: string | null;
  percentile_scope: string | null;
}

export interface InsightIndexRow {
  date: string;
  index: InsightMarket;
  close: number;
}

export interface InsightIndexResponse {
  rows: InsightIndexRow[];
}

// Types for signal event-study, factor lens & factor exposure (Track B)
export type SignalStudyType =
  /** 조건 없는 유동성 전 종목-일 — 다른 모든 행의 비교 기준. */
  | "baseline"
  | "bull_divergence"
  | "frgn_streak10"
  | "high_intensity"
  | "spike_1d_5"
  | "spike_1d_5_10"
  | "spike_1d_10"
  | "drop_1d_5"
  | "spike_5d_15"
  | "spike_20d_20"
  | "spike_20d_50"
  | "near_52w_high_entry"
  | "near_52w_high_hold";

export interface SignalStudyRow {
  signal_type: SignalStudyType;
  horizon: 5 | 20 | 60;
  /**
   * 이벤트 수. 신호 간 비교 불가 — 상태형 신호에만 20일 쿨다운이 걸리고
   * 1일 급등/급락과 baseline에는 걸리지 않는다.
   */
  n_events: number;
  /** Mean forward excess return vs equal-weight cross-sectional mean, %. */
  mean_excess: number;
  /**
   * Median forward excess return vs equal-weight cross-sectional mean, %.
   * 벤치마크가 평균이고 수익률 분포가 우편향이라 baseline조차 음수다 —
   * 절대값이 아니라 baseline 행과의 차이로만 판정할 것.
   */
  median_excess: number;
  /** Share of events with positive excess return, %. */
  hit_rate: number;
  /** Mean absolute forward return, %. */
  avg_fwd_ret: number;
}

export interface SignalStudyResponse {
  as_of: string | null;
  rows: SignalStudyRow[];
  return_basis: string | null;
  execution_rule: string | null;
  calculation_version: string | null;
  status?: "rebuild_required_or_unavailable";
}

export type FactorName = "momentum" | "value" | "size" | "lowvol";

export interface FactorCurrentRow {
  factor: FactorName;
  /** Long-short factor spread returns, %. */
  ret_1d: number;
  ret_1w: number;
  ret_1m: number;
  ret_ytd: number;
}

export interface FactorHistoryPoint {
  date: string;
  factor: FactorName;
  /** Cumulative factor-spread index (rebased client-side). */
  cum_index: number;
}

export interface FactorLensResponse {
  as_of: string | null;
  current: FactorCurrentRow[];
  history: FactorHistoryPoint[];
  return_basis: string | null;
  execution_rule: string | null;
  calculation_version: string | null;
  status?: "rebuild_required_or_unavailable";
}

export interface FactorExposureRow {
  factor: FactorName;
  /** Portfolio factor score as a 0–100 percentile of the universe. */
  percentile: number;
}

export interface FactorExposureResponse {
  as_of: string;
  exposures: FactorExposureRow[];
  /** One-line human tilt summary, e.g. "소형·저변동 쏠림". */
  tilt: string;
  /** Present when the request was partially/fully skipped (e.g. US-only). */
  note?: string;
}

// Types for rebalancing signals (Task 5)
export interface RebalSignalItem {
  ticker: string;
  name: string;
  target_weight: number;
  prev_weight: number;
  action: "enter" | "exit" | "keep";
  rank: number | null;
}

export interface RebalSignal {
  port_id: number;
  port_name: string;
  freq: string;
  next_rebal: string;
  is_stale: boolean;
  items: RebalSignalItem[];
}

export interface RebalSignalsResponse {
  as_of: string | null;
  signals: RebalSignal[];
}

// Types for KR intraday market operations (Task 4)
export interface IntradayStockRow {
  ticker: string;
  name: string;
  /** null when the server's non-finite guard (`_r()`) drops a bad value. */
  close: number | null;
  /** null when the server's non-finite guard (`_r()`) drops a bad value. */
  chg_pct: number | null;
  /** Present (possibly null) on top_value/top_movers rows; absent on my.* rows. */
  value?: number | null;
  /** Present only on my.* rows. */
  meta_id?: number;
}

export interface IntradaySectorRow {
  name: string;
  chg_pct: number;
  value_krw: number;
  n: number;
  flow: { t: string; chg_pct: number }[];
}

export interface IntradayMarketResponse {
  active: boolean;
  is_open?: boolean;
  as_of?: string;
  trade_date?: string;
  indices?: {
    key: string;
    level: number;
    chg_pct: number | null;
    sparkline: { t: string; level: number }[];
  }[];
  breadth?: { advancers: number; decliners: number; unchanged: number };
  sectors?: IntradaySectorRow[];
  top_value?: IntradayStockRow[];
  top_movers?: { up: IntradayStockRow[]; down: IntradayStockRow[] };
  my?: { watchlist: IntradayStockRow[]; holdings: IntradayStockRow[] };
}

export const api = createApi({
  reducerPath: "api",
  baseQuery: fetchBaseQuery({
    // 브라우저는 같은 출처의 Next.js 프록시만 호출한다. Lambda URL과 API 키는
    // 서버 Route Handler 안에 남아 클라이언트 번들·네트워크 패널에 노출되지 않는다.
    baseUrl: "/api/backend/",
  }),
  tagTypes: [
    "Strategy",
    "Portfolio",
    "News",
    "Watchlist",
    "Holdings",
    "Attention",
    "Actions",
    "Journal",
    "Notifications",
    "Research",
    "ResearchStatus",
    "Earnings",
    "PortfolioLedger",
  ],
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
    fetchPriceCoverage: builder.query<PriceCoverageResponse, number[]>({
      query: (metaIds) => `/price/coverage?meta_ids=${metaIds.join(",")}`,
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
    fetchStrategyLiveById: builder.query<StrategyLiveResponse, number>({
      query: (port_id) => `backtest/strategy/live/${port_id}`,
      providesTags: ["Portfolio"],
    }),
    fetchStrategyAnalytics: builder.query<StrategyAnalyticsResponse, number>({
      query: (portId) => `/backtest/strategy/analytics/${portId}`,
      providesTags: ["Portfolio"],
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
      // in_watchlist / holding must refresh when either mutates
      providesTags: ["Watchlist", "Holdings"],
    }),
    fetchStockFundamentals: builder.query<StockFundamentalsResponse, number>({
      query: (metaId) => `/stock/${metaId}/fundamentals`,
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
      invalidatesTags: ["Watchlist", "Attention", "Actions"],
    }),
    removeFromWatchlist: builder.mutation<WatchlistMutationResponse, number>({
      query: (metaId) => ({
        url: `/watchlist/${metaId}`,
        method: "DELETE",
      }),
      invalidatesTags: ["Watchlist", "Attention", "Actions"],
    }),
    updateWatchlist: builder.mutation<
      WatchlistMutationResponse,
      UpdateWatchlistPayload
    >({
      query: ({ meta_id, ...body }) => ({
        url: `/watchlist/${meta_id}`,
        method: "PUT",
        body,
      }),
      invalidatesTags: ["Watchlist", "Attention", "Actions"],
    }),

    // Holdings (real positions) endpoints
    fetchHoldings: builder.query<HoldingsResponse, void>({
      query: () => "/holdings",
      transformResponse: (response: HoldingsResponse) => {
        // 프런트/API가 순차 배포되어도 가격 누락을 0원으로 오인하지 않는다.
        const positions = response.positions.map((position) => ({
          ...position,
          weight:
            position.market_value_krw == null
              ? null
              : (position.weight ?? null),
        }));
        const pricedPositions = positions.filter(
          (position) => position.market_value_krw != null,
        ).length;
        const unpricedPositions = positions.length - pricedPositions;
        return {
          ...response,
          positions,
          summary: {
            ...response.summary,
            asset_alloc: response.summary.asset_alloc ?? [],
            top3_weight: response.summary.top3_weight ?? null,
            effective_positions:
              response.summary.effective_positions ?? null,
            priced_positions:
              response.summary.priced_positions ?? pricedPositions,
            unpriced_positions:
              response.summary.unpriced_positions ?? unpricedPositions,
            valuation_complete:
              response.summary.valuation_complete ?? unpricedPositions === 0,
          },
        };
      },
      providesTags: ["Holdings"],
    }),
    fetchHoldingsRisk: builder.query<HoldingsRiskResponse, void>({
      query: () => "/holdings/risk",
      providesTags: ["Holdings"],
    }),
    fetchPortfolioLedger: builder.query<PortfolioLedgerResponse, void>({
      query: () => "/portfolio-ledger",
      providesTags: ["PortfolioLedger"],
    }),
    addPortfolioLedgerEvent: builder.mutation<
      { event_id: string; created: boolean; summary: LedgerSummary },
      AddLedgerEventPayload
    >({
      query: (body) => ({ url: "/portfolio-ledger", method: "POST", body }),
      invalidatesTags: ["PortfolioLedger", "Holdings", "Attention", "Actions"],
    }),

    fetchOverview: builder.query<OverviewResponse, void>({
      query: () => "/overview",
      providesTags: ["Holdings"],
    }),
    fetchJournal: builder.query<JournalResponse, void>({
      query: () => "/journal",
      providesTags: ["Journal"],
    }),
    createJournal: builder.mutation<
      { entry_id: string; count: number },
      CreateJournalPayload
    >({
      query: (body) => ({ url: "/journal", method: "POST", body }),
      invalidatesTags: ["Journal", "Actions"],
    }),
    reviewJournal: builder.mutation<
      { review_id: string },
      { entry_id: string; outcome: string; lesson?: string }
    >({
      query: ({ entry_id, ...body }) => ({
        url: `/journal/${entry_id}/reviews`,
        method: "POST",
        body,
      }),
      invalidatesTags: ["Journal", "Actions"],
    }),
    addHolding: builder.mutation<HoldingMutationResponse, AddHoldingPayload>({
      query: (body) => ({
        url: "/holdings",
        method: "POST",
        body,
      }),
      invalidatesTags: ["Holdings", "Attention", "Actions"],
    }),
    updateHoldingMetadata: builder.mutation<
      HoldingMutationResponse,
      UpdateHoldingMetadataPayload
    >({
      query: ({ meta_id, ...body }) => ({
        url: `/holdings/${meta_id}/metadata`,
        method: "PUT",
        body,
      }),
      invalidatesTags: ["Holdings", "Attention", "Actions"],
    }),
    removeHolding: builder.mutation<HoldingMutationResponse, number>({
      query: (metaId) => ({
        url: `/holdings/${metaId}`,
        method: "DELETE",
      }),
      invalidatesTags: ["Holdings", "Attention", "Actions"],
    }),

    // Attention ("오늘 주목") endpoint
    fetchAttention: builder.query<AttentionResponse, void>({
      query: () => "/attention",
      providesTags: ["Attention"],
    }),

    fetchActions: builder.query<
      ActionCenterResponse,
      { horizonDays?: number; includeDismissed?: boolean } | void
    >({
      query: (params) => {
        const query = new URLSearchParams();
        if (params?.horizonDays) query.set("horizon_days", String(params.horizonDays));
        if (params?.includeDismissed) query.set("include_dismissed", "true");
        const suffix = query.toString();
        return `/actions${suffix ? `?${suffix}` : ""}`;
      },
      providesTags: ["Actions"],
    }),
    fetchResearch: builder.query<ResearchFeedResponse, ResearchFeedParams | void>({
      query: (params) => {
        const query = new URLSearchParams();
        if (params?.sourceId) query.set("source_id", params.sourceId);
        if (params?.view && params.view !== "all") query.set("view", params.view);
        if (params?.lane && params.lane !== "core") query.set("lane", params.lane);
        if (params?.query?.trim()) query.set("q", params.query.trim());
        if (params?.entryId) query.set("entry_id", params.entryId);
        if (params?.offset) query.set("offset", String(params.offset));
        if (params?.limit) query.set("limit", String(params.limit));
        const suffix = query.toString();
        return `/research${suffix ? `?${suffix}` : ""}`;
      },
      providesTags: ["Research"],
    }),
    fetchResearchStatus: builder.query<ResearchStatusResponse, void>({
      query: () => "/research/status",
      providesTags: ["ResearchStatus"],
    }),
    acknowledgeResearchSeen: builder.mutation<
      ResearchStatusResponse,
      { through: string }
    >({
      query: (body) => ({
        url: "/research/seen",
        method: "PUT",
        body,
      }),
      invalidatesTags: ["ResearchStatus"],
    }),
    updateResearchReadState: builder.mutation<
      { entry_id: string; is_read: boolean },
      { entryId: string; read: boolean }
    >({
      query: ({ entryId, read }) => ({
        url: `/research/${entryId}/read`,
        method: "PUT",
        body: { read },
      }),
      invalidatesTags: ["Research"],
    }),
    updateResearchSavedState: builder.mutation<
      { entry_id: string; is_saved: boolean },
      { entryId: string; saved: boolean }
    >({
      query: ({ entryId, saved }) => ({
        url: `/research/${entryId}/saved`,
        method: "PUT",
        body: { saved },
      }),
      invalidatesTags: ["Research"],
    }),
    markAllResearchRead: builder.mutation<
      { updated: number; total: number; unread: number; lane: ResearchLane },
      { lane: ResearchLane }
    >({
      query: ({ lane }) => ({
        url: `/research/read/all?lane=${encodeURIComponent(lane)}`,
        method: "PUT",
      }),
      invalidatesTags: ["Research"],
    }),
    fetchEarnings: builder.query<
      EarningsResponse,
      { scope?: EarningsScope; days?: number; resultsDays?: number; query?: string } | void
    >({
      query: (params) => {
        const query = new URLSearchParams();
        if (params?.scope) query.set("scope", params.scope);
        if (params?.days) query.set("days", String(params.days));
        if (params?.resultsDays) query.set("results_days", String(params.resultsDays));
        if (params?.query?.trim()) query.set("q", params.query.trim());
        const suffix = query.toString();
        return `/earnings${suffix ? `?${suffix}` : ""}`;
      },
      providesTags: ["Earnings"],
    }),
    updateActionState: builder.mutation<
      { event_id: string; state: ActionState; snoozed_until: string | null },
      { event_id: string; state: ActionState; snoozed_until?: string }
    >({
      query: ({ event_id, ...body }) => ({
        url: `/actions/${event_id}/state`,
        method: "PUT",
        body,
      }),
      invalidatesTags: ["Actions"],
    }),
    fetchNotificationConfig: builder.query<NotificationConfigResponse, void>({
      query: () => "/notifications/config",
      providesTags: ["Notifications"],
    }),
    subscribeNotifications: builder.mutation<
      { subscription_id: string; subscribed: boolean },
      PushSubscriptionPayload
    >({
      query: (body) => ({ url: "/notifications/subscriptions", method: "POST", body }),
      invalidatesTags: ["Notifications"],
    }),
    unsubscribeNotifications: builder.mutation<
      { unsubscribed: boolean },
      { endpoint: string }
    >({
      query: (body) => ({ url: "/notifications/subscriptions", method: "DELETE", body }),
      invalidatesTags: ["Notifications"],
    }),
    sendTestNotification: builder.mutation<
      {
        enabled: boolean;
        subscriptions: number;
        events: number;
        sent: number;
        failed: number;
        disabled: number;
      },
      void
    >({
      query: () => ({ url: "/notifications/test", method: "POST" }),
    }),

    // Market spotlight ("오늘의 신호 종목") endpoint
    fetchSpotlight: builder.query<SpotlightResponse, void>({
      query: () => "/insight/spotlight",
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
    fetchNewsBriefing: builder.query<NewsBriefingResponse, void>({
      query: () => "/news/briefing",
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
    fetchIntradayMarket: builder.query<IntradayMarketResponse, void>({
      query: () => "intraday/market",
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
    fetchInsightSignalStudy: builder.query<SignalStudyResponse, void>({
      query: () => "/insight/signals/study",
    }),
    fetchInsightFactors: builder.query<FactorLensResponse, void>({
      query: () => "/insight/factors",
    }),
    // POST query: auto-fetches for a holdings meta_id set; server skips US.
    fetchInsightFactorExposure: builder.query<
      FactorExposureResponse,
      number[]
    >({
      query: (metaIds) => ({
        url: "/insight/factor-exposure",
        method: "POST",
        body: { meta_id: metaIds },
      }),
    }),

    // Rebalancing signals (next rebalancing window)
    fetchRebalSignals: builder.query<RebalSignalsResponse, void>({
      query: () => "/backtest/rebal-signals",
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
    setStrategyStatus: builder.mutation<
      { port_id: number; status: string },
      { portId: number; status: "saved" | "active" }
    >({
      query: ({ portId, status }) => ({
        url: `/backtest/strategy/${portId}/status`,
        method: "POST",
        body: { status },
      }),
      invalidatesTags: ["Strategy", "Actions"],
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
  useFetchPriceCoverageQuery,
  useFetchStrategyMonthlyNavQuery,
  useFetchStrategyByIdQuery,
  useFetchStNavByIdQuery,
  useFetchStRebalByIdQuery,
  useFetchBmByIdQuery,
  useFetchStrategyLiveByIdQuery,
  useFetchStrategyAnalyticsQuery,
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
  useFetchStockFundamentalsQuery,
  useFetchWatchlistQuery,
  useAddToWatchlistMutation,
  useRemoveFromWatchlistMutation,
  useUpdateWatchlistMutation,
  // Holdings hooks
  useFetchHoldingsQuery,
  useFetchHoldingsRiskQuery,
  useFetchPortfolioLedgerQuery,
  useAddPortfolioLedgerEventMutation,
  useFetchOverviewQuery,
  useFetchJournalQuery,
  useCreateJournalMutation,
  useReviewJournalMutation,
  useAddHoldingMutation,
  useUpdateHoldingMetadataMutation,
  useRemoveHoldingMutation,
  // Attention hook
  useFetchAttentionQuery,
  useFetchActionsQuery,
  useFetchResearchQuery,
  useFetchResearchStatusQuery,
  useAcknowledgeResearchSeenMutation,
  useUpdateResearchReadStateMutation,
  useUpdateResearchSavedStateMutation,
  useMarkAllResearchReadMutation,
  useFetchEarningsQuery,
  useUpdateActionStateMutation,
  useFetchNotificationConfigQuery,
  useSubscribeNotificationsMutation,
  useUnsubscribeNotificationsMutation,
  useSendTestNotificationMutation,
  // Market spotlight hook
  useFetchSpotlightQuery,
  // News hooks
  useFetchNewsQuery,
  useFetchNewsBriefingQuery,
  // KR insight hooks
  useFetchInsightFlowsTopQuery,
  useFetchInsightFlowsMarketQuery,
  useFetchInsightFlowsTickerQuery,
  useFetchInsightBreadthQuery,
  useFetchInsightSignalsQuery,
  useFetchInsightIndexQuery,
  useFetchIntradayMarketQuery,
  useFetchInsightSectorHeatmapQuery,
  useFetchInsightSectorRotationQuery,
  useFetchInsightValuationQuery,
  useFetchInsightSignalStudyQuery,
  useFetchInsightFactorsQuery,
  useFetchInsightFactorExposureQuery,
  // Rebalancing signals hook
  useFetchRebalSignalsQuery,
  // Mutation hooks
  useRunBacktestMutation,
  useRunBacktestFromWeightsMutation,
  useSaveStrategyMutation,
  useSetStrategyStatusMutation,
  // Optimization hooks
  useCalculateEfficientFrontierMutation,
  useCalculateRiskParityMutation,
  useCalculateCorrelationMutation,
} = api;
