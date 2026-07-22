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
- sector_index: 시장×업종 일별 시총가중 지수 (2016~, 시작 100 체인).
- sector_perf: 업종별 최신 성과 스냅샷 (1d/1w/1m/3m/YTD + 시총 비중).
- kr_etf_meta: 현재 상장 KRX ETF 유니버스 → 앱 meta 확장용 (APP_DATA 루트에 저장).
- valuation_daily: 시장별 밸류에이션 집계 (시총가중 조화 PER·PBR, 배당수익률)
  — krx_fundamental 미수집 시 스킵.
- track_strategies: 저장된 전략의 실전(저장 후) NAV 추적 (P7)
  → {APP_DATA}/portfolio/live_nav.parquet [port_id, trade_date, value, as_of].

모든 테이블에 as_of(마지막 거래일 "YYYY-MM-DD") 컬럼 포함.

사용:
    APP_DATA=... QDATA_LAKE=... python scripts/build_insights.py
"""

import json
import os
import sys
import traceback

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server"))

from datastore import fx, meta, portfolio, storage  # noqa: E402
from module import regime  # noqa: E402
from module.backtest import Backtest  # noqa: E402
from module.util import backtest_result  # noqa: E402
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


MIN_SECTOR_STOCKS = 5  # 구성 종목 5개 미만 업종은 지수 제외 (노이즈 컷)
ETF_META_ID_BASE = 900_000  # KR ETF meta_id = 900000 + int(ticker); 비숫자 티커는 990000+ 순번


def _sector_index() -> pd.DataFrame:
    """시장×업종 일별 시총가중 지수 — sector_index/sector_perf 공용 (1회 계산 캐시).

    업종 분류는 월별 스냅샷 — 각 일자에 그 이전 최근 스냅샷을 merge_asof로 매핑.
    일별 업종 수익률 = 전일 시총 가중 평균 (adj_close pct_change), 시작 100 체인.
    """
    if "sector_index" in _cache:
        return _cache["sector_index"]

    px = qdata_api.load_krx_prices(start="2016-01-01", columns=["adj_close", "mktcap"])
    sec = qdata_api.load_krx_sector()[["date", "ticker", "market", "sector"]]

    merged = pd.merge_asof(
        px.sort_values("date"),
        sec.sort_values("date"),
        on="date",
        by="ticker",
        direction="backward",
    ).dropna(subset=["sector"])

    merged = merged.sort_values(["ticker", "date"])
    g = merged.groupby("ticker")
    merged["ret"] = g["adj_close"].pct_change()
    merged["w"] = g["mktcap"].shift(1)  # 전일 시총 가중 (look-ahead 방지)
    valid = merged.dropna(subset=["ret", "w"]).copy()
    valid["wret"] = valid["ret"] * valid["w"]

    agg = (
        valid.groupby(["date", "market", "sector"], as_index=False)
        .agg(wret=("wret", "sum"), w=("w", "sum"), n_stocks=("ret", "size"))
    )
    agg = agg[(agg["n_stocks"] >= MIN_SECTOR_STOCKS) & (agg["w"] > 0)].copy()
    agg["ret_1d"] = agg["wret"] / agg["w"]

    agg = agg.sort_values(["market", "sector", "date"]).reset_index(drop=True)
    keys = [agg["market"], agg["sector"]]
    cum = (1.0 + agg["ret_1d"]).groupby(keys).cumprod()
    agg["index_value"] = 100.0 * cum / cum.groupby(keys).transform("first")
    agg["ret_1d"] = agg["ret_1d"] * 100  # 출력은 %
    agg["n_stocks"] = agg["n_stocks"].astype(int)

    df = agg[["date", "market", "sector", "index_value", "ret_1d", "n_stocks"]].copy()
    df["as_of"] = pd.Timestamp(px["date"].max()).strftime("%Y-%m-%d")
    _cache["sector_index"] = df
    return df


def build_sector_index() -> pd.DataFrame:
    return _sector_index()


def build_sector_perf() -> pd.DataFrame:
    """업종별 최신 성과 스냅샷 — sector_index 체인에서 1d/1w/1m/3m/YTD 수익률(%).

    mktcap_weight: 최신 업종 스냅샷 기준 해당 시장 시총 대비 업종 시총 비중(%).
    """
    si = _sector_index()
    as_of = si["as_of"].iloc[0]
    last_date = si["date"].max()
    year_start = pd.Timestamp(pd.Timestamp(last_date).year, 1, 1)

    # 시장별 업종 시총 비중 — 최신 가격 스냅샷 × 최신 업종 분류
    sec = qdata_api.load_krx_sector()
    latest_sec = sec[sec["date"] == sec["date"].max()][["ticker", "market", "sector"]]
    snap = _latest_price_snapshot()[["mktcap"]]
    cap = latest_sec.join(snap, on="ticker").dropna(subset=["mktcap"])
    sector_cap = cap.groupby(["market", "sector"])["mktcap"].sum()
    market_cap = cap.groupby("market")["mktcap"].sum()
    weight = (sector_cap / market_cap * 100).rename("mktcap_weight")

    rows = []
    for (market, sector), grp in si.groupby(["market", "sector"]):
        grp = grp.sort_values("date")
        if grp["date"].iloc[-1] != last_date:  # 최신일에 없는 업종(개편·소멸) 제외
            continue
        iv = grp["index_value"].to_numpy()
        last = iv[-1]

        def _ret(n: int):
            return (last / iv[-1 - n] - 1) * 100 if len(iv) > n else None

        ytd_base = grp[grp["date"] < year_start]
        ret_ytd = (
            (last / ytd_base["index_value"].iloc[-1] - 1) * 100 if not ytd_base.empty else None
        )
        rows.append(
            {
                "market": market,
                "sector": sector,
                "ret_1d": grp["ret_1d"].iloc[-1],
                "ret_1w": _ret(5),
                "ret_1m": _ret(21),
                "ret_3m": _ret(63),
                "ret_ytd": ret_ytd,
                "n_stocks": int(grp["n_stocks"].iloc[-1]),
                "mktcap_weight": weight.get((market, sector)),
            }
        )
    df = pd.DataFrame(rows).sort_values(["market", "sector"]).reset_index(drop=True)
    df["as_of"] = as_of
    return df


def build_kr_etf_meta() -> pd.DataFrame:
    """현재 상장 KRX ETF → 앱 meta 스키마 행.

    meta_id = 900000 + int(ticker) (6자리 숫자 티커); 비숫자·충돌 시 990000+ 순번.
    krx_etf에는 종목명·시총이 없어 name=ticker, marketcap=None (클라이언트는 티커 표시).
    """
    etf = qdata_api.load_krx_etf_prices()
    last = etf["date"].max()
    live = sorted(etf.loc[etf["date"] == last, "ticker"].unique())
    rng = etf[etf["ticker"].isin(live)].groupby("ticker")["date"].agg(["min", "max"])

    used: set[int] = set()
    next_seq = ETF_META_ID_BASE + 90_000  # 990000
    rows = []
    for ticker in live:
        if ticker.isdigit() and ETF_META_ID_BASE + int(ticker) not in used:
            mid = ETF_META_ID_BASE + int(ticker)
        else:
            while next_seq in used:
                next_seq += 1
            mid = next_seq
        used.add(mid)
        rows.append(
            {
                "meta_id": mid,
                "ticker": ticker,
                "name": ticker,
                "security_type": "etf",
                "asset_class": None,
                "sector": None,
                "iso_code": "KR",
                "marketcap": None,
                "min_date": rng.loc[ticker, "min"].strftime("%Y-%m-%d"),
                "max_date": rng.loc[ticker, "max"].strftime("%Y-%m-%d"),
            }
        )
    df = pd.DataFrame(rows)
    df["as_of"] = pd.Timestamp(last).strftime("%Y-%m-%d")
    return df


def build_valuation_daily():
    """시장별 일별 밸류에이션 — 시총가중 조화 PER/PBR + 시총가중 배당수익률.

    PER/PBR=0은 KRX 결측 표기(적자 등)라 양수만 사용. pct_rank는 전 기간 백분위.
    krx_fundamental 미수집(백필 중)이면 None 반환 → main이 스킵.
    """
    try:
        f = qdata_api.load_krx_fundamental(columns=["market", "per", "pbr", "div"])
    except FileNotFoundError:
        print("[skip] valuation (fundamental 미수집)")
        return None

    start = pd.Timestamp(f["date"].min()).strftime("%Y-%m-%d")
    px = qdata_api.load_krx_prices(start=start, columns=["mktcap"])
    m = f.merge(px[["date", "ticker", "mktcap"]], on=["date", "ticker"], how="inner")
    m = m[m["mktcap"] > 0]

    def _agg(g: pd.DataFrame) -> pd.Series:
        pe = g[g["per"] > 0]
        pb = g[g["pbr"] > 0]
        dv = g.dropna(subset=["div"])
        return pd.Series(
            {
                "per": pe["mktcap"].sum() / (pe["mktcap"] / pe["per"]).sum() if len(pe) else np.nan,
                "pbr": pb["mktcap"].sum() / (pb["mktcap"] / pb["pbr"]).sum() if len(pb) else np.nan,
                "div": (dv["div"] * dv["mktcap"]).sum() / dv["mktcap"].sum() if len(dv) else np.nan,
            }
        )

    df = m.groupby(["date", "market"]).apply(_agg, include_groups=False).reset_index()
    df = df.sort_values(["market", "date"]).reset_index(drop=True)
    for col in ("pbr", "per"):
        df[f"pct_rank_{col}"] = df.groupby("market")[col].rank(pct=True) * 100
    df = df[["date", "market", "per", "pbr", "div", "pct_rank_pbr", "pct_rank_per"]]
    df["as_of"] = pd.Timestamp(m["date"].max()).strftime("%Y-%m-%d")
    return df


MOMENTUM_WARMUP_DAYS = 400  # 모멘텀 12개월 룩백 + 여유 (저장 시점 이전 워밍업 데이터)


def build_track_strategies():
    """저장된 전략 실전 추적 (P7) — 저장 시점(created_at)부터 오늘까지
    POST /backtest와 동일한 엔진으로 NAV를 다시 굴린다.

    행: [port_id, trade_date, value, as_of]. NAV는 saved_at 기준 1000 시작.
    포트폴리오 단위 실패는 경고 후 스킵 (예: US 개별주 아카이브가 끝난 종목은
    가격이 있는 데까지만 커브가 나온다 — 엔진이 자동 처리).
    """
    ports = portfolio.records()
    if ports.empty:
        print("[skip] track_strategies (저장된 포트폴리오 없음)")
        return None

    st = meta.strategy_df().set_index("strategy_id")["strategy"]
    frames = []
    for p in ports.itertuples():
        try:
            saved_at = pd.Timestamp(p.created_at)

            cfg = None
            raw = getattr(p, "config", None)
            if isinstance(raw, str) and raw.strip():
                cfg = json.loads(raw)
            if not cfg:  # P2 이전 행 — config 컬럼 부재/None
                cfg = {
                    "algorithm": st.get(p.strategy_id, "eq"),
                    "rebal_freq": "M",
                    "cost_bps": 10.0,
                    "params": {},
                }
            algorithm = cfg.get("algorithm") or "eq"
            freq = cfg.get("rebal_freq") or "M"
            cost_bps = float(cfg.get("cost_bps") or 10.0)
            params = cfg.get("params") or {}

            meta_ids = portfolio.universe(int(p.port_id))
            if not meta_ids:
                raise ValueError("유니버스가 비어 있음")

            bt = Backtest(strategy_name=p.port_name)
            warmup_start = (saved_at - pd.Timedelta(days=MOMENTUM_WARMUP_DAYS)).date()
            price = bt.data(meta_id=meta_ids, start_date=warmup_start, end_date=None)
            if price.empty:
                raise ValueError("가격 데이터 없음")
            if cfg.get("currency") == "KRW":
                mapping = meta.resolve(meta_ids=meta_ids)
                price = fx.to_krw(price, dict(zip(mapping["ticker"], mapping["iso_code"])))

            weight = bt.rebalance(
                price=price,
                method=algorithm,
                freq=freq,
                custom_weight=params.get("weights"),
                params=params,
            )
            if weight is None or weight.empty:
                raise ValueError("리밸런스 비중 산출 실패")

            # 저장 시점의 목표 배분은 즉시 실행된 것으로 본다 — saved_at 이전
            # 마지막 리밸런스 행을 saved_at으로 재날짜해 시드로 쓰고, 이후 행과
            # 이어붙인다 (기간 중간 저장도 다음 리밸런스 전까지 커브가 나온다).
            weight = weight.sort_index()
            weight.index = pd.to_datetime(weight.index)
            saved_norm = saved_at.normalize()
            pre = weight.loc[:saved_norm]
            if pre.empty:
                raise ValueError("저장 시점 이전 리밸런스 비중 없음 (워밍업 부족)")
            seed = pre.iloc[[-1]].copy()
            seed.index = pd.DatetimeIndex([saved_norm])
            weight = pd.concat([seed, weight.loc[weight.index > saved_norm]])

            _, nav, _ = backtest_result(
                weight=weight, price=price, start_date=saved_at.date(), cost_bps=cost_bps
            )
            nav = nav.dropna()
            if nav.empty:
                raise ValueError("NAV 비어 있음")

            part = nav.reset_index()
            part.columns = ["trade_date", "value"]
            part.insert(0, "port_id", int(p.port_id))
            frames.append(part)
        except Exception as e:
            print(
                f"[warn] track_strategies port_id={p.port_id}({p.port_name}) 실패: {e}",
                file=sys.stderr,
            )

    if not frames:
        print("[skip] track_strategies (추적 가능한 포트폴리오 없음)")
        return None

    df = pd.concat(frames, ignore_index=True)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df.sort_values(["port_id", "trade_date"]).reset_index(drop=True)
    df["as_of"] = pd.Timestamp(df["trade_date"].max()).strftime("%Y-%m-%d")
    return df


# ---------------------------------------------------------------- 실행


BUILDERS = [
    ("insight/regime_asset_perf.parquet", build_regime_asset_perf, {}),
    ("insight/flows_summary.parquet", build_flows_summary, {}),
    ("insight/flows_top.parquet", build_flows_top, {}),
    ("insight/flows_by_ticker.parquet", build_flows_by_ticker, {"row_group_size": 100_000}),
    ("insight/breadth_daily.parquet", build_breadth_daily, {}),
    ("insight/flows_signals.parquet", build_flows_signals, {}),
    ("insight/sector_index.parquet", build_sector_index, {}),
    ("insight/sector_perf.parquet", build_sector_perf, {}),
    ("kr_etf_meta.parquet", build_kr_etf_meta, {}),  # 앱 루트 — meta_df()가 union
    ("insight/valuation_daily.parquet", build_valuation_daily, {}),
    ("portfolio/live_nav.parquet", build_track_strategies, {}),  # 전략 실전 추적 (P7)
]


def main():
    failed = []
    for relpath, builder, write_kwargs in BUILDERS:
        name = relpath.rsplit("/", 1)[-1].removesuffix(".parquet")
        try:
            df = builder()
            if df is None:  # 소스 미수집 등으로 빌더가 스스로 스킵
                continue
            target = storage.write_parquet(df, *relpath.split("/"), **write_kwargs)
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
