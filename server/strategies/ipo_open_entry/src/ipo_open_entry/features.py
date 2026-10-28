"""가설 피처(H1~H9)와 통제 변수 (brief §11).

원시 필드(fields.py)는 상장 전 공시만, 시장 피처는 결정일(상장일 전날)까지의 가격만 쓴다.
정규화·결측 대체는 모형이 학습창 안에서 한다. 여기서는 원값만 만든다.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ipo_open_entry import engine

HYPOTHESIS_COLUMNS = [
    "h1_unlocked_inst",
    "h1p_float_ratio",
    "h2_lockup_bid",
    "h2_lockup_alloc",
    "h3_bookbuild_ratio",
    "h3_bid_top",
    "h4_retail_comp",
    "h4_refund",
    "h5_price_vs_top",
    "h6_secondary",
    "h8_log_offer_amount",
    "h8_log_float_value",
    "h9_longterm",
]
ONE_DAY = pd.Timedelta(days=1)


def _ratio(num: pd.Series, den: pd.Series) -> pd.Series:
    out = num / den
    return out.where(np.isfinite(out) & (den > 0))


def hypothesis_features(f: pd.DataFrame) -> pd.DataFrame:
    """원시 필드 → 가설 피처 원값. 분모가 없거나 0이면 NaN."""
    out = pd.DataFrame(index=f.index)
    float_ratio = _ratio(f["float_shares"], f["listed_shares"])
    float_ratio = float_ratio.fillna(f["float_pct"] / 100)
    listed = f["listed_shares"].fillna(_ratio(f["float_shares"], f["float_pct"] / 100))
    float_shares = f["float_shares"].fillna(f["float_pct"] / 100 * f["listed_shares"])
    locked = f["lockup_alloc_share"].fillna(f["lockup_bid_share"]).clip(0, 1)
    out["h1_unlocked_inst"] = _ratio(f["inst_final_alloc_shares"] * (1 - locked), listed)
    out["h1p_float_ratio"] = float_ratio
    out["h2_lockup_bid"] = f["lockup_bid_share"]
    out["h2_lockup_alloc"] = f["lockup_alloc_share"]
    out["h3_bookbuild_ratio"] = f["bookbuild_ratio"]
    out["h3_bid_top"] = f["bid_top_share"]
    out["h4_retail_comp"] = _ratio(f["retail_sub_shares"], f["retail_initial_alloc_shares"])
    refund = f["retail_sub_amount"] - f["retail_final_alloc_amount"]
    out["h4_refund"] = _ratio(refund, float_shares * f["final_price"])
    out["h5_price_vs_top"] = _ratio(f["final_price"], f["band_high"]) - 1
    out["h6_secondary"] = _ratio(f["sell_shares"], f["offer_shares"])
    out["h8_log_offer_amount"] = np.log(f["final_price"] * f["offer_shares"])
    out["h8_log_float_value"] = np.log(float_shares * f["final_price"])
    out["h9_longterm"] = f["longterm_bookbuild_share"]
    return out.replace([np.inf, -np.inf], np.nan)


def b1_trades(events: pd.DataFrame, bars: pd.DataFrame, config: dict) -> pd.DataFrame:
    """'모두 산다'(체제 상한가 지정가)의 사건별 체결·청산. 상장일 바가 없는 사건은 건너뛴다."""
    day0 = bars[(bars["day"] == 0)].set_index("event_id")
    ok = day0.index[np.isfinite(day0["open"]) & np.isfinite(day0["low"])]
    ev = events[events["event_id"].isin(ok)]
    decisions = pd.DataFrame({"event_id": ev["event_id"], "buy": True, "limit_mult": np.nan})
    return engine.build_trades(ev, bars, decisions, config)


def prior_drift(
    events: pd.DataFrame, trades: pd.DataFrame, horizon: int, n: int, min_n: int
) -> pd.Series:
    """H7: 결정일 전날까지 청산이 끝난 직전 n건의 같은 청산 stress 순수익 평균.

    '끝난'은 체결됐고, 바가 모자라 잘리지 않았고, 청산일 ≤ 결정일 전날인 거래다. 이렇게 정하면
    결정일 뒤 가격을 지워도 같은 집합이 나온다(잘린 청산은 빠진다).
    """
    done = trades[(trades["horizon"] == horizon) & trades["filled"]].copy()
    if "truncated" in done:
        done = done[~done["truncated"].astype(bool)]
    done = done.sort_values(["listing_date", "event_id"])
    out = {}
    for e in events.itertuples(index=False):
        cutoff = e.listing_date - ONE_DAY
        prior = done[(done["exit_date"] <= cutoff) & (done["listing_date"] < e.listing_date)]
        tail = prior["net_stress"].tail(n)
        out[e.event_id] = float(tail.mean()) if len(tail) >= min_n else math.nan
    return pd.Series(out, name=f"h7_prior_drift_h{horizon}", dtype=float)


def market_momentum(events: pd.DataFrame, index_close: pd.Series, lookback: int) -> pd.Series:
    """통제 변수: 결정일 전날 종가 기준 지수의 lookback 거래일 수익(부호 자유)."""
    s = index_close.dropna().sort_index()
    out = {}
    for e in events.itertuples(index=False):
        past = s.loc[: e.listing_date - ONE_DAY]
        if len(past) > lookback:
            out[e.event_id] = float(past.iloc[-1] / past.iloc[-1 - lookback] - 1)
        else:
            out[e.event_id] = math.nan
    return pd.Series(out, name="ctrl_market_mom", dtype=float)


def build_features(
    events: pd.DataFrame,
    fields_table: pd.DataFrame,
    bars: pd.DataFrame,
    index_close: pd.Series,
    config: dict,
) -> pd.DataFrame:
    """사건별 피처 표(index = event_id): 가설 피처 + 청산별 H7 + 시장 통제."""
    spec = config["features"]
    out = hypothesis_features(fields_table.loc[events["event_id"]])
    trades = b1_trades(events, bars, config)
    for h in config["execution"]["horizons"]:
        out = out.join(
            prior_drift(events, trades, int(h), spec["h7_prior_events"], spec["h7_min_events"])
        )
    out = out.join(market_momentum(events, index_close, spec["market_lookback_days"]))
    out.index.name = "event_id"
    return out
