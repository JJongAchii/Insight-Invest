"""관심종목 가격·수급 enrich 회귀 테스트."""

import pandas as pd
import pytest

from app.routers import watchlist as router


def test_kr_latest_prices_routes_etf_through_shared_price_contract(monkeypatch):
    source = pd.DataFrame(
        {
            "meta_id": [114, 114],
            "ticker": ["114800", "114800"],
            "trade_date": pd.to_datetime(["2026-08-24", "2026-08-25"]),
            "close": [1040.0, 1032.0],
            "gross_return": [0.0369, -0.0077],
        }
    )
    called = {}

    def fake_read_price_data(iso_code, **kwargs):
        called.update({"iso_code": iso_code, **kwargs})
        return source.copy()

    monkeypatch.setattr(router, "read_price_data", fake_read_price_data)

    result = router._kr_latest_prices([114])

    assert called["iso_code"] == "KR"
    assert called["meta_ids"] == [114]
    latest, previous, change, as_of = result[114]
    assert latest == 1032.0
    assert previous == 1040.0
    assert change == pytest.approx(-0.77)
    assert as_of == "2026-08-25"


def test_watchlist_requests_flows_for_stocks_only(monkeypatch):
    items = pd.DataFrame(
        {
            "meta_id": [1, 2],
            "added_at": pd.to_datetime(["2026-08-26", "2026-08-26"], utc=True),
            "note": ["", ""],
            "thesis": ["", ""],
            "catalyst": ["", ""],
            "invalidation": ["", ""],
            "review_date": [None, None],
            "alerts_enabled": [False, False],
            "alert_price_above": [None, None],
            "alert_price_below": [None, None],
            "alert_change_pct": [None, None],
        }
    )
    master = pd.DataFrame(
        {
            "meta_id": [1, 2],
            "ticker": ["005930", "114800"],
            "name": ["삼성전자", "KODEX 인버스"],
            "iso_code": ["KR", "KR"],
            "security_type": ["STOCK", "ETF"],
        }
    )
    flow_tickers = []

    monkeypatch.setattr(router.watchlist_store, "list_items", lambda: items.copy())
    monkeypatch.setattr(router.meta, "meta_df", lambda: master.copy())
    monkeypatch.setattr(
        router,
        "_kr_latest_prices",
        lambda meta_ids: {
            1: (80_000.0, 79_000.0, 1.27, "2026-08-25"),
            2: (1_032.0, 1_040.0, -0.77, "2026-08-25"),
        },
    )

    def fake_flows(tickers):
        flow_tickers.extend(tickers)
        return {"005930": {"frgn": 1_000.0, "inst": -500.0}}

    monkeypatch.setattr(router, "_kr_flows", fake_flows)

    response = router.get_watchlist()

    assert flow_tickers == ["005930"]
    by_id = {row["meta_id"]: row for row in response["items"]}
    assert by_id[2]["latest_price"] == 1_032.0
    assert by_id[2]["chg_pct"] == pytest.approx(-0.77)
    assert by_id[2]["frgn_net_20d"] is None
    assert by_id[2]["inst_net_20d"] is None
