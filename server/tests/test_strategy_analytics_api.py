"""GET /backtest/strategy/analytics/{port_id} + live 확장 계약.

응답 스키마가 계약이다 (Phase 2 프론트가 이 형태를 소비) — 브리프
.superpowers/sdd/2026-08-03-strategy-analytics-backend/task-3-brief.md §Interfaces
그대로 못박는다. 섹션 단위 degrade(그 키만 null) 와 500 금지를 함께 검증한다.
"""

import asyncio
import json

import numpy as np
import pandas as pd
import pytest


def _write(tmp_path, name, df):
    d = tmp_path / "portfolio"
    d.mkdir(exist_ok=True)
    df.to_parquet(d / name, index=False)


def _seed_portfolio(tmp_path, monkeypatch, *, port_id=1, config=None, created_at="2026-07-01"):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    _write(
        tmp_path,
        "portfolio.parquet",
        pd.DataFrame(
            {
                "port_id": [port_id],
                "port_name": [f"막포{port_id}"],
                "strategy_id": [1],
                "created_at": [pd.Timestamp(created_at)],
                "config": [json.dumps(config) if config is not None else None],
                "status": ["saved"],
            }
        ),
    )
    _write(
        tmp_path,
        "universe.parquet",
        pd.DataFrame({"port_id": [port_id] * 3, "meta_id": [1, 2, 3]}),
    )


