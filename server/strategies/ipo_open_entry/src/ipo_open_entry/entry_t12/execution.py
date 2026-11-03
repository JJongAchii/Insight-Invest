"""Entry execution rules for entry-t12-v1. The audited engine is reused unchanged.

Two choices change, both fixed the night before listing:

- limit multiple per buy: a constant, or a conviction ladder read only from the t12
  decision row (primary score margin, supplement flag) and earlier quarters' decisions
- fill mode: ``gfd`` is the existing day order (open fill, else intraday fill when the low
  goes below the limit); ``open-only`` keeps only the opening-auction fill and cancels the
  order right after the open

The listing-day open and low decide fills only; they never set the limit.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ipo_open_entry import engine

FILLS = ("gfd", "open-only")
DECISION_COLUMNS = ["event_id", "quarter", "buy", "additional_buy", "score", "threshold"]
OUTCOME_COLUMNS = [
    "entry_price",
    "exit_day",
    "exit_date",
    "exit_price",
    "rolls",
    "locked_exit",
    "rolled",
    "truncated",
    "gross",
    "net_base",
    "net_stress",
]


def _allowed(value, allowed):
    if not any(math.isclose(float(value), a) for a in allowed):
        raise ValueError(f"limit multiple {value} is outside the registered set {allowed}")
    return float(value)


def limit_mults(decisions: pd.DataFrame, rule: dict, allowed, min_history: int) -> pd.Series:
    """Limit multiple for each buy (NaN for passes), indexed like ``decisions``.

    Reads only the decision row fields in ``DECISION_COLUMNS``. The strong tier compares a
    primary buy's score margin with the median margin of primary buys from earlier quarters,
    which were all decided before the current quarter began.
    """
    d = decisions[DECISION_COLUMNS].copy()
    buy = d["buy"].astype(bool)
    out = pd.Series(np.nan, index=d.index, dtype=float)
    kind = rule.get("kind")
    if kind == "constant":
        if set(rule) != {"kind", "mult"}:
            raise ValueError(f"constant rule takes only mult: {rule}")
        out[buy] = _allowed(rule["mult"], allowed)
        return out
    if kind != "conviction":
        raise ValueError(f"unapproved limit rule: {rule}")
    if set(rule) != {"kind", "complement", "primary", "strong"}:
        raise ValueError(f"conviction rule takes complement, primary, strong: {rule}")
    supplement = buy & d["additional_buy"].astype(bool)
    primary = buy & ~d["additional_buy"].astype(bool)
    out[supplement] = _allowed(rule["complement"], allowed)
    out[primary] = _allowed(rule["primary"], allowed)
    if rule["strong"] is None:
        return out
    strong = _allowed(rule["strong"], allowed)
    margin = d["score"] - d["threshold"]
    for quarter in sorted(d.loc[primary, "quarter"].unique()):
        past = primary & (d["quarter"] < quarter)
        if int(past.sum()) < min_history:
            continue
        cut = float(margin[past].median())
        now = primary & (d["quarter"] == quarter) & (margin >= cut)
        out[now] = strong
    return out


def build_trades(
    events: pd.DataFrame, bars: pd.DataFrame, orders: pd.DataFrame, config: dict, fill: str
) -> pd.DataFrame:
    """Engine trades for ``orders`` (event_id, buy, limit_mult), then apply the fill mode.

    ``open-only`` turns every fill that did not happen at the open into an unfilled order.
    An open fill is exactly the engine's first branch: not at cap and open < limit.
    """
    if fill not in FILLS:
        raise ValueError(f"unapproved fill mode: {fill}")
    trades = engine.build_trades(events, bars, orders, config)
    if fill == "gfd" or trades.empty:
        return trades
    day0 = bars[bars["day"] == 0].set_index("event_id")["open"]
    opened = trades["event_id"].map(day0)
    if opened.isna().any():
        raise ValueError("missing listing-day open")
    open_fill = trades["filled"].astype(bool) & ~trades["at_cap"].astype(bool)
    open_fill &= opened < trades["limit_price"]
    drop = trades["filled"].astype(bool) & ~open_fill
    out = trades.copy()
    out["filled"] = out["filled"].astype(bool) & ~drop
    for column in OUTCOME_COLUMNS:
        if column not in out:
            continue
        if out[column].dtype == bool:
            out[column] = out[column].astype(object)
        out.loc[drop, column] = np.nan
    return out


def fill_state(trades: pd.DataFrame, bars: pd.DataFrame) -> pd.Series:
    """open / intraday / unfilled for each order row (diagnostic only)."""
    day0 = bars[bars["day"] == 0].set_index("event_id")["open"]
    opened = trades["event_id"].map(day0)
    filled = trades["filled"].astype(bool)
    at_open = filled & ~trades["at_cap"].astype(bool) & (opened < trades["limit_price"])
    return pd.Series(
        np.where(~filled, "unfilled", np.where(at_open, "open", "intraday")), index=trades.index
    )


def portfolio(
    orders: pd.DataFrame, data: dict, config: dict, start: pd.Timestamp, fill: str
) -> dict:
    """Trades, NAV and summary for one horizon — ``evaluate.portfolio`` with the fill mode."""
    horizons = [int(h) for h in config["execution"]["horizons"]]
    if len(horizons) != 1:
        raise ValueError("entry-t12-v1 evaluates one horizon")
    h = horizons[0]
    ev = data["events"]
    dec = orders[orders["event_id"].isin(ev["event_id"])]
    calendar = pd.DatetimeIndex(sorted(data["bars"]["date"].dropna().unique()))
    calendar = calendar[calendar >= start]
    trades = build_trades(ev, data["bars"], dec, config, fill)
    initial = float(config["sizing"]["initial_nav"])
    out = {"trades": trades, "nav": {}, "summary": {}}
    for case in ("base", "stress"):
        if len(trades):
            nav = engine.simulate_nav(trades, data["bars"], calendar, case, config)
        else:
            nav = pd.DataFrame({"date": calendar, "nav": initial, "cash": initial, "exposure": 0.0})
        out["nav"][(h, case)] = nav
        out["summary"][f"h{h}_{case}"] = engine.summarize(nav, start, initial)
    return out
