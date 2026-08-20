"""수익률 산출의 신호일·체결일 계약 회귀 테스트."""

import asyncio
import os
import sys

import numpy as np
import pandas as pd
import pytest

_SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import build_insights as bi  # noqa: E402

from app.routers import backtest as backtest_router  # noqa: E402
from app.routers import insight  # noqa: E402
from module import backtest as backtest_module  # noqa: E402
from module import signal_stats  # noqa: E402
from module.strategy import Momentum  # noqa: E402


def test_forward_return_enters_next_open_and_holds_exact_horizon():
    dates = pd.bdate_range("2026-08-03", periods=5)
    adjusted_open = pd.DataFrame(
        {"AAA": [100.0, 90.0, 99.0, 108.9, 119.79]},
        index=dates,
    )

    out = bi._forward_open_returns(adjusted_open, 1)

    # D=8/3 신호는 당일 100이 아니라 D+1의 90에 진입해 D+2의 99에 청산한다.
    assert out.loc[dates[0], "AAA"] == pytest.approx(10.0)
    assert out.loc[dates[1], "AAA"] == pytest.approx(10.0)
    assert out.loc[dates[2], "AAA"] == pytest.approx(10.0)
    assert out.iloc[-2:].isna().all().all()


def test_forward_return_requires_positive_horizon():
    with pytest.raises(ValueError, match="양수"):
        bi._forward_open_returns(pd.DataFrame({"AAA": [1.0, 2.0]}), 0)


def test_factor_scores_do_not_change_when_future_tail_is_perturbed():
    """여러 조기 경계에서 미래 꼬리를 바꿔도 과거 팩터 점수는 같아야 한다.

    긴 패널이 아닌 날짜×종목 wide frame의 순수 점수 함수에 적용한다. 횡단면 rank는
    같은 날짜 안에서만 계산하므로 별도로 시간축 전방 참조가 없음을 확인한다.
    """
    rng = np.random.default_rng(7)
    dates = pd.bdate_range("2025-01-02", periods=320)
    columns = ["AAA", "BBB", "CCC"]
    price = pd.DataFrame(
        100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, (len(dates), len(columns))), axis=0)),
        index=dates,
        columns=columns,
    )
    market_cap = price * pd.Series({"AAA": 1e8, "BBB": 2e8, "CCC": 3e8})
    per = pd.DataFrame(10.0, index=dates, columns=columns)
    original = bi._factor_scores(price, market_cap, per)

    for cut in (5, 22, 61, 253, 300):
        changed = price.copy()
        changed.iloc[cut:] = changed.iloc[cut:].iloc[::-1].to_numpy() * -5.0
        changed_cap = market_cap.copy()
        changed_cap.iloc[cut:] = changed_cap.iloc[cut:].iloc[::-1].to_numpy() * 5.0
        changed_per = per.copy()
        changed_per.iloc[cut:] = changed_per.iloc[cut:].iloc[::-1].to_numpy() * 5.0
        rebuilt = bi._factor_scores(changed, changed_cap, changed_per)
        for factor in bi.FACTOR_NAMES:
            pd.testing.assert_frame_equal(
                original[factor].iloc[:cut],
                rebuilt[factor].iloc[:cut],
                check_exact=False,
                rtol=1e-12,
                atol=1e-12,
            )


def test_return_artifact_contract_is_explicit():
    assert bi.PRICE_RETURN_BASIS == "split_adjusted_price_return_ex_cash_distributions"
    assert "entry_open_D+1" in bi.NEXT_OPEN_EXECUTION_RULE
    assert bi.FACTOR_EXECUTION_RULE.endswith("exit_open_D+2")
    assert bi.RETURN_CALCULATION_VERSION.endswith("v2")


def test_legacy_same_close_study_is_hidden_until_v2_rebuild(monkeypatch):
    legacy = pd.DataFrame({"signal_type": ["baseline"], "horizon": [20], "median_excess": [0.0]})
    monkeypatch.setattr(signal_stats.storage, "read_parquet", lambda *_args, **_kwargs: legacy)

    assert signal_stats.load_study() is None


def test_current_study_version_is_accepted(monkeypatch):
    current = pd.DataFrame(
        {
            "signal_type": ["baseline"],
            "horizon": [20],
            "median_excess": [0.0],
            "calculation_version": [bi.RETURN_CALCULATION_VERSION],
        }
    )
    monkeypatch.setattr(signal_stats.storage, "read_parquet", lambda *_args, **_kwargs: current)

    assert signal_stats.load_study() is current


