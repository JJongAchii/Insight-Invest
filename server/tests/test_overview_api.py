"""홈 판단 요약은 방향 충돌과 데이터 신선도를 숨기지 않는다."""

import pandas as pd

from app.routers import overview


def _phase_history():
    return pd.DataFrame(
        {
            "phase": ["Goldilocks", "Goldilocks"],
            "growth_up": [True, True],
            "inflation_up": [False, False],
        },
        index=pd.PeriodIndex(["2026-06", "2026-07"], freq="M"),
    )


def test_overview_calls_out_cross_signal_conflict(monkeypatch):
    monkeypatch.setattr(overview.regime_mod, "phase_history", _phase_history)
    monkeypatch.setattr(
        overview.regime_mod,
        "risk_gauge",
        lambda: {"score": 20.0, "as_of": "2026-08-15", "components": []},
    )

    breadth = pd.DataFrame(
        {
            "date": list(pd.bdate_range("2026-08-10", periods=6)) * 2,
            "market": ["KOSPI"] * 6 + ["KOSDAQ"] * 6,
            "pct_above_ma20": [48, 46, 44, 42, 40, 38] * 2,
        }
    )
    flows = pd.DataFrame(
        {
            "date": pd.bdate_range("2026-08-10", periods=5),
            "market": "ALL",
            "investor": "frgn",
            "net_value": [1e10] * 5,
        }
    )

    def read_parquet(*parts, **kwargs):
        if parts[-1] == "breadth_daily.parquet":
            return breadth.copy()
        if parts[-1] == "flows_summary.parquet":
            return flows.copy()
        if parts[-1] == "data_status.parquet":
            raise FileNotFoundError
        raise AssertionError(parts)

    monkeypatch.setattr(overview.storage, "read_parquet", read_parquet)

    out = overview.get_overview()

    assert out["tone"] == "mixed"
    assert any("시장 위험도" in text for text in out["conflicts"])
    assert any("외국인" in text for text in out["conflicts"])
    assert {item["key"] for item in out["evidence"]} == {
        "phase",
        "gauge",
        "breadth",
        "flow",
    }
    assert [item["key"] for item in out["horizons"]] == [
        "intraday",
        "tactical",
        "structural",
    ]
    assert out["tone_label"] == "시간축별 혼조"


def test_valuation_uses_expensive_side_percentile_wording(monkeypatch):
    valuation = pd.DataFrame(
        {
            "date": [pd.Timestamp("2026-08-15")],
            "market": ["KOSPI"],
            "pct_rank_per": [90.0],
            "pct_rank_pbr": [98.0],
        }
    )
    monkeypatch.setattr(overview.storage, "read_parquet", lambda *args, **kwargs: valuation)

    item, pos, neg = overview._valuation_evidence()

    assert item is not None
    assert "역사적 상위 6.0%" in item["title"]
    assert pos == 0
    assert neg == 1


def test_data_status_marks_failed_required_build(monkeypatch):
    sidecar = pd.DataFrame(
        {
            "dataset": ["us_prices"],
            "status": ["error"],
            "as_of": [None],
            "built_at": ["2026-08-18T09:00:00+09:00"],
            "row_count": [None],
            "message": ["missing dividends"],
        }
    )
    monkeypatch.setattr(overview.storage, "read_parquet", lambda *args, **kwargs: sidecar)

    rows = overview._data_status()

    us = next(row for row in rows if row["dataset"] == "us_prices")
    assert us["level"] == "error"
    assert us["detail"] == "최근 빌드 실패"


def test_calculation_contracts_do_not_overstate_kr_etf_or_execution_timing():
    contracts = {row["key"]: row for row in overview._calculation_contracts()}

    etf = contracts["kr_etf_returns"]
    assert etf["basis"] == "KRX reference-price adjusted return"
    assert "Total Return으로 표시하지 않습니다" in etf["detail"]

    cash = contracts["kr_cash_distributions"]
    assert cash["basis"] == "Unavailable"
    assert cash["version"] == "kr_cash_events_gated_v1"

    study = contracts["factor_signal_returns"]
    assert study["execution"] == "D close signal → D+1 open entry"
    assert study["version"] == "kr_price_return_v2"

    backtest = contracts["backtest_returns"]
    assert backtest["version"] == "backtest_close_execution_v2"
    assert "혼합 시 실행 중단" in backtest["coverage"]

    us_valuation = contracts["us_valuation"]
    assert us_valuation["coverage"] == "PER/PBR 미산출"
