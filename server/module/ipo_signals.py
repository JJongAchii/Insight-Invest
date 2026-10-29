"""공모주 신호·보유 산출 (계약 ipo-live-ops) — 저녁 배치(build_insights `ipo_signals`)가 부른다.

운용 규칙: quant-lab op-day1-v2(t01 매수, 손절 없음) + 2일째 종가 매도(하한가 종가면 다음 거래일 종가로
최대 5거래일 이월). 결정 계산은 `module.ipo_t01`(quant-lab 결정 경로 사본)이 한다.

저장(APP_DATA 아래)
- `ipo/decisions.json`: event_id → 결정 기록. 한 번 쓴 기록은 다시 쓰지 않는다(덮어쓰지 않는 기록)
- `ipo/positions.json`: event_id → 사용자가 입력한 실제 체결·매도(화면에서 수정). 배치는 읽기만 한다
- `ipo/status.json`: 데이터 상태(레이크 날짜·다음 거래일·상장 예정·문제)
- `ipo/ipo_signals.parquet`: 결정마다 한 행 — 신호·체결 추정·매도 예정·결과(빌더 반환값)

체결 추정은 백테스트 엔진 규칙 그대로다: 시가 < 지정가면 시가, 아니면 그날 저가가 지정가 아래로 내려갔을
때 지정가. 사용자 입력이 있으면 그것이 이긴다.
"""

from __future__ import annotations

import datetime as dt
import logging
import math

import pandas as pd

from datastore import storage
from module import ipo_t01

logger = logging.getLogger(__name__)

DECISIONS = ("ipo", "decisions.json")
POSITIONS = ("ipo", "positions.json")
STATUS = ("ipo", "status.json")
#: 운용 매도: 2번째 거래일 종가(1 = 상장일 종가)
SELL_HORIZON = 2
#: 배정 비율 안내(백테스트 가정: 거래마다 전일 평가금액의 1/slots)
UPCOMING_DAYS = 21
KST = dt.timezone(dt.timedelta(hours=9))


def _read(parts: tuple[str, ...]) -> dict:
    return storage.read_json(*parts) if storage.exists(*parts) else {}


def _jsonable(v):
    if isinstance(v, dict):
        return {str(k): _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, pd.Timestamp):
        return f"{v:%Y-%m-%d}"
    if hasattr(v, "item"):
        v = v.item()
    if isinstance(v, float) and not math.isfinite(v):
        return None
    return v


def schedule(api, asof: pd.Timestamp) -> pd.DataFrame:
    """as-of 뒤 상장 예정 공모(공모 유형, 코스피·코스닥 또는 시장 미확인).

    레이크 이벤트의 market은 상장 뒤 KRX 첫 거래로 채워지므로 상장 전에는 비어 있다 — 상장 전 공시의 상장
    시장 코드(최신 접수)로 채운다. 공시로도 모르면 남겨 두고 decide_next가 '결정 대기'로 알린다(조용히 빼지
    않는다). 코넥스 등 다른 시장은 뺀다.
    """
    sch = api.load_ipo_schedule(start=str((asof + pd.Timedelta(days=1)).date()))
    sch = sch[(sch["listing_type"] == "ipo") & sch["listing_date"].isna()].copy()
    if sch.empty:
        return sch.reset_index(drop=True)
    obs = api.load_ipo_observations(
        event_ids=sch["event_id"].tolist(), metrics=["listing_market_code"]
    )
    obs = obs[pd.to_datetime(obs["filed_date"]) <= asof]
    code = _latest(obs).set_index("event_id")["value_text"] if len(obs) else pd.Series(dtype=str)
    filed = code.map(lambda c: MARKET_CODES.get(str(c or "").split(":")[0], OTHER_MARKET))
    known = sch["market"].where(sch["market"].isin(ipo_t01.MARKETS))
    market = known.fillna(sch["event_id"].map(filed))
    sch["market"] = market.astype(object).where(market.notna(), None)
    keep = sch["market"].isna() | sch["market"].isin(ipo_t01.MARKETS)
    return sch[keep].reset_index(drop=True)


