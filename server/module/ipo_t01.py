"""공모주 t01 운영 결정 (계약 ipo-live-ops, quant-lab 운용 규칙 op-day1-v2).

결정 계산은 quant-lab `strategies/ipo-open-entry`의 결정 경로를 바이트 그대로 옮긴 사본
(`server/strategies/ipo_open_entry`, `VENDOR.json`)이 한다 — 백테스트한 코드와 운영 코드가 같아야
백테스트 성과가 그 규칙의 성과다. 이 모듈은 그 사본을 부르고, quant-lab `operate/lake.py`와
`dataset.py`가 하던 레이크 적재(qdata.api)만 옮겨 적었다(qlab 의존을 빼려고). 옮겨 적은 함수는
이름과 순서를 원본과 같게 둔다.

결정 순서는 quant-lab `scripts/decide.py`의 t01 경로와 같다.
1. 결정 시점: 계획 상장일 D의 전 KRX 거래일(as-of) 장 마감 뒤. 레이크 마지막 KRX 날짜가 as-of와 같아야 한다
2. 학습: 분기 시작 전에 세 청산이 끝난 개발 사건(고정 데이터셋)과 개발 구간 뒤 사건(레이크)
3. 피처: as-of까지 자른 입력으로 `features.build_features`
4. 결정: `SignedRegression`(운용 규칙의 인자) fit → decide, 주문 = 공모가 × 1.5 호가 내림 당일 유효 지정가
"""

from __future__ import annotations

import datetime as dt
import functools
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

LINE_DIR = Path(__file__).resolve().parents[1] / "strategies" / "ipo_open_entry"
if str(LINE_DIR / "src") not in sys.path:
    sys.path.insert(0, str(LINE_DIR / "src"))

from ipo_open_entry import engine, evaluate, fields, rules  # noqa: E402
from ipo_open_entry.config import load_config  # noqa: E402
from ipo_open_entry.models.regression import SignedRegression  # noqa: E402
from ipo_open_entry.operate import calendar, decision  # noqa: E402
from ipo_open_entry.operate.decision import NotEligible, NotReady, TooLate  # noqa: E402

SPEC_PATH = LINE_DIR / "docs" / "operating-rule-day1.md"
DATASET = LINE_DIR / "data" / "dev-20260909-v4"
FILES = ("events", "fields", "bars", "index")
PRICE_COLUMNS = ["open", "high", "low", "close"]
MARKETS = ("KOSPI", "KOSDAQ")
#: 결정 전에 원문이 다 받아져 있어야 하는 공모의 최초 접수 창 — 개발 구간 끝 이 일수 전부터.
#: 개발 뒤 상장 사건(학습·직전 공모 결과)과 상장 예정 대상이 이 창에 든다
COVERAGE_DAYS = 180
FIELD_TYPES = ("ipo", "transfer")  # quant-data가 모든 원문을 받는 유형. 나머지는 기준 문서만

__all__ = ["NotEligible", "NotReady", "TooLate", "decide_listing", "engine", "rule", "rules"]


@functools.lru_cache(maxsize=1)
def rule() -> dict:
    """운용 규칙 문서(op-day1-v2) 머리말."""
    text = SPEC_PATH.read_text()
    return yaml.safe_load(text.split("---")[1])


def make_strategy() -> SignedRegression:
    return SignedRegression(**rule()["strategy_args"])


@functools.lru_cache(maxsize=1)
def config() -> dict:
    return load_config()


@functools.lru_cache(maxsize=1)
def dev_data() -> dict[str, pd.DataFrame]:
    """운용 규칙의 학습 데이터셋(개발 구간 상장분, 고정)."""
    return {name: pd.read_parquet(DATASET / f"{name}.parquet") for name in FILES}


@functools.lru_cache(maxsize=1)
def dev_table() -> pd.DataFrame:
    return evaluate.build_table(dev_data(), config())


def dev_end() -> pd.Timestamp:
    return pd.Timestamp(config()["sealed_window"]["dev_end"])


# --- quant-lab dataset.py에서 옮겨 적음 -------------------------------------------------------


