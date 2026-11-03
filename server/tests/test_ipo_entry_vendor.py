"""공모주 진입 규칙 사본 — quant-lab entry-t12-v1 t06과 같은 주문을 낸다(계약 ipo-live-ops v3 II_ENTRY).

- 기준 파일: `tests/fixtures/ipo_entry_t06_orders.csv` — scripts/vendor_ipo_t01.py가 같은 quant-lab 커밋의
  t06 산출(`docs/evidence/runs/entry-t12-v1/t06.json`)에서 만든다. 해시는 VENDOR.json의 entry 절에 있다
- 지정가: 개발 구간 평가 사건 616건에서 운영의 한 행 계산(`ipo_t12.entry_limit_mult`)이 t06의 배수와 같다
- 체결 추정: t06 매수 130건에서 운영의 시가 전용 추정(`ipo_signals.entry_estimate`)이 quant-lab의 체결 상태와 같다
"""

import hashlib
import math
from pathlib import Path

import pandas as pd
import pytest

from module import ipo_signals, ipo_t01, ipo_t12

from ipo_open_entry.entry_t12 import execution  # isort: skip

FIXTURE = Path(__file__).parent / "fixtures" / "ipo_entry_t06_orders.csv"
T12_FIXTURE = Path(__file__).parent / "fixtures" / "ipo_t12_decisions.csv"
VARIANT = {
    "selection": "t12",
    "limit": {"kind": "conviction", "complement": 1.25, "primary": 1.5, "strong": None},
    "fill": "open-only",
}


@pytest.fixture(scope="module")
def t06() -> pd.DataFrame:
    return pd.read_csv(FIXTURE).set_index("event_id")


@pytest.fixture(scope="module")
def t12() -> pd.DataFrame:
    return pd.read_csv(T12_FIXTURE).set_index("event_id")


def test_entry_record_names_the_quant_lab_trial_and_fixture():
    record = ipo_t12.entry_vendor()
    assert record["trial_id"] == "t06" and record["variant"] == VARIANT
    assert record["config_digest"] == "8455ab64e29b" and len(record["trial_commit"]) == 40
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == record["fixture_sha256"]
    rule = ipo_t12.entry_rule()
    assert rule["spec"] == ipo_t12.ENTRY_SPEC == "entry-t12-v1-t06"
    assert rule["fill"] == "open-only" and rule["limit"] == VARIANT["limit"]


def test_entry_keeps_the_t12_buys(t06, t12):
    """진입 규칙은 매수 선택을 바꾸지 않는다 — t06의 매수·보완 매수가 t12와 같다."""
    assert len(t06) == 616 and int(t06["buy"].sum()) == 130
    t12 = t12.loc[t06.index]
    assert t06["buy"].tolist() == t12["buy"].astype(bool).tolist()
    assert t06["additional_buy"].tolist() == t12["additional_buy"].astype(bool).tolist()


def test_one_row_limit_multiple_matches_quant_lab_t06(t06, t12):
    """운영은 결정 한 행으로 배수를 정한다. 616건 전체에서 t06과 같다(보완 1.25배, 1차 1.5배, 패스 없음)."""
    qs = pd.Timestamp("2026-10-01")
    got = []
    for event_id, r in t12.loc[t06.index].iterrows():
        made = {
            "buy": bool(r["buy"]),
            "additional_buy": bool(r["additional_buy"]),
            "score": float(r["score"]),
            "threshold": float(r["threshold"]),
        }
        got.append(ipo_t12.entry_limit_mult(made, qs))
    want = t06["limit_mult"].tolist()
    for g, w in zip(got, want, strict=True):
        assert (g is None and math.isnan(w)) or g == pytest.approx(w)
    assert {g for g in got if g is not None} == {1.25, 1.5}


def test_open_only_estimate_matches_quant_lab_fill_states(t06):
    """t06 매수 130건: 운영의 시가 전용 체결 추정이 quant-lab 산출의 체결 상태(open / unfilled)와 같다.

    같은 사건을 당일 유효 지정가로 추정하면 장중 체결이 생겨 다르다 — 시험에 검출력이 있다.
    """
    data, cfg = ipo_t01.dev_data(), ipo_t01.config()
    engine, rules = ipo_t01.engine, ipo_t01.rules
    events = data["events"].set_index("event_id")
    day0 = data["bars"][data["bars"]["day"] == 0].set_index("event_id")
    tol = float(cfg["execution"]["cap_tolerance"])
    tie = bool(cfg["execution"]["tie_fills"])
    buys = t06[t06["buy"]]
    open_only, gfd = [], []
    for event_id, r in buys.iterrows():
        e = events.loc[event_id]
        limit = engine.limit_price(e.offer_price, e.listing_date, e.market, r["limit_mult"], cfg)
        cap = tol * rules.cap_multiple(e.regime, cfg) * e.offer_price
        args = (engine, day0.loc[event_id, "open"], day0.loc[event_id, "low"], limit, cap, tie)
        open_only.append(ipo_signals.entry_estimate(*args, "open-only")[0])
        gfd.append(ipo_signals.entry_estimate(*args, "gfd")[0])
    want = (buys["fill_state"] == "open").tolist()
    assert open_only == want
    assert sum(want) == 77 and set(buys["fill_state"]) == {"open", "unfilled"}
    assert gfd != want  # 당일 유효 지정가였다면 장중 체결이 더 있다
    # quant-lab의 build_trades(open-only)와도 같다
    orders = buys.reset_index()[["event_id", "buy", "limit_mult"]]
    trades = execution.build_trades(
        data["events"],
        data["bars"],
        orders,
        {**cfg, "execution": {**cfg["execution"], "horizons": [2]}},
        "open-only",
    )
    filled = trades.set_index("event_id").loc[buys.index, "filled"].astype(bool).tolist()
    assert filled == want
