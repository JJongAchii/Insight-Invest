"""공모주 신호·보유 산출 — 가짜 qdata로 결정 기록·체결 추정·매도 예정·상태를 확인한다."""

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from datastore import storage
from module import ipo_signals, ipo_t01

KST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime(2026, 11, 2, 22, 20, tzinfo=KST)  # 월요일 밤 배치 — 다음 거래일 11/3
SESSIONS = pd.bdate_range("2026-10-20", "2026-11-13")


class FakeApi:
    def __init__(self, last: str, schedule: pd.DataFrame, events: pd.DataFrame, prices=None):
        self.last = pd.Timestamp(last)
        self.sched = schedule
        self.events = events
        self.prices = (
            prices
            if prices is not None
            else pd.DataFrame(columns=["date", "ticker", *ipo_t01.PRICE_COLUMNS])
        )

    def load_krx_index_prices(self, start, codes):
        days = SESSIONS[(SESSIONS >= pd.Timestamp(start)) & (SESSIONS <= self.last)]
        return pd.DataFrame(
            [{"date": d, "index_code": c, "close": 900.0} for d in days for c in codes]
        )

    def load_ipo_schedule(self, start=None, end=None):
        s = self.sched
        return s[s["planned_listing_date"] >= pd.Timestamp(start)] if start else s

    def load_ipo_events(self):
        return self.events

    def load_krx_prices(self, start, end, tickers, columns):
        p = self.prices
        m = p["ticker"].isin(tickers) & p["date"].between(pd.Timestamp(start), pd.Timestamp(end))
        return p[m].reset_index(drop=True)


def _schedule(rows):
    return pd.DataFrame(
        [
            {
                "event_id": e,
                "corp_name": n,
                "stock_code": t,
                "market": "KOSDAQ",
                "listing_type": "ipo",
                "status": "completed",
                "planned_listing_date": pd.Timestamp(d),
                "planned_rcept_no": f"R{e}",
                "planned_filed_date": pd.Timestamp(d) - pd.Timedelta(days=5),
                "final_price": 10_000.0,
                "final_price_filed_date": pd.Timestamp(d) - pd.Timedelta(days=10),
                "listing_date": pd.NaT,
            }
            for e, n, t, d in rows
        ]
    )


def _events(rows):
    return pd.DataFrame(
        [{"event_id": e, "stock_code": t, "listing_date": pd.Timestamp(d) if d else pd.NaT}
         for e, t, d in rows]  # fmt: skip
    )


def _bars(ticker, start, opens, lows, closes):
    days = SESSIONS[SESSIONS >= pd.Timestamp(start)][: len(opens)]
    return pd.DataFrame(
        {
            "date": days,
            "ticker": ticker,
            "open": opens,
            "high": np.maximum(opens, closes) * 1.02,
            "low": lows,
            "close": closes,
        }
    )