def trading_calendar(
    index_prices: pd.DataFrame, prices: pd.DataFrame, until: pd.Timestamp
) -> pd.DatetimeIndex:
    """KRX 거래일: 지수 시세가 있는 날 ∪ 종목이 실제로 거래된 날."""
    dates = set(index_prices["date"]) | set(prices["date"])
    cal = pd.DatetimeIndex(sorted(dates))
    return cal[cal <= until]


def event_bars(
    events: pd.DataFrame, prices: pd.DataFrame, cal: pd.DatetimeIndex, n_days: int
) -> pd.DataFrame:
    """사건마다 상장일부터 KRX 거래일 n_days개의 일봉. 거래가 없는 날은 가격이 NaN이다."""
    pos = cal.get_indexer(events["listing_date"])
    if (pos < 0).any():
        missing = events.loc[pos < 0, "event_id"].tolist()
        raise ValueError(f"상장일이 KRX 달력에 없다: {missing}")
    rows = []
    for e, p in zip(events.itertuples(index=False), pos, strict=True):
        for day, date in enumerate(cal[p : p + n_days]):
            rows.append({"event_id": e.event_id, "ticker": e.ticker, "day": day, "date": date})
    frame = pd.DataFrame(rows, columns=["event_id", "ticker", "day", "date"])
    px = prices[["ticker", "date", *PRICE_COLUMNS]]
    out = frame.merge(px, on=["ticker", "date"], how="left", validate="many_to_one")
    no_trade = (out[["open", "high", "low"]] == 0).all(axis=1)
    out.loc[no_trade, PRICE_COLUMNS] = np.nan
    return out.drop(columns="ticker")


# --- quant-lab operate/lake.py에서 옮겨 적음 --------------------------------------------------


def index_frame(api, cfg: dict, start) -> pd.DataFrame:
    """달력 지수와 시장 통제 지수의 종가(long)."""
    codes = [cfg["lake"]["calendar_index_code"], cfg["features"]["market_index_code"]]
    ix = api.load_krx_index_prices(start=str(pd.Timestamp(start).date()), codes=codes)
    ix["date"] = pd.to_datetime(ix["date"]).astype("datetime64[ns]")
    return ix


def lake_last_date(ix: pd.DataFrame) -> pd.Timestamp:
    """두 지수 모두 있는 마지막 날 — 그날 KRX 발행이 끝났다고 본다."""
    both = ix.groupby("date")["index_code"].nunique()
    return both.index[both == 2].max()


def target_event(api, event_id: str, listing_date, market: str, cfg: dict) -> tuple:
    """대상 사건 한 행, 그 원시 필드, 상장 전 관측값, 사용한 공시 목록."""
    d = pd.Timestamp(listing_date).normalize()
    ev = api.load_ipo_events()
    row = ev[ev["event_id"] == event_id]
    if len(row) != 1:
        raise NotEligible(f"레이크에 사건 {event_id}가 {len(row)}건이다")
    e = row.iloc[0]
    if e["listing_type"] != cfg["universe"]["listing_type"]:
        raise NotEligible(f"{event_id}: 상장 유형이 {e['listing_type']}다")
    if e["status"] == "withdrawn":
        raise NotEligible(f"{event_id}: 철회된 공모다")
    if pd.notna(e["listing_date"]):
        raise TooLate(f"{event_id}: 레이크에 이미 상장일 {pd.Timestamp(e['listing_date']).date()}")
    if market not in MARKETS:
        raise NotEligible(f"시장이 {market}다")
    obs = api.load_ipo_observations(event_ids=[event_id])
    one = pd.DataFrame({"event_id": [event_id], "listing_date": [d]})
    table = fields.build_fields(obs, one)
    offer = float(table.at[event_id, "final_price"])
    if not math.isfinite(offer):
        raise NotEligible(f"{event_id}: 상장 전 공시에 확정 공모가가 없다")
    used = fields.pre_listing(obs, one)
    docs = api.load_ipo_documents(event_ids=[event_id]).set_index("rcept_no")
    disclosures = [
        {
            "rcept_no": str(r),
            "filed_date": pd.Timestamp(g["filed_date"].iloc[0]),
            "report_nm": docs["report_nm"].get(r),
            "rows": int(len(g)),
        }
        for r, g in used.groupby("rcept_no", sort=True)
    ]
    target = {
        "event_id": event_id,
        "corp_name": e["corp_name"],
        "market": market,
        "listing_date": d,
        "offer_price": offer,
        "regime": rules.regime(d, cfg),
        "first_filed": pd.Timestamp(e["first_filed"]),
    }
    return target, table, used, disclosures


