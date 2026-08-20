"""종목·시장 밸류에이션 기준일, 공식비율 재검산, 커버리지 계약."""

import os
import sys

import pandas as pd
import pytest
from qdata import api as qdata_api

from app.routers import price
from datastore import storage

_SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import build_insights as bi  # noqa: E402


def test_kr_summary_uses_same_day_inputs_and_recomputes_ratios(monkeypatch):
    px = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-08-18", "2026-08-19"]),
            "ticker": ["000001", "000001"],
            "close": [90.0, 100.0],
            "value": [1e8, 2e8],
            "mktcap": [900.0, 1000.0],
            "shares": [10.0, 10.0],
        }
    )
    fund = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-08-18", "2026-08-19"]),
            "ticker": ["000001", "000001"],
            "per": [9.0, 10.0],
            "pbr": [1.8, 2.0],
            "div": [2.0, 3.0],
            "eps": [10.0, 10.0],
            "bps": [50.0, 50.0],
            "dps": [1.8, 3.0],
        }
    )
    monkeypatch.setattr(qdata_api, "load_krx_prices", lambda **_kwargs: px.copy())
    monkeypatch.setattr(qdata_api, "load_krx_fundamental", lambda **_kwargs: fund.copy())
    monkeypatch.setattr(
        storage,
        "read_parquet",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(FileNotFoundError()),
    )

    out = price._kr_summary_extras("000001", "STOCK")

    assert out["per"] == pytest.approx(10.0)
    assert out["pbr"] == pytest.approx(2.0)
    assert out["div"] == pytest.approx(3.0)
    assert out["valuation"]["as_of"] == "2026-08-19"
    assert out["valuation"]["price_as_of"] == out["valuation"]["fundamental_as_of"]
    assert out["valuation"]["per_status"] == "ok"
    assert out["valuation"]["checks"]["per_recomputed"] == pytest.approx(10.0)
    assert out["valuation"]["checks"]["tolerance"] == price.KRX_RATIO_TOLERANCE


def test_kr_summary_explains_non_positive_eps_instead_of_showing_zero(monkeypatch):
    px = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-08-19"]),
            "ticker": ["000002"],
            "close": [100.0],
            "value": [2e8],
            "mktcap": [1000.0],
            "shares": [10.0],
        }
    )
    fund = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-08-19"]),
            "ticker": ["000002"],
            "per": [0.0],
            "pbr": [2.0],
            "div": [0.0],
            "eps": [-1.0],
            "bps": [50.0],
            "dps": [0.0],
        }
    )
    monkeypatch.setattr(qdata_api, "load_krx_prices", lambda **_kwargs: px.copy())
    monkeypatch.setattr(qdata_api, "load_krx_fundamental", lambda **_kwargs: fund.copy())
    monkeypatch.setattr(
        storage,
        "read_parquet",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(FileNotFoundError()),
    )

    out = price._kr_summary_extras("000002", "STOCK")

    assert out["per"] is None
    assert out["valuation"]["per_status"] == "loss_or_zero_earnings"
    assert any("PER" in reason for reason in out["valuation"]["missing_reasons"])


def test_market_valuation_keeps_price_universe_and_reports_missing_fundamentals(monkeypatch):
    day = pd.Timestamp("2026-08-19")
    price_rows = pd.DataFrame(
        {
            "date": [day] * 4,
            "ticker": ["AAA", "BBB", "CCC", "DDD"],
            "market": ["KOSPI"] * 4,
            "close": [100.0] * 4,
            "mktcap": [1000.0, 2000.0, 3000.0, 4000.0],
            "shares": [10.0, 20.0, 30.0, 40.0],
        }
    )
    fundamentals = pd.DataFrame(
        {
            "date": [day] * 3,
            "ticker": ["AAA", "BBB", "CCC"],
            "per": [10.0, 0.0, 0.0],
            "pbr": [2.0, 1.0, 0.0],
            "div": [1.0, 0.0, 2.0],
            "eps": [10.0, -1.0, 0.0],
            "bps": [50.0, 100.0, 0.0],
            "dps": [1.0, 0.0, 2.0],
        }
    )
    monkeypatch.setattr(bi.qdata_api, "load_krx_fundamental", lambda **_kwargs: fundamentals.copy())
    monkeypatch.setattr(bi.qdata_api, "load_krx_prices", lambda **_kwargs: price_rows.copy())

    out = bi.build_valuation_daily()
    row = out.iloc[0]

    assert row["n_stocks"] == 4
    assert row["fundamental_name_coverage_pct"] == pytest.approx(75.0)
    assert row["fundamental_mktcap_coverage_pct"] == pytest.approx(60.0)
    assert row["per_name_coverage_pct"] == pytest.approx(25.0)
    assert row["per_mktcap_coverage_pct"] == pytest.approx(10.0)
    assert row["non_positive_eps_name_pct"] == pytest.approx(50.0)
    assert row["earnings_name_coverage_pct"] == pytest.approx(75.0)
    assert row["earnings_mktcap_coverage_pct"] == pytest.approx(60.0)
    assert row["aggregate_earnings_yield_pct"] == pytest.approx(80.0 / 6000.0 * 100.0)
    assert row["calculation_version"] == "kr_market_valuation_v2"
