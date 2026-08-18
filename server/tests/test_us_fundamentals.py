"""US 재무 요약은 SEC filed 시점과 정정 제출을 보존한다."""

import pandas as pd
import pytest
from app.routers import price


def test_latest_annual_fact_uses_latest_amendment_and_prior_period():
    df = pd.DataFrame(
        {
            "tag": ["Revenues", "Revenues", "Revenues"],
            "qtrs": [4, 4, 4],
            "uom": ["USD", "USD", "USD"],
            "ddate": pd.to_datetime(["2024-12-31", "2025-12-31", "2025-12-31"]),
            "filed": pd.to_datetime(["2025-02-10", "2026-02-10", "2026-03-01"]),
            "value": [100.0, 115.0, 120.0],
        }
    )

    out = price._latest_annual_fact(df, "revenue")

    assert out["value"] == 120.0
    assert out["filed"] == "2026-03-01"
    assert out["yoy_pct"] == pytest.approx(20.0)


def test_balance_fact_requires_instant_qtrs_zero():
    df = pd.DataFrame(
        {
            "tag": ["Assets", "Assets"],
            "qtrs": [4, 0],
            "uom": ["USD", "USD"],
            "ddate": pd.to_datetime(["2025-12-31", "2025-12-31"]),
            "filed": pd.to_datetime(["2026-02-10", "2026-02-10"]),
            "value": [999.0, 500.0],
        }
    )

    out = price._latest_annual_fact(df, "assets")

    assert out["value"] == 500.0


def test_us_fundamentals_requests_filed_cut_and_massive_cik(monkeypatch):
    calls = {}
    refs = pd.DataFrame(
        {"ticker": ["AAA"], "cik": [1234], "active": [True], "asof": [pd.Timestamp.today()]}
    )
    facts = pd.DataFrame(
        {
            "tag": ["NetIncomeLoss"],
            "qtrs": [4],
            "uom": ["USD"],
            "ddate": pd.to_datetime(["2025-12-31"]),
            "filed": pd.to_datetime(["2026-02-10"]),
            "value": [25.0],
            "form": ["10-K"],
            "fp": ["FY"],
        }
    )

    from qdata import api as qdata_api

    monkeypatch.setattr(qdata_api, "load_us_tickers", lambda asof=None: refs.copy())

    def load_facts(**kwargs):
        calls.update(kwargs)
        return facts.copy()

    monkeypatch.setattr(qdata_api, "load_sec_fundamental", load_facts)

    out = price._us_fundamentals("AAA")

    assert calls["ciks"] == [1234]
    assert calls["end"] <= pd.Timestamp.today().strftime("%Y-%m-%d")
    assert out["available"] is True
    assert out["facts"][0]["key"] == "net_income"
