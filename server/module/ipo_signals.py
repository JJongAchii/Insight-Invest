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
    """as-of 뒤 상장 예정 공모(코스피·코스닥, 공모 유형)."""
    sch = api.load_ipo_schedule(start=str((asof + pd.Timedelta(days=1)).date()))
    sch = sch[(sch["listing_type"] == "ipo") & sch["market"].isin(ipo_t01.MARKETS)]
    return sch[sch["listing_date"].isna()].reset_index(drop=True)


def decide_next(api, sch: pd.DataFrame, nxt: pd.Timestamp, decisions: dict, now) -> list[str]:
    """다음 거래일 상장분을 결정해 decisions에 더한다. 결정할 수 없으면 사유를 기록한다.

    NotReady(데이터가 아직 결정 시점에 못 미침)는 기록하지 않는다 — 다음 실행이 다시 시도하고, 상태가
    '데이터 지연'으로 보인다. 반환: 문제 문장.
    """
    problems = []
    for e in sch[sch["planned_listing_date"] == nxt].itertuples(index=False):
        if e.event_id in decisions:
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
