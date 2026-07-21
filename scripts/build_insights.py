#!/usr/bin/env python
"""로컬 일일 파이프라인용 인사이트 사전계산 빌더.

Lambda가 아닌 로컬에서 실행한다 — qdata 레이크(QDATA_LAKE)를 읽어
APP_DATA(기본 s3://insight-invest-datalake/app) 아래 parquet로 결과를 쓴다.
krx_flows 전체 로드(수백 MB)는 로컬에서만 허용 — Lambda에서는 절대 금지.

빌더:
- regime_asset_perf: 매크로 4국면 × 자산 월간수익 기술통계 (P3).
- flows_summary: 시장(KOSPI/KOSDAQ/ALL) × 투자자별 일별 수급 합계 (전 기간).
- flows_top: 1d/5d/21d 창 × frgn/inst 순매수·순매도 상위 30.
- flows_by_ticker: 최근 3년 종목별 수급 피벗 — ticker 정렬 + row_group_size
  분할로 Lambda의 per-ticker 필터가 로우그룹 프루닝되게 한다.
- breadth_daily: 시장폭 (등락 종목수·52주 신고/신저·상하한·MA20 상회 비율).
- flows_signals: 종목×투자자 최신 스냅샷 — 연속 순매수/도 일수, 20일 강도,
  수급-가격 다이버전스.

모든 테이블에 as_of(마지막 거래일 "YYYY-MM-DD") 컬럼 포함.

사용:
    APP_DATA=... QDATA_LAKE=... python scripts/build_insights.py
"""

import os
import sys
import traceback

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server"))

from datastore import storage  # noqa: E402
from module import regime  # noqa: E402
from qdata import api as qdata_api  # noqa: E402

ETF_TICKERS = ["SPY", "QQQ", "TLT", "GLD", "DBC"]
WINDOWS = {"1d": 1, "1w": 5, "1m": 21}  # 거래일 수
MKTCAP_FLOOR = 1e10  # 시총 100억 미만 제외 (signals 노이즈 컷)

_cache: dict = {}


# ---------------------------------------------------------------- 공용 로더 (1회 로드 캐시)


def _flows() -> pd.DataFrame:
    """krx_flows 전체 (long). 로컬 전용 — 374MB 파일 통째 로드."""
    if "flows" not in _cache:
        _cache["flows"] = qdata_api.load_krx_flows()
    return _cache["flows"]


def _trade_dates() -> np.ndarray:
    """수급 기준 거래일 오름차순."""
    if "dates" not in _cache:
        _cache["dates"] = np.sort(_flows()["date"].unique())
    return _cache["dates"]


def _as_of() -> str:
    return pd.Timestamp(_trade_dates()[-1]).strftime("%Y-%m-%d")


def _latest_price_snapshot() -> pd.DataFrame:
    """마지막 거래일 종목 스냅샷 [market, close, chg_pct, mktcap] (index=ticker)."""
    if "snap" not in _cache:
        start = (pd.Timestamp.today() - pd.DateOffset(days=14)).strftime("%Y-%m-%d")
        px = qdata_api.load_krx_prices(start=start, columns=["market", "close", "chg_pct", "mktcap"])
        last = px["date"].max()
        _cache["snap"] = (
            px[px["date"] == last].set_index("ticker")[["market", "close", "chg_pct", "mktcap"]]
        )
    return _cache["snap"]


def _name_map() -> dict:
    """최신 섹터 스냅샷 기준 ticker → 종목명."""
    if "names" not in _cache:
        sec = qdata_api.load_krx_sector()
        latest = sec[sec["date"] == sec["date"].max()]
        _cache["names"] = latest.set_index("ticker")["name"].to_dict()
    return _cache["names"]


# ---------------------------------------------------------------- 빌더


def _monthly_returns() -> pd.DataFrame:
    """자산별 월간 수익률(%) — 월말 종가 기준, 인덱스는 월간 Period."""
    px = qdata_api.load_prices(ETF_TICKERS, fields=("adj_close",))["adj_close"]
    rets = px.resample("ME").last().pct_change() * 100

    idx = qdata_api.load_krx_index()
    kospi = (
        idx[idx["index"] == "KOSPI"].set_index("date")["close"].sort_index()
    )
    rets["KOSPI"] = kospi.resample("ME").last().pct_change() * 100

    rets.index = pd.PeriodIndex(rets.index, freq="M")
    return rets


def build_regime_asset_perf() -> pd.DataFrame:
    phases = regime.phase_history()["phase"]
    rets = _monthly_returns()

    long = rets.stack().rename("ret").reset_index()
    long.columns = ["month", "ticker", "ret"]
    long["phase"] = long["month"].map(phases)
    long = long.dropna(subset=["phase", "ret"])

    rows = []
    for (phase, ticker), g in long.groupby(["phase", "ticker"]):
        mean_pct = g["ret"].mean()
        rows.append(
            {
                "phase": phase,
                "ticker": ticker,
                "mean_monthly_ret": mean_pct,
                "ann_ret": ((1 + mean_pct / 100) ** 12 - 1) * 100,
                "hit_rate": (g["ret"] > 0).mean() * 100,
                "n_months": int(len(g)),
            }
        )
    df = pd.DataFrame(rows).sort_values(["phase", "ticker"]).reset_index(drop=True)
    df["as_of"] = pd.Timestamp.today().strftime("%Y-%m-%d")
    return df


