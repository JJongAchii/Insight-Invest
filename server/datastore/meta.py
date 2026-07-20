"""종목 메타·전략·매크로 정의 — RDS tb_meta/tb_strategy/tb_macro 덤프 parquet.

거의 불변 데이터라 프로세스 수명 동안 캐시한다 (Lambda 컨테이너 재사용 시 유지,
콜드스타트 시 자연 갱신).
"""

from functools import lru_cache

import pandas as pd

from datastore import storage


@lru_cache(maxsize=1)
def meta_df() -> pd.DataFrame:
    """tb_meta 전체: meta_id, ticker, name, isin, security_type, asset_class,
    sector, iso_code, marketcap, fee, remark, min_date, max_date."""
    return storage.read_parquet("meta.parquet")


@lru_cache(maxsize=1)
def strategy_df() -> pd.DataFrame:
    """tb_strategy: strategy_id, strategy, strategy_name."""
    return storage.read_parquet("strategy.parquet")


@lru_cache(maxsize=1)
def macro_df() -> pd.DataFrame:
    """tb_macro: macro_id, fred(시리즈 ID), 표시명 등 매크로 정의."""
    return storage.read_parquet("macro.parquet")


def resolve(meta_ids: list[int] | None = None, tickers: list[str] | None = None) -> pd.DataFrame:
    """meta_id/ticker 부분집합의 [meta_id, ticker, iso_code] 매핑."""
    df = meta_df()[["meta_id", "ticker", "iso_code"]]
    if meta_ids is not None:
        df = df[df["meta_id"].isin(meta_ids)]
    if tickers is not None:
        df = df[df["ticker"].isin(tickers)]
    return df.reset_index(drop=True)