@pytest.fixture
def app_data(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    return tmp_path


def _decided(event_id, listing, buy=True, limit=15_000.0):
    return {
        "event_id": event_id,
        "corp_name": event_id,
        "market": "KOSDAQ",
        "listing_date": listing,
        "status": "decided",
        "buy": buy,
        "regime": "R2",
        "offer_price": 10_000.0,
        "order": {"buy": buy, "limit_mult": 1.5 if buy else None,
                  "limit_price": limit if buy else None},  # fmt: skip
        "score": 0.1,
        "threshold": 0.05,
        "spec": "op-day1-v2",
    }


def test_next_listing_is_decided_once_and_not_ready_is_not_recorded(app_data, monkeypatch):
    calls = []

    def fake_decide(api, event_id, listing, market, now):
        calls.append(event_id)
        if event_id == "late":
            raise ipo_t01.NotReady("레이크 마지막 날짜가 결정 시점보다 이르다")
        if event_id == "noprice":
            raise ipo_t01.NotEligible("확정 공모가가 없다")
        return {"order": {"buy": True, "limit_mult": 1.5, "limit_price": 15_000.0},
                "regime": "R2", "offer_price": 10_000.0, "score": 0.2}  # fmt: skip

    monkeypatch.setattr(ipo_t01, "decide_listing", fake_decide)
    sched = _schedule(
        [
            ("a", "가", "111110", "2026-11-03"),
            ("late", "나", "222220", "2026-11-03"),
            ("noprice", "다", "333330", "2026-11-03"),
            ("later", "라", "444440", "2026-11-10"),
        ]
    )
    api = FakeApi("2026-11-02", sched, _events([("a", "111110", None)]))
    frame = ipo_signals.build(api, now=NOW)
    decisions = storage.read_json(*ipo_signals.DECISIONS)
    assert set(decisions) == {"a", "noprice"}  # 결정 대기(NotReady)는 기록하지 않는다
    assert decisions["noprice"]["status"] == "not_eligible" and decisions["noprice"]["buy"] is False
    assert set(frame["event_id"]) == {"a", "noprice"}
    a = frame.set_index("event_id").loc["a"]
    assert a["position"] == "signal" and a["limit_price"] == 15_000.0
    assert a["sell_on"] == "2026-11-04"  # 상장 다음 거래일 종가
    status = storage.read_json(*ipo_signals.STATUS)
    assert status["next_session"] == "2026-11-03" and status["as_of"] == "2026-11-02"
    assert any("결정 대기" in p for p in status["problems"])
    assert [u["event_id"] for u in status["upcoming"]] == ["a", "late", "noprice", "later"]
    # 다시 돌려도 이미 쓴 결정은 다시 계산하지 않는다
    calls.clear()
    ipo_signals.build(api, now=NOW)
    assert calls == ["late"]


def _position(rec, bars, last, override=None):
    events = _events([(rec["event_id"], "555550", rec["listing_date"])])
    api = FakeApi(last, _schedule([]), events, bars)
    cfg = ipo_t01.config()
    ix = ipo_t01.index_frame(api, cfg, "2026-10-20")
    return ipo_signals.position(api, rec, ix, pd.Timestamp(last), "555550", override or {})


def test_fill_at_open_below_the_limit_then_sell_at_the_second_close():
    rec = _decided("e", "2026-11-03")
    bars = _bars("555550", "2026-11-03", [12_000.0, 13_000.0], [11_500.0, 12_500.0],
                 [12_500.0, 13_500.0])  # fmt: skip
    held = _position(rec, bars.iloc[:1], "2026-11-03")
    assert held["position"] == "holding" and held["entry_price"] == 12_000.0
    assert held["sell_on"] == pd.Timestamp("2026-11-04")
    sold = _position(rec, bars, "2026-11-04")
    assert sold["position"] == "sold" and sold["exit_price"] == 13_500.0
    assert sold["net_base"] == pytest.approx(13_500 / 12_000 - 1, abs=0.01)


def test_open_above_the_limit_fills_only_when_the_low_trades_through():
    rec = _decided("e", "2026-11-03")
    never = _bars("555550", "2026-11-03", [16_000.0], [15_200.0], [15_500.0])
    assert _position(rec, never, "2026-11-03")["position"] == "unfilled"
    dipped = _bars("555550", "2026-11-03", [16_000.0], [14_000.0], [15_500.0])
    out = _position(rec, dipped, "2026-11-03")
    assert out["position"] == "holding" and out["entry_price"] == 15_000.0


def test_a_lower_limit_close_rolls_the_sale_to_the_next_close():
    rec = _decided("e", "2026-11-03")
    bars = _bars("555550", "2026-11-03", [12_000.0, 9_000.0], [11_500.0, 8_820.0],
                 [12_600.0, 8_820.0])  # fmt: skip  # 2일째 종가 = 전일 종가 × 0.7(하한가)
    out = _position(rec, bars, "2026-11-04")
    assert out["position"] == "holding" and out["rolls"] == 1
    assert out["sell_on"] == pd.Timestamp("2026-11-05")


def test_user_entries_override_the_estimate():
    rec = _decided("e", "2026-11-03")
    never = _bars("555550", "2026-11-03", [16_000.0], [15_200.0], [15_500.0])
    out = _position(rec, never, "2026-11-03", {"filled": True, "entry_price": 15_000.0})
    assert out["position"] == "holding" and out["entry_price"] == 15_000.0
    sold = _position(rec, never, "2026-11-03",
                     {"filled": True, "entry_price": 15_000.0, "exit_price": 16_500.0,
                      "exit_date": "2026-11-04"})  # fmt: skip
    assert sold["position"] == "sold" and sold["exit_price"] == 16_500.0