def build_flows_summary() -> pd.DataFrame:
    """시장 × 투자자별 일별 수급 합계 (전 기간) + market="ALL" 합산 행."""
    flows = _flows()
    cols = ["buy_value", "sell_value", "net_value"]
    per_mkt = flows.groupby(["date", "market", "investor"], as_index=False)[cols].sum()
    all_mkt = flows.groupby(["date", "investor"], as_index=False)[cols].sum()
    all_mkt["market"] = "ALL"
    df = pd.concat([per_mkt, all_mkt], ignore_index=True)
    df = df[["date", "market", "investor", *cols]].sort_values(
        ["date", "market", "investor"]
    ).reset_index(drop=True)
    df["as_of"] = _as_of()
    return df


def build_flows_top() -> pd.DataFrame:
    """창(1d/1w/1m) × 투자자(frgn/inst) 순매수 상위 30(rank 1..30) · 순매도 상위 30(rank -1..-30)."""
    flows = _flows()
    dates = _trade_dates()
    snap = _latest_price_snapshot()
    names = _name_map()

    frames = []
    max_win = max(WINDOWS.values())
    recent = flows[
        (flows["date"] >= dates[-max_win]) & (flows["investor"].isin(["frgn", "inst"]))
    ]
    for wname, n in WINDOWS.items():
        sub = recent[recent["date"] >= dates[-n]]
        agg = sub.groupby(["investor", "ticker", "market"], as_index=False)[
            ["net_value", "net_volume"]
        ].sum()
        for inv in ("frgn", "inst"):
            a = agg[agg["investor"] == inv]
            top = a.nlargest(30, "net_value").copy()
            top["rank"] = range(1, len(top) + 1)
            bot = a.nsmallest(30, "net_value").copy()
            bot["rank"] = range(-1, -len(bot) - 1, -1)
            part = pd.concat([top, bot], ignore_index=True)
            part["window"] = wname
            frames.append(part)

    df = pd.concat(frames, ignore_index=True)
    df["name"] = df["ticker"].map(names).fillna(df["ticker"])
    df = df.join(snap[["close", "chg_pct", "mktcap"]], on="ticker")
    df = df[
        [
            "window", "investor", "rank", "ticker", "name", "market",
            "net_value", "net_volume", "close", "chg_pct", "mktcap",
        ]
    ].reset_index(drop=True)
    df["as_of"] = _as_of()
    return df


def build_flows_by_ticker() -> pd.DataFrame:
    """최근 3년 종목별 수급 피벗 [ticker, date, frgn_net, inst_net, indiv_net].

    ticker→date 정렬 후 row_group_size=100_000으로 쓰기 —
    Lambda의 filters=[("ticker","==",…)] 읽기가 로우그룹 통계로 프루닝된다.
    """
    flows = _flows()
    cutoff = pd.Timestamp(_trade_dates()[-1]) - pd.DateOffset(years=3)
    sub = flows.loc[flows["date"] >= cutoff, ["date", "ticker", "investor", "net_value"]]
    wide = sub.pivot(index=["ticker", "date"], columns="investor", values="net_value")
    wide = wide.rename(
        columns={"frgn": "frgn_net", "inst": "inst_net", "indiv": "indiv_net"}
    ).reset_index()
    df = wide[["ticker", "date", "frgn_net", "inst_net", "indiv_net"]].sort_values(
        ["ticker", "date"]
    ).reset_index(drop=True)
    df.columns.name = None
    df["as_of"] = _as_of()
    return df


def build_breadth_daily() -> pd.DataFrame:
    """시장폭 일별 지표 — 2016년부터 계산(252d 워밍업), 2017년부터 출력."""
    px = qdata_api.load_krx_prices(
        start="2016-01-01", columns=["market", "close", "chg_pct", "value"]
    )
    close_w = px.pivot(index="date", columns="ticker", values="close").sort_index()
    roll_max = close_w.rolling(252, min_periods=252).max()
    roll_min = close_w.rolling(252, min_periods=252).min()
    ma20 = close_w.rolling(20, min_periods=20).mean()

    def _stack(mask: pd.DataFrame, name: str) -> pd.Series:
        s = mask.stack()
        s.name = name
        return s

    flags = pd.concat(
        [
            _stack(close_w == roll_max, "new_high_52w"),
            _stack(close_w == roll_min, "new_low_52w"),
            _stack(close_w > ma20, "above_ma20"),
            _stack(ma20.notna() & close_w.notna(), "ma20_valid"),
        ],
        axis=1,
    )
    long = px.join(flags, on=["date", "ticker"])
    long["advances"] = long["chg_pct"] > 0
    long["declines"] = long["chg_pct"] < 0
    long["unchanged"] = long["chg_pct"] == 0
    long["limit_up"] = long["chg_pct"] >= 29.5
    long["limit_down"] = long["chg_pct"] <= -29.5

    g = long.groupby(["date", "market"])
    df = g[
        [
            "advances", "declines", "unchanged", "new_high_52w", "new_low_52w",
            "limit_up", "limit_down", "above_ma20", "ma20_valid",
        ]
    ].sum()
    df["total_value"] = g["value"].sum()
    df["pct_above_ma20"] = np.where(
        df["ma20_valid"] > 0, df["above_ma20"] / df["ma20_valid"] * 100, np.nan
    )
    df = df.reset_index()
    df = df[df["date"] >= "2017-01-01"]
    count_cols = [
        "advances", "declines", "unchanged", "new_high_52w", "new_low_52w",
        "limit_up", "limit_down",
    ]
    df[count_cols] = df[count_cols].astype(int)
    df = df[
        ["date", "market", *count_cols, "pct_above_ma20", "total_value"]
    ].sort_values(["date", "market"]).reset_index(drop=True)
    df["as_of"] = pd.Timestamp(px["date"].max()).strftime("%Y-%m-%d")
    return df


