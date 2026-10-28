"""체결·청산·비용·자산곡선 엔진 (brief §4·§5·§6). 모든 전략과 기준선이 같은 코드를 지난다.

입력 형태
- events: event_id, market, listing_date, offer_price, regime
- bars: event_id, day(상장일 = 0, KRX 거래일 순번), date, open, high, low, close
  (거래정지일은 가격이 NaN)
- decisions: event_id, buy(bool), limit_mult(NaN이면 체제 상한가에 주문)

상장일 바에서 결정에 쓰는 값은 없다. 시가·저가는 체결 판정에만, 종가는 청산·평가에만 쓴다.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ipo_open_entry import rules


def entry_fill(
    open_: float, low: float, limit_price: float, cap_threshold: float, tie_fills: bool
) -> tuple[bool, float]:
    """당일 유효 지정가 매수 한 건의 체결 여부와 가격.

    - 시가 < 지정가(상한 도달이 아닐 때): 시가에 전량 체결
    - 그 밖: 그날 저가가 기준가 아래로 내려갔으면 기준가에 체결. 기준가 이하 거래가 있었다면
      그 가격의 매수 주문은 모두 체결된 것이다
    - 상한 도달(시가 ≥ cap_threshold)이면 기준가 = min(지정가, 시가). 계산한 상한가가 실제보다
      한 호가 높아도 '저가 < 지정가'가 늘 참이 되어 있을 수 없는 체결이 생기지 않게 한다
    """
    if not (math.isfinite(open_) and math.isfinite(low)):
        raise ValueError("상장일 시가·저가가 없다 — 표본 단계에서 걸러야 한다")
    at_cap = open_ >= cap_threshold
    if not at_cap and open_ < limit_price:
        return True, float(open_)
    ref = min(limit_price, open_) if at_cap else limit_price
    if low < ref or (tie_fills and low <= ref):
        return True, float(ref)
    return False, float("nan")


def exit_fill(
    bars: pd.DataFrame,
    horizon: int,
    market: str,
    regime_name: str,
    offer: float,
    config: dict,
) -> dict:
    """h일째 종가 매도. 하한가 종가면 다음 거래일로 넘긴다(최대 이월 일수 뒤에는 그날 종가).

    거래정지일(가격 NaN)은 건너뛰되 이월로 세지 않는다. 바가 모자라면 마지막 종가에 팔고
    truncated로 표시한다.
    """
    max_rolls = int(config["execution"]["lower_limit_roll_max_days"])
    b = bars.sort_values("day").reset_index(drop=True)
    listing_open = float(b.loc[b.day == 0, "open"].iloc[0])
    prev_close: float | None = None
    rolls, locked_any = 0, False
    last_close, last_date, last_day = None, None, None
    for row in b.itertuples(index=False):
        if not math.isfinite(row.close):
            continue
        floor = rules.lower_limit(
            int(row.day), row.date, market, regime_name, offer, listing_open, prev_close, config
        )
        last_close, last_date, last_day = float(row.close), row.date, int(row.day)
        if row.day >= horizon - 1:
            locked = row.close <= floor
            if locked and rolls < max_rolls:
                rolls += 1
                locked_any = True
                prev_close = float(row.close)
                continue
            return {
                "exit_day": int(row.day),
                "exit_date": row.date,
                "exit_price": float(row.close),
                "rolls": rolls,
                "locked_exit": bool(locked),
                "rolled": locked_any,
                "truncated": False,
            }
        prev_close = float(row.close)
    if last_close is None:
        raise ValueError("청산할 종가가 하나도 없다")
    return {
        "exit_day": last_day,
        "exit_date": last_date,
        "exit_price": last_close,
        "rolls": rolls,
        "locked_exit": False,
        "rolled": locked_any,
        "truncated": True,
    }


def net_return(
    entry: float, exit_: float, sell_date: pd.Timestamp, case: str, config: dict
) -> float:
    """비용 후 수익: 매수는 (수수료+슬리피지), 매도는 (수수료+슬리피지+매도세)."""
    side = rules.side_costs_bps(case, config)
    tax = rules.sell_tax_bps(sell_date, config, case)
    return exit_ * (1 - (side + tax) / 1e4) / (entry * (1 + side / 1e4)) - 1


def limit_price(offer: float, listing_date, market: str, limit_mult: float, config: dict) -> float:
    """주문 지정가: limit_mult가 NaN이면 체제 상한가, 아니면 min(L×공모가 호가 내림, 상한가)."""
    cap = rules.cap_price(offer, listing_date, market, config)
    if limit_mult is None or not math.isfinite(limit_mult):
        return cap
    return min(rules.floor_tick(offer * float(limit_mult), listing_date, market), cap)


def build_trades(
    events: pd.DataFrame, bars: pd.DataFrame, decisions: pd.DataFrame, config: dict
) -> pd.DataFrame:
    """산다고 정한 사건마다 체결과 세 청산의 수익을 계산한다(청산별 한 행)."""
    tol = float(config["execution"]["cap_tolerance"])
    tie = bool(config["execution"]["tie_fills"])
    horizons = [int(h) for h in config["execution"]["horizons"]]
    ev = events.set_index("event_id")
    grouped = {k: g for k, g in bars.groupby("event_id")}
    rows = []
    for dec in decisions.itertuples(index=False):
        if not dec.buy:
            continue
        e = ev.loc[dec.event_id]
        b = grouped[dec.event_id]
        day0 = b.loc[b.day == 0].iloc[0]
        p = limit_price(e.offer_price, e.listing_date, e.market, dec.limit_mult, config)
        cap_threshold = tol * rules.cap_multiple(e.regime, config) * e.offer_price
        filled, entry = entry_fill(day0.open, day0.low, p, cap_threshold, tie)
        for h in horizons:
            row = {
                "event_id": dec.event_id,
                "horizon": h,
                "listing_date": e.listing_date,
                "regime": e.regime,
                "limit_price": p,
                "at_cap": bool(day0.open >= cap_threshold),
                "filled": filled,
                "entry_price": entry,
            }
            if filled:
                ex = exit_fill(b, h, e.market, e.regime, e.offer_price, config)
                row.update(ex)
                row["gross"] = ex["exit_price"] / entry - 1
                for case in ("base", "stress"):
                    row[f"net_{case}"] = net_return(
                        entry, ex["exit_price"], ex["exit_date"], case, config
                    )
            rows.append(row)
    return pd.DataFrame(rows)


def simulate_nav(
    trades: pd.DataFrame,
    bars: pd.DataFrame,
    calendar: pd.DatetimeIndex,
    case: str,
    config: dict,
) -> pd.DataFrame:
    """한 청산 시점의 일별 NAV. 사건당 예산 = 전일 NAV / slots, 지정가만큼 현금을 묶는다.

    같은 날 주문들이 묶을 현금이 가용 현금을 넘으면 그날 주문 수량을 같은 비율로 줄인다. 매도 대금은
    그날 종가 뒤에 들어오므로 다음 거래일 주문부터 쓰인다. 노는 현금 수익은 config 값(기본 0).
    """
    if trades["horizon"].nunique() > 1:
        raise ValueError("simulate_nav 는 청산 시점 하나의 거래만 받는다")
    slots = float(config["sizing"]["slots"])
    side = rules.side_costs_bps(case, config) / 1e4
    nav_prev = float(config["sizing"]["initial_nav"])
    cash = nav_prev
    closes = {
        k: g.dropna(subset=["close"]).set_index("date")["close"]
        for k, g in bars[bars.event_id.isin(trades.event_id)].groupby("event_id")
    }
    by_day = {d: g for d, g in trades.groupby("listing_date")}
    positions: dict[str, dict] = {}
    out = []
    for t in calendar:
        todays = by_day.get(t)
        if todays is not None:
            budget = nav_prev / slots
            orders = list(todays.itertuples(index=False))
            qty = {r.event_id: math.floor(budget / r.limit_price) for r in orders}
            reserve = sum(qty[r.event_id] * r.limit_price for r in orders)
            if reserve > cash > 0:
                scale = cash / reserve
                qty = {k: math.floor(q * scale) for k, q in qty.items()}
            elif cash <= 0:
                qty = dict.fromkeys(qty, 0)
            for r in orders:
                q = qty[r.event_id]
                if not r.filled or q <= 0:
                    continue
                cash -= q * r.entry_price * (1 + side)
                tax = rules.sell_tax_bps(r.exit_date, config, case) / 1e4
                positions[r.event_id] = {
                    "qty": q,
                    "exit_date": r.exit_date,
                    "exit_value": q * r.exit_price * (1 - side - tax),
                }
        for k in [k for k, pos in positions.items() if pos["exit_date"] == t]:
            cash += positions.pop(k)["exit_value"]
        held = 0.0
        for k, pos in positions.items():
            s = closes[k]
            held += pos["qty"] * float(s.loc[:t].iloc[-1])
        nav = cash + held
        out.append({"date": t, "nav": nav, "cash": cash, "exposure": held / nav if nav else 0.0})
        nav_prev = nav
    return pd.DataFrame(out)


def summarize(nav: pd.DataFrame, start: pd.Timestamp, initial_nav: float) -> dict:
    """절대 지표와 테일 4종(objective §3.1).

    CAGR, 변동성, Sharpe, MDD, 최악 월, 월수익 왜도·첨도.
    """
    s = nav.set_index("date")["nav"]
    years = (s.index[-1] - pd.Timestamp(start)).days / 365.25
    cagr = (s.iloc[-1] / initial_nav) ** (1 / years) - 1 if years > 0 else float("nan")
    daily = s.pct_change().fillna(s.iloc[0] / initial_nav - 1)
    vol = float(daily.std(ddof=1) * np.sqrt(252))
    sharpe = float(daily.mean() / daily.std(ddof=1) * np.sqrt(252)) if daily.std() > 0 else 0.0
    peak = s.cummax().clip(lower=initial_nav)
    monthly = s.resample("ME").last().pct_change()
    monthly.iloc[0] = s.resample("ME").last().iloc[0] / initial_nav - 1
    return {
        "cagr": float(cagr),
        "vol": vol,
        "sharpe": sharpe,
        "mdd": float((s / peak - 1).min()),
        "worst_month": float(monthly.min()),
        "skew_monthly": float(monthly.skew()),
        "kurt_monthly": float(monthly.kurt()),
        "months": int(monthly.size),
        "final_nav": float(s.iloc[-1]),
    }
