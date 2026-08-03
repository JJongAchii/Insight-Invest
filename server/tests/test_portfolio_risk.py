"""portfolio_risk 순수 계산 — 손계산 픽스처 검증.

고정비중 포트 수익률·MDD·시나리오 윈도우는 틀려도 에러 없이 그럴듯한
숫자가 나오는 지점이다. 2종목 50:50 손계산과 대조해 못박는다.
"""

import numpy as np
import pandas as pd
import pytest

from module.portfolio_risk import MIN_OVERLAP_DAYS, build_report, clean_panel


def _panel(values: dict, start="2022-01-03") -> pd.DataFrame:
    n = len(next(iter(values.values())))
    return pd.DataFrame(values, index=pd.bdate_range(start, periods=n))


def test_two_asset_hand_math():
    # A: +10% 후 보합, B: 보합 후 -10% → 50:50 rp = [+5%, -5%]
    p = _panel({"A": [100.0, 110.0, 110.0], "B": [100.0, 100.0, 90.0]})
    r = build_report(p, {"A": 0.5, "B": 0.5})
    # 검증엔 MIN_OVERLAP 미달이지만 로직 검증용으로 임계 우회
    assert r.get("insufficient")  # 기본 임계에서는 생략된다

    r = build_report(p, {"A": 0.5, "B": 0.5}, min_overlap=2)
    # rp = [0.05, -0.05]; NAV = [1.05, 0.9975]; MDD = 0.9975/1.05-1 = -5%
    assert r["max_drawdown"] == pytest.approx(-5.0, rel=1e-6)
    # ann_vol = std([0.05,-0.05], ddof=1) * sqrt(252) * 100
    expected_vol = float(np.std([0.05, -0.05], ddof=1) * np.sqrt(252) * 100)
    assert r["ann_vol"] == pytest.approx(expected_vol, rel=1e-9)
    assert r["mdd_from"] < r["mdd_to"]
    # 2관측 상관은 ±1로 퇴화한다 — 이 픽스처는 두 종목 모두 평균 위→아래로
    # 같이 움직이므로 +1 (개별 수익률의 부호가 아니라 평균 대비 방향이 결정)
    assert r["avg_pair_corr"] == pytest.approx(1.0, rel=1e-9)
    assert r["corr"].shape == (2, 2)


def test_single_asset_skips_corr():
    p = _panel({"A": list(np.linspace(100, 130, 80))})
    r = build_report(p, {"A": 1.0}, min_overlap=10)
    assert r["corr"] is None and r["avg_pair_corr"] is None
    assert r["ann_vol"] is not None


def test_worst_window_finds_injected_crash():
    # 250일 보합 + 중간 20일 연속 -2% 구간 주입
    rets = [0.0] * 100 + [-0.02] * 20 + [0.0] * 130
    prices = 100 * np.cumprod([1.0] + [1 + x for x in rets[1:]])
    p = _panel({"A": list(prices), "B": list(prices)})
    r = build_report(p, {"A": 0.5, "B": 0.5}, min_overlap=10)
    worst20 = next(s for s in r["scenarios"] if s["key"] == "worst_20d")
    assert worst20["ret_pct"] == pytest.approx(((0.98**20) - 1) * 100, rel=1e-6)
    # 최악 구간의 끝은 주입 구간 안이다
    assert p.index[100] <= pd.Timestamp(worst20["end"]) <= p.index[125]


def test_crisis_window_requires_full_coverage():
    # 2021년 시작 이력 → covid_2020 계산 불가 (null + note)
    p = _panel(
        {"A": list(np.linspace(100, 120, 300)), "B": list(np.linspace(50, 60, 300))},
        start="2021-01-04",
    )
    r = build_report(p, {"A": 0.5, "B": 0.5}, min_overlap=10)
    covid = next(s for s in r["scenarios"] if s["key"] == "covid_2020")
    assert covid["ret_pct"] is None and covid["note"]


def test_crisis_window_computed_when_covered():
    idx = pd.bdate_range("2019-06-03", periods=400)
    a = pd.Series(100.0, index=idx)
    # covid 구간에만 매일 -1%
    win = (idx >= "2020-02-14") & (idx <= "2020-03-23")
    daily = np.where(win, 0.99, 1.0)
    a = pd.Series(100 * np.cumprod(daily), index=idx)
    p = pd.DataFrame({"A": a, "B": a})
    r = build_report(p, {"A": 0.5, "B": 0.5}, min_overlap=10)
    covid = next(s for s in r["scenarios"] if s["key"] == "covid_2020")
    n_win = int(win.sum())
    assert covid["ret_pct"] == pytest.approx(((0.99**n_win) - 1) * 100, rel=1e-6)


def test_clean_panel_trims_leading_and_ffills_frozen():
    # B는 늦게 상장(선두 NaN), C는 중간에 동결(후행 NaN → ffill로 0수익)
    a = list(np.linspace(100, 110, 100))
    b = [np.nan] * 30 + list(np.linspace(50, 55, 70))
    c = list(np.linspace(200, 210, 60)) + [np.nan] * 40
    p = clean_panel(_panel({"A": a, "B": b, "C": c}))
    assert p.index[0] == _panel({"A": a}).index[30]  # 공통 시작 = B 상장일
    assert not p.isna().any().any()  # 동결 구간은 ffill로 채워짐
    assert p["C"].iloc[-1] == p["C"].iloc[-41]  # 동결 가격 평탄화 (경고는 라우터 몫)
