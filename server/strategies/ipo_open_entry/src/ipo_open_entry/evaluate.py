"""상장일 순 walk-forward 평가와 지표 (brief §5·§7~§10).

전략은 `fit(train)`과 `decide(test)` 두 함수를 가진다.
- train: 학습 사건(분기 시작 전에 세 청산이 모두 끝난 사건)의 피처 + 라벨(LABEL_COLUMNS)
- test: 그 분기에 상장하는 사건의 피처를 상장일 하나씩 넘긴다(같은 날 상장분만 함께).
  라벨과 시가 배수 m은 평가기가 지운 뒤 넘긴다
- decide 반환: event_id, buy(bool), limit_mult(NaN이면 체제 상한가 지정가)

정규화·결측 대체·문턱은 전략이 train 안에서만 정한다.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

import numpy as np
import pandas as pd

from ipo_open_entry import engine, features

KEY_COLUMNS = ["event_id", "listing_date", "regime", "market", "offer_price"]


class Strategy(Protocol):
    name: str

    def fit(self, train: pd.DataFrame) -> None: ...

    def decide(self, test: pd.DataFrame) -> pd.DataFrame: ...


class BuyNothing:
    """B0: 아무것도 사지 않는다."""

    name = "B0"

    def fit(self, train: pd.DataFrame) -> None:
        pass

    def decide(self, test: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame({"event_id": test["event_id"], "buy": False, "limit_mult": np.nan})


class BuyAll:
    """B1: 모든 공모주를 체제 상한가 지정가로 산다(limit_mult가 있으면 그 배수로)."""

    def __init__(self, limit_mult: float = np.nan):
        self.limit_mult = limit_mult
        self.name = "B1" if np.isnan(limit_mult) else f"B1-L{limit_mult:g}"

    def fit(self, train: pd.DataFrame) -> None:
        pass

    def decide(self, test: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(
            {"event_id": test["event_id"], "buy": True, "limit_mult": self.limit_mult}
        )


def labels(data: dict, config: dict) -> pd.DataFrame:
    """사건별 학습 라벨: 시가 진입 가정의 청산별 수익과 B1(상한가 지정가) 체결 결과."""
    ev, bars = data["events"], data["bars"]
    day0 = bars[bars["day"] == 0].set_index("event_id")
    ev = ev.set_index("event_id")
    out = pd.DataFrame(index=ev.index)
    out["m"] = day0["open"] / ev["offer_price"]
    b1 = features.b1_trades(data["events"], bars, config)
    out["b1_filled"] = b1[b1["horizon"] == 1].set_index("event_id")["filled"]
    out["at_cap"] = b1[b1["horizon"] == 1].set_index("event_id")["at_cap"]
    grouped = dict(tuple(bars.groupby("event_id")))
    for h in config["execution"]["horizons"]:
        gross, net, exit_dates = {}, {}, {}
        for e in ev.itertuples():
            ex = engine.exit_fill(
                grouped[e.Index], int(h), e.market, e.regime, e.offer_price, config
            )
            entry = float(day0.at[e.Index, "open"])
            gross[e.Index] = ex["exit_price"] / entry - 1
            net[e.Index] = engine.net_return(
                entry, ex["exit_price"], ex["exit_date"], "stress", config
            )
            exit_dates[e.Index] = ex["exit_date"]
        out[f"ret_open_h{h}"] = pd.Series(gross)
        out[f"net_open_h{h}"] = pd.Series(net)
        out[f"exit_date_h{h}"] = pd.Series(exit_dates)
        b1h = b1[b1["horizon"] == h].set_index("event_id")
        out[f"b1_net_h{h}"] = b1h["net_stress"]
    out.index.name = "event_id"
    return out


LABEL_PREFIXES = ("m", "b1_", "at_cap", "ret_open_", "net_open_", "exit_date_")


def label_columns(frame: pd.DataFrame) -> list[str]:
    return [c for c in frame.columns if c == "m" or c.startswith(LABEL_PREFIXES[1:])]


def build_table(data: dict, config: dict) -> pd.DataFrame:
    """사건별 피처 + 라벨 표."""
    index_close = data["index"].set_index("date")["kosdaq"]
    feats = features.build_features(
        data["events"], data["fields"].set_index("event_id"), data["bars"], index_close, config
    )
    table = data["events"][KEY_COLUMNS].set_index("event_id").join(feats).join(labels(data, config))
    return table.reset_index()


def quarter_starts(start: pd.Timestamp, end: pd.Timestamp) -> pd.DatetimeIndex:
    return pd.date_range(start, end, freq="QS")


def walk_forward(
    make_strategy: Callable[[], Strategy], table: pd.DataFrame, config: dict
) -> pd.DataFrame:
    """분기 초마다 새 전략을 학습해 그 분기 상장 사건의 결정을 낸다."""
    oos_start = pd.Timestamp(config["windows"]["oos_start"])
    exits = [f"exit_date_h{h}" for h in config["execution"]["horizons"]]
    last_exit = table[exits].max(axis=1)
    labels_ = label_columns(table)
    decisions = []
    end = table["listing_date"].max()
    for qs in quarter_starts(oos_start, end):
        qe = qs + pd.offsets.QuarterBegin(startingMonth=1)
        test = table[(table["listing_date"] >= qs) & (table["listing_date"] < qe)]
        if test.empty:
            continue
        train = table[(table["listing_date"] < qs) & (last_exit < qs)]
        strategy = make_strategy()
        strategy.fit(train.copy())
        # 상장일 단위로 결정한다 — 같은 분기의 뒤 상장분이 앞 결정에 섞이지 않게
        for day, day_test in test.groupby("listing_date"):
            out = strategy.decide(day_test.drop(columns=labels_).copy())
            if set(out["event_id"]) != set(day_test["event_id"]):
                raise ValueError(f"{strategy.name}: {day.date()} 결정이 시험 사건과 맞지 않는다")
            decisions.append(out.assign(quarter=qs))
    return pd.concat(decisions, ignore_index=True)


def portfolio(
    decisions: pd.DataFrame,
    data: dict,
    config: dict,
    start: pd.Timestamp,
    regime: str | None = None,
) -> dict:
    """청산·비용별 거래와 NAV, 요약 지표. regime을 주면 그 체제 사건만 그 구간에서 잰다."""
    ev = data["events"]
    if regime is not None:
        ev = ev[ev["regime"] == regime]
    dec = decisions[decisions["event_id"].isin(ev["event_id"])]
    calendar = pd.DatetimeIndex(sorted(data["bars"]["date"].dropna().unique()))
    calendar = calendar[calendar >= start]
    trades = engine.build_trades(ev, data["bars"], dec, config)
    out = {"trades": trades, "nav": {}, "summary": {}}
    initial = float(config["sizing"]["initial_nav"])
    for h in config["execution"]["horizons"]:
        th = trades[trades["horizon"] == h] if len(trades) else trades
        for case in ("base", "stress"):
            if len(th):
                nav = engine.simulate_nav(th, data["bars"], calendar, case, config)
            else:
                nav = pd.DataFrame(
                    {"date": calendar, "nav": initial, "cash": initial, "exposure": 0.0}
                )
            out["nav"][(h, case)] = nav
            out["summary"][f"h{h}_{case}"] = engine.summarize(nav, start, initial)
    for case in ("base", "stress"):
        out["summary"][f"mean_cagr_{case}"] = float(
            np.mean(
                [out["summary"][f"h{h}_{case}"]["cagr"] for h in config["execution"]["horizons"]]
            )
        )
    return out


def event_stats(trades: pd.DataFrame, decisions: pd.DataFrame, horizon: int) -> dict:
    """단위 없는 사건 지표: 선택·체결 수, 체결 사건의 평균 stress 순수익과 적중률."""
    th = trades[(trades["horizon"] == horizon)] if len(trades) else trades
    filled = th[th["filled"]] if len(th) else th
    net = filled["net_stress"] if len(filled) else pd.Series(dtype=float)
    return {
        "selected": int(decisions["buy"].sum()),
        "filled": int(len(filled)),
        "mean_net_stress": float(net.mean()) if len(net) else float("nan"),
        "hit_rate": float((net > 0).mean()) if len(net) else float("nan"),
    }


def paired_vs_b1(
    trades: pd.DataFrame, b1_trades: pd.DataFrame, horizon: int, n_boot: int, seed: int
) -> dict:
    """B1 대비 사건별 쌍 차이(같은 1단위 투입, 미체결은 0).

    평균과 상장월 블록 부트스트랩 90% 구간을 낸다.
    """

    def per_event(t):
        th = t[t["horizon"] == horizon]
        return th.set_index("event_id")["net_stress"].where(th.set_index("event_id")["filled"], 0.0)

    b1 = per_event(b1_trades).fillna(0.0)
    mine = per_event(trades).reindex(b1.index).fillna(0.0) if len(trades) else b1 * 0.0
    diff = mine - b1
    month = b1_trades[b1_trades["horizon"] == horizon].set_index("event_id")["listing_date"]
    month = month.reindex(diff.index).dt.to_period("M")
    blocks = [diff[month == m].to_numpy() for m in month.unique()]
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(blocks), len(blocks))
        sample = np.concatenate([blocks[i] for i in pick])
        boots.append(sample.mean())
    lo, hi = np.percentile(boots, [5, 95]) if boots else (np.nan, np.nan)
    return {
        "mean_diff": float(diff.mean()),
        "ci90": [float(lo), float(hi)],
        "events": int(diff.size),
    }
