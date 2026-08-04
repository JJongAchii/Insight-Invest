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
- spotlight: 오늘의 신호 종목 — 전시장 스캔 그룹 3종(신고가 유지·외인 연속매수
  10일+·매집형) × 상한 5. 웹 홈 레인·텔레그램 신호 섹션 공용.
- sector_index: 시장×업종 일별 시총가중 지수 (2016~, 시작 100 체인).
- sector_perf: 업종별 최신 성과 스냅샷 (1d/1w/1m/3m/YTD + 시총 비중).
- kr_etf_meta: 현재 상장 KRX ETF 유니버스 → 앱 meta 확장용 (APP_DATA 루트에 저장).
- valuation_daily: 시장별 밸류에이션 집계 (시총가중 조화 PER·PBR, 배당수익률)
  — krx_fundamental 미수집 시 스킵.
- signal_study: 신호 13종 × 지평선 3개 전방 초과성과. 벤치마크는 유동성 유니버스
  동일가중 횡단면 평균이고, 조건 없는 baseline 행이 비교 기준으로 함께 들어간다.
- track_strategies: 저장된 전략의 실전(저장 후) NAV 추적 (P7)
  → {APP_DATA}/portfolio/live_nav.parquet [port_id, trade_date, value, as_of].
  같은 book(드리프트 보유 비중)을 함수 내부에서 직접
  {APP_DATA}/portfolio/live_weights.parquet [port_id, trade_date, ticker, weight,
  as_of]로도 기록한다.
- rebal_signals: active 전략의 리밸 전일 신호 — 다음 거래일이 새 주기면 목표 비중
  → {APP_DATA}/portfolio/rebal_signals.parquet.

모든 테이블에 as_of(마지막 거래일 "YYYY-MM-DD") 컬럼 포함.

사용:
    APP_DATA=... QDATA_LAKE=... python scripts/build_insights.py