def _bumpy_nav(idx: pd.DatetimeIndex) -> pd.Series:
    """상승 추세 + 중간 낙폭 1회 (에피소드 상식성 검증용). 짧은 인덱스에도 안전."""
    n = len(idx)
    trend = 1000 * (1.0005 ** np.arange(n))
    dip_start = max(1, n // 3)
    dip_end = min(n, dip_start + 15)
    vals = trend.copy()
    if dip_end > dip_start:
        vals[dip_start:dip_end] = np.linspace(
            trend[dip_start], trend[dip_start] * 0.85, dip_end - dip_start
        )
    if dip_end < n:
        vals[dip_end:] = trend[dip_end:] * 0.85  # 낙폭 후에도 같은 성장률로 복귀
    return pd.Series(vals, index=idx, dtype="float64")


def _seed_nav(tmp_path, port_id, idx, values=None):
    s = values if values is not None else _bumpy_nav(idx)
    _write(
        tmp_path,
        "nav.parquet",
        pd.DataFrame({"port_id": port_id, "trade_date": s.index, "value": s.to_numpy()}),
    )
    return s


def _seed_bm_nav(tmp_path, port_id, idx):
    bm = pd.Series(1000 * (1.0002 ** np.arange(len(idx))), index=idx, dtype="float64")
    _write(
        tmp_path,
        "benchmark_nav.parquet",
        pd.DataFrame({"port_id": port_id, "trade_date": bm.index, "value": bm.to_numpy()}),
    )
    return bm


def _patch_meta(monkeypatch):
    """portfolio.rebalance()가 이름 조인에 쓰는 meta.meta_df — lru_cache라 실제
    APP_DATA 파일을 절대 건드리지 않도록 모듈 참조를 직접 대체한다."""
    import datastore.meta as meta_mod

    monkeypatch.setattr(
        meta_mod,
        "meta_df",
        lambda: pd.DataFrame({"ticker": ["AAA", "BBB"], "name": ["에이", "비"]}),
    )


def _seed_rebal(tmp_path, port_id, idx, monkeypatch=None):
    if monkeypatch is not None:
        _patch_meta(monkeypatch)
    rebal_dates = idx[::60][:4]  # 몇 개의 리밸 시점
    rows = []
    for i, d in enumerate(rebal_dates):
        if i % 2 == 0:
            rows.append({"rebal_date": d, "ticker": "AAA", "weight": 1.0})
        else:
            rows.append({"rebal_date": d, "ticker": "AAA", "weight": 0.5})
            rows.append({"rebal_date": d, "ticker": "BBB", "weight": 0.5})
    df = pd.DataFrame(rows)
    df.insert(0, "port_id", port_id)
    _write(tmp_path, "rebalance.parquet", df)
    return df


def _phase_series(idx: pd.DatetimeIndex) -> pd.DataFrame:
    """월간 Period 인덱스 + phase 컬럼 — regime.phase_history 대체 픽스처."""
    months = pd.period_range(idx.min().to_period("M"), idx.max().to_period("M"), freq="M")
    phases = ["Goldilocks" if i % 2 == 0 else "Reflation" for i in range(len(months))]
    return pd.DataFrame({"phase": phases}, index=months)


def _patch_regime(monkeypatch, bt, phase_df):
    monkeypatch.setattr(bt.regime, "phase_history", lambda: phase_df)


# ---------- empty 계약 ----------


def test_analytics_unknown_port_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    import app.routers.backtest as bt

    assert asyncio.run(bt.get_strategy_analytics(999)) == {"empty": True}


def test_analytics_no_nav_returns_empty(tmp_path, monkeypatch):
    _seed_portfolio(tmp_path, monkeypatch, port_id=1)
    import app.routers.backtest as bt

    assert asyncio.run(bt.get_strategy_analytics(1)) == {"empty": True}


# ---------- 정상 경로 ----------


@pytest.fixture()
def full_fixture(tmp_path, monkeypatch):
    """2019-06 시작 300거래일 — rolling(>=252) 확보 + covid 구간(2020-02~03) 커버."""
    idx = pd.bdate_range("2019-06-03", periods=300)
    config = {
        "algorithm": "momentum",
        "rebal_freq": "Q",
        "cost_bps": 15.0,
        "currency": "USD",
        "benchmark": "SPY",
        "params": {},
    }
    _seed_portfolio(tmp_path, monkeypatch, port_id=1, config=config)
    nav = _seed_nav(tmp_path, 1, idx)
    bm = _seed_bm_nav(tmp_path, 1, idx)
    _seed_rebal(tmp_path, 1, idx, monkeypatch)

    import app.routers.backtest as bt

    _patch_regime(monkeypatch, bt, _phase_series(idx))
    return bt, nav, bm, idx


def test_analytics_full_response_keys(full_fixture):
    bt, nav, bm, idx = full_fixture
    r = asyncio.run(bt.get_strategy_analytics(1))

    assert set(r.keys()) == {
        "premise",
        "rolling",
        "drawdowns",
        "phases",
        "crisis",
        "monthly",
        "trading",
        "notes",
        "as_of",
    }
    assert r["as_of"] == idx.max().strftime("%Y-%m-%d")
    assert r["notes"] == {}  # 정상 응답 — 강등된 섹션 없음

    p = r["premise"]
    assert p["algorithm"] == "momentum"
    assert p["rebal_freq"] == "Q"
    assert p["cost_bps"] == pytest.approx(15.0)
    assert p["currency"] == "USD"
    assert p["universe_n"] == 3
    assert p["saved_at"] == "2026-07-01"
    assert p["bt_start"] == idx.min().strftime("%Y-%m-%d")
    assert p["bt_end"] == idx.max().strftime("%Y-%m-%d")
    assert p["bt_days"] == len(idx)
    assert p["n_rebals"] == 4
    assert p["cost_warning"] is False


def test_analytics_rolling_populated_with_bm(full_fixture):
    bt, *_ = full_fixture
    r = asyncio.run(bt.get_strategy_analytics(1))
    rolling = r["rolling"]
    assert rolling is not None
    assert rolling["window"] == 252
    assert len(rolling["rows"]) > 0
    row = rolling["rows"][0]
    assert set(row.keys()) == {"date", "roll_ret", "roll_sharpe"}
    assert rolling["bm_rows"] is not None
    assert len(rolling["bm_rows"]) > 0


def test_analytics_drawdown_episodes_sane(full_fixture):
    bt, *_ = full_fixture
    r = asyncio.run(bt.get_strategy_analytics(1))
    dd = r["drawdowns"]
    assert dd is not None
    assert len(dd["underwater"]) > 0
    assert len(dd["episodes"]) >= 1
    ep = dd["episodes"][0]
    assert ep["depth_pct"] < 0  # 낙폭은 음수
    assert ep["peak"] is not None and ep["trough"] is not None
    # 저점이 고점보다 이후 시점
    assert ep["trough"] >= ep["peak"]


def test_analytics_phases_at_most_four_rows(full_fixture):
    bt, *_ = full_fixture
    r = asyncio.run(bt.get_strategy_analytics(1))
    phases = r["phases"]
    assert phases is not None
    assert len(phases["rows"]) <= 4
    for row in phases["rows"]:
        assert set(row.keys()) == {"phase", "mean_ret_pct", "n_months", "bm_mean_ret_pct"}
        assert row["n_months"] > 0
        assert row["bm_mean_ret_pct"] is not None  # bm 이력 존재


def test_analytics_crisis_covid_value_present(full_fixture):
    bt, *_ = full_fixture
    r = asyncio.run(bt.get_strategy_analytics(1))
    crisis = r["crisis"]
    covid = next(c for c in crisis if c["key"] == "covid_2020")
    assert covid["ret_pct"] is not None
    assert covid["note"] is None


def test_analytics_monthly_and_trading_shape(full_fixture):
    bt, *_ = full_fixture
    r = asyncio.run(bt.get_strategy_analytics(1))
    m = r["monthly"]
    assert set(m.keys()) == {"win_rate", "win_rate_vs_bm", "best", "worst"}
    assert m["win_rate"] is not None

    t = r["trading"]
    assert t["n_rebals"] == 4
    assert t["rebals_per_year"] is not None
    assert t["avg_turnover"] is not None
    assert t["cost_drag_pct_10bps"] is not None
    assert t["cost_drag_pct_30bps"] is not None
    # 30bps 드래그가 10bps보다 커야 한다 (같은 부호, 3배 비용 — 각각 독립 반올림되므로 근사)
    assert t["cost_drag_pct_30bps"] == pytest.approx(t["cost_drag_pct_10bps"] * 3, abs=0.005)


# ---------- cost_warning 로직 ----------


def test_analytics_cost_warning_true_when_zero(tmp_path, monkeypatch):
    idx = pd.bdate_range("2024-01-02", periods=260)
    config = {"algorithm": "eq", "rebal_freq": "M", "cost_bps": 0.0, "currency": "KRW"}
    _seed_portfolio(tmp_path, monkeypatch, port_id=1, config=config)
    _seed_nav(tmp_path, 1, idx)
    _seed_rebal(tmp_path, 1, idx, monkeypatch)

    import app.routers.backtest as bt

    _patch_regime(monkeypatch, bt, _phase_series(idx))
    r = asyncio.run(bt.get_strategy_analytics(1))
    assert r["premise"]["cost_warning"] is True


def test_analytics_cost_warning_true_when_config_missing(tmp_path, monkeypatch):
    idx = pd.bdate_range("2024-01-02", periods=260)
    _seed_portfolio(tmp_path, monkeypatch, port_id=1, config=None)
    _seed_nav(tmp_path, 1, idx)
    _seed_rebal(tmp_path, 1, idx, monkeypatch)

    import app.routers.backtest as bt

    _patch_regime(monkeypatch, bt, _phase_series(idx))
    r = asyncio.run(bt.get_strategy_analytics(1))
    assert r["premise"]["cost_warning"] is True
    assert r["premise"]["algorithm"] is None
    assert r["premise"]["cost_bps"] is None


def test_analytics_cost_warning_false_when_positive(tmp_path, monkeypatch):
    idx = pd.bdate_range("2024-01-02", periods=260)
    config = {"algorithm": "eq", "rebal_freq": "M", "cost_bps": 10.0, "currency": "KRW"}
    _seed_portfolio(tmp_path, monkeypatch, port_id=1, config=config)
    _seed_nav(tmp_path, 1, idx)
    _seed_rebal(tmp_path, 1, idx, monkeypatch)

    import app.routers.backtest as bt

    _patch_regime(monkeypatch, bt, _phase_series(idx))
    r = asyncio.run(bt.get_strategy_analytics(1))
    assert r["premise"]["cost_warning"] is False


# ---------- rolling null 이력 부족 ----------


def test_analytics_rolling_null_when_short_history(tmp_path, monkeypatch):
    idx = pd.bdate_range("2024-01-02", periods=100)  # < 252
    config = {"algorithm": "eq", "rebal_freq": "M", "cost_bps": 10.0, "currency": "KRW"}
    _seed_portfolio(tmp_path, monkeypatch, port_id=1, config=config)
    _seed_nav(tmp_path, 1, idx)
    _seed_rebal(tmp_path, 1, idx, monkeypatch)

    import app.routers.backtest as bt

    _patch_regime(monkeypatch, bt, _phase_series(idx))
    r = asyncio.run(bt.get_strategy_analytics(1))
    assert r["rolling"] is None
    assert r["notes"]["rolling"] == f"이력 {len(idx)}일 — 252일 창 미달"
    # 다른 섹션은 여전히 채워진다 — 한 섹션 실패가 전체를 죽이지 않는다
    assert r["premise"] is not None
    assert r["drawdowns"] is not None


# ---------- crisis 미커버 규칙 ----------


def test_analytics_crisis_note_when_history_does_not_cover(tmp_path, monkeypatch):
    idx = pd.bdate_range("2024-01-02", periods=200)  # covid 이후 시작 — 미커버
    config = {"algorithm": "eq", "rebal_freq": "M", "cost_bps": 10.0, "currency": "KRW"}
    _seed_portfolio(tmp_path, monkeypatch, port_id=1, config=config)
    _seed_nav(tmp_path, 1, idx)
    _seed_rebal(tmp_path, 1, idx, monkeypatch)

    import app.routers.backtest as bt

    _patch_regime(monkeypatch, bt, _phase_series(idx))
    r = asyncio.run(bt.get_strategy_analytics(1))
    covid = next(c for c in r["crisis"] if c["key"] == "covid_2020")
    assert covid["ret_pct"] is None
    assert covid["note"]


# ---------- phases degrade ----------


def test_analytics_phases_null_when_regime_fails(tmp_path, monkeypatch):
    idx = pd.bdate_range("2024-01-02", periods=260)
    config = {"algorithm": "eq", "rebal_freq": "M", "cost_bps": 10.0, "currency": "KRW"}
    _seed_portfolio(tmp_path, monkeypatch, port_id=1, config=config)
    _seed_nav(tmp_path, 1, idx)
    _seed_rebal(tmp_path, 1, idx, monkeypatch)

    import app.routers.backtest as bt

    def boom():
        raise RuntimeError("qdata lake unavailable")

    monkeypatch.setattr(bt.regime, "phase_history", boom)
    r = asyncio.run(bt.get_strategy_analytics(1))
    assert r["phases"] is None
    assert r["notes"]["phases"] == "계산 실패"
    # 500 없이 나머지 응답은 정상
    assert r["premise"] is not None
    assert r["monthly"] is not None


# ---------- 공용 로드 격리 (bm_nav/rebal I/O 실패 — 부재와 달리 예외) ----------


def test_analytics_bm_load_failure_isolates_rolling_and_phases(full_fixture, monkeypatch):
    """benchmark_nav가 (부재가 아니라) 예외를 던져도 500이 아니라 dict 응답 —
    bm 의존 필드(rolling.bm_rows, phases[].bm_mean_ret_pct)만 null로 떨어진다."""
    bt, *_ = full_fixture

    def boom(port_id=None):
        raise RuntimeError("S3 timeout")

    monkeypatch.setattr(bt.portfolio, "benchmark_nav", boom)
    r = asyncio.run(bt.get_strategy_analytics(1))

    assert "empty" not in r
    assert r["notes"]["bm"] == "벤치마크 로드 실패 — BM 비교 생략"
    assert r["rolling"] is not None
    assert len(r["rolling"]["rows"]) > 0  # 전략 자체 rolling은 살아있다
    assert r["rolling"]["bm_rows"] is None
    assert r["phases"] is not None
    assert len(r["phases"]["rows"]) > 0
    assert all(row["bm_mean_ret_pct"] is None for row in r["phases"]["rows"])
    # bm과 무관한 섹션은 전부 살아있다 — rolling/phases 자체는 강등되지 않았다
    assert "rolling" not in r["notes"]
    assert "phases" not in r["notes"]
    assert r["premise"] is not None
    assert r["drawdowns"] is not None
    assert r["monthly"] is not None
    assert r["trading"] is not None


def test_analytics_rebal_load_failure_nulls_n_rebals_and_trading(full_fixture, monkeypatch):
    """rebalance()가 예외를 던지면 premise.n_rebals(0과 구분되는 None)와 trading만
    null로 떨어지고, premise의 다른 필드·rebal과 무관한 섹션은 살아있다."""
    bt, *_ = full_fixture

    def boom(port_id=None):
        raise RuntimeError("corrupted parquet")

    monkeypatch.setattr(bt.portfolio, "rebalance", boom)
    r = asyncio.run(bt.get_strategy_analytics(1))

    assert "empty" not in r
    assert r["premise"] is not None
    assert r["premise"]["n_rebals"] is None  # 0(확인된 무리밸)과 구분
    assert r["premise"]["algorithm"] == "momentum"  # 나머지 premise 필드는 살아있다
    assert r["premise"]["bt_start"] is not None
    assert r["trading"] is None
    assert r["notes"]["trading"] == "리밸 이력 로드 실패"
    # rebal과 무관한 섹션은 전부 살아있다
    assert r["rolling"] is not None
    assert r["drawdowns"] is not None
    assert r["phases"] is not None
    assert r["monthly"] is not None


# ---------- live 확장 ----------


def _seed_live_nav(tmp_path, port_id, idx, values):
    df = pd.DataFrame(
        {
            "port_id": port_id,
            "trade_date": idx,
            "value": values,
            "as_of": [str(idx.max().date())] * len(idx),
        }
    )
    _write(tmp_path, "live_nav.parquet", df)


def _seed_live_weights(tmp_path, port_id, rows):
    df = pd.DataFrame(rows)
    df.insert(0, "port_id", port_id)
    _write(tmp_path, "live_weights.parquet", df)


def test_live_weights_filters_to_latest_trade_date(tmp_path, monkeypatch):
    _seed_portfolio(tmp_path, monkeypatch, port_id=1, config=None)
    idx = pd.bdate_range("2024-01-02", periods=5)
    _seed_nav(tmp_path, 1, idx)

    _seed_live_weights(
        tmp_path,
        1,
        [
            {"trade_date": pd.Timestamp("2026-07-30"), "ticker": "AAA", "weight": 0.6},
            {"trade_date": pd.Timestamp("2026-07-30"), "ticker": "BBB", "weight": 0.4},
            {"trade_date": pd.Timestamp("2026-07-31"), "ticker": "AAA", "weight": 0.55},
            {"trade_date": pd.Timestamp("2026-07-31"), "ticker": "BBB", "weight": 0.45},
        ],
    )

    import app.routers.backtest as bt

    r = asyncio.run(bt.get_strategy_live(1))
    assert r["weights"] is not None
    assert {w["trade_date"] for w in r["weights"]} == {"2026-07-31"}
    assert {w["ticker"] for w in r["weights"]} == {"AAA", "BBB"}
    got = {w["ticker"]: w["weight"] for w in r["weights"]}
    assert got["AAA"] == pytest.approx(0.55)


def test_live_weights_absent_is_none_and_existing_fields_intact(tmp_path, monkeypatch):
    _seed_portfolio(tmp_path, monkeypatch, port_id=1, config=None)
    idx = pd.bdate_range("2024-01-02", periods=5)
    _seed_nav(tmp_path, 1, idx)

    import app.routers.backtest as bt

    r = asyncio.run(bt.get_strategy_live(1))
    assert r["weights"] is None
    assert r["expectation"] is None
    # 기존 필드·계약 불변
    assert set(r.keys()) >= {
        "port_id",
        "saved_at",
        "as_of",
        "nav",
        "metrics_live",
        "metrics_backtest",
        "weights",
        "expectation",
    }
    assert r["nav"] == []


def test_live_expectation_present_with_sufficient_history(tmp_path, monkeypatch):
    _seed_portfolio(tmp_path, monkeypatch, port_id=1, config=None)
    bt_idx = pd.bdate_range("2023-01-02", periods=400)
    _seed_nav(
        tmp_path,
        1,
        bt_idx,
        values=pd.Series(1000 * (1.001 ** np.arange(len(bt_idx))), index=bt_idx, dtype="float64"),
    )

    live_idx = pd.bdate_range("2026-07-01", periods=21)
    live_vals = np.linspace(1000, 1050, len(live_idx))
    _seed_live_nav(tmp_path, 1, live_idx, live_vals)

    import app.routers.backtest as bt

    r = asyncio.run(bt.get_strategy_live(1))
    assert r["expectation"] is not None
    exp = r["expectation"]
    assert set(exp.keys()) == {
        "n_days",
        "live_ret_pct",
        "ret_percentile",
        "live_dd_pct",
        "dd_percentile",
    }
    assert exp["n_days"] == len(live_idx) - 1
    assert exp["live_ret_pct"] == pytest.approx(5.0, abs=0.01)


def test_live_expectation_null_when_live_history_too_short(tmp_path, monkeypatch):
    _seed_portfolio(tmp_path, monkeypatch, port_id=1, config=None)
    bt_idx = pd.bdate_range("2023-01-02", periods=400)
    _seed_nav(
        tmp_path,
        1,
        bt_idx,
        values=pd.Series(1000 * (1.001 ** np.arange(len(bt_idx))), index=bt_idx, dtype="float64"),
    )

    live_idx = pd.bdate_range("2026-07-01", periods=3)  # n=2 < 5
    live_vals = np.linspace(1000, 1010, len(live_idx))
    _seed_live_nav(tmp_path, 1, live_idx, live_vals)

    import app.routers.backtest as bt

    r = asyncio.run(bt.get_strategy_live(1))
    assert r["expectation"] is None
