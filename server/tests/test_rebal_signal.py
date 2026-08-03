"""리밸 전일 신호 순수 로직 — 엔진 동일성 앵커가 핵심.

next_period_weights가 Momentum.simulate의 같은 날짜 행과 정확히 일치해야
신호가 백테스트와 같은 숫자다. 어긋나면 '내일 살 종목'이 거짓이 된다.
"""

import numpy as np
import pandas as pd
import pytest

from module.rebal_signal import (
    classify_actions,
    is_new_period,
    next_business_day,
    next_period_weights,
)
from module.strategy import Momentum


def test_next_business_day_skips_weekend():
    assert next_business_day(pd.Timestamp("2026-02-27")) == pd.Timestamp("2026-03-02")  # 금→월
    assert next_business_day(pd.Timestamp("2026-03-03")) == pd.Timestamp("2026-03-04")  # 화→수


@pytest.mark.parametrize(
    "as_of,nxt,freq,expected",
    [
        ("2026-02-27", "2026-03-02", "M", True),  # 월말 금 → 새 달 월요일
        ("2026-03-10", "2026-03-11", "M", False),  # 월중
        ("2026-02-27", "2026-03-02", "Q", False),  # 2월→3월은 같은 1분기
        ("2026-03-31", "2026-04-01", "Q", True),  # 분기 경계
        ("2026-12-31", "2027-01-01", "Y", True),  # 연 경계
        ("2026-06-30", "2026-07-01", "Y", False),
    ],
)
def test_is_new_period(as_of, nxt, freq, expected):
    assert is_new_period(pd.Timestamp(as_of), pd.Timestamp(nxt), freq) is expected


def _drift_panel(n=420, cols=4) -> pd.DataFrame:
    # 결정적 패널 — 열마다 다른 드리프트로 모멘텀 순위가 뚜렷함 (난수 금지)
    idx = pd.bdate_range("2023-01-02", periods=n)
    data = {f"T{i}": 100.0 * np.power(1.0 + 0.0004 * (i + 1), np.arange(n)) for i in range(cols)}
    return pd.DataFrame(data, index=idx)


def test_momentum_engine_identity_anchor():
    """simulate가 마지막 리밸일에 만든 행 == 그 전일까지 가격으로 산출한 신호."""
    price = _drift_panel()
    sim = Momentum(top_n=2, lookback_months=6).simulate(price=price, freq="M")
    last_date = sim.index[-1]
    trunc = price.loc[: last_date - pd.Timedelta(days=1)]
    mine = next_period_weights(trunc, "momentum", {"top_n": 2, "lookback_months": 6})
    row = sim.loc[last_date].dropna()
    assert set(mine) == set(row.index)
    for t, w in mine.items():
        assert w == pytest.approx(float(row[t]), rel=1e-12)


def test_dual_mmt_ignores_params_like_engine():
    """Backtest.rebalance는 dual_mmt에서 params를 무시하고 4/12 고정 — 동일해야 한다."""
    price = _drift_panel(cols=6)
    a = next_period_weights(price, "dual_mmt", {"top_n": 2, "lookback_months": 3})
    b = next_period_weights(price, "momentum", {"top_n": 4, "lookback_months": 12})
    assert a == b


def test_eq_and_custom_weights():
    price = _drift_panel(cols=3)  # columns T0, T1, T2
    eq = next_period_weights(price, "eq", None)
    assert eq == {t: pytest.approx(1 / 3) for t in price.columns}
    cw = next_period_weights(price, "custom", {"weights": {"T0": 0.6, "NOT_IN_PANEL": 0.4}})
    # FixedWeight.simulate와 동일 — 패널 밖 티커는 엔진이 절대 보유하지 않는다.
    assert cw == {"T0": 0.6}


def test_quarterly_rebal_needs_longer_panel():
    """Critical #1: 400일 고정 워밍업은 분기 리밸의 12개월 룩백(13개 월말)을
    못 채워 prev가 조용히 비고 전량 '진입'으로 오표시됐다. 주기별 창 확장
    (build_insights.build_rebal_signals의 extra={"Q":120,"Y":420})으로 고쳤다 —
    이 테스트는 그 산술이 실제로 필요함을 pure 계층에서 문서화한다(빌더 미호출).

    ~275거래일(≈13개월) 패널은 분기 리밸 시점에 룩백을 못 채워 빈 프레임을
    내고(예전 400일 워밍업의 실패 모드), ~420거래일(≈20개월) 패널은 채운다.
    """
    short_panel = _drift_panel(n=275)
    empty = Momentum(top_n=2, lookback_months=12).simulate(price=short_panel, freq="Q")
    assert empty.empty

    long_panel = _drift_panel(n=420)
    nonempty = Momentum(top_n=2, lookback_months=12).simulate(price=long_panel, freq="Q")
    assert not nonempty.empty


def test_classify_actions_enter_exit_keep():
    prev = {"A": 0.5, "B": 0.5}
    target = {"A": 0.7, "C": 0.3}
    rows = classify_actions(prev, target)
    by = {r["ticker"]: r for r in rows}
    assert by["A"]["action"] == "keep" and by["A"]["prev_weight"] == 0.5
    assert by["C"]["action"] == "enter" and by["C"]["prev_weight"] == 0.0
    assert (
        by["B"]["action"] == "exit" and by["B"]["target_weight"] == 0.0 and by["B"]["rank"] is None
    )
    # rank는 target 비중 내림차순 1..N
    assert by["A"]["rank"] == 1 and by["C"]["rank"] == 2
