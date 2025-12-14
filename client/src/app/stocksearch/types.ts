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

export interface FilterState {
  market: MarketFilter;
  sector: string;
  cap: CapFilter;
  search: string;
}

// Market cap thresholds (in USD)
export const CAP_THRESHOLDS = {
  large: 10_000_000_000, // > $10B
  mid: 2_000_000_000, // $2B - $10B
  small: 0, // < $2B
};
