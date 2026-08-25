"""선택 목표 비중은 구 보유 파일과 호환되고 실제 비중 괴리를 명시한다."""

import pandas as pd
from app.routers import holdings as router
from datastore import holdings as store


def test_legacy_holdings_are_promoted_with_empty_target(monkeypatch):
    legacy = pd.DataFrame(
        {
            "meta_id": [1],
            "shares": [10.0],
            "avg_cost": [90.0],
            "currency": ["KRW"],
            "opened_at": [pd.Timestamp("2026-01-01")],
            "note": [""],
            "updated_at": [pd.Timestamp("2026-01-01")],
        }
    )
    monkeypatch.setattr(store.storage, "exists", lambda *args: True)
    monkeypatch.setattr(store.storage, "read_parquet", lambda *args: legacy.copy())

    out = store.list_items()

    assert "target_weight" in out.columns
    assert pd.isna(out.loc[0, "target_weight"])


def test_holdings_response_computes_target_drift(monkeypatch):
    items = pd.DataFrame(
        {
            "meta_id": [1, 2],
            "shares": [10.0, 20.0],
            "avg_cost": [90.0, 40.0],
            "currency": ["KRW", "KRW"],
            "target_weight": [0.4, 0.6],
        }
    )
    md = pd.DataFrame(
        {
            "meta_id": [1, 2],
            "ticker": ["000001", "000002"],
            "name": ["가나", "다라"],
            "iso_code": ["KR", "KR"],
            "security_type": ["stock", "stock"],
            "sector": ["A", "B"],
        }
    )
    monkeypatch.setattr(router.holdings_store, "list_items", lambda: items)
    monkeypatch.setattr(router.meta, "meta_df", lambda: md)
    monkeypatch.setattr(
        router, "build_price_map", lambda df: {1: (100.0, 0.0), 2: (50.0, 0.0)}
    )
    monkeypatch.setattr(router, "_usdkrw_latest", lambda: None)

    out = router.get_holdings()

    by_id = {row["meta_id"]: row for row in out["positions"]}
    assert by_id[1]["weight"] == 0.5
    assert by_id[1]["target_weight"] == 0.4
    assert by_id[1]["drift_pp"] == 10.0
    assert by_id[2]["drift_pp"] == -10.0
    assert out["summary"]["target_total"] == 1.0
    assert out["summary"]["top3_weight"] == 1.0
    assert out["summary"]["effective_positions"] == 2.0
    assert out["summary"]["asset_alloc"] == [{"label": "Equity", "weight": 1.0}]


def test_holdings_response_marks_missing_prices_without_fake_zero_weight(monkeypatch):
    items = pd.DataFrame(
        {
            "meta_id": [8919],
            "shares": [283.0],
            "avg_cost": [8.02],
            "currency": ["USD"],
            "target_weight": [None],
        }
    )
    md = pd.DataFrame(
        {
            "meta_id": [8919],
            "ticker": ["CPSH"],
            "name": ["CPS Technologies"],
            "iso_code": ["US"],
            "security_type": ["stock"],
            "sector": ["Technology"],
        }
    )
    monkeypatch.setattr(router.portfolio_ledger, "has_events", lambda: False)
    monkeypatch.setattr(router.holdings_store, "list_items", lambda: items)
    monkeypatch.setattr(router.meta, "meta_df", lambda: md)
    monkeypatch.setattr(router, "build_price_map", lambda _df: {})
    monkeypatch.setattr(router, "_usdkrw_latest", lambda: 1_380.0)

    out = router.get_holdings()

    position = out["positions"][0]
    assert position["latest_price"] is None
    assert position["market_value_krw"] is None
    assert position["weight"] is None
    assert out["summary"]["priced_positions"] == 0
    assert out["summary"]["unpriced_positions"] == 1
    assert out["summary"]["valuation_complete"] is False
    assert out["summary"]["top_weight"] is None
    assert out["summary"]["hhi"] is None