def post_dev_events(api, end, asof, ix: pd.DataFrame, cfg: dict) -> dict:
    """개발 구간 끝 뒤 as-of까지 상장한 사건의 표·필드·일봉(as-of까지). 오염 구간 사건은 뺀다."""
    ev = api.load_ipo_events()
    ev = ev[ev["listing_type"] == cfg["universe"]["listing_type"]]
    ev = ev[(ev["listing_date"] > end) & (ev["listing_date"] <= asof)]
    ev = ev[ev["stock_code"].notna() & ev["market"].isin(MARKETS)]
    ev = ev.rename(columns={"stock_code": "ticker"}).reset_index(drop=True)
    ev["listing_date"] = pd.to_datetime(ev["listing_date"]).astype("datetime64[ns]")
    dup = ev["ticker"].duplicated(keep=False)
    if dup.any():
        raise ValueError(f"같은 종목코드의 상장 사건이 둘 이상: {sorted(ev.loc[dup, 'ticker'])}")
    if ev.empty:
        empty = pd.DataFrame(columns=["event_id", "day", "date", *PRICE_COLUMNS])
        return {"events": ev, "fields": pd.DataFrame(), "bars": empty, "contaminated": []}
    obs = api.load_ipo_observations(event_ids=ev["event_id"].tolist())
    table = fields.build_fields(obs, ev)
    ev["offer_price"] = ev["event_id"].map(table["final_price"])
    ev = ev[ev["offer_price"].notna()].reset_index(drop=True)
    ev["regime"] = [rules.regime(d, cfg) for d in ev["listing_date"]]
    prices = api.load_krx_prices(
        start=str(ev["listing_date"].min().date()),
        end=str(pd.Timestamp(asof).date()),
        tickers=sorted(ev["ticker"].unique()),
        columns=PRICE_COLUMNS,
    )
    prices["date"] = pd.to_datetime(prices["date"]).astype("datetime64[ns]")
    cal = trading_calendar(ix, prices, pd.Timestamp(asof))
    bars = event_bars(ev, prices, cal, int(cfg["execution"]["bars_after_listing"]))
    day0 = bars[bars["day"] == 0].set_index("event_id")
    usable = day0.index[np.isfinite(day0[["open", "low", "close"]]).all(axis=1)]
    ev = ev[ev["event_id"].isin(usable)].reset_index(drop=True)
    bars = bars[bars["event_id"].isin(usable)].reset_index(drop=True)
    bad = decision.contaminated_events(bars)
    keep = ~ev["event_id"].isin(bad)
    return {
        "events": ev[keep].reset_index(drop=True),
        "fields": table.loc[ev.loc[keep, "event_id"]],
        "bars": bars[~bars["event_id"].isin(bad)].reset_index(drop=True),
        "contaminated": list(bad),
    }


def kosdaq_close(dev_index: pd.DataFrame, ix: pd.DataFrame, cfg: dict, asof) -> pd.Series:
    """시장 통제 지수 종가: 개발 데이터셋의 지수에 그 뒤 레이크 지수를 잇는다(as-of까지)."""
    code = cfg["features"]["market_index_code"]
    dev = dev_index.set_index("date")["kosdaq"].dropna()
    lake = ix[ix["index_code"] == code].set_index("date")["close"].sort_index()
    joined = pd.concat([dev, lake[lake.index > dev.index.max()]])
    return joined[joined.index <= pd.Timestamp(asof)]


# --- 결정 -------------------------------------------------------------------------------------