def decide_next(api, sch: pd.DataFrame, nxt: pd.Timestamp, decisions: dict, now) -> list[str]:
    """다음 거래일 상장분을 결정해 decisions에 더한다. 결정할 수 없으면 사유를 기록한다.

    NotReady(데이터가 아직 결정 시점에 못 미침)는 기록하지 않는다 — 다음 실행이 다시 시도하고, 상태가
    '데이터 지연'으로 보인다. 반환: 문제 문장.
    """
    problems = []
    for e in sch[sch["planned_listing_date"] == nxt].itertuples(index=False):
        if e.event_id in decisions:
            continue
        if e.market not in ipo_t01.MARKETS:
            problems.append(f"{e.corp_name}: 결정 대기 — 상장 시장을 공시에서 아직 확인하지 못했다")
            continue
        base = {
            "event_id": e.event_id,
            "corp_name": e.corp_name,
            "market": e.market,
            "listing_date": nxt,
            "planned_rcept_no": e.planned_rcept_no,
            "decided_at": now.astimezone(KST).isoformat(timespec="seconds"),
        }
        try:
            made = ipo_t01.decide_listing(api, e.event_id, nxt, e.market, now)
        except ipo_t01.NotReady as exc:
            problems.append(f"{e.corp_name}: 결정 대기 — {exc}")
            continue
        except (ipo_t01.NotEligible, ipo_t01.TooLate) as exc:
            decisions[e.event_id] = _jsonable(
                {**base, "status": "not_eligible", "reason": str(exc), "buy": False}
            )
            continue
        except Exception as exc:  # 한 종목의 실패가 다른 종목 결정을 막지 않게 — 사유를 남긴다
            logger.exception("ipo decision failed: %s", e.event_id)
            problems.append(f"{e.corp_name}: 결정 실패 — {type(exc).__name__}: {exc}")
            continue
        decisions[e.event_id] = _jsonable({**base, **made, "status": "decided",
                                            "buy": bool(made["order"]["buy"])})  # fmt: skip
    return problems


def _bars(api, rec: dict, ix: pd.DataFrame, asof: pd.Timestamp, ticker: str) -> pd.DataFrame:
    listing = pd.Timestamp(rec["listing_date"])
    prices = api.load_krx_prices(
        start=str(listing.date()),
        end=str(asof.date()),
        tickers=[ticker],
        columns=ipo_t01.PRICE_COLUMNS,
    )
    prices["date"] = pd.to_datetime(prices["date"]).astype("datetime64[ns]")
    cal = ipo_t01.trading_calendar(ix, prices, asof)
    cal = cal[cal >= listing]
    if cal.empty or cal[0] != listing:
        return pd.DataFrame(columns=["event_id", "day", "date", *ipo_t01.PRICE_COLUMNS])
    events = pd.DataFrame({"event_id": [rec["event_id"]], "ticker": [ticker],
                           "listing_date": [listing]})  # fmt: skip
    n = int(ipo_t01.config()["execution"]["bars_after_listing"])
    return ipo_t01.event_bars(events, prices, cal, n)


