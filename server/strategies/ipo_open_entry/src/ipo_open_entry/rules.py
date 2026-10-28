"""KRX 가격 규칙 — 호가단위, 상장일 가격 범위, 가격제한, 매도세 (brief §2·§4·§6).

가격 판정은 원가격(`close` 등)으로 한다. `adj_close`는 재스케일된 계열이라
가격제한 판정에 쓰면 틀린다.
"""

from __future__ import annotations

import math

import pandas as pd

#: 2023-01-25 호가단위 개편: 코스피·코스닥 공통 7단계로 통일
TICK_REFORM = pd.Timestamp("2023-01-25")
#: (이 가격 미만이면, 호가단위)
_TICKS_UNIFIED = (
    (2_000, 1),
    (5_000, 5),
    (20_000, 10),
    (50_000, 50),
    (200_000, 100),
    (500_000, 500),
    (math.inf, 1_000),
)
_TICKS_KOSPI_OLD = (
    (1_000, 1),
    (5_000, 5),
    (10_000, 10),
    (50_000, 50),
    (100_000, 100),
    (500_000, 500),
    (math.inf, 1_000),
)
_TICKS_KOSDAQ_OLD = ((1_000, 1), (5_000, 5), (10_000, 10), (50_000, 50), (math.inf, 100))


def tick_size(price: float, date: pd.Timestamp, market: str) -> int:
    """그 가격대의 호가단위. 시장은 'KOSPI' 또는 'KOSDAQ'."""
    if pd.Timestamp(date) >= TICK_REFORM:
        table = _TICKS_UNIFIED
    elif market == "KOSPI":
        table = _TICKS_KOSPI_OLD
    elif market == "KOSDAQ":
        table = _TICKS_KOSDAQ_OLD
    else:
        raise ValueError(f"시장을 모른다: {market!r}")
    for upper, tick in table:
        if price < upper:
            return tick
    raise AssertionError("unreachable")


def floor_tick(price: float, date: pd.Timestamp, market: str) -> float:
    """price 이하의 가장 높은 호가."""
    tick = tick_size(price, date, market)
    return math.floor(price / tick + 1e-9) * tick


def ceil_tick(price: float, date: pd.Timestamp, market: str) -> float:
    """price 이상의 가장 낮은 호가. 올림이 호가대를 넘으면 그 호가대 단위로 다시 맞춘다."""
    tick = tick_size(price, date, market)
    up = math.ceil(price / tick - 1e-9) * tick
    tick_up = tick_size(up, date, market)
    return up if tick_up == tick else math.ceil(price / tick_up - 1e-9) * tick_up


def regime(listing_date: pd.Timestamp, config: dict) -> str | None:
    """상장일 체제. R1·R2 밖(2015-06-15 이전)은 None."""
    d = pd.Timestamp(listing_date)
    r1, r2 = (pd.Timestamp(config["regimes"][k]["start"]) for k in ("R1", "R2"))
    if d >= r2:
        return "R2"
    if d >= r1:
        return "R1"
    return None


def cap_multiple(regime_name: str, config: dict) -> float:
    """상장일 시가(동시호가) 상한 배수: R1 2.0, R2 4.0."""
    return float(config["regimes"][regime_name]["open_band"][1])


def cap_price(offer: float, listing_date: pd.Timestamp, market: str, config: dict) -> float:
    """체제 상한가 — 공모가×상한 배수를 호가단위로 내린 값."""
    mult = cap_multiple(regime(listing_date, config), config)
    return floor_tick(offer * mult, listing_date, market)


def lower_limit(
    day: int,
    date: pd.Timestamp,
    market: str,
    regime_name: str,
    offer: float,
    listing_open: float,
    prev_close: float | None,
    config: dict,
) -> float:
    """그날 하한가. 1일째(day 0)는 R1 시가×0.7, R2 공모가×0.6, 2일째부터 전일 종가×0.7."""
    limit = float(config["execution"]["daily_limit"])
    if day == 0:
        if config["regimes"][regime_name]["day1_limit_base"] == "open":
            base = listing_open * (1 - limit)
        else:
            base = offer * float(config["regimes"][regime_name]["open_band"][0])
    else:
        if prev_close is None or not math.isfinite(prev_close):
            raise ValueError("2일째 이후 하한가에는 전일 종가가 필요하다")
        base = prev_close * (1 - limit)
    return ceil_tick(base, date, market)


def sell_tax_bps(sell_date: pd.Timestamp, config: dict, case: str) -> float:
    """매도세(농특세 포함, bp). base는 매도일 법정세율, stress는 고정값."""
    spec = config["costs"][case]
    if spec.get("sell_tax") != "statutory":
        return float(spec["sell_tax_bps"])
    schedule = sorted(
        (pd.Timestamp(row["from"]), float(row["bps"]))
        for row in config["costs"]["statutory_sell_tax_bps"]
    )
    d = pd.Timestamp(sell_date)
    rate = None
    for start, bps in schedule:
        if d >= start:
            rate = bps
    if rate is None:
        raise ValueError(f"세율표가 {d.date()} 을 덮지 않는다")
    return rate


def side_costs_bps(case: str, config: dict) -> float:
    """매수·매도 각 측의 수수료 + 슬리피지(bp). 매도세는 따로 더한다."""
    spec = config["costs"][case]
    return float(spec["commission_bps_per_side"]) + float(spec["slippage_bps_per_side"])