def missing_documents(api, asof, event_id: str | None = None) -> list[str]:
    """결정에 쓰는 공모(최초 접수가 개발 구간 끝 COVERAGE_DAYS일 전 ~ asof, 그리고 대상)의 원문 중 아직
    받지 못한 접수번호.

    운영 레이크는 공시 원문을 하루 예산만큼 이어받는다(quant-data ADR-0034). 덜 받은 채로 결정하면 대상의
    공모가·학습 사건·직전 공모 결과가 연구 레이크와 달라져 quant-lab과 다른 결정이 나온다 — 그날은 결정을
    미룬다. 필드 유형(ipo·transfer)은 모든 원문을, 나머지는 분류에 쓰는 기준 문서만 본다.
    """
    since = dev_end() - pd.Timedelta(days=COVERAGE_DAYS)
    ev = api.load_ipo_events()
    live = ev[
        ((ev["first_filed"] >= since) & (ev["first_filed"] <= asof)) | (ev["event_id"] == event_id)
    ]
    docs = api.load_ipo_documents(event_ids=live["event_id"].tolist())
    gap = docs[(docs["filed_date"] <= asof) & (docs["parse_status"] == "not_downloaded")]
    field = gap["event_id"].isin(live.loc[live["listing_type"].isin(FIELD_TYPES), "event_id"])
    anchor = gap["rcept_no"].isin(live["first_rcept_no"])
    return sorted(gap.loc[field | anchor, "rcept_no"].astype(str))


def decide_listing(
    api, event_id: str, listing_date, market: str, now: dt.datetime | None = None
) -> dict:
    """상장 예정 공모주 하나의 t01 결정. 결정할 수 없으면 NotReady·TooLate·NotEligible을 낸다."""
    cfg = config()
    listing = pd.Timestamp(listing_date).normalize()
    now = now or dt.datetime.now(dt.UTC)
    ix = index_frame(api, cfg, dev_end() - pd.Timedelta(days=120))
    lake_last = lake_last_date(ix)
    asof = decision.check_timing(listing, lake_last, now)
    # 대상 필드를 읽기 전에 — 덜 받은 공시로 '부적격'을 기록하거나 다른 결정을 내지 않게
    gaps = missing_documents(api, asof, event_id)
    if gaps:
        raise NotReady(
            f"최근 공모 공시 원문 {len(gaps)}건을 아직 받지 못했다(운영 레이크가 이어받는 중, "
            f"예: {', '.join(gaps[:3])})"
        )

    dev = dev_data()
    target, target_fields, used_obs, disclosures = target_event(api, event_id, listing, market, cfg)
    post = post_dev_events(api, dev_end(), asof, ix, cfg)
    close = kosdaq_close(dev["index"], ix, cfg, asof)
    prior_events = pd.concat([dev["events"], post["events"]], ignore_index=True)
    prior_fields = pd.concat([dev["fields"].set_index("event_id"), post["fields"]])
    prior_bars = pd.concat([dev["bars"], post["bars"]], ignore_index=True)
    feats = decision.target_features(
        target, target_fields, prior_events, prior_fields, prior_bars, close, asof, cfg
    )
    qs = decision.quarter_start(listing)
    post_table = decision.post_dev_table(dev, post, close, cfg)
    horizons = [int(h) for h in cfg["execution"]["horizons"]]
    train = decision.training_table(dev_table(), post_table, qs, horizons)
    row = pd.DataFrame([{**{c: target[c] for c in evaluate.KEY_COLUMNS}, **feats.to_dict()}])
    made = decision.decide(make_strategy, train, row)
    order = decision.order(target, made, cfg)
    return {
        "spec": rule()["spec"],
        "event_id": event_id,
        "corp_name": target["corp_name"],
        "market": market,
        "listing_date": listing,
        "decision_session": asof,
        "lake_last_date": lake_last,
        "offer_price": target["offer_price"],
        "regime": target["regime"],
        "order": order,
        "score": made["score"],
        "threshold": made["threshold"],
        "q": made["q"],
        "train_events": made["train_events"],
        "train_sha256": made["train_sha256"],
        "coef_sha256": made["coef_sha256"],
        "disclosures": disclosures,
        "post_dev_training_events": [] if post_table is None else post_table["event_id"].tolist(),
        "excluded_contaminated": post["contaminated"],
        "features": {k: (None if pd.isna(v) else float(v)) for k, v in feats.items()},
    }


def next_session(day) -> pd.Timestamp:
    """day 다음 KRX 거래일(옮긴 quant-lab 달력)."""
    d = pd.Timestamp(day).normalize()
    later = calendar.sessions(d + pd.Timedelta(days=1), d + pd.Timedelta(days=21))
    if later.empty:
        raise ValueError(f"{d.date()} 뒤 3주 안에 KRX 거래일이 없다 — 달력을 갱신한다")
    return later[0]
