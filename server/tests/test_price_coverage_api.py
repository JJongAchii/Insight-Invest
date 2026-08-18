import pandas as pd

from app.routers import price


def test_price_coverage_uses_actual_common_interval(monkeypatch):
    monkeypatch.setattr(
        price.datastore,
        "meta_df",
        lambda: pd.DataFrame(
            [
                {"meta_id": 1, "ticker": "005930", "iso_code": "KR"},
                {"meta_id": 2, "ticker": "SPY", "iso_code": "US"},
            ]
        ),
    )

    def fake_prices(iso_code, meta_ids=None):
        dates = (
            ["2020-01-03", "2020-01-06", "2020-01-07"]
            if iso_code == "KR"
            else ["2020-01-02", "2020-01-03", "2020-01-06"]
        )
        meta_id = 1 if iso_code == "KR" else 2
        return pd.DataFrame({"meta_id": meta_id, "trade_date": pd.to_datetime(dates)})

    monkeypatch.setattr(price.datastore, "read_price_data", fake_prices)

    result = price.get_price_coverage("1,2")

    assert result["complete"] is True
    assert result["effective_start"] == "2020-01-03"
    assert result["effective_end"] == "2020-01-06"
    assert result["price_field"] == "adj_close"


def test_price_coverage_fails_closed_for_unknown_asset(monkeypatch):
    monkeypatch.setattr(
        price.datastore,
        "meta_df",
        lambda: pd.DataFrame([{"meta_id": 1, "ticker": "SPY", "iso_code": "US"}]),
    )
    monkeypatch.setattr(
        price.datastore,
        "read_price_data",
        lambda *_args, **_kwargs: pd.DataFrame(
            {"meta_id": [1], "trade_date": pd.to_datetime(["2020-01-02"])}
        ),
    )

    result = price.get_price_coverage("1,999")

    assert result["complete"] is False
    assert any(asset["meta_id"] == 999 and asset["rows"] == 0 for asset in result["assets"])
