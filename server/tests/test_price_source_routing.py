from datetime import date

import pandas as pd
import pytest

from datastore import prices


def _price(meta_id: int, ticker: str, value: float) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "meta_id": [meta_id],
            "trade_date": [pd.Timestamp("2026-08-20")],
            "ticker": [ticker],
            "adj_close": [value],
            "gross_return": [0.01],
        }
    )


def test_kr_price_source_routes_by_security_type_not_meta_id(monkeypatch):
    """신규 ID의 크기와 무관하게 STOCK/ETF를 각 qdata 패널로 보낸다."""
    mapping = pd.DataFrame(
        {
            # 과거 규칙과 정반대인 ID로 회귀를 탐지한다.
            "meta_id": [2_000_000, 10],
            "ticker": ["005930", "069500"],
            "iso_code": ["KR", "KR"],
            "security_type": ["STOCK", "ETF"],
        }
    )
    monkeypatch.setattr(prices.meta, "resolve", lambda **_kwargs: mapping)
    monkeypatch.setattr(
        prices,
        "_kr_prices",
        lambda *_args: _price(2_000_000, "005930", 80_000.0),
    )
    monkeypatch.setattr(
        prices,
        "_kr_etf_prices",
        lambda *_args: _price(10, "069500", 40_000.0),
    )

    result = prices.read_price_data(
        "KR",
        meta_ids=[2_000_000, 10],
        start_date=date(2026, 8, 20),
        end_date=date(2026, 8, 20),
    )

    assert set(result["meta_id"]) == {2_000_000, 10}
    assert result.set_index("ticker")["adj_close"].to_dict() == {
        "005930": 80_000.0,
        "069500": 40_000.0,
    }


def test_kr_etf_source_is_explicitly_raw_price(monkeypatch):
    mapping = pd.DataFrame({"meta_id": [10], "ticker": ["069500"]})
    source = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-08-19", "2026-08-20"]),
            "ticker": ["069500", "069500"],
            "close": [40_000.0, 40_400.0],
        }
    )
    monkeypatch.setattr(prices.qdata_api, "load_krx_etf_prices", lambda **_kwargs: source.copy())

    result = prices._kr_etf_prices(mapping, date(2026, 8, 19), date(2026, 8, 20))

    assert result["series_value"].tolist() == [40_000.0, 40_400.0]
    assert set(result["return_basis"]) == {"raw_price_return_ex_cash_distributions"}
    assert result["gross_return"].iloc[1] == pytest.approx(0.01)


def test_kr_etf_prefers_krx_reference_price_adjusted_series(monkeypatch):
    mapping = pd.DataFrame({"meta_id": [10], "ticker": ["069500"]})
    source = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-08-19", "2026-08-20"]),
            "ticker": ["069500", "069500"],
            "close": [40_000.0, 38_000.0],
            "adj_close": [38_000.0, 38_000.0],
            "chg_pct": [0.0, 0.0],
        }
    )
    monkeypatch.setattr(prices.qdata_api, "load_krx_etf_prices", lambda **_kwargs: source.copy())

    result = prices._kr_etf_prices(mapping, date(2026, 8, 19), date(2026, 8, 20))

    assert result["series_value"].tolist() == [38_000.0, 38_000.0]
    assert set(result["return_basis"]) == {"krx_reference_price_adjusted_return"}
    assert result["gross_return"].tolist() == [0.0, 0.0]
