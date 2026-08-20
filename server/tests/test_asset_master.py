import pandas as pd
import pytest

from module import asset_master as am


def _source_parts():
    kr_master = pd.DataFrame(
        {
            "asof": pd.to_datetime(["2026-08-20", "2026-08-20"]),
            "ticker": ["005930", "462860"],
            "market": ["KOSPI", "KOSDAQ"],
            "name": ["삼성전자", "더즌"],
            "sector": ["전기전자", "통신"],
            "mktcap": [500_000, 150_000],
        }
    )
    etf = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-08-20"]),
            "ticker": ["069500"],
            "name": ["KODEX 200"],
            "index_name": ["코스피 200"],
            "mktcap": [10_000],
        }
    )
    us = pd.DataFrame(
        {
            "asof": pd.to_datetime(["2026-08-20", "2026-08-20", "2026-08-20"]),
            "ticker": ["AAPL", "SPY", "WARRANT"],
            "name": ["Apple", "SPDR S&P 500 ETF", "Some Warrant"],
            "type": ["CS", "ETF", "WARRANT"],
            "active": [True, True, True],
        }
    )
    details = pd.DataFrame(
        {
            "ticker": ["AAPL", "SPY"],
            "market_cap": [3_000_000, None],
            "sic_description": ["Technology", None],
            "list_date": pd.to_datetime(["1980-12-12", "1993-01-22"]),
        }
    )
    return (
        am.kr_stock_rows(kr_master),
        am.kr_etf_rows(etf),
        am.us_rows(us, details),
    )


def test_reconcile_preserves_ids_and_adds_new_listing_stably():
    source = am.compose_source_master(*_source_parts())
    assert str(source["marketcap"].dtype) == "Int64"
    registry = pd.DataFrame(
        [
            {"meta_id": 2951, "iso_code": "KR", "ticker": "005930", "created_at": "old"},
            {"meta_id": 1, "iso_code": "US", "ticker": "SPY", "created_at": "old"},
        ]
    )

    master, updated, added = am.reconcile_registry(source, registry, "2026-08-20")

    ids = master.set_index(["iso_code", "ticker"])["meta_id"]
    assert ids[("KR", "005930")] == 2951
    assert ids[("US", "SPY")] == 1
    assert ids[("KR", "462860")] > 2951
    assert master.loc[master["ticker"].eq("462860"), "name"].item() == "더즌"
    assert "WARRANT" not in set(master["ticker"])
    assert added == 3

    rerun, rerun_registry, rerun_added = am.reconcile_registry(source, updated, "2026-08-21")
    pd.testing.assert_series_equal(master["meta_id"], rerun["meta_id"])
    pd.testing.assert_frame_equal(updated, rerun_registry)
    assert rerun_added == 0


def test_compose_rejects_cross_source_duplicate_key():
    kr, etf, us = _source_parts()
    etf = etf.copy()
    etf.loc[:, "ticker"] = "005930"
    with pytest.raises(ValueError, match="키 중복"):
        am.compose_source_master(kr, etf, us)


def test_reference_coverage_fails_loudly():
    source = am.compose_source_master(*_source_parts())
    registry = pd.DataFrame(columns=am.REGISTRY_COLUMNS)
    master, _, _ = am.reconcile_registry(source, registry, "2026-08-20")

    with pytest.raises(ValueError, match="462999"):
        am.assert_ticker_coverage(master, "intraday", ["462860", "462999"])


def test_catalog_is_code_owned_not_storage(monkeypatch):
    from datastore import catalog

    assert catalog.strategy_df()["strategy"].tolist() == ["eq", "dual_mmt"]
    assert "CPIAUCSL" in set(catalog.macro_df()["fred"])
