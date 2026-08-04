"""US 가격 서빙 단일 경로 — 앱 us_prices.parquet 하나만 읽는다 (fresh/stale 분기 제거)."""

import pandas as pd
import pytest

from datastore import prices


@pytest.fixture
def fake_us_file(monkeypatch):
    df = pd.DataFrame(
        {
            "meta_id": [1, 1, 55, 55],
            "trade_date": pd.to_datetime(["2026-01-05", "2026-01-06"] * 2),
            "ticker": ["SPY", "SPY", "SHY", "SHY"],
            "adj_close": [500.0, 505.0, 82.0, 82.1],
            "gross_return": [float("nan"), 0.01, float("nan"), 82.1 / 82.0 - 1],
        }
    )

    def fake_read(name, columns=None, filters=None):
        assert name == "us_prices.parquet"
        return df[columns] if columns else df

    monkeypatch.setattr(prices.storage, "read_parquet", fake_read)
    monkeypatch.setattr(
        prices.meta,
        "resolve",
        lambda meta_ids=None, tickers=None: pd.DataFrame(
            {"meta_id": [1, 55], "ticker": ["SPY", "SHY"], "iso_code": "US"}
        ),
    )
    return df


def test_read_price_data_us_single_source(fake_us_file):
    out = prices.read_price_data("US", tickers=["SPY", "SHY"])
    assert list(out.columns) == ["meta_id", "trade_date", "ticker", "adj_close", "gross_return"]
    assert set(out.ticker) == {"SPY", "SHY"}
    assert out.equals(out.sort_values(["ticker", "trade_date"]).reset_index(drop=True))


def test_us_adj_close_wide(fake_us_file):
    wide = prices.us_adj_close_wide(["SPY", "SHY"])
    assert list(wide.columns) == ["SHY", "SPY"] or list(wide.columns) == ["SPY", "SHY"]
    assert wide.loc[pd.Timestamp("2026-01-06"), "SPY"] == 505.0


def test_no_yfinance_table_dependency():
    """fresh-set 경로가 완전히 사라졌는지 — 심볼 자체가 없어야 한다."""
    assert not hasattr(prices, "_qdata_us_tickers")
    assert not hasattr(prices, "_us_fresh_prices")
