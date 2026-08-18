"""phase_history 발표 시차 가드 — CLI·CPI 모두 참조월+1로 배치되는지.

CPI가 참조월 그대로 붙으면 국면이 실제 발표보다 2~6주 먼저 바뀌어 보인다
(look-ahead). 레짐 페이지·브리핑·attention 매크로 경보가 전부 이 함수를
읽으므로, 시차 회귀는 조용히 전 화면에 퍼진다 — 여기서 못박는다.
"""

import pandas as pd
from module import regime


def _monthly(vals, start="2020-01-31") -> pd.Series:
    idx = pd.date_range(start, periods=len(vals), freq="ME")
    return pd.Series(vals, index=idx, dtype="float64")


def test_phase_uses_lagged_cli_and_cpi(monkeypatch):
    n = 40
    # CLI 계속 상승 → growth_up 고정 True. 물가 축만 국면을 가른다.
    cli = _monthly([100.0 + i for i in range(n)])
    # CPI는 마지막 참조월에만 급등 → YoY delta가 그 달에만 양전.
    cpi = _monthly([100.0] * (n - 1) + [130.0])
    monkeypatch.setattr(regime, "_cli", lambda country="USA": cli)
    monkeypatch.setattr(regime, "_cpi", lambda: cpi)
    monkeypatch.setattr(regime, "PHASE_START", "2021-01")

    df = regime.phase_history()
    last_ref = pd.Period(cpi.index[-1], freq="M")  # CPI 급등의 참조월

    # 발표 시차: 참조월 데이터는 참조월+1 행에 반영돼야 한다 (CLI와 동일 규약)
    assert df.index.max() == last_ref + 1
    assert bool(df.loc[last_ref + 1, "inflation_up"])
    # 참조월 자체의 행은 급등을 아직 모른다 (그 시점엔 미발표)
    assert not bool(df.loc[last_ref, "inflation_up"])


def test_risk_gauge_exposes_component_dates_and_uses_slowest(monkeypatch):
    daily = pd.bdate_range("2026-07-01", periods=130)
    monthly = pd.date_range("2024-01-31", periods=24, freq="ME")
    fred = {
        "T10Y2Y": pd.Series(range(len(daily)), index=daily, dtype="float64"),
        "BAMLH0A0HYM2": pd.Series([3.0], index=[daily[-1]]),
        "VIXCLS": pd.Series(range(len(daily)), index=daily, dtype="float64"),
        "UNRATE": pd.Series(range(len(monthly)), index=monthly, dtype="float64"),
    }
    hyg_ief = pd.DataFrame(
        {"HYG": range(100, 100 + len(daily)), "IEF": range(90, 90 + len(daily))},
        index=daily,
        dtype="float64",
    )
    monkeypatch.setattr(regime, "_fred", lambda key: fred[key])
    monkeypatch.setattr(regime, "_hyg_ief", lambda: hyg_ief)

    out = regime.risk_gauge()

    assert all(component["as_of"] for component in out["components"])
    assert out["as_of"] == monthly[-1].strftime("%Y-%m-%d")