def build_flows_signals() -> pd.DataFrame:
    """종목 × 투자자(frgn/inst) 최신 수급 신호 스냅샷.

    streak: 마지막 거래일과 같은 부호의 연속 일수 (+매수 연속 / -매도 연속).
    intensity_20d: 20일 순매수 합 / 시총 (%). ret_20d: adj_close 20거래일 수익률(%).
    divergence: 가격↓+수급↑ = "bull", 가격↑+수급↓ = "bear".
    """
    flows = _flows()
    dates = _trade_dates()
    snap = _latest_price_snapshot()
    names = _name_map()

    # streak 탐색 창 — 260거래일이면 실무적으로 충분 (그 이상 연속은 260으로 포화)
    sub = flows[
        (flows["date"] >= dates[-260]) & (flows["investor"].isin(["frgn", "inst"]))
    ]

    # 20거래일 가격수익률 (adj_close)
    adj = qdata_api.load_krx_prices(
        start=pd.Timestamp(dates[-30]).strftime("%Y-%m-%d"), columns=["adj_close"]
    )
    adates = np.sort(adj["date"].unique())
    a_now = adj[adj["date"] == adates[-1]].set_index("ticker")["adj_close"]
    a_prev = adj[adj["date"] == adates[-21]].set_index("ticker")["adj_close"]
    ret_20d = (a_now / a_prev - 1) * 100

    frames = []
    for inv in ("frgn", "inst"):
        w = (
            sub[sub["investor"] == inv]
            .pivot(index="date", columns="ticker", values="net_value")
            .sort_index()
        )
        sign = np.sign(w.to_numpy(dtype="float64"))  # NaN 보존
        last_sign = sign[-1]
        match = sign == last_sign[None, :]  # NaN 비교 → False (streak 단절)
        streak_len = np.cumprod(match[::-1], axis=0).sum(axis=0)
        streak = streak_len * np.nan_to_num(last_sign)

        d = pd.DataFrame(
            {
                "ticker": w.columns,
                "streak": streak.astype(int),
                "net_1d": w.iloc[-1].to_numpy(),
                "net_20d": w.iloc[-20:].sum().to_numpy(),
            }
        )
        d["investor"] = inv
        frames.append(d)

    df = pd.concat(frames, ignore_index=True)
    df = df.join(snap, on="ticker")  # market, close, chg_pct, mktcap
    df = df[df["mktcap"] >= MKTCAP_FLOOR]
    df["name"] = df["ticker"].map(names).fillna(df["ticker"])
    df["intensity_20d"] = df["net_20d"] / df["mktcap"] * 100
    df["ret_20d"] = df["ticker"].map(ret_20d)
    df["divergence"] = None
    df.loc[(df["ret_20d"] < 0) & (df["intensity_20d"] > 0.3), "divergence"] = "bull"
    df.loc[(df["ret_20d"] > 0) & (df["intensity_20d"] < -0.3), "divergence"] = "bear"
    df = df[
        [
            "ticker", "name", "market", "close", "chg_pct", "mktcap", "investor",
            "streak", "net_1d", "net_20d", "intensity_20d", "ret_20d", "divergence",
        ]
    ].reset_index(drop=True)
    df["as_of"] = _as_of()
    return df


# ---------------------------------------------------------------- 실행


BUILDERS = [
    ("regime_asset_perf", build_regime_asset_perf, {}),
    ("flows_summary", build_flows_summary, {}),
    ("flows_top", build_flows_top, {}),
    ("flows_by_ticker", build_flows_by_ticker, {"row_group_size": 100_000}),
    ("breadth_daily", build_breadth_daily, {}),
    ("flows_signals", build_flows_signals, {}),
]


def main():
    failed = []
    for name, builder, write_kwargs in BUILDERS:
        try:
            df = builder()
            target = storage.write_parquet(df, "insight", f"{name}.parquet", **write_kwargs)
            print(f"{name} → {target} ({len(df)} rows, as_of={df['as_of'].iloc[0]})")
        except Exception:
            failed.append(name)
            print(f"{name} FAILED:", file=sys.stderr)
            traceback.print_exc()
    if failed:
        print(f"실패한 빌더: {failed}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
