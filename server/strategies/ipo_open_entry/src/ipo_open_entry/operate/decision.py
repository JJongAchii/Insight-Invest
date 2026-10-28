"""운용 결정 — 상장 전 거래일 장 마감 뒤의 정보만으로 동결 후보의 결정을 계산한다.

결정 문서도 만든다.

한 사건의 결정은 이렇게 만든다 (docs/operating-rule.md).
1. 결정 시점: 계획 상장일 D의 전 KRX 거래일(as-of) 장 마감 뒤. 레이크의 마지막 KRX 날짜가 그
   as-of와 같아야 한다. 더 이르면 발행이 덜 끝났고(`NotReady`),
   D 이상이면 이미 상장했다(`TooLate`). 계산 시각은 D 09:00 KST 전이어야 한다(`TooLate`).
2. 학습: 분기 시작 qs 전에 세 청산이 모두 끝난 사건 — 동결 데이터셋의 개발 사건과, 개발 구간 뒤
   상장해 청산이 끝난 사건(백테스트의 분기 재적합과 같은 규칙).
3. 피처: 개발과 같은 함수(`features.build_features`)에 as-of까지 자른 입력을 넣는다. 상장일부터
   일봉 창이 KRX 시간외 오염 구간(`CONTAMINATED`)에 닿는 사건은 H7 입력과 학습에서 뺀다.
4. 결정: 동결 전략의 fit(학습) → decide(그 사건 한 행). 점수는 결정 규칙이 쓰는 값(세 청산
   예측 평균)이다.

결정 문서는 대상 사건의 상장 뒤 정보(시가·종가·수익)를 담지 않는다(`FORBIDDEN_KEY_PARTS`).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math

import numpy as np
import pandas as pd

from ipo_open_entry import engine, evaluate, features
from ipo_open_entry.operate import calendar

SCHEMA_VERSION = 1
LINE = "ipo-open-entry"
KST = dt.timezone(dt.timedelta(hours=9))
OPEN_TIME = dt.time(9, 0)
CLOSE_TIME = dt.time(15, 30)
#: KRX 시간외 시장 가격이 EC2 저녁 수집 종가를 덮어쓴 구간
#: (quant-data 0156ece가 2026-10-13에 고쳤고 과거 행은 다시 수집하지 않았다)
CONTAMINATED = (pd.Timestamp("2026-09-14"), pd.Timestamp("2026-10-12"))
#: 결정 문서의 어떤 키에도 들어가면 안 되는 말 — 대상 사건의 상장 뒤 결과를 담지 않는다
FORBIDDEN_KEY_PARTS = ("nav", "pnl", "cagr", "return", "profit", "gross", "net_", "exit", "close")
#: 결정 전에 고정된 규칙을 담는 최상위 절 — 규칙 매개변수 이름(예: take_profit)은 결과가 아니다
RULE_SECTIONS = ("rule", "spec")


class NotReady(RuntimeError):
    """결정 시점의 정보가 아직 다 없다 — 결정하지 않고 발행을 기다린다."""


class TooLate(RuntimeError):
    """결정 시각이 지났다 — 상장 전 결정이 될 수 없다."""


class NotEligible(RuntimeError):
    """이 사건은 결정 대상이 아니다(확정 공모가 없음, 철회, 유형이 다름, 거래일 아님 등)."""


def deadline(listing_date) -> dt.datetime:
    d = pd.Timestamp(listing_date)
    return dt.datetime(d.year, d.month, d.day, OPEN_TIME.hour, OPEN_TIME.minute, tzinfo=KST)


def decision_session(listing_date) -> pd.Timestamp:
    d = pd.Timestamp(listing_date).normalize()
    if not calendar.is_session(d):
        raise NotEligible(f"계획 상장일 {d.date()}이 KRX 거래일이 아니다")
    return calendar.previous_session(d)


def check_timing(listing_date, lake_last, now: dt.datetime) -> pd.Timestamp:
    """결정 시점(as-of)을 정하고 지금 결정해도 되는지 본다. as-of를 돌려준다."""
    d = pd.Timestamp(listing_date).normalize()
    asof = decision_session(d)
    if now >= deadline(d):
        raise TooLate(f"{d.date()} 09:00 KST가 지났다 — 결정은 상장일 장 시작 전에만 낸다")
    after_close = dt.datetime(
        asof.year, asof.month, asof.day, CLOSE_TIME.hour, CLOSE_TIME.minute, tzinfo=KST
    )
    if now < after_close:
        raise NotReady(f"결정 시점({asof.date()} 장 마감) 전이다")
    last = pd.Timestamp(lake_last).normalize()
    if last >= d:
        raise TooLate(f"레이크에 상장일 {d.date()} 이후 시세가 있다 — 상장 전 결정이 아니다")
    if last < asof:
        raise NotReady(
            f"레이크의 마지막 KRX 날짜 {last.date()}가 결정 시점 {asof.date()}보다 이르다"
        )
    if last != asof:
        raise ValueError(
            f"레이크 마지막 날짜 {last.date()}와 달력의 결정 시점 {asof.date()}가 다르다"
        )
    return asof


def quarter_start(listing_date) -> pd.Timestamp:
    return pd.Timestamp(listing_date).to_period("Q").start_time


def contaminated_events(bars: pd.DataFrame) -> pd.Index:
    """일봉 창(상장일부터 bars_after_listing 거래일)이 오염 구간에 닿는 사건."""
    lo, hi = CONTAMINATED
    hit = bars[(bars["date"] >= lo) & (bars["date"] <= hi)]
    return pd.Index(sorted(hit["event_id"].unique()))


def training_table(dev_table, post_table, qs, horizons) -> pd.DataFrame:
    """분기 시작 전에 세 청산이 모두 끝난 개발 사건과 개발 구간 뒤 사건."""
    parts = [dev_table]
    if post_table is not None and len(post_table):
        parts.append(post_table)
    t = pd.concat(parts, ignore_index=True)
    exits = [f"exit_date_h{h}" for h in horizons]
    done = (t["listing_date"] < qs) & (t[exits].max(axis=1) < qs)
    return t[done].reset_index(drop=True)


def completed_events(events: pd.DataFrame, bars: pd.DataFrame, config: dict) -> pd.Index:
    """as-of까지의 일봉으로 세 청산이 모두 잘리지 않고 끝난 사건.

    일봉이 모자라 잘린 청산(하한가 이월·거래정지 중 as-of에 닿음)은 라벨이 아직 정해지지 않았다.
    """
    grouped = dict(tuple(bars.groupby("event_id")))
    horizons = [int(h) for h in config["execution"]["horizons"]]
    done = []
    for e in events.itertuples(index=False):
        b = grouped.get(e.event_id)
        if b is None or not np.isfinite(b.loc[b["day"] == 0, "open"]).all():
            continue
        fills = [
            engine.exit_fill(b, h, e.market, e.regime, e.offer_price, config) for h in horizons
        ]
        if not any(f["truncated"] for f in fills):
            done.append(e.event_id)
    return pd.Index(done)


def post_dev_table(
    dev_data: dict, post: dict, index_close: pd.Series, config: dict
) -> pd.DataFrame | None:
    """개발 구간 뒤 상장해 청산이 끝난 사건의 피처·라벨 표.

    개발 사건과 같은 함수(`evaluate.build_table`)로 만든다.
    """
    ev = post["events"]
    done = completed_events(ev, post["bars"], config)
    if done.empty:
        return None
    data = {
        "events": pd.concat([dev_data["events"], ev], ignore_index=True),
        "fields": pd.concat([dev_data["fields"], post["fields"].reset_index()], ignore_index=True),
        "bars": pd.concat([dev_data["bars"], post["bars"]], ignore_index=True),
        "index": pd.DataFrame({"date": index_close.index, "kosdaq": index_close.to_numpy()}),
    }
    table = evaluate.build_table(data, config)
    return table[table["event_id"].isin(done)].reset_index(drop=True)


def target_features(
    target: dict,
    target_fields: pd.DataFrame,
    prior_events: pd.DataFrame,
    prior_fields: pd.DataFrame,
    prior_bars: pd.DataFrame,
    index_close: pd.Series,
    asof: pd.Timestamp,
    config: dict,
) -> pd.Series:
    """대상 사건의 피처 한 행. 이전 사건 일봉·지수는 as-of 뒤를 버리고 넣는다."""
    cols = list(evaluate.KEY_COLUMNS)
    events = pd.concat([prior_events[cols], pd.DataFrame([{c: target[c] for c in cols}])])
    events = events.reset_index(drop=True)
    table = pd.concat([prior_fields, target_fields])
    bars = prior_bars[prior_bars["date"] <= asof]
    close = index_close[index_close.index <= asof]
    feats = features.build_features(events, table, bars, close, config)
    return feats.loc[target["event_id"]]


def prior_trades_used(prior_events, prior_bars, listing_date, config) -> pd.DataFrame:
    """H7이 읽은 직전 거래(청산별 마지막 n건) — 결정의 입력 사본으로 남긴다."""
    spec = config["features"]
    trades = features.b1_trades(prior_events, prior_bars, config)
    cutoff = pd.Timestamp(listing_date) - features.ONE_DAY
    out = []
    for h in config["execution"]["horizons"]:
        done = trades[(trades["horizon"] == h) & trades["filled"]]
        if "truncated" in done:
            done = done[~done["truncated"].astype(bool)]
        done = done[(done["exit_date"] <= cutoff) & (done["listing_date"] < listing_date)]
        tail = done.sort_values(["listing_date", "event_id"]).tail(int(spec["h7_prior_events"]))
        out.append(tail[["event_id", "listing_date", "horizon", "exit_date", "net_stress"]])
    return pd.concat(out, ignore_index=True)


def _rounded(v):
    if isinstance(v, dict):
        return {str(k): _rounded(x) for k, x in sorted(v.items(), key=lambda kv: str(kv[0]))}
    if isinstance(v, (list, tuple, np.ndarray)):
        return [_rounded(x) for x in v]
    return round(float(v), 12)


def decide(make_strategy, train: pd.DataFrame, target_row: pd.DataFrame) -> dict:
    """동결 전략을 학습 표로 맞추고 대상 한 행의 결정과 점수를 낸다."""
    strategy = make_strategy()
    strategy.fit(train.copy())
    out = strategy.decide(target_row.copy())
    if len(out) != 1 or out["event_id"].iloc[0] != target_row["event_id"].iloc[0]:
        raise ValueError("결정이 대상 사건 한 행이 아니다")
    buy = bool(out["buy"].iloc[0])
    mult = float(out["limit_mult"].iloc[0])
    coefs = _rounded(getattr(strategy, "coefs_", {}))
    return {
        "buy": buy,
        "limit_mult": mult if buy and math.isfinite(mult) else None,
        # 결정 규칙이 쓰는 점수(세 청산 예측 평균, SignedRegression._predict)
        "score": float(strategy._predict(target_row)[0]),
        "threshold": float(getattr(strategy, "threshold_", math.nan)),
        "q": getattr(strategy, "q_", None),
        "strategy_name": strategy.name,
        "coef_sha256": hashlib.sha256(json.dumps(coefs).encode()).hexdigest(),
        "train_events": int(len(train)),
        "train_sha256": hashlib.sha256("\n".join(sorted(train["event_id"])).encode()).hexdigest(),
    }


def order(target: dict, decision: dict, config: dict) -> dict:
    """상장일 동시호가 전에 내는 당일 유효 지정가 주문(사지 않으면 주문 없음)."""
    if not decision["buy"]:
        return {"buy": False, "limit_mult": None, "limit_price": None}
    price = engine.limit_price(
        float(target["offer_price"]),
        pd.Timestamp(target["listing_date"]),
        target["market"],
        decision["limit_mult"] if decision["limit_mult"] is not None else math.nan,
        config,
    )
    return {"buy": True, "limit_mult": decision["limit_mult"], "limit_price": float(price)}


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


def forbidden_keys(doc, path: str = "") -> list[str]:
    bad = []
    if isinstance(doc, dict):
        for k, v in doc.items():
            if not path and k in RULE_SECTIONS:
                continue
            if any(part in str(k).lower() for part in FORBIDDEN_KEY_PARTS):
                bad.append(f"{path}/{k}")
            bad += forbidden_keys(v, f"{path}/{k}")
    elif isinstance(doc, list):
        for i, v in enumerate(doc):
            bad += forbidden_keys(v, f"{path}[{i}]")
    return bad


def decision_key(spec_id: str, listing_date, event_id: str) -> str:
    return f"{spec_id}/{pd.Timestamp(listing_date):%Y-%m-%d}/{event_id}.json"


def inputs_key(spec_id: str, listing_date, event_id: str) -> str:
    return f"{spec_id}/{pd.Timestamp(listing_date):%Y-%m-%d}/{event_id}.inputs.json"


def encode(doc: dict) -> bytes:
    return (
        json.dumps(_jsonable(doc), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()


def build_document(
    *,
    spec: dict,
    target: dict,
    listing_source: str,
    asof: pd.Timestamp,
    now: dt.datetime,
    host: str,
    commit: str,
    tool_sha256: str,
    lake: dict,
    disclosures: list[dict],
    fields_row: pd.Series,
    feats: pd.Series,
    decision: dict,
    order_: dict,
    inputs_sha256: str,
    config: dict,
) -> dict:
    """결정 문서. 상장 뒤 결과를 담는 키가 있으면 만들지 않는다."""
    d = pd.Timestamp(target["listing_date"])
    doc = {
        "schema_version": SCHEMA_VERSION,
        "line": LINE,
        "spec": spec,
        "code_commit": commit,
        "tool_sha256": tool_sha256,
        "event": {
            "event_id": target["event_id"],
            "corp_name": target.get("corp_name"),
            "market": target["market"],
            "planned_listing_date": d,
            "listing_date_source": listing_source,
            "first_filed": target.get("first_filed"),
            "regime": target["regime"],
            "r3_subperiod": bool(d >= pd.Timestamp(config["subperiods"]["R3"])),
        },
        "decision_session": asof,
        "deadline_kst": deadline(d).isoformat(),
        "decided_at_utc": now.astimezone(dt.UTC).isoformat(),
        "decided_at_kst": now.astimezone(KST).isoformat(),
        "host": host,
        "lake": lake,
        "disclosures": disclosures,
        "offer_price": float(target["offer_price"]),
        "fields": {k: fields_row[k] for k in fields_row.index if k != "industry"},
        "industry": fields_row.get("industry"),
        "features": feats.to_dict(),
        "model": {k: v for k, v in decision.items() if k not in ("buy", "limit_mult")},
        "decision": order_,
        "inputs_sha256": inputs_sha256,
    }
    doc = _jsonable(doc)
    bad = forbidden_keys(doc)
    if bad:
        raise ValueError(f"결정 문서에 상장 뒤 결과 키가 있다: {bad}")
    return doc
