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
OBS_COLUMNS = ["event_id", "rcept_no", "filed_date", "metric", "value", "value_text"]


class FakeApi:
    def __init__(
        self, last: str, schedule: pd.DataFrame, events: pd.DataFrame, prices=None, obs=None
    ):
        self.last = pd.Timestamp(last)
        self.sched = schedule
        self.events = events
        self.obs = obs if obs is not None else pd.DataFrame(columns=OBS_COLUMNS)
        self.docs = pd.DataFrame(columns=["rcept_no", "event_id", "filed_date", "parse_status"])
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

    def load_ipo_observations(self, event_ids=None, metrics=None):
        o = self.obs
        if event_ids is not None:
            o = o[o["event_id"].isin(event_ids)]
        if metrics is not None:
            o = o[o["metric"].isin(metrics)]
        return o.reset_index(drop=True)

    def load_ipo_documents(self, event_ids=None):
        d = self.docs
        return d[d["event_id"].isin(event_ids)] if event_ids is not None else d

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


def _events(rows, first_filed="2026-10-01"):
    return pd.DataFrame(
        [{"event_id": e, "stock_code": t, "listing_date": pd.Timestamp(d) if d else pd.NaT,
          "corp_name": e, "market": None, "listing_type": "ipo",
          "status": "priced" if not d else "completed",
          "first_filed": pd.Timestamp(first_filed)}
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


def _obs(event_id, rcept_no, filed, **values):
    rows = []
    for metric, v in values.items():
        num = isinstance(v, (int, float))
        rows.append(
            {
                "event_id": event_id,
                "rcept_no": rcept_no,
                "filed_date": pd.Timestamp(filed),
                "metric": metric,
                "value": float(v) if num else None,
                "value_text": None if num else v,
            }
        )
    return rows


def test_calendar_shows_each_offering_stage_and_the_rule_days(app_data, monkeypatch):
    monkeypatch.setattr(
        ipo_t01,
        "decide_listing",
        lambda *a, **k: {"order": {"buy": True, "limit_mult": 1.5, "limit_price": 15_000.0},
                         "regime": "R2", "offer_price": 10_000.0},  # fmt: skip
    )
    sched = _schedule([("listing", "상장확정", "111110", "2026-11-03")])
    events = _events(
        [("listing", "111110", None), ("sub", None, None), ("book", None, None),
         ("old", None, None)]  # fmt: skip
    )
    events.loc[events["event_id"] == "old", "first_filed"] = pd.Timestamp("2026-05-01")
    obs = pd.DataFrame(
        _obs("listing", "L1", "2026-10-20", subscription_start="2026-10-26",
             subscription_end="2026-10-27", payment_date="2026-10-29", final_price=10_000,
             listing_market_code="2:코스닥시장")
        + _obs("sub", "S1", "2026-10-15", bookbuild_start="2026-10-20",
               bookbuild_end="2026-10-24", final_price=20_000, band_low=18_000,
               band_high=20_000, subscription_start="2026-11-05",
               subscription_end="2026-11-06", payment_date="2026-11-10",
               listing_market_code="1:유가증권시장")
        # 정정 공시가 수요예측 일정을 늦췄다 — 늦게 접수된 값이 이긴다
        + _obs("book", "B1", "2026-10-10", bookbuild_start="2026-11-04")
        + _obs("book", "B2", "2026-10-28", bookbuild_start="2026-11-09",
               bookbuild_end="2026-11-13")
    )  # fmt: skip
    api = FakeApi("2026-11-02", sched, events, obs=obs)
    ipo_signals.build(api, now=NOW)
    status = storage.read_json(*ipo_signals.STATUS)
    items = {i["event_id"]: i for i in status["calendar"]}
    assert set(items) == {"listing", "sub", "book"}  # 일정 없이 오래된 신고는 뺀다
    listing = items["listing"]
    assert listing["stage"] == "listing_scheduled" and listing["market"] == "KOSDAQ"
    assert listing["decision_night"] == "2026-11-02" and listing["sell_session"] == "2026-11-04"
    assert items["sub"]["stage"] == "priced" and items["sub"]["market"] == "KOSPI"
    assert items["book"]["stage"] == "bookbuilding"
    assert items["book"]["bookbuild_start"] == "2026-11-09"
    kinds = {(e["event_id"], e["kind"]) for e in status["calendar_events"]}
    assert {("listing", "decision"), ("listing", "buy"), ("listing", "sell")} <= kinds
    assert ("sub", "subscription") in kinds and ("book", "bookbuild") in kinds
    dates = [e["date"] for e in status["calendar_events"]]
    assert dates == sorted(dates)
    assert not any("공모 일정" in p for p in status["problems"])


def test_decision_waits_while_recent_filings_are_not_downloaded():
    """운영 레이크가 공시 원문을 다 받기 전에는 결정을 미룬다(NotReady — 기록하지 않음). 2026-10-28 첫 수집은
    상장 하루 전 공모의 공모가 확정·실적보고서를 받지 못했다 — 그대로 결정하면 '부적격'이 기록되거나
    quant-lab과 다른 결정이 나온다."""
    events = _events([("t", None, None), ("old", "777770", "2026-10-10")], first_filed="2026-09-01")
    events["first_rcept_no"] = ["20260901000001", "20260901000002"]
    events.loc[events["event_id"] == "old", "listing_type"] = "unknown"
    api = FakeApi("2026-11-02", _schedule([]), events)
    api.docs = pd.DataFrame(
        {"rcept_no": ["20260901000001", "20261027000003", "20260901000002", "20260915000004"],
         "event_id": ["t", "t", "old", "old"],
         "filed_date": pd.to_datetime(["2026-09-01", "2026-10-27", "2026-09-01", "2026-09-15"]),
         "parse_status": ["ok", "not_downloaded", "ok", "not_downloaded"]}
    )  # fmt: skip
    asof = pd.Timestamp("2026-11-02")
    # 필드 유형(ipo)은 모든 원문, 미분류(unknown)는 기준 문서만 본다
    assert ipo_t01.missing_documents(api, asof) == ["20261027000003"]
    with pytest.raises(ipo_t01.NotReady, match="원문 1건"):
        ipo_t01.decide_listing(api, "t", "2026-11-03", "KOSDAQ", NOW)
    api.docs.loc[api.docs["rcept_no"] == "20261027000003", "parse_status"] = "ok"
    assert ipo_t01.missing_documents(api, asof) == []
    # 오래전에 처음 접수된 대상도 자기 원문은 다 있어야 한다
    events.loc[events["event_id"] == "t", "first_filed"] = pd.Timestamp("2025-01-02")
    api.docs.loc[api.docs["rcept_no"] == "20260901000001", "parse_status"] = "not_downloaded"
    assert ipo_t01.missing_documents(api, asof) == []
    assert ipo_t01.missing_documents(api, asof, "t") == ["20260901000001"]


def test_schedule_takes_the_market_from_the_filing_before_listing(app_data):
    """상장 전 레이크 이벤트의 market은 비어 있다(2026-10-29 운영 레이크의 상장 예정 6건 모두). 공시의 상장 시장
    코드로 채우지 않으면 결정 대상이 0건이 된다. 공시로도 모르면 '결정 대기', 코넥스는 뺀다."""
    sched = _schedule(
        [
            ("kq", "가", None, "2026-11-03"),
            ("ks", "나", None, "2026-11-03"),
            ("nx", "다", None, "2026-11-03"),
            ("unk", "라", None, "2026-11-03"),
        ]
    )
    sched["market"] = None
    obs = pd.DataFrame(
        [
            {"event_id": "kq", "rcept_no": "1", "filed_date": pd.Timestamp("2026-09-01"),
             "metric": "listing_market_code", "value": np.nan, "value_text": "2:코스닥시장"},
            {"event_id": "ks", "rcept_no": "2", "filed_date": pd.Timestamp("2026-09-01"),
             "metric": "listing_market_code", "value": np.nan, "value_text": "1:유가증권시장"},
            {"event_id": "nx", "rcept_no": "3", "filed_date": pd.Timestamp("2026-09-01"),
             "metric": "listing_market_code", "value": np.nan, "value_text": "3:코넥스시장"},
            {"event_id": "unk", "rcept_no": "4", "filed_date": pd.Timestamp("2026-11-05"),
             "metric": "listing_market_code", "value": np.nan, "value_text": "2:코스닥시장"},
        ]
    )  # fmt: skip
    api = FakeApi("2026-11-02", sched, _events([]), obs=obs)
    got = ipo_signals.schedule(api, pd.Timestamp("2026-11-02"))
    assert dict(zip(got["event_id"], got["market"])) == {"kq": "KOSDAQ", "ks": "KOSPI", "unk": None}
    problems = ipo_signals.decide_next(
        api, got[got["event_id"] == "unk"], pd.Timestamp("2026-11-03"), {}, NOW
    )
    assert (
        problems and "상장 시장" in problems[0]
    )  # as-of 뒤 공시는 쓰지 않고, 모르면 기록 없이 대기
