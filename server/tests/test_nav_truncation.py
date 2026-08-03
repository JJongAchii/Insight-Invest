"""혼합 유니버스 시세 단절 시 NAV 거짓 급락 방지 — 공통 이력 절단.

US 아카이브 동결(2025-12-12)로 일부 자산의 시세가 중간에 끊기면
calculate_nav의 NaN-skip 합산이 그 자산 가치를 0으로 만들어, NAV가 동결
비중만큼 하루 만에 거짓 급락한다 (2026-08 실측: 동결 3/4 유니버스 -75.1%).
패널을 전 컬럼 공통 마지막 날짜로 절단하면 커브가 짧게 끝날 뿐 거짓말하지
않는다.
"""

import numpy as np
import pandas as pd

from module.util import calculate_nav, truncate_to_common_history


def _panel():
    idx = pd.bdate_range("2025-11-03", periods=60)
    a = pd.Series(100.0, index=idx)  # 끝까지 존재
    b = pd.Series(100.0, index=idx)
    b.iloc[30:] = np.nan  # 30일째부터 동결 (시세 단절)
    return pd.DataFrame({"A": a, "B": b})


def test_truncate_ends_at_common_last_date():
    p = truncate_to_common_history(_panel())
    assert len(p) == 30
    assert not p.isna().any().any()


def test_truncate_noop_on_full_panel():
    idx = pd.bdate_range("2025-11-03", periods=20)
    p = pd.DataFrame({"A": np.linspace(1, 2, 20), "B": np.linspace(3, 4, 20)}, index=idx)
    assert truncate_to_common_history(p).equals(p)


def test_truncate_all_nan_returns_empty():
    idx = pd.bdate_range("2025-11-03", periods=5)
    p = pd.DataFrame({"A": [np.nan] * 5}, index=idx)
    assert truncate_to_common_history(p).empty


def test_nav_ends_honestly_when_held_asset_freezes():
    """보유 자산 시세가 끊기면 NAV가 급락하는 대신 커브가 거기서 끝난다."""
    price = _panel()
    weight = pd.DataFrame({"A": [0.5], "B": [0.5]}, index=[price.index[0]])

    _, nav = calculate_nav(weight=weight.copy(), price=price.copy())
    worst = nav["value"].pct_change().min()
    assert worst > -0.05  # 보합 가격 — 동결 비중(50%) 거짓 급락이 없어야 한다
    assert nav.index.max() == price["B"].last_valid_index()  # 커브는 단절 시점에 종료


def test_nav_unaffected_by_unheld_frozen_column():
    """미보유 유니버스 자산의 시세 단절은 커브를 자르지 않는다."""
    price = _panel()
    price["C"] = 100.0  # 전 기간 존재하는 자산 둘만 보유
    weight = pd.DataFrame({"A": [0.5], "C": [0.5]}, index=[price.index[0]])

    _, nav = calculate_nav(weight=weight.copy(), price=price.copy())
    assert nav.index.max() == price.index.max()  # B의 동결과 무관하게 끝까지
    assert nav["value"].pct_change().min() > -0.05
