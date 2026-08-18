// Stock search types

export interface MetaRow {
  meta_id: number;
  ticker: string;
  name: string;
  isin: string;
  security_type: string;
  asset_class: string | null;
  sector: string | null;
  iso_code: string;
  marketcap: number;
  fee: number | null;
}

export type MarketFilter = "all" | "US" | "KR";

export type CapFilter = "all" | "large" | "mid" | "small";

export type TypeFilter = "all" | "stock" | "etf";

export interface FilterState {
  market: MarketFilter;
  sector: string;
  cap: CapFilter;
  type: TypeFilter;
  search: string;
}

// 원천 통화를 유지한다. KR 시가총액(KRW)에 USD 임계치를 적용하지 않는다.
export const CAP_THRESHOLDS: Record<"KR" | "US", { large: number; mid: number }> = {
  US: { large: 10_000_000_000, mid: 2_000_000_000 },
  KR: { large: 10_000_000_000_000, mid: 1_000_000_000_000 },
};