def position(api, rec: dict, ix, asof, ticker, override: dict) -> dict:
    """매수 결정 하나의 체결·매도 상태(백테스트 엔진 규칙 + 사용자 입력)."""
    cfg = ipo_t01.config()
    engine = ipo_t01.engine
    rules = ipo_t01.rules
    listing = pd.Timestamp(rec["listing_date"])
    limit = float(rec["order"]["limit_price"])
    out = {"ticker": ticker, "sell_plan": "2번째 거래일 종가"}
    if asof < listing or ticker is None:
        return {**out, "position": "signal", "sell_on": ipo_t01.next_session(listing)}
    bars = _bars(api, rec, ix, asof, ticker)
    day0 = bars[bars["day"] == 0]
    if day0.empty or not math.isfinite(float(day0["open"].iloc[0])):
        return {**out, "position": "awaiting_listing_data"}
    regime = rec["regime"]
    offer = float(rec["offer_price"])
    cap_threshold = (
        float(cfg["execution"]["cap_tolerance"]) * rules.cap_multiple(regime, cfg) * offer
    )
    filled, entry = engine.entry_fill(
        float(day0["open"].iloc[0]), float(day0["low"].iloc[0]), limit, cap_threshold,
        bool(cfg["execution"]["tie_fills"]),
    )  # fmt: skip
    if override.get("filled") is not None:
        filled = bool(override["filled"])
    if override.get("entry_price") is not None:
        entry = float(override["entry_price"])
    out.update({"filled_estimate": bool(filled), "entry_price": entry if filled else None})
    if not filled:
        return {**out, "position": "unfilled"}
    ex = engine.exit_fill(bars, SELL_HORIZON, rec["market"], regime, offer, cfg)
    if override.get("exit_price") is not None:
        exit_date = pd.Timestamp(override.get("exit_date") or ex["exit_date"])
        return {**out, "position": "sold", "exit_date": exit_date,
                "exit_price": float(override["exit_price"]), "rolls": ex["rolls"],
                "net_base": engine.net_return(entry, float(override["exit_price"]), exit_date,
                                              "base", cfg)}  # fmt: skip
    if ex["truncated"]:
        # 아직 매도일 종가가 없다 — 다음 거래일 종가에 판다(하한가 이월 중이면 그 횟수)
        return {**out, "position": "holding", "sell_on": ipo_t01.next_session(asof),
                "rolls": ex["rolls"]}  # fmt: skip
    return {**out, "position": "sold", "exit_date": ex["exit_date"],
            "exit_price": ex["exit_price"], "rolls": ex["rolls"],
            "net_base": engine.net_return(entry, ex["exit_price"], ex["exit_date"], "base", cfg),
            "net_stress": engine.net_return(entry, ex["exit_price"], ex["exit_date"], "stress",
                                            cfg)}  # fmt: skip


#: 진행 중 공모 일정에 읽는 관측값(상장 전 공시) — 날짜는 value_text, 가격은 value
DATE_METRICS = (
    "bookbuild_start",
    "bookbuild_end",
    "price_announce_date",
    "subscription_start",
    "subscription_end",
    "payment_date",
)
PRICE_METRICS = ("band_low", "band_high", "final_price")
MARKET_CODES = {"1": "KOSPI", "2": "KOSDAQ"}
OTHER_MARKET = "OTHER"  # 공시의 상장 시장이 코스피·코스닥이 아님(코넥스 등) — 이 규칙 대상 밖
STAGE_LABELS = {
    "filed": "신고서 제출",
    "bookbuilding": "수요예측",
    "priced": "공모가 확정",
    "subscription": "청약",
    "paid": "납입 완료 · 상장일 공시 대기",
    "listing_scheduled": "상장일 확정",
}
#: 진행 중으로 보는 최초 신고서 접수 창(그보다 오래됐고 앞으로 일정도 없으면 뺀다)
CALENDAR_LOOKBACK_DAYS = 180
CALENDAR_WINDOW = (7, 60)  # 달력 일정: 기준일 7일 전 ~ 60일 뒤


def _latest(obs: pd.DataFrame) -> pd.DataFrame:
    """event_id × metric마다 가장 늦게 접수된 관측값(정정 공시가 이긴다)."""
    obs = obs.sort_values(["event_id", "metric", "filed_date", "rcept_no"])
    return obs.groupby(["event_id", "metric"], as_index=False).last()


def _stage(item: dict, asof: pd.Timestamp) -> str:
    def on_or_before(key):
        v = item.get(key)
        return v is not None and pd.Timestamp(v) <= asof

    if item.get("planned_listing_date") is not None:
        return "listing_scheduled"
    if on_or_before("payment_date"):
        return "paid"
    if on_or_before("subscription_start"):
        return "subscription"
    if item.get("final_price") is not None:
        return "priced"
    if item.get("bookbuild_start") is not None:
        return "bookbuilding"
    return "filed"