def test_factor_api_hides_mixed_or_legacy_artifacts(monkeypatch):
    legacy_current = pd.DataFrame(
        {"factor": ["momentum"], "ret_1d": [1.0], "as_of": ["2026-08-20"]}
    )
    current_history = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-08-18"]),
            "factor": ["momentum"],
            "cum_index": [100.0],
            "as_of": ["2026-08-20"],
            "calculation_version": [bi.RETURN_CALCULATION_VERSION],
        }
    )
    monkeypatch.setattr(
        insight,
        "_read",
        lambda name, **_kwargs: (
            legacy_current if name == "factor_current.parquet" else current_history
        ),
    )

    out = asyncio.run(insight.get_factors())

    assert out["current"] == []
    assert out["history"] == []
    assert out["status"] == "rebuild_required_or_unavailable"


def test_general_backtest_rejects_mixed_return_bases(monkeypatch):
    mapping = pd.DataFrame(
        {
            "meta_id": [1, 2],
            "ticker": ["SPY", "005930"],
            "iso_code": ["US", "KR"],
        }
    )
    monkeypatch.setattr(backtest_module.datastore.meta, "resolve", lambda **_kwargs: mapping)

    def read_price_data(iso_code, **_kwargs):
        row = {
            "trade_date": pd.Timestamp("2026-08-20"),
            "ticker": "SPY" if iso_code == "US" else "005930",
            "adj_close": 100.0,
        }
        if iso_code == "KR":
            row["return_basis"] = bi.PRICE_RETURN_BASIS
        return pd.DataFrame([row])

    monkeypatch.setattr(backtest_module.datastore, "read_price_data", read_price_data)

    with pytest.raises(backtest_module.ReturnBasisMismatchError, match="혼합할 수 없습니다"):
        backtest_module.Backtest().data(meta_id=[1, 2])


def test_general_backtest_rejects_partially_missing_requested_assets(monkeypatch):
    mapping = pd.DataFrame(
        {
            "meta_id": [1, 2],
            "ticker": ["SPY", "MISSING"],
            "iso_code": ["US", "US"],
        }
    )
    monkeypatch.setattr(backtest_module.datastore.meta, "resolve", lambda **_kwargs: mapping)
    monkeypatch.setattr(
        backtest_module.datastore,
        "read_price_data",
        lambda **_kwargs: pd.DataFrame(
            {
                "trade_date": pd.to_datetime(["2026-08-20"]),
                "ticker": ["SPY"],
                "adj_close": [100.0],
            }
        ),
    )

    with pytest.raises(backtest_module.MissingPriceCoverageError, match="MISSING"):
        backtest_module.Backtest().data(meta_id=[1, 2])


def test_general_backtest_rejects_ids_missing_from_asset_master(monkeypatch):
    mapping = pd.DataFrame(
        {
            "meta_id": [1],
            "ticker": ["SPY"],
            "iso_code": ["US"],
        }
    )
    monkeypatch.setattr(backtest_module.datastore.meta, "resolve", lambda **_kwargs: mapping)

    with pytest.raises(backtest_module.MissingPriceCoverageError, match="999"):
        backtest_module.Backtest().data(meta_id=[1, 999])


def test_general_backtest_rejects_tickers_missing_from_asset_master(monkeypatch):
    mapping = pd.DataFrame(
        {
            "meta_id": [1],
            "ticker": ["SPY"],
            "iso_code": ["US"],
        }
    )
    monkeypatch.setattr(backtest_module.datastore.meta, "resolve", lambda **_kwargs: mapping)

    with pytest.raises(backtest_module.MissingPriceCoverageError, match="UNKNOWN"):
        backtest_module.Backtest().data(tickers=["SPY", "UNKNOWN"])


def test_momentum_weights_ignore_execution_day_and_future_prices():
    rng = np.random.default_rng(19)
    dates = pd.bdate_range("2023-01-02", periods=700)
    columns = ["AAA", "BBB", "CCC", "DDD"]
    prices = pd.DataFrame(
        100.0 * np.exp(np.cumsum(rng.normal(0.0002, 0.01, (len(dates), len(columns))), axis=0)),
        index=dates,
        columns=columns,
    )
    strategy = Momentum(top_n=2, lookback_months=6)
    original = strategy.simulate(prices, freq="M")
    execution_date = original.index[len(original) // 2]

    changed = prices.copy()
    changed.loc[execution_date:] = changed.loc[execution_date:] * np.array([10.0, 0.1, 5.0, 0.2])
    rebuilt = strategy.simulate(changed, freq="M")

    pd.testing.assert_series_equal(
        original.loc[execution_date],
        rebuilt.loc[execution_date],
        check_names=False,
    )
    contract = backtest_router._execution_contract("momentum", bi.PRICE_RETURN_BASIS)
    assert contract["signal_rule"] == "data_through_previous_session_close"
    assert contract["execution_price"] == "close"
