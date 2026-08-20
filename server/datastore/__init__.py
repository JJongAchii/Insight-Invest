"""datastore — qdata와 앱 네이티브 parquet 데이터 계층.

- 시세: qdata 미러(KR 전 종목·FRED) + Massive에서 매일 합성한 us_prices.parquet
- 메타: qdata 원천에서 매일 발행한 asset_master.parquet
- 포트폴리오: {APP_DATA}/portfolio 아래 앱 네이티브 상태
- APP_DATA는 로컬 경로 또는 s3:// (Lambda에서는 s3)
"""

from datastore import holdings, portfolio, watchlist
from datastore.meta import macro_df, meta_df, strategy_df
from datastore.prices import read_price_data

__all__ = [
    "meta_df",
    "strategy_df",
    "macro_df",
    "read_price_data",
    "portfolio",
    "watchlist",
    "holdings",
]
