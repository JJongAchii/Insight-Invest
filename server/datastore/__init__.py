"""datastore — RDS·Iceberg·Athena를 대체하는 parquet 데이터 계층.

- 시세: qdata 미러(KR 전 종목·US ETF·FRED) + us_prices.parquet(1993~2025 US 개별주 아카이브)
- 메타·포트폴리오: {APP_DATA}/ 아래 parquet (RDS tb_* 덤프에서 이관)
- APP_DATA는 로컬 경로 또는 s3:// (Lambda에서는 s3)
"""

from datastore.meta import macro_df, meta_df, strategy_df
from datastore.prices import read_price_data
from datastore import holdings, portfolio, watchlist

__all__ = [
    "meta_df",
    "strategy_df",
    "macro_df",
    "read_price_data",
    "portfolio",
    "watchlist",
    "holdings",
]
