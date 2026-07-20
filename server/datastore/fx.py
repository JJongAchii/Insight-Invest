"""환율 — qdata ECOS 미러의 USDKRW 시계열과 원화 환산 헬퍼."""

from functools import lru_cache

import pandas as pd
from qdata import api as qdata_api


@lru_cache(maxsize=1)
def usdkrw() -> pd.Series:
    """USDKRW 일별 환율 (datetime 인덱스). 프로세스 수명 동안 캐시."""
    s = qdata_api.load_ecos("usdkrw")["usdkrw"].dropna()
    s.index = pd.to_datetime(s.index)
    return s.sort_index()


def to_krw(price_df: pd.DataFrame, tickers_iso: dict[str, str]) -> pd.DataFrame:
    """US 티커 컬럼을 원화 환산한다 (KR 컬럼은 그대로).

    환율은 price 날짜에 reindex 후 ffill (레이크 반영 지연·휴장일 대비, 선두 NaN은 bfill).
    """
    fx = usdkrw().reindex(price_df.index).ffill().bfill()
    out = price_df.copy()
    for col in out.columns:
        if tickers_iso.get(col) == "US":
            out[col] = out[col] * fx
    return out