"""

import json
import os
import sys
import traceback
import warnings

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server"))

from datastore import fx, meta, portfolio, storage  # noqa: E402
from module import regime  # noqa: E402
from module import spotlight  # noqa: E402
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


US_PRICE_FLOOR = "2008-01-02"  # 스펙 D4 — 배당 축 신뢰 구간 (ETF 분배금 2007 중반부터)


def build_us_prices():
    """US 가격 앱 추출 (P0) — massive 미러에서 meta US 티커의 총수익 계열 재생성.

    스펙 docs/superpowers/specs/2026-08-04-us-price-source-unification-design.md §3.
    미러 읽기 실패 시 None 반환 → 기존 us_prices.parquet 유지 (경고만 — 하류 빌더는
    어제 데이터로 진행). 연속성 가드 제외·배당락 소실은 반드시 경고 로그로 남긴다.
    """
    from module import us_prices as uspx

    try:
        m = meta.meta_df()
        us = m[m["iso_code"] == "US"][["meta_id", "ticker"]].drop_duplicates("ticker")
        seg_src = {s for segs in uspx.TICKER_SEGMENTS.values() for s, _, _ in segs}
        want = sorted(set(us["ticker"]) | seg_src)

        frames = []
        for y in range(int(US_PRICE_FLOOR[:4]), pd.Timestamp.today().year + 1):
            chunk = qdata_api.load_us_prices(
                start=max(f"{y}-01-01", US_PRICE_FLOOR), end=f"{y}-12-31",
                tickers=want, columns=["close", "adj_close"],
            )
            if not chunk.empty:
                frames.append(chunk)
        px = pd.concat(frames, ignore_index=True)
        px["date"] = pd.to_datetime(px["date"])
        div = qdata_api.load_us_dividends(tickers=want)
        div["ex_date"] = pd.to_datetime(div["ex_date"])
        px, div = uspx.stitch_segments(px, div, uspx.TICKER_SEGMENTS)
    except Exception:
        print("[warn] us_prices: 미러 읽기 실패 — 기존 파일 유지", file=sys.stderr)
        traceback.print_exc()
        return None

    stale_days = (pd.Timestamp.today().normalize() - px["date"].max()).days
    if stale_days > 4:
        print(f"[warn] us_prices: 미러 최종일 {px['date'].max().date()} ({stale_days}일 경과) — "
              "리밸 신호는 is_new_period 가 자연 스킵", file=sys.stderr)

    out, skipped, lost_div = [], [], 0.0
    for tk, g in px.groupby("ticker", sort=False):
        g = g.sort_values("date").set_index("date")
        issues = uspx.continuity_issues(g)
        if issues:
            skipped.append(f"{tk}({'; '.join(issues[:2])})")
            continue
        dv = div[div["ticker"] == tk]
        lost_div += float(dv.loc[~dv["ex_date"].isin(g.index), "cash_amount"].sum())
        res = uspx.compose_total_return(g, dv)
        res = res.reset_index().rename(columns={"date": "trade_date"})
        res["ticker"] = tk
        out.append(res)

    if skipped:
        print(f"[warn] us_prices: 연속성 가드 제외 {len(skipped)}종목 — {skipped[:20]}",
              file=sys.stderr)
    if lost_div:
        print(f"[warn] us_prices: 비거래일 배당락 소실 합계 ${lost_div:.2f}", file=sys.stderr)

    df = pd.concat(out, ignore_index=True).merge(us, on="ticker", how="inner")
    missing = sorted(set(us["ticker"]) - set(df["ticker"]))
    if missing:
        print(f"[warn] us_prices: meta 등록 but 미수록 {len(missing)}종목 "
              "(플로어 이전 상폐·미러 부재·가드 제외)", file=sys.stderr)
    df = df[["meta_id", "trade_date", "ticker", "adj_close", "gross_return"]]
    df = df.sort_values(["ticker", "trade_date"]).reset_index(drop=True)
    df["as_of"] = _as_of()
    return df


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
    _cache["flows_signals"] = df  # build_spotlight가 재사용 (재계산 방지)
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


def _book_to_weights(
    book: pd.DataFrame,
    price: pd.DataFrame,
    port_id: int,
    nav_last,
    fallback_weights: "pd.Series | None" = None,
) -> pd.DataFrame:
    """엔진 book(index Date, columns ticker/weights)을 [port_id, trade_date, ticker,
    weight] long으로 정규화. weight는 투자 자산 내 비중(book 자체 관례 —
    현금 비반영, 합≈1.0, 현금 보유 여부와 무관)이다.

    calculate_nav는 매 리밸 구간의 마지막 날을 다음 구간의 리밸 행과 중복되지
    않도록 제외한다(iloc[:-1]) — 그런데 마지막 구간은 다음 구간이 없어 그 날
    (=nav 마지막 날)이 통째로 빠진다. book 마지막 행에 같은 구간의 가격 드리프트를
    적용해(book 자체의 투자자산-내 정규화 관례와 동치: w_i × price_rel_i, 합 1로
    재정규화) 그 하루를 채운다 — 그래야 live_weights의 마지막 날짜가 live_nav와
    맞는다.

    구간이 단 하루뿐이면(오늘 막 저장된 전략 — saved_at == nav_last) 위 iloc[:-1]이
    그 유일한 행마저 지워 book이 통째로 빈다 — 드리프트 기준행이 없어 가격 보정도
    불가능하다. 이때는 fallback_weights(리밸 스케줄의 마지막 행 — 저장 당일은
    드리프트 전이라 목표 비중 == 보유 비중)를 nav_last 날짜 행으로 쓰되, book과
    같은 관례로 투자자산 내 재정규화한다 — custom(FixedWeight 등, 현금 잔여를
    허용하는) 전략은 원시 목표 비중의 합이 1 미만일 수 있는데, 그대로 쓰면 다음날
    부터는 엔진 book(항상 재정규화, 합 1.0)이 이어받아 비율·합이 인위적으로
    점프한다. fallback도 없거나 합이 0 이하면 조용히 사라지는 대신 경고를 남기고
    빈 프레임을 반환한다.
    """
    if book.empty:
        seed = None
        if fallback_weights is not None and not fallback_weights.empty:
            seed = fallback_weights[fallback_weights != 0]
            s = float(seed.sum())
            seed = seed / s if s > 0 else None  # book 관례와 동일 — 투자자산 내 재정규화 (현금 잔여 무시)
        if seed is not None and not seed.empty:
            tail_row = seed.rename("weights").rename_axis("ticker").reset_index()
            tail_row.insert(0, "Date", nav_last)
            book = tail_row.set_index("Date")
        else:
            print(
                f"[warn] live_weights port_id={port_id}: book·fallback 모두 없음 — 빈 행",
                file=sys.stderr,
            )
    elif book.index.max() < nav_last:
        book_last = book.index.max()
        tail = book.loc[[book_last]].set_index("ticker")["weights"]
        tickers = tail.index.intersection(price.columns)
        rel = price.loc[nav_last, tickers] / price.loc[book_last, tickers]
        drifted = (tail.reindex(tickers) * rel).dropna()
        if drifted.sum() > 0:
            drifted = drifted / drifted.sum()
            tail_row = drifted.rename("weights").rename_axis("ticker").reset_index()
            tail_row.insert(0, "Date", nav_last)
            book = pd.concat([book, tail_row.set_index("Date")])

    if book.empty:
        bw = pd.DataFrame(columns=["trade_date", "ticker", "weight"])
    else:
        bw = book.reset_index()[["Date", "ticker", "weights"]]
        bw.columns = ["trade_date", "ticker", "weight"]
    bw.insert(0, "port_id", port_id)
    return bw


def _write_live_weights(df: pd.DataFrame) -> None:
    print(f"[live_weights] {len(df)}행")
    storage.write_parquet(df, "portfolio", "live_weights.parquet")


def build_track_strategies():
    """저장된 전략 실전 추적 (P7) — 저장 시점(created_at)부터 오늘까지
    POST /backtest와 동일한 엔진으로 NAV를 다시 굴린다.

    행: [port_id, trade_date, value, as_of]. NAV는 saved_at 기준 1000 시작.
    포트폴리오 단위 실패는 경고 후 스킵 (예: US 개별주 아카이브가 끝난 종목은
    가격이 있는 데까지만 커브가 나온다 — 엔진이 자동 처리).

    부산물: 같은 book(드리프트 보유 비중)을 portfolio/live_weights.parquet로
    이 함수가 직접 기록한다 — 반환값(DataFrame)은 BUILDERS 파이프라인이
    live_nav.parquet 쓰기에 이미 쓰고 있어(한 빌더 두 산출물), rebal_signals의
    빈-케이스 직접 기록과 같은 방식으로 여기서 바로 저장한다.
    """
    wcols = portfolio._EMPTY["live_weights.parquet"]
    ports = portfolio.records()
    if ports.empty:
        print("[skip] track_strategies (저장된 포트폴리오 없음)")
        _write_live_weights(pd.DataFrame(columns=wcols))
        return None

    st = meta.strategy_df().set_index("strategy_id")["strategy"]
    frames = []
    weight_frames = []
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
            # 보유 자산의 시세 단절 처리는 엔진(calculate_nav)이 구간 단위로 한다 —
            # 패널 전체를 자르면 미보유 동결 자산 때문에 멀쩡한 커브까지 잘린다.

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

            book, nav, _ = backtest_result(
                weight=weight, price=price, start_date=saved_at.date(), cost_bps=cost_bps
            )
            nav = nav.dropna()
            if nav.empty:
                raise ValueError("NAV 비어 있음")

            part = nav.reset_index()
            part.columns = ["trade_date", "value"]
            part.insert(0, "port_id", int(p.port_id))

            fallback = weight.iloc[-1].dropna()
            # nav-weights는 쌍으로 기록/스킵 — 한쪽만 남는 비대칭 금지
            bw = _book_to_weights(book, price, int(p.port_id), nav.index.max(), fallback)
            frames.append(part)
            weight_frames.append(bw)
        except Exception as e:
            print(
                f"[warn] track_strategies port_id={p.port_id}({p.port_name}) 실패: {e}",
                file=sys.stderr,
            )

    if not frames:
        print("[skip] track_strategies (추적 가능한 포트폴리오 없음)")
        _write_live_weights(pd.DataFrame(columns=wcols))
        return None

    df = pd.concat(frames, ignore_index=True)
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    df = df.sort_values(["port_id", "trade_date"]).reset_index(drop=True)
    df["as_of"] = pd.Timestamp(df["trade_date"].max()).strftime("%Y-%m-%d")

    wdf = (
        pd.concat(weight_frames, ignore_index=True)
        if weight_frames
        else pd.DataFrame(columns=wcols[:-1])
    )
    wdf = wdf.sort_values(["port_id", "trade_date", "ticker"]).reset_index(drop=True)
    wdf["as_of"] = df["as_of"].iloc[0]
    _write_live_weights(wdf[wcols])

    return df


def build_rebal_signals():
    """active 전략의 리밸 전일 신호 — 다음 거래일이 새 주기면 목표 비중 산출.

    prev(직전 목표)는 저장 parquet이 아니라 엔진 재계산(bt.rebalance 마지막 행)
    에서 얻는다 — 저장본은 백테스트 시점 이후 갱신되지 않아 오래 운영된 전략에서
    낡는다. active 0개면 빈 파일을 직접 써서 잔존 신호를 지운다 (비활성화 직후
    어제 신호가 남는 것 방지 — main()의 write 경로는 빈 프레임을 다루지 못한다).
    """
    from module import rebal_signal

    ports = portfolio.records()
    active = ports[ports["status"] == "active"] if not ports.empty else ports
    sig_cols = portfolio._EMPTY["rebal_signals.parquet"]
    if active.empty:
        storage.write_parquet(pd.DataFrame(columns=sig_cols), "portfolio", "rebal_signals.parquet")
        print("[rebal_signals] active 전략 없음 — 빈 파일 기록")
        return None

    st = meta.strategy_df().set_index("strategy_id")["strategy"]
    names = meta.meta_df()[["ticker", "name"]].drop_duplicates("ticker").set_index("ticker")["name"]
    frames = []
    for p in active.itertuples():
        try:
            cfg = json.loads(p.config) if isinstance(p.config, str) and p.config.strip() else {}
            algorithm = cfg.get("algorithm") or st.get(p.strategy_id, "eq")
            freq = cfg.get("rebal_freq") or "M"
            params = cfg.get("params") or {}

            meta_ids = portfolio.universe(int(p.port_id))
            bt = Backtest(strategy_name=p.port_name)
            # Q/Y 리밸은 패널 안에 주기 시작 리밸일이 들어와야 prev(엔진 재계산)가
            # 나온다 — 12개월 룩백은 13개 월말을 요구하므로 주기만큼 창을 늘린다.
            extra = {"M": 0, "Q": 120, "Y": 420}.get(freq, 0)
            warmup = (pd.Timestamp.today() - pd.Timedelta(days=MOMENTUM_WARMUP_DAYS + extra)).date()
            price = bt.data(meta_id=meta_ids, start_date=warmup)
            if price.empty:
                raise ValueError("가격 데이터 없음")
            if cfg.get("currency") == "KRW":
                mapping = meta.resolve(meta_ids=meta_ids)
                price = fx.to_krw(price, dict(zip(mapping["ticker"], mapping["iso_code"])))
            # bt.rebalance는 내부에서 price.loc[start:end].dropna()를 적용한다 —
            # 여기서도 미리 dropna해 next_period_weights와 bt.rebalance가 같은
            # 패널을 보게 한다 (혼합 캘린더 NaN으로 두 계산이 갈리는 것 방지).
            price = price.dropna()

            as_of = price.index.max()
            nxt = rebal_signal.next_business_day(as_of)
            if not rebal_signal.is_new_period(as_of, nxt, freq):
                continue  # 이번 밤은 신호 없음

            target = rebal_signal.next_period_weights(price, algorithm, params)
            if not target:
                raise ValueError("목표 비중 산출 실패")
            w = bt.rebalance(price=price, method=algorithm, freq=freq,
                             custom_weight=params.get("weights"), params=params)
            if w is None or w.empty:
                raise ValueError("prev 산출 실패 — 워밍업 창 부족 (전량 '진입' 오표시 방지)")
            prev = w.iloc[-1].dropna().to_dict()

            rows = pd.DataFrame(rebal_signal.classify_actions(prev, target))
            rows.insert(0, "port_id", int(p.port_id))
            rows.insert(1, "port_name", p.port_name)
            rows.insert(2, "freq", freq)
            rows.insert(3, "as_of", as_of.strftime("%Y-%m-%d"))
            rows.insert(4, "next_rebal", nxt.strftime("%Y-%m-%d"))
            rows["name"] = rows["ticker"].map(names).fillna(rows["ticker"])
            frames.append(rows[sig_cols])
            print(f"[rebal_signals] {p.port_name}: {len(rows)}행 (next {nxt.date()})")
        except Exception as e:
            print(f"[warn] rebal_signals 스킵 ({p.port_name}): {e}", file=sys.stderr)

    if not frames:
        storage.write_parquet(pd.DataFrame(columns=sig_cols), "portfolio", "rebal_signals.parquet")
        print("[rebal_signals] 이번 밤 신호 없음 — 빈 파일 기록")
        return None
    df = pd.concat(frames, ignore_index=True)
    if df["as_of"].nunique() > 1:
        # 막지 않는다 — 전략별 유니버스가 다르면 as_of가 정당하게 갈릴 수 있고,
        # API 응답은 표시용으로 첫 행 as_of만 쓴다 (app/routers/backtest.py).
        print(
            f"[warn] rebal_signals: 전략별 as_of 불일치 {sorted(df['as_of'].unique())}",
            file=sys.stderr,
        )
    return df


# ---------------------------------------------------------------- Track B: 신호 이벤트 스터디 / 팩터 렌즈


SIGNAL_HORIZONS = (5, 20, 60)  # 이벤트 이후 성과 측정 거래일 수
SIGNAL_COOLDOWN = 20  # 종목별 이벤트 재발화 최소 간격(거래일) — 연속 참 구간 dedup


def _signed_streak(F: pd.DataFrame) -> pd.DataFrame:
    """일자×종목 부호 연속일수 (매수 연속=양수, 매도 연속=음수, 0/미상장=0).

    각 일자에서 전일과 부호가 같으면 런 길이+1, 부호가 바뀌거나 NaN이면 리셋.
    """
    S = np.sign(F.to_numpy(dtype="float64"))  # NaN 보존 (미거래일 → 런 단절)
    n = S.shape[0]
    run = np.zeros_like(S)
    run[0] = np.where(np.isnan(S[0]), 0.0, 1.0)
    prev = S[0]
    for i in range(1, n):
        cur = S[i]
        same = (cur == prev) & ~np.isnan(cur)  # NaN==x → False (단절)
        run[i] = np.where(same, run[i - 1] + 1.0, np.where(np.isnan(cur), 0.0, 1.0))
        prev = cur
    return pd.DataFrame(run * np.nan_to_num(S), index=F.index, columns=F.columns)


def _event_cooldown(pos: np.ndarray, cooldown: int) -> np.ndarray:
    """crossing 발화 좌표 [(date_pos, ticker_pos), ...]에 종목별 쿨다운 적용.

    같은 종목에서 직전 채택 이벤트로부터 cooldown 거래일 미만이면 스킵.
    """
    if len(pos) == 0:
        return np.empty((0, 2), dtype=int)
    order = np.lexsort((pos[:, 0], pos[:, 1]))  # 1순위 ticker, 2순위 date
    p = pos[order]
    keep = []
    last_ticker, last_date = -1, -(10 ** 9)
    for dpos, tpos in p:
        if tpos != last_ticker or dpos - last_date >= cooldown:
            keep.append((dpos, tpos))
            last_ticker, last_date = tpos, dpos
    return np.array(keep, dtype=int)


def _study_row(sig: str, h: int, excess: np.ndarray, fwd_ret: np.ndarray) -> dict:
    """signal_study 한 행. 표본이 비면 통계는 NaN — 행 자체는 남긴다."""
    return {
        "signal_type": sig,
        "horizon": h,
        "n_events": int(len(excess)),
        "mean_excess": float(np.mean(excess)) if len(excess) else np.nan,
        "median_excess": float(np.median(excess)) if len(excess) else np.nan,
        "hit_rate": float((excess > 0).mean() * 100) if len(excess) else np.nan,
        "avg_fwd_ret": float(np.mean(fwd_ret)) if len(fwd_ret) else np.nan,
    }


def build_signal_study():
    """신호 이벤트 스터디 — 전 기간(2016~) 신호 발생 재구성 + 전방 초과성과.

    유동성 종목(시총≥100억, 스팩 제외, 당일 거래 존재)에 한해 13개 신호를
    정의하고, 각 이벤트 이후 h∈{5,20,60} 거래일 초과수익(adj_close 기반)을
    집계한다. baseline을 포함한 모든 신호가 이 유니버스를 공유한다.

    벤치마크는 **유동성 유니버스 동일가중 횡단면 평균**이다. 시총가중 KOSPI를
    쓰면 (1) KOSDAQ 종목을 KOSPI 지수에 대고 재게 되고 (2) 지수를 소수 대형주가
    끌기 때문에 중앙값 종목이 구조적으로 지수를 못 따라가, 모든 신호가 음수로
    보여 "이 신호는 나쁘다"로 오독된다. baseline 행이 그 기준을 명시한다 —
    어떤 신호든 baseline과의 차이로만 판정해야 한다.

    n_events는 신호 간 비교 불가다. 상태형 신호에만 crossing+cooldown을
    적용하기 때문이다(아래 참조). 중앙값·승률만 비교한다.

    near_52w_high_entry도 상태형이라 "고점 근처에 머문 모든 날"이 아니라 "그
    구간에 처음 진입한 날"만 센다. 진입일의 성과는 우상향 꼬리를 띠어 중앙값은
    기준선보다 낮고 승률·평균은 기준선보다 높다 — 중앙값만 보고 역방향으로
    오독하지 않도록 주의. "고점 근처에 머문 모든 날"은 near_52w_high_hold
    (daily_conds, cooldown 없음)로 별도 집계한다 — 부호가 반대(중앙값 기준선
    대비 플러스)인 별개 집단이니 이름이 비슷하다고 섞어 읽지 말 것.

    최중량 빌더 — 실패해도 파이프라인 비중단(내부 try/except → None).
    """
    try:
        px = qdata_api.load_krx_prices(
            columns=["adj_close", "close", "chg_pct", "mktcap", "volume"]
        )
        px = px[["date", "ticker", "adj_close", "chg_pct", "mktcap", "volume"]]  # close 미사용
        P = px.pivot(index="date", columns="ticker", values="adj_close").sort_index()
        M = px.pivot(index="date", columns="ticker", values="mktcap").reindex_like(P)
        CH = px.pivot(index="date", columns="ticker", values="chg_pct").reindex_like(P)
        V = px.pivot(index="date", columns="ticker", values="volume").reindex_like(P)
        del px

        frgn = _flows()
        frgn = frgn[frgn["investor"] == "frgn"][["date", "ticker", "net_value"]]
        F = frgn.pivot(index="date", columns="ticker", values="net_value")
        del frgn
        F = F.reindex(index=P.index, columns=P.columns)

        ret_5d = (P / P.shift(5) - 1) * 100
        ret_20d = (P / P.shift(20) - 1) * 100
        hi_252 = P.rolling(252, min_periods=200).max()
        frgn_net_20d = F.rolling(20, min_periods=20).sum()
        intensity_20d = frgn_net_20d / M * 100
        streak = _signed_streak(F)

        # 스팩 제외 — 시점별 이름 기준. 스팩은 합병 시 같은 티커로 사명만 바뀌므로
        # '한 번이라도 스팩'이 아니라 '그 시점에 스팩'으로 걸러야 한다. 스팩은
        # 공모가 부근 고정이라 신고가류 신호 모집단을 오염시킨다(2026-07-31 실측:
        # 당일 근접 유지 후보의 절반 가까이가 스팩). 선정(module/spotlight)과
        # 통계가 같은 유니버스를 재야 실측치가 거짓말을 하지 않는다.
        sec = qdata_api.load_krx_sector()[["date", "ticker", "name"]]
        # float로 피벗해야 NaN 섞인 bool이 object dtype이 되며 내는 FutureWarning이 없다
        sec["is_spac"] = sec["name"].astype(str).str.contains("스팩", na=False).astype("float64")
        S = (
            sec.pivot_table(index="date", columns="ticker", values="is_spac", aggfunc="last")
            .reindex(index=P.index, columns=P.columns)
            .ffill()
            .fillna(0.0)
            .astype(bool)
        )
        del sec
        # 거래정지·무거래일 제외 — 그날 거래할 수 없었던 종목의 신호는 실행
        # 불가능하고, 정지 종목의 동결 가격은 신고가류 신호와 전방수익률을 함께
        # 오염시킨다 (2026-07-31 실측: 8거래일 거래량 0 종목이 유지 그룹 1위).
        # module/spotlight.active_tickers의 당일 거래량 기준과 동일하다.
        liquid = (M >= MKTCAP_FLOOR) & ~S & (V > 0)
        del S, V
        del frgn_net_20d, F

        # 상태형 — 한 번 참이 되면 며칠 유지된다. crossing으로 첫날만 잡고
        # cooldown으로 재발화를 걸러야 한 사건이 여러 번 세어지지 않는다.
        cond_52w = (P >= hi_252 * 0.98) & liquid  # entry(진입일)·hold(유지 전 일수)가 공유
        state_conds = {
            "bull_divergence": (ret_20d < -5) & (intensity_20d > 0.3) & liquid,
            "frgn_streak10": (streak >= 10) & liquid,
            "high_intensity": (intensity_20d >= 1.0) & liquid,
            "spike_5d_15": (ret_5d >= 15) & liquid,
            "spike_20d_20": (ret_20d >= 20) & liquid,
            "spike_20d_50": (ret_20d >= 50) & liquid,
            "near_52w_high_entry": cond_52w,
        }
        # 하루짜리 사건 — crossing은 거의 무의미하고(연속 급등일은 드물다),
        # cooldown은 서로 다른 진짜 급등을 임의로 버린다. 조건 그대로 쓴다.
        # spike_1d_5(≥5%)는 spike_1d_10(≥10%)의 상위집합이라 그대로 두면
        # "5~10%" 구간을 읽으려는 소비자가 10%+ 날짜까지 섞인 통계를 인용하게
        # 된다 — spike_1d_5_10으로 배타적 구간을 별도로 둔다.
        daily_conds = {
            "spike_1d_5": (CH >= 5) & liquid,
            "spike_1d_5_10": (CH >= 5) & (CH < 10) & liquid,
            "spike_1d_10": (CH >= 10) & liquid,
            "drop_1d_5": (CH <= -5) & liquid,
            # 유지형 신고가 — "고점 근처에 머문 모든 날"의 분포라 cooldown이 없다
            # (baseline과 같은 이유). 2026-07-27 사전 측정(§1.1)과 정확히 일치해야 한다.
            "near_52w_high_hold": cond_52w,
        }
        del ret_5d, ret_20d, hi_252, intensity_20d, streak, CH, M

        Pv = P.to_numpy(dtype="float64")
        Lv = liquid.to_numpy()
        n_dates = len(P.index)
        as_of = _as_of()
        del P, liquid

        events = {}  # 지평선 루프에서 재사용 — 좌표 계산은 한 번이면 된다
        for sig, cond in state_conds.items():
            crossing = cond & ~cond.shift(1, fill_value=False)  # 조건이 처음 참이 되는 날
            events[sig] = _event_cooldown(np.argwhere(crossing.to_numpy()), SIGNAL_COOLDOWN)
        for sig, cond in daily_conds.items():
            events[sig] = np.argwhere(cond.to_numpy())
        del state_conds, daily_conds, cond_52w

        rows = []
        for h in SIGNAL_HORIZONS:
            fwd = np.full_like(Pv, np.nan)
            fwd[: n_dates - h] = (Pv[h:] / Pv[: n_dates - h] - 1) * 100
            fwd = np.where(Lv, fwd, np.nan)  # 벤치마크·기준선 모두 유동성 유니버스
            with warnings.catch_warnings():  # 상장 전/상폐 후 전부-NaN 행 → 빈 평균
                warnings.simplefilter("ignore", RuntimeWarning)
                bench = np.nanmean(fwd, axis=1, keepdims=True)
            exc = fwd - bench

            # baseline — 이벤트가 아니라 유동성 전 종목-일. cooldown은 정의상 없다.
            ok = np.isfinite(exc)
            rows.append(_study_row("baseline", h, exc[ok], fwd[ok]))

            for sig, ev in events.items():
                dpos, tpos = ev[:, 0], ev[:, 1]
                keep = dpos + h < n_dates  # 지평선이 이력 밖이면 제외
                dpos, tpos = dpos[keep], tpos[keep]
                e, f = exc[dpos, tpos], fwd[dpos, tpos]
                m = np.isfinite(e) & np.isfinite(f)  # 상폐 등 결측 제외
                rows.append(_study_row(sig, h, e[m], f[m]))
            del fwd, bench, exc, ok

        df = pd.DataFrame(rows)
        df["as_of"] = as_of
        print("[signal_study]")
        print(df.to_string(index=False))
        return df
    except Exception:
        print("[warn] signal_study 실패 (비중단):", file=sys.stderr)
        traceback.print_exc()
        return None


FACTOR_NAMES = ("momentum", "value", "size", "lowvol")


def _factor_scores(P: pd.DataFrame, M: pd.DataFrame, PER: pd.DataFrame) -> dict:
    """일자×종목 팩터 점수 (점수 높을수록 팩터 롱 방향).

    momentum: 12-1개월 수익(252d 전→21d 전) 고→저.  value: 이익수익률 1/PER(>0) 고→저.
    size: −시총 (소형−대형).  lowvol: −(60일 실현변동성) (저변동−고변동).
    """
    returns = P.pct_change(fill_method=None)
    return {
        "momentum": P.shift(21) / P.shift(252) - 1,
        "value": (1.0 / PER).where(PER > 0),
        "size": -M,
        "lowvol": -(returns.rolling(60, min_periods=40).std()),
    }


def _factor_returns_df():
    """일별 롱숏 5분위 스프레드 (KOSPI+KOSDAQ 유동성 유니버스) — 1회 계산 캐시.

    각 일자 횡단면을 팩터별로 5분위 랭크, 상위20% 평균 익일수익 − 하위20% 평균
    (등가중, 익일수익으로 look-ahead 방지). cum_index는 시작 100 재기준화 체인.
    """
    if "factor_returns" in _cache:
        return _cache["factor_returns"]

    px = qdata_api.load_krx_prices(columns=["adj_close", "mktcap"])
    P = px.pivot(index="date", columns="ticker", values="adj_close").sort_index()
    M = px.pivot(index="date", columns="ticker", values="mktcap").sort_index()
    del px

    fund = qdata_api.load_krx_fundamental(columns=["per"])  # 미수집 시 FileNotFoundError
    PER = (
        fund.pivot(index="date", columns="ticker", values="per")
        .sort_index()
        .reindex(index=P.index, columns=P.columns)
    )
    del fund

    liquid = M >= MKTCAP_FLOOR
    fwd_1d = P.shift(-1) / P - 1  # 익일수익 (t→t+1) — look-ahead 방지
    scores = _factor_scores(P, M, PER)
    del PER

    frames = []
    for factor in FACTOR_NAMES:
        valid = liquid & scores[factor].notna() & fwd_1d.notna()
        ranks = scores[factor].where(valid).rank(axis=1, pct=True)  # 횡단면 백분위
        top = fwd_1d.where(ranks > 0.8).mean(axis=1)  # 상위 5분위 등가중
        bot = fwd_1d.where(ranks <= 0.2).mean(axis=1)  # 하위 5분위 등가중
        spread = ((top - bot) * 100).dropna()
        norm = (1 + spread / 100).cumprod()
        cum_index = 100.0 * norm / norm.iloc[0]  # 시작 100 재기준화 (sector_index 관례)
        frames.append(
            pd.DataFrame(
                {
                    "date": spread.index,
                    "factor": factor,
                    "spread": spread.to_numpy(),
                    "cum_index": cum_index.to_numpy(),
                }
            )
        )
    df = pd.concat(frames, ignore_index=True).sort_values(["factor", "date"]).reset_index(drop=True)
    df["as_of"] = pd.Timestamp(P.index[-1]).strftime("%Y-%m-%d")
    _cache["factor_returns"] = df
    return df


def build_factor_returns():
    """팩터 일별 스프레드·누적지수 전 기간 [date, factor, spread, cum_index]."""
    try:
        df = _factor_returns_df()
        print("[factor_returns]")
        print(
            df.groupby("factor")
            .agg(n=("spread", "size"), spread_mean=("spread", "mean"),
                 cum_last=("cum_index", "last"))
            .to_string()
        )
        return df
    except FileNotFoundError:
        print("[skip] factor_returns (fundamental 미수집)")
        return None
    except Exception:
        print("[warn] factor_returns 실패 (비중단):", file=sys.stderr)
        traceback.print_exc()
        return None


def build_factor_current():
    """팩터 현재 스냅샷 [factor, ret_1d, ret_1w, ret_1m, ret_ytd] — cum_index 파생."""
    try:
        fr = _factor_returns_df()
    except FileNotFoundError:
        print("[skip] factor_current (fundamental 미수집)")
        return None
    except Exception:
        print("[warn] factor_current 실패 (비중단):", file=sys.stderr)
        traceback.print_exc()
        return None
    if fr is None or fr.empty:
        return None

    last_date = fr["date"].max()
    year_start = pd.Timestamp(pd.Timestamp(last_date).year, 1, 1)
    rows = []
    for factor, g in fr.groupby("factor"):
        cum = g.sort_values("date").set_index("date")["cum_index"]

        def _ret(n: int):
            return (cum.iloc[-1] / cum.iloc[-1 - n] - 1) * 100 if len(cum) > n else None

        ytd_base = cum[cum.index < year_start]
        ret_ytd = (cum.iloc[-1] / ytd_base.iloc[-1] - 1) * 100 if not ytd_base.empty else None
        rows.append(
            {
                "factor": factor,
                "ret_1d": _ret(1),
                "ret_1w": _ret(5),
                "ret_1m": _ret(21),
                "ret_ytd": ret_ytd,
            }
        )
    df = pd.DataFrame(rows)
    df["as_of"] = fr["as_of"].iloc[0]
    print("[factor_current]")
    print(df.to_string(index=False))
    return df


def build_factor_pct_ticker():
    """종목별 팩터 백분위 (0-100) 스냅샷 [ticker, momentum, value, size, lowvol].

    백분위 高 = 팩터 롱 방향(고모멘텀/저평가/소형/저변동). 유동성 유니버스 내 순위.
    _factor_scores와 같은 정의를 쓰되 최신 거래일 단면만 취한다.
    브리프 재료이자, Lambda /factor-exposure의 520일 로드를 대체한다.
    """
    try:
        start = (pd.Timestamp.today() - pd.Timedelta(days=520)).strftime("%Y-%m-%d")
        px = qdata_api.load_krx_prices(start=start, columns=["adj_close", "mktcap"])
        P = px.pivot(index="date", columns="ticker", values="adj_close").sort_index()
        M = px.pivot(index="date", columns="ticker", values="mktcap").sort_index()
        del px
        try:
            fund = qdata_api.load_krx_fundamental(start=start, columns=["per"])
            PER = (
                fund.pivot(index="date", columns="ticker", values="per")
                .sort_index()
                .reindex(index=P.index, columns=P.columns)
            )
        except FileNotFoundError:
            PER = pd.DataFrame(index=P.index, columns=P.columns, dtype="float64")

        last = P.index[-1]
        returns = P.pct_change(fill_method=None)
        scores = {
            "momentum": (P.shift(21) / P.shift(252) - 1).loc[last],
            "value": (1.0 / PER).where(PER > 0).loc[last],
            "size": (-M).loc[last],
            "lowvol": (-(returns.rolling(60, min_periods=40).std())).loc[last],
        }
        liquid = M.loc[last] >= MKTCAP_FLOOR
        df = pd.DataFrame(
            {f: (scores[f].where(liquid).rank(pct=True) * 100) for f in FACTOR_NAMES}
        )
        df = df.dropna(how="all").reset_index().rename(columns={"index": "ticker"})
        df.columns.name = None
        df["as_of"] = pd.Timestamp(last).strftime("%Y-%m-%d")
        print(f"[factor_pct_ticker] {len(df)} 종목, as_of={df['as_of'].iloc[0]}")
        return df
    except Exception:
        print("[warn] factor_pct_ticker 실패 (비중단):", file=sys.stderr)
        traceback.print_exc()
        return None


def build_spotlight():
    """오늘의 신호 종목 — 전시장 스캔 그룹 3종 (선정 로직: module/spotlight.py).

    수급·가격 필드는 flows_signals 스냅샷(유동성 유니버스)을 쓰고, 52주 신고가
    근접 상태만 최근 800일(달력) adj_close 패널로 별도 계산한다 — hold_days는
    창 길이에서 포화되므로 표시는 "N일+"로 읽는다. 실측치(기준선 대비)는 넣지
    않는다 — 그 뺄셈은 서빙 시점에 signal_stats가 signal_study와 조인해서 한다.
    """
    try:
        flows_sig = _cache.get("flows_signals")
        if flows_sig is None:
            flows_sig = build_flows_signals()
        frgn = flows_sig[flows_sig["investor"] == "frgn"]

        start = (pd.Timestamp.today() - pd.Timedelta(days=800)).strftime("%Y-%m-%d")
        px = qdata_api.load_krx_prices(start=start, columns=["adj_close", "volume"])
        P = px.pivot(index="date", columns="ticker", values="adj_close").sort_index()
        V = px.pivot(index="date", columns="ticker", values="volume").reindex_like(P)
        del px

        near = spotlight.near_high_state(P)
        del P
        # 거래정지·무거래 제외 — build_signal_study의 당일 거래량 조건과 동일 기준
        active = spotlight.active_tickers(V)
        del V
        n_halted = int((~frgn["ticker"].isin(active)).sum())
        if n_halted:
            print(f"[spotlight] 거래정지·무거래 {n_halted}종목 제외 (당일 거래량 0)")
        frgn = frgn[frgn["ticker"].isin(active)]
        n_spac = int(frgn["name"].astype(str).str.contains("스팩", na=False).sum())
        print(f"[spotlight] 스팩 {n_spac}종목 유니버스 제외")
        df, dropped = spotlight.select_spotlight(frgn, near)
        for g, n in dropped.items():  # 조용한 절삭 금지
            print(f"[spotlight] {g}: 상한 {spotlight.CAP_PER_GROUP} 적용, {n}종목 잘림")
        if df.empty:
            print("[spotlight] 후보 0 — 저장 생략 (전일 파일 유지)", file=sys.stderr)
            return None
        df["as_of"] = _as_of()
        print(f"[spotlight] {len(df)} rows, as_of={df['as_of'].iloc[0]}")
        return df
    except Exception:
        print("[warn] spotlight 실패 (비중단):", file=sys.stderr)
        traceback.print_exc()
        return None


# ---------------------------------------------------------------- 실행


BUILDERS = [
    ("us_prices.parquet", build_us_prices, {"row_group_size": 100_000}),  # P0: US 가격 앱 추출
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
    ("insight/signal_study.parquet", build_signal_study, {}),  # Track B: 신호 이벤트 스터디
    ("insight/factor_returns.parquet", build_factor_returns, {}),  # Track B: 팩터 렌즈
    ("insight/factor_current.parquet", build_factor_current, {}),  # (factor_returns 캐시 파생)
    ("insight/factor_pct_ticker.parquet", build_factor_pct_ticker, {}),  # 브리프 재료 + Lambda 부담 경감
    ("insight/spotlight.parquet", build_spotlight, {}),  # 오늘의 신호 종목 (전시장 스캔)
    ("portfolio/live_nav.parquet", build_track_strategies, {}),  # 전략 실전 추적 (P7)
    ("portfolio/rebal_signals.parquet", build_rebal_signals, {}),  # active 전략 리밸 전일 신호
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
