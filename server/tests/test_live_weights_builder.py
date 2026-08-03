"""P7 live_weights 빌더(`scripts/build_insights.py::_book_to_weights`) — 당일 저장
전략의 무증상 weights 소실 방지.

calculate_nav의 book은 매 리밸 구간의 마지막 날을 다음 구간의 리밸 행과
중복되지 않도록 제외한다(iloc[:-1]). 구간이 단 하루뿐이면(오늘 막 저장된
전략 — saved_at == nav 마지막 날) 그 유일한 행마저 지워져 book이 통째로
빈다. `book.index.max()`는 이때 NaT이고, `NaT < nav_last`는 항상 False라
보정 분기가 조용히 스킵되어 nav는 기록되고 weights만 비는 무증상 실패가
난다(2026-08 리뷰 라운드 1 실측). `_book_to_weights`는 이 경우 fallback
비중(리밸 스케줄 마지막 행 — 드리프트 전이라 목표==보유)으로 그 하루를
채우고, fallback도 없으면 경고를 남기고 빈 프레임을 반환한다(조용한 소실
금지).
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

_SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

try:
    import build_insights

    _IMPORT_ERROR = None
except Exception as e:  # 환경 문제(자격증명·의존성 부재 등)는 스킵, 에러 아님
    build_insights = None
    _IMPORT_ERROR = e

from module.util import calculate_nav


def _skip_if_import_failed():
    if build_insights is None:
        pytest.skip(f"build_insights import 실패 (환경 문제): {_IMPORT_ERROR}")


def test_single_day_book_is_empty_by_engine_construction():
    """전제 확인: 구간이 하루뿐이면 calculate_nav의 book이 실제로 통째로 빈다.

    (오늘 막 저장된 전략을 같은 밤 배치가 추적하는 흔한 경우와 동일 조건.)
    """
    idx = pd.bdate_range("2026-07-31", periods=1)
    price = pd.DataFrame({"A": [100.0]}, index=idx)
    weight = pd.DataFrame({"A": [1.0]}, index=[idx[0]])

    book, nav = calculate_nav(weight=weight.copy(), price=price.copy())
    assert book.empty
    assert len(nav) == 1


def test_book_empty_falls_back_to_seed_weights_instead_of_silently_dropping():
    """book이 비어도(당일 저장) fallback_weights가 있으면 그 비중으로 1행이 나온다 —
    이전 버전은 NaT < nav_last가 항상 False라 이 경우 조용히 0행이었다."""
    _skip_if_import_failed()

    idx = pd.bdate_range("2026-07-31", periods=1)
    price = pd.DataFrame({"A": [100.0], "B": [50.0]}, index=idx)
    weight = pd.DataFrame({"A": [0.6], "B": [0.4]}, index=[idx[0]])

    book, nav = calculate_nav(weight=weight.copy(), price=price.copy())
    assert book.empty  # 사전 조건

    fallback = weight.iloc[-1].dropna()
    bw = build_insights._book_to_weights(book, price, 999, nav.index.max(), fallback)

    assert not bw.empty, "fallback이 있는데도 빈 프레임이면 무증상 소실 회귀"
    assert list(bw.columns) == ["port_id", "trade_date", "ticker", "weight"]
    assert set(bw["ticker"]) == {"A", "B"}
    assert (bw["trade_date"] == nav.index.max()).all()
    assert (bw["port_id"] == 999).all()
    got = bw.set_index("ticker")["weight"]
    assert got["A"] == pytest.approx(0.6)
    assert got["B"] == pytest.approx(0.4)


def test_book_empty_fallback_with_cash_remainder_renormalizes_like_book():
    """custom(FixedWeight 등, 현금 잔여를 허용하는) 전략의 폴백은 원시 비중(합<1)
    그대로가 아니라 book과 같은 관례로 투자자산 내 재정규화돼야 한다 — 안 그러면
    엔진 book이 이어받는 다음날부터 비율·합이 인위적으로 점프한다(round 2 리뷰).
    """
    _skip_if_import_failed()

    idx = pd.bdate_range("2026-07-31", periods=1)
    price = pd.DataFrame({"SPY": [100.0], "IEF": [90.0]}, index=idx)
    empty_book = pd.DataFrame(columns=["ticker", "weights"])
    empty_book.index.name = "Date"

    fallback = pd.Series({"SPY": 0.5, "IEF": 0.2})  # 합 0.7 — 현금 30% 잔여
    bw = build_insights._book_to_weights(empty_book, price, 1, idx[0], fallback)

    assert not bw.empty
    got = bw.set_index("ticker")["weight"]
    assert got["SPY"] == pytest.approx(0.5 / 0.7, rel=1e-6)  # 0.714286
    assert got["IEF"] == pytest.approx(0.2 / 0.7, rel=1e-6)  # 0.285714
    assert bw["weight"].sum() == pytest.approx(1.0, rel=1e-6)


def test_book_and_fallback_both_empty_warns_and_returns_empty_frame(capsys):
    """book도 fallback도 없으면 조용히 사라지지 않고 경고를 남긴 뒤 빈 프레임을 낸다."""
    _skip_if_import_failed()

    idx = pd.bdate_range("2026-07-31", periods=1)
    price = pd.DataFrame({"A": [100.0]}, index=idx)
    empty_book = pd.DataFrame(columns=["ticker", "weights"])
    empty_book.index.name = "Date"

    bw = build_insights._book_to_weights(empty_book, price, 999, idx[0], None)

    assert bw.empty
    assert list(bw.columns) == ["port_id", "trade_date", "ticker", "weight"]
    err = capsys.readouterr().err
    assert "live_weights" in err and "999" in err


def test_multi_interval_book_gets_tail_day_correction():
    """리밸이 여러 번 있는 다행(≥2행) 케이스에서도 book 마지막 날짜가 nav보다
    하루 이른 구조적 갭이 재현되고, _book_to_weights가 그 마지막 날을 채운다."""
    _skip_if_import_failed()

    idx = pd.bdate_range("2025-01-01", periods=40)
    a = pd.Series(np.linspace(100, 110, 40), index=idx)
    b = pd.Series(np.linspace(50, 55, 40), index=idx)
    price = pd.DataFrame({"A": a, "B": b})
    weight = pd.DataFrame({"A": [0.6, 0.5], "B": [0.4, 0.5]}, index=[idx[0], idx[20]])

    book, nav = calculate_nav(weight=weight.copy(), price=price.copy())
    assert not book.empty
    assert book.index.max() < nav.index.max()  # 구조적 갭 사전 확인

    fallback = weight.iloc[-1].dropna()
    bw = build_insights._book_to_weights(book, price, 1, nav.index.max(), fallback)

    assert bw["trade_date"].max() == nav.index.max()
    last_day = bw[bw["trade_date"] == nav.index.max()]
    assert set(last_day["ticker"]) == {"A", "B"}
    assert last_day["weight"].sum() == pytest.approx(1.0)