def calendar(api, asof: pd.Timestamp, sch: pd.DataFrame, decisions: dict) -> tuple[list, list]:
    """진행 중 공모(상장 전) 일정과 날짜별 일정 목록. 상장일이 공시되면 이 규칙의 신호 계산·매수·매도일을
    겹친다. 반환: (공모별 항목, 날짜별 일정)."""
    ev = api.load_ipo_events()
    first = pd.to_datetime(ev["first_filed"])
    cur = ev[
        (ev["listing_type"] == "ipo")
        & (ev["status"] != "withdrawn")
        & ev["listing_date"].isna()
        & (first >= asof - pd.Timedelta(days=CALENDAR_LOOKBACK_DAYS))
    ]
    if cur.empty:
        return [], []
    obs = api.load_ipo_observations(
        event_ids=cur["event_id"].tolist(),
        metrics=[*DATE_METRICS, *PRICE_METRICS, "listing_market_code"],
    )
    latest = _latest(obs) if len(obs) else obs
    planned = dict(zip(sch["event_id"], sch["planned_listing_date"], strict=True))
    lo = asof - pd.Timedelta(days=CALENDAR_WINDOW[0])
    hi = asof + pd.Timedelta(days=CALENDAR_WINDOW[1])
    items, events = [], []
    for e in cur.itertuples(index=False):
        rows = latest[latest["event_id"] == e.event_id].set_index("metric")
        item = {"event_id": e.event_id, "corp_name": e.corp_name}
        for m in DATE_METRICS:
            v = rows["value_text"].get(m) if m in rows.index else None
            item[m] = pd.Timestamp(v) if isinstance(v, str) and v else None
        for m in PRICE_METRICS:
            v = rows["value"].get(m) if m in rows.index else None
            item[m] = float(v) if v is not None and pd.notna(v) else None
        # 각주 표시('주2)')를 공모가로 읽은 파싱 오류는 결정 경로와 같은 밴드 대조로 거른다
        band = [item["band_low"] or math.nan, item["band_high"] or math.nan]
        if item["final_price"] is not None and not ipo_t01.fields.plausible_price(
            item["final_price"], *band
        ):
            item["final_price"] = None
        code = (
            rows["value_text"].get("listing_market_code")
            if "listing_market_code" in rows.index
            else None
        )
        market = e.market if isinstance(e.market, str) and e.market else None
        item["market"] = market or MARKET_CODES.get(str(code or "").split(":")[0])
        item["planned_listing_date"] = planned.get(e.event_id)
        dates = [v for k, v in item.items() if k in (*DATE_METRICS, "planned_listing_date") and v]
        if not dates and first[ev["event_id"] == e.event_id].iloc[0] < asof - pd.Timedelta(days=60):
            continue  # 일정 공시가 하나도 없이 오래된 신고 — 사실상 멈춘 공모
        if dates and max(dates) < lo:
            continue  # 일정이 모두 지났는데 상장도 철회도 기록되지 않은 공모
        item["stage"] = _stage(item, asof)
        item["stage_label"] = STAGE_LABELS[item["stage"]]
        rec = decisions.get(e.event_id) or {}
        item["decided"] = bool(rec)
        item["buy"] = rec.get("buy") if rec else None
        d = item["planned_listing_date"]
        if d is not None:
            item["decision_night"] = ipo_t01.calendar.previous_session(d)
            item["buy_session"] = d
            item["sell_session"] = ipo_t01.next_session(d)
        else:
            item["decision_night"] = item["buy_session"] = item["sell_session"] = None
        items.append(item)

        def add(day, kind, label):
            if day is not None and lo <= pd.Timestamp(day) <= hi:
                events.append({"date": day, "event_id": e.event_id,
                               "corp_name": e.corp_name, "kind": kind, "label": label})  # fmt: skip

        end = item["bookbuild_end"]
        add(item["bookbuild_start"], "bookbuild",
            "수요예측 시작" + (f"(~{end:%m-%d})" if end is not None else ""))  # fmt: skip
        add(item["price_announce_date"], "price", "공모가 확정 공고")
        sub_end = item["subscription_end"]
        add(item["subscription_start"], "subscription",
            "청약" + (f"(~{sub_end:%m-%d})" if sub_end is not None else ""))  # fmt: skip
        add(item["payment_date"], "payment", "납입")
        add(d, "listing", "상장")
        add(item["decision_night"], "decision", "t01 신호 계산(밤)")
        if item["buy"]:
            add(item["buy_session"], "buy", "매수 주문(08:30~09:00 동시호가)")
            add(item["sell_session"], "sell", "종가 매도(15:20~15:30)")
    items.sort(key=lambda i: (i["planned_listing_date"] or i["payment_date"]
                              or i["subscription_start"] or pd.Timestamp.max, i["corp_name"]))  # fmt: skip
    events.sort(key=lambda x: (x["date"], x["corp_name"], x["kind"]))
    return items, events


