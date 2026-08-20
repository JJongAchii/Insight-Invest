"""qdata에서 매일 발행한 단일 자산 마스터와 앱 코드 카탈로그."""

import time
from functools import lru_cache

import pandas as pd

from datastore import storage
from datastore.catalog import macro_df, strategy_df


@lru_cache(maxsize=1)
def _meta_for_bucket(_bucket: int) -> pd.DataFrame:
    return storage.read_parquet("asset_master.parquet")


def meta_df() -> pd.DataFrame:
    """통합 자산 마스터. 5분마다 새 발행분을 확인해 warm Lambda도 갱신한다."""
    return _meta_for_bucket(int(time.time() // 300))


def resolve(meta_ids: list[int] | None = None, tickers: list[str] | None = None) -> pd.DataFrame:
    """meta_id/ticker 부분집합의 가격 소스 라우팅 매핑."""
    df = meta_df()[["meta_id", "ticker", "iso_code", "security_type"]]
    if meta_ids is not None:
        df = df[df["meta_id"].isin(meta_ids)]
    if tickers is not None:
        df = df[df["ticker"].isin(tickers)]
    return df.reset_index(drop=True)
