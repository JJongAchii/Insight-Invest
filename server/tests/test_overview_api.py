"""홈 판단 요약은 방향 충돌과 데이터 신선도를 숨기지 않는다."""

import pandas as pd
import pytest

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


@pytest.mark.parametrize(
    "now,dataset,expected",
    [
        ("2026-09-07 10:39", "us_prices", "2026-09-04 19:00"),
        ("2026-09-07 10:40", "us_prices", "2026-09-07 09:00"),
        ("2026-09-07 20:39", "breadth_daily", "2026-09-04 19:00"),
        ("2026-09-07 20:40", "breadth_daily", "2026-09-07 19:00"),
        ("2026-09-06 21:00", "us_prices", "2026-09-04 19:00"),
    ],
)
def test_refresh_deadline_respects_batch_window_and_weekend(now, dataset, expected):
    kst = "Asia/Seoul"
    assert overview._required_batch_start(dataset, pd.Timestamp(now, tz=kst)) == pd.Timestamp(
        expected, tz=kst
    )


@pytest.mark.parametrize(
    "dataset,as_of,built_at,expected",
    [
        ("breadth_daily", "2026-09-03", "2026-09-03T19:24:00+09:00", "warn"),
        ("us_prices", "2026-09-02", "2026-09-04T09:11:00+09:00", "warn"),
        ("breadth_daily", "2026-09-07", "2026-09-07T19:24:00+09:00", "ok"),
        # US Labor Day: a fresh scheduled check can legitimately retain Friday's data.
        ("us_prices", "2026-09-04", "2026-09-07T19:24:00+09:00", "ok"),
        ("breadth_daily", "2026-09-07", None, "unknown"),
    ],
)
def test_data_status_does_not_hide_missed_batch(monkeypatch, dataset, as_of, built_at, expected):
    class Clock:
        @staticmethod
        def now(tz):
            return pd.Timestamp("2026-09-07 22:00", tz=tz).to_pydatetime()

    monkeypatch.setattr(overview, "datetime", Clock)
    sidecar = pd.DataFrame(
        [{"dataset": dataset, "status": "ok", "as_of": as_of, "built_at": built_at}]
    )
    monkeypatch.setattr(overview.storage, "read_parquet", lambda *a, **kw: sidecar)
    row = next(r for r in overview._data_status() if r["dataset"] == dataset)
    assert row["level"] == expected
    if expected == "warn":
        assert "예약 갱신 미확인" in row["detail"]


@pytest.mark.parametrize(
    "now,as_of,elapsed,level",
    [
        ("2026-09-08 00:30", "2026-09-04", 0, "ok"),
        ("2026-09-08 10:45", "2026-09-04", 1, "ok"),
        ("2026-09-08 20:50", "2026-09-04", 1, "ok"),
        ("2026-09-09 10:45", "2026-09-04", 2, "warn"),
        ("2026-11-03 07:59", "2026-10-30", 0, "ok"),
        ("2026-11-03 08:00", "2026-10-30", 1, "ok"),
    ],
)
def test_us_age_uses_settled_et_day_across_kst_midnight_and_dst(
    monkeypatch, now, as_of, elapsed, level
):
    current = pd.Timestamp(now, tz="Asia/Seoul")

    class Clock:
        @staticmethod
        def now(tz):
            return current.tz_convert(tz).to_pydatetime()

    monkeypatch.setattr(overview, "datetime", Clock)
    sidecar = pd.DataFrame(
        [{"dataset": "us_prices", "status": "ok", "as_of": as_of, "built_at": current.isoformat()}]
    )
    monkeypatch.setattr(overview.storage, "read_parquet", lambda *a, **kw: sidecar)
    us = next(row for row in overview._data_status() if row["dataset"] == "us_prices")
    assert us["market_sessions_old"] == elapsed
    assert us["level"] == level