def build(api, now: dt.datetime | None = None) -> pd.DataFrame:
    """결정·보유 표를 만들고 상태를 쓴다. 반환: ipo_signals 표(결정마다 한 행)."""
    now = now or dt.datetime.now(dt.UTC)
    cfg = ipo_t01.config()
    ix = ipo_t01.index_frame(api, cfg, ipo_t01.dev_end() - pd.Timedelta(days=120))
    asof = ipo_t01.lake_last_date(ix)
    nxt = ipo_t01.next_session(asof)
    decisions = _read(DECISIONS)
    overrides = _read(POSITIONS)
    problems: list[str] = []
    try:
        sch = schedule(api, asof)
    except Exception as exc:
        logger.exception("ipo schedule load failed")
        sch = pd.DataFrame(columns=["event_id", "planned_listing_date"])
        problems.append(f"상장 예정 일정을 읽지 못함 — {type(exc).__name__}: {exc}")
    before = set(decisions)
    problems += decide_next(api, sch, nxt, decisions, now)
    if set(decisions) != before:
        storage.write_json(decisions, *DECISIONS)

    events = api.load_ipo_events()[["event_id", "stock_code", "listing_date"]].set_index("event_id")
    rows = []
    for rec in decisions.values():
        row = {k: rec.get(k) for k in ("event_id", "corp_name", "market", "listing_date",
                                        "status", "reason", "buy", "offer_price", "score",
                                        "threshold", "spec", "decided_at", "decision_session")}  # fmt: skip
        order = rec.get("order") or {}
        row["limit_price"] = order.get("limit_price")
        if rec.get("buy"):
            ticker = (
                events["stock_code"].get(rec["event_id"])
                if rec["event_id"] in events.index
                else None
            )
            ticker = ticker if isinstance(ticker, str) and ticker else None
            try:
                row.update(position(api, rec, ix, asof, ticker, overrides.get(rec["event_id"], {})))
            except Exception as exc:
                logger.exception("ipo position failed: %s", rec["event_id"])
                problems.append(f"{rec.get('corp_name')}: 보유 계산 실패 — {exc}")
        rows.append(row)
    frame = pd.DataFrame(rows)
    try:
        cal_items, cal_events = calendar(api, asof, sch, decisions)
    except Exception as exc:
        logger.exception("ipo calendar failed")
        cal_items, cal_events = [], []
        problems.append(f"공모 일정을 만들지 못함 — {type(exc).__name__}: {exc}")
    upcoming = sch[sch["planned_listing_date"] <= asof + pd.Timedelta(days=UPCOMING_DAYS)]
    status = {
        "as_of": asof,
        "generated_at": now.astimezone(KST).isoformat(timespec="seconds"),
        "next_session": nxt,
        "rule": {"spec": ipo_t01.rule()["spec"], "entry": "공모가 × 1.5 호가 내림 당일 유효 지정가",
                 "exit": "2번째 거래일 종가(하한가 종가면 다음 거래일 종가, 최대 5거래일)",
                 "stop_loss": None,
                 "sizing": f"한 종목에 전일 계좌 평가금액의 1/{cfg['sizing']['slots']}"},  # fmt: skip
        "upcoming": [
            {
                "event_id": r.event_id,
                "corp_name": r.corp_name,
                "market": r.market,
                "planned_listing_date": r.planned_listing_date,
                "final_price": r.final_price,
                "decided": r.event_id in decisions,
            }  # fmt: skip
            for r in upcoming.itertuples(index=False)
        ],
        "calendar": cal_items,
        "calendar_events": cal_events,
        "problems": problems,
    }
    storage.write_json(_jsonable(status), *STATUS)
    if frame.empty:
        frame = pd.DataFrame(columns=["event_id"])
    frame["as_of"] = f"{asof:%Y-%m-%d}"
    for col in frame.columns:
        if frame[col].map(lambda v: isinstance(v, pd.Timestamp)).any():
            frame[col] = frame[col].map(
                lambda v: f"{v:%Y-%m-%d}" if isinstance(v, pd.Timestamp) else v
            )
    return frame
