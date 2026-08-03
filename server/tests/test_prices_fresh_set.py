"""US fresh 티커 판별이 레이크 전 테이블 스캔(coverage) 없이 동작하는지.

coverage()는 krx 전 패널·US 아카이브까지 읽어 Lambda 2048MB를 뚫는다
(2026-08-03 /backtest/strategy/bm OOM 실측: 피크 ~2.0GB vs 직접 읽기 ~0.1GB).
_qdata_us_tickers에 필요한 건 yfinance 티커 목록뿐이다 — 여기서 못박는다.
"""

import pandas as pd

from datastore import prices as ds_prices


def test_us_fresh_tickers_reads_only_yfinance_table(monkeypatch):
    ds_prices._qdata_us_tickers.cache_clear()
    idx = pd.date_range("2024-01-01", periods=3)
    wide = pd.DataFrame(
        {("adj_close", "SPY"): [1.0] * 3, ("adj_close", "QQQ"): [1.0] * 3}, index=idx
    )
    wide.columns = pd.MultiIndex.from_tuples(wide.columns)
    monkeypatch.setattr(ds_prices.qdata_api, "load_prices", lambda **kw: wide)

    def boom():
        raise AssertionError("coverage()는 레이크 전체를 스캔한다 — 호출 금지")

    monkeypatch.setattr(ds_prices.qdata_api, "coverage", boom)
    try:
        assert ds_prices._qdata_us_tickers() == frozenset({"SPY", "QQQ"})
    finally:
        ds_prices._qdata_us_tickers.cache_clear()
