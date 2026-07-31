"""spotlight 선정 로직 — 픽스처 패널 단위 테스트.

조건 경계(0.98·streak>=10·ret_20d<-5)가 build_signal_study와 같은지,
hold_days가 마지막 연속 구간만 세는지, 상한·also_in이 맞는지 못박는다.
틀려도 에러가 나지 않고 그럴듯한 종목이 나오는 지점이라 테스트가 필수다.
"""

import json

import numpy as np
import pandas as pd
import pytest

from module.spotlight import CAP_PER_GROUP, near_high_state, select_spotlight


def _panel(values: dict) -> pd.DataFrame:
    n = len(next(iter(values.values())))
    return pd.DataFrame(values, index=pd.bdate_range("2024-01-02", periods=n))


def test_near_high_state_boundary():
    n = 260
    steady = [100.0] * n  # 계속 신고가 → 포함
    below = [100.0] * (n - 1) + [97.9]  # 0.98 문턱 밑 → 제외
    exact = [100.0] * (n - 1) + [98.0]  # 정확히 0.98 → 포함 (빌더의 >= 와 동일)
    df = near_high_state(_panel({"A": steady, "B": below, "C": exact}))
    assert "A" in df.index and "C" in df.index
    assert "B" not in df.index
    assert df.loc["C", "dist_pct"] == pytest.approx(-2.0)


def test_near_high_state_counts_trailing_run_only():
    n = 260
    vals = [100.0] * (n - 3) + [90.0, 100.0, 100.0]  # 중간 이탈 후 복귀 → 마지막 연속 2일
    df = near_high_state(_panel({"A": vals}))
    assert df.loc["A", "hold_days"] == 2


def test_near_high_state_requires_min_periods():
    # 유효 관측 199일 — rolling max가 NaN이라 상태가 성립하지 않는다 (min_periods=200)
    short = [np.nan] * 61 + [100.0] * 199
    df = near_high_state(_panel({"A": short}))
    assert "A" not in df.index


_FLOW_COLS = [
    "ticker",
    "name",
    "market",
    "close",
    "chg_pct",
    "mktcap",
    "streak",
    "intensity_20d",
    "ret_20d",
    "divergence",
]


def _flows_fixture() -> pd.DataFrame:
    rows = [
        ["000001", "매집A", "KOSPI", 1000.0, -1.0, 2e10, 3, 1.5, -6.0, "bull"],
        ["000002", "경계B", "KOSPI", 1000.0, 0.0, 2e10, 2, 0.5, -5.0, "bull"],  # -5.0 → 제외
        ["000003", "연속C", "KOSDAQ", 500.0, 0.5, 3e10, 12, 0.8, 2.0, None],
        ["000004", "연속D", "KOSPI", 700.0, 0.2, 4e10, 10, 0.1, 1.0, None],  # 10 → 포함
        ["000005", "짧은E", "KOSPI", 700.0, 0.2, 4e10, 9, 0.1, 1.0, None],  # 9 → 제외
        ["000006", "고점F", "KOSPI", 900.0, 0.1, 5e10, 11, 0.2, 8.0, None],  # 신고가∩연속매수
        ["000007", "고점G", "KOSDAQ", 800.0, 0.3, 1e10, 1, 0.0, 5.0, None],
    ]
    return pd.DataFrame(rows, columns=_FLOW_COLS)


def _near_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {"dist_pct": [-0.5, -1.9], "hold_days": [30, 3]}, index=["000006", "000007"]
    )


def test_select_boundaries_ordering_membership():
    df, dropped = select_spotlight(_flows_fixture(), _near_fixture())
    by = dict(tuple(df.groupby("signal_type")))

    assert list(by["bull_divergence"]["ticker"]) == ["000001"]  # ret_20d == -5.0은 제외
    # streak desc: C(12) > F(11) > D(10). E(9)는 제외
    assert list(by["frgn_streak10"]["ticker"]) == ["000003", "000006", "000004"]
    # hold_days desc: F(30) > G(3)
    assert list(by["near_52w_high_hold"]["ticker"]) == ["000006", "000007"]

    f_near = by["near_52w_high_hold"].set_index("ticker").loc["000006"]
    assert json.loads(f_near["also_in"]) == ["frgn_streak10"]
    f_streak = by["frgn_streak10"].set_index("ticker").loc["000006"]
    assert json.loads(f_streak["also_in"]) == ["near_52w_high_hold"]
    assert dropped == {}


def test_select_caps_and_reports_dropped():
    f = _flows_fixture()
    extra = pd.DataFrame(
        [
            [f"9{i:05d}", f"연속{i}", "KOSPI", 100.0, 0.0, 2e10, 20 + i, 0.5, 1.0, None]
            for i in range(8)
        ],
        columns=_FLOW_COLS,
    )
    df, dropped = select_spotlight(pd.concat([f, extra], ignore_index=True), _near_fixture())
    streak = df[df["signal_type"] == "frgn_streak10"]
    assert len(streak) == CAP_PER_GROUP
    assert dropped["frgn_streak10"] == 6  # 후보 11(기존 3 + 추가 8) - 상한 5


def test_select_with_no_near_high_candidates():
    empty = pd.DataFrame(columns=["dist_pct", "hold_days"])
    df, _ = select_spotlight(_flows_fixture(), empty)
    assert "near_52w_high_hold" not in set(df["signal_type"])
    assert {"hold_days", "dist_pct", "also_in"} <= set(df.columns)
