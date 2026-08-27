"""가격이 비어 있어도 종목 메타데이터는 JSON 안전하게 응답한다."""

import json

import numpy as np
import pandas as pd

from app.routers import price


def test_empty_price_history_is_json_serializable(monkeypatch):
    monkeypatch.setattr(
        price.datastore,
        "meta_df",
        lambda: pd.DataFrame(
            [
                {
                    "meta_id": np.int64(8919),
                    "ticker": "CPSH",
                    "name": "CPS Technologies",
                    "sector": pd.NA,
                    "iso_code": "US",
                    "marketcap": pd.NA,
                }
            ]
        ),
    )
    monkeypatch.setattr(price.datastore, "read_price_data", lambda **_kwargs: pd.DataFrame())

    result = price.get_price_history(8919)

    assert result["prices"] == []
    assert result["meta"] == {
        "meta_id": 8919,
        "ticker": "CPSH",
        "name": "CPS Technologies",
        "sector": None,
        "iso_code": "US",
        "marketcap": None,
    }
    assert result["series_contract"]["label"] == "Total Return"
    assert result["series_contract"]["cash_distributions"] == "included"
    json.dumps(result)


def test_kr_etf_series_contract_never_claims_total_return():
    meta = pd.Series({"iso_code": "KR", "security_type": "ETF"})

    contract = price._series_contract(meta, "krx_reference_price_adjusted_return")

    assert contract["label"] == "KRX Adjusted Price"
    assert contract["series_type"] == "krx_reference_price_adjusted"
    assert "Total Return은 아닙니다" in contract["warning"]


def test_stock_detail_exposes_us_reference_provenance(monkeypatch):
    from datastore import holdings, watchlist

    row = {
        "meta_id": 1,
        "ticker": "SPY",
        "name": "SPDR S&P 500 ETF Trust",
        "sector": pd.NA,
        "iso_code": "US",
        "security_type": "ETF",
        "security_subtype": "ETF",
        "marketcap": pd.NA,
        "marketcap_source": pd.NA,
        "marketcap_as_of": pd.NA,
        "shares_outstanding": 1_000,
        "weighted_shares_outstanding": pd.NA,
        "fund_size": 500_000,
        "fund_size_source": "estimate_close_x_share_class_shares",
        "fund_size_as_of": "2026-08-26",
        "reference_as_of": "2026-08-20",
    }
    monkeypatch.setattr(price.datastore, "meta_df", lambda: pd.DataFrame([row]))
    monkeypatch.setattr(price, "_build_summary", lambda *_args: {"meta_id": 1})
    monkeypatch.setattr(watchlist, "list_items", lambda: pd.DataFrame())
    monkeypatch.setattr(holdings, "list_items", lambda: pd.DataFrame())

    out = price.get_stock_detail(1)

    assert out["meta"]["security_subtype"] == "ETF"
    assert out["meta"]["shares_outstanding"] == 1_000
    assert out["meta"]["fund_size"] == 500_000
    assert out["meta"]["fund_size_as_of"] == "2026-08-26"
    assert out["meta"]["reference_as_of"] == "2026-08-20"


def test_summary_latest_price_uses_tradable_close_not_index_value(monkeypatch):
    meta = pd.Series(
        {
            "meta_id": 10,
            "ticker": "069500",
            "name": "KODEX 200",
            "iso_code": "KR",
            "security_type": "ETF",
        }
    )
    history = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2026-08-19", "2026-08-20"]),
            "close": [100.0, 80.0],
            "adj_close": [90.0, 90.0],
            "series_value": [90.0, 90.0],
            "return_basis": ["krx_reference_price_adjusted_return"] * 2,
        }
    )
    monkeypatch.setattr(price.datastore, "read_price_data", lambda **_kwargs: history.copy())
    monkeypatch.setattr(price, "_kr_summary_extras", lambda *_args: dict(price._EMPTY_EXTRAS))

    out = price._build_summary(10, meta)

    assert out["latest_price"] == 80.0
