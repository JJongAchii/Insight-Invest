"""strategy_analytics 순수 계산 — 손계산 픽스처.

낙폭 에피소드 경계(회복일·미회복), 백분위 정의, 턴오버 합산은 틀려도
그럴듯한 숫자가 나오는 지점이다. 전부 손으로 재계산 가능한 픽스처로 못박는다.
"""

import numpy as np
import pandas as pd
import pytest

from module.strategy_analytics import (
    crisis_returns,
    drawdown_episodes,
    live_percentile,
    monthly_returns,
    monthly_stats,
    phase_monthly_means,
    rolling_stats,
    turnover_stats,
)


def _nav(vals, start="2024-01-01") -> pd.Series:
    return pd.Series(vals, index=pd.bdate_range(start, periods=len(vals)), dtype="float64")


def test_drawdown_episodes_boundaries_and_recovery():
    # 100→120(고점)→90(저점,-25%)→121(회복) 그리고 말미 진행 중 낙폭 -10%
    vals = [100, 120, 105, 90, 110, 121, 130, 117]
    eps = drawdown_episodes(_nav(vals), top_n=5)
    assert len(eps) == 2
    e1 = eps[0]  # 깊은 순 정렬 — -25%가 먼저
    assert e1["depth_pct"] == pytest.approx(-25.0)
    assert str(e1["peak"])[:10] == "2024-01-02"  # 120 고점일
    assert str(e1["trough"])[:10] == "2024-01-04"  # 90 저점일
    assert str(e1["recover"])[:10] == "2024-01-08"  # 121 ≥ 120 복귀일
    assert e1["days_to_recover"] == 4  # 고점 다음날부터 회복일까지 거래일 수
    e2 = eps[1]  # 130→117 진행 중
    assert e2["depth_pct"] == pytest.approx(-10.0)
    assert e2["recover"] is None and e2["days_to_recover"] is None


def test_rolling_stats_window_math():
    n = 300
    nav = _nav(list(100 * (1.001 ** np.arange(n))))  # 일 0.1% 복리
    rs = rolling_stats(nav, window=252)
    assert len(rs) == n - 252
    expected = (1.001**252 - 1) * 100
    assert rs["roll_ret"].iloc[0] == pytest.approx(expected, rel=1e-9)
    assert rs["roll_sharpe"].iloc[-1] > 10  # 무변동 양수 드리프트 — 매우 큼 (정확값 불요)


def test_monthly_stats_win_rates():
    # 4개월: +2%, -1%, +3%, -2% → 절대 승률 50%
    idx = pd.bdate_range("2024-01-01", periods=90)
    monthly_mult = {1: 1.02, 2: 0.99, 3: 1.03, 4: 0.98}
    daily = []
    v = 100.0
    prev_month = None
    for d in idx:
        if prev_month is not None and d.month != prev_month:
            v *= monthly_mult.get(prev_month, 1.0)
        prev_month = d.month
        daily.append(v)
    # 간단화: 월내 보합, 월 경계에서 점프 — monthly_returns가 월말 값으로 재현
    nav = pd.Series(daily, index=idx)
    m = monthly_returns(nav)
    st = monthly_stats(nav, None)
    assert st["win_rate"] == pytest.approx((m > 0).mean() * 100)
    assert st["win_rate_vs_bm"] is None
    assert len(st["best"]) <= 5 and len(st["worst"]) <= 5
    st2 = monthly_stats(nav, nav)  # 자기 자신 대비 — 초과 0, 승률 0%
    assert st2["win_rate_vs_bm"] == pytest.approx(0.0)


def test_turnover_stats_hand_math():
    # 리밸 3회: 전액 A → A/B 반반 → 전액 B
    rebal = pd.DataFrame(
        {
            "rebal_date": pd.to_datetime(["2024-01-02", "2024-07-01", "2025-01-02"]),
            "ticker": ["A", "A", "B"],
            "weight": [1.0, 0.5, 1.0],
        }
    )
    rebal = pd.concat(
        [
            rebal,
            pd.DataFrame(
                {"rebal_date": [pd.Timestamp("2024-07-01")], "ticker": ["B"], "weight": [0.5]}
            ),
        ]
    )
    ts = turnover_stats(rebal)
    assert ts["n_rebals"] == 3
    # 턴오버: 1회차 Σ|w|=1.0(전액 매수), 2회차 |0.5-1|+|0.5-0|=1.0, 3회차 |0-0.5|+|1-0.5|=1.0
    assert ts["avg_turnover"] == pytest.approx(1.0)
    assert ts["rebals_per_year"] == pytest.approx(3 / 1.0, rel=0.1)  # 1년 구간 3회


def test_live_percentile_definition():
    # 백테스트: 일 0.1% 복리 500일. 라이브: 20일에 +5% (분포 최상단 → 백분위 ~100)
    bt = _nav(list(100 * (1.001 ** np.arange(500))))
    live = _nav(list(np.linspace(1000, 1050, 21)), start="2026-01-01")
    r = live_percentile(bt, live)
    assert r["n_days"] == 20
    assert r["live_ret_pct"] == pytest.approx(5.0)
    assert r["ret_percentile"] > 99.0
    # 라이브가 고점이면 현재 낙폭 0 → dd 백분위는 정의상 상단
    assert r["live_dd_pct"] == pytest.approx(0.0)


def test_live_percentile_insufficient_history():
    bt = _nav([100, 101, 102])
    live = _nav(list(np.linspace(1000, 1010, 30)), start="2026-01-01")
    assert live_percentile(bt, live) is None


def test_crisis_returns_coverage_rule():
    nav = _nav(list(np.linspace(100, 120, 300)), start="2021-01-01")
    out = crisis_returns(nav, {"covid_2020": ("2020-02-14", "2020-03-23")})
    assert out[0]["ret_pct"] is None and out[0]["note"]
    nav2 = _nav(list(np.linspace(100, 120, 300)), start="2020-01-02")
    out2 = crisis_returns(nav2, {"covid_2020": ("2020-02-14", "2020-03-23")})
    assert out2[0]["ret_pct"] is not None


def test_phase_monthly_means_grouping():
    monthly = pd.Series(
        [1.0, 2.0, -1.0, 3.0],
        index=pd.PeriodIndex(["2024-01", "2024-02", "2024-03", "2024-04"], freq="M"),
    )
    phases = pd.Series(
        ["Goldilocks", "Goldilocks", "Reflation", "Reflation"],
        index=monthly.index,
    )
    out = phase_monthly_means(monthly, phases)
    assert out.loc["Goldilocks", "mean_ret_pct"] == pytest.approx(1.5)
    assert int(out.loc["Reflation", "n_months"]) == 2
