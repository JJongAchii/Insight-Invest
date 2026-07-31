"""KR 인사이트 API — scripts/build_insights.py가 만든 사전계산 parquet의 얇은 리더.

{APP_DATA}/insight/*.parquet을 pyarrow filters 푸시다운으로 읽기만 한다 —
무거운 집계는 전부 로컬 빌더 몫. 파일이 없으면 빈 payload (regime 패턴).
금액 단위는 원 그대로 반환 — 억 단위 환산은 클라이언트 책임.
"""

import json
import math
import os
import sys
from functools import lru_cache
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../../../")))
from datastore import holdings as holdings_store
from datastore import meta as meta_store
from datastore import storage
from datastore import watchlist as watchlist_store
from module import signal_stats
from module import spotlight as spotlight_mod

router = APIRouter(prefix="/insight", tags=["Insight"])

MKTCAP_FLOOR = 1e10  # 유동성 컷 — build_insights의 팩터/신호 유니버스와 동일
FACTOR_NAMES = ("momentum", "value", "size", "lowvol")
# 팩터별 (고백분위 라벨, 저백분위 라벨) — factor-exposure tilt 요약용
TILT_LABELS = {
    "momentum": ("고모멘텀", "저모멘텀"),
    "value": ("저평가", "고평가"),
    "size": ("소형", "대형"),
    "lowvol": ("저변동성", "고변동성"),
}


def _finite(x) -> Optional[float]:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _round2(obj):
    """응답 트리의 float를 2자리 반올림, NaN/inf → None (재귀)."""
    if isinstance(obj, dict):
        return {k: _round2(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round2(v) for v in obj]
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, (int, str)) or obj is None:
        return obj
    f = _finite(obj)
    return round(f, 2) if f is not None else None


def _read(name: str, columns=None, filters=None) -> Optional[pd.DataFrame]:
    try:
        return storage.read_parquet("insight", name, columns=columns, filters=filters)
    except FileNotFoundError:
        return None


def _as_of(df: pd.DataFrame) -> Optional[str]:
    return str(df["as_of"].iloc[0]) if "as_of" in df.columns and not df.empty else None


def _date_str(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    return df


@router.get("/flows/top")
async def get_flows_top(window: str = "1w", investor: str = "frgn"):
    """투자자별 순매수/순매도 상위 30 — window ∈ 1d/1w/1m, investor ∈ frgn/inst."""
    df = _read(
        "flows_top.parquet",
        filters=[("window", "==", window), ("investor", "==", investor)],
    )
    if df is None or df.empty:
        return {"window": window, "investor": investor, "as_of": None, "buys": [], "sells": []}

    cols = [
        "rank",
        "ticker",
        "name",
        "market",
        "net_value",
        "net_volume",
        "close",
        "chg_pct",
        "mktcap",
    ]
    buys = df[df["rank"] > 0].sort_values("rank")[cols]
    sells = df[df["rank"] < 0].sort_values("rank", ascending=False)[cols].copy()
    sells["rank"] = -sells["rank"]  # 순매도 목록은 양수 rank 1..30으로 제공
    return _round2(
        {
            "window": window,
            "investor": investor,
            "as_of": _as_of(df),
            "buys": buys.to_dict(orient="records"),
            "sells": sells.to_dict(orient="records"),
        }
    )


@router.get("/flows/market")
async def get_flows_market(days: int = 365):
    """시장(KOSPI/KOSDAQ/ALL) × 투자자별 일별 순매수 — 최근 N일."""
    df = _read(
        "flows_summary.parquet",
        columns=["date", "market", "investor", "net_value", "as_of"],
    )
    if df is None or df.empty:
        return {"as_of": None, "rows": []}
    cutoff = df["date"].max() - pd.Timedelta(days=days)
    df = _date_str(df[df["date"] >= cutoff])
    return _round2(
        {
            "as_of": _as_of(df),
            "rows": df[["date", "market", "investor", "net_value"]].to_dict(orient="records"),
        }
    )


@router.get("/flows/ticker/{ticker}")
async def get_flows_ticker(ticker: str, months: int = 12):
    """종목별 투자자 순매수 시계열 — ticker 필터 푸시다운 (로우그룹 프루닝)."""
    df = _read("flows_by_ticker.parquet", filters=[("ticker", "==", ticker)])
    if df is None or df.empty:
        return {"ticker": ticker, "as_of": None, "rows": []}
    cutoff = df["date"].max() - pd.DateOffset(months=months)
    df = _date_str(df[df["date"] >= cutoff].sort_values("date"))
    return _round2(
        {
            "ticker": ticker,
            "as_of": _as_of(df),
            "rows": df[["date", "frgn_net", "inst_net", "indiv_net"]].to_dict(orient="records"),
        }
    )


@router.get("/breadth")
async def get_breadth(days: int = 365, market: Optional[str] = None):
    """시장폭 일별 지표 — 최근 N일, market(KOSPI/KOSDAQ) 미지정 시 전체."""
    filters = [("market", "==", market)] if market else None
    df = _read("breadth_daily.parquet", filters=filters)
    if df is None or df.empty:
        return {"as_of": None, "rows": []}
    cutoff = df["date"].max() - pd.Timedelta(days=days)
    df = _date_str(df[df["date"] >= cutoff].sort_values(["date", "market"]))
    rows = df.drop(columns=["as_of"]).to_dict(orient="records")
    return _round2({"as_of": _as_of(df), "rows": rows})


@router.get("/flows/signals")
async def get_flows_signals(
    signal_type: str = Query("streak", alias="type"), investor: str = "frgn"
):
    """수급 신호 스냅샷 — type ∈ streak(연속일수)/intensity(20일 강도)/divergence."""
    df = _read("flows_signals.parquet", filters=[("investor", "==", investor)])
    if df is None or df.empty:
        return {"as_of": None, "rows": []}

    if signal_type == "streak":
        df = df.reindex(df["streak"].abs().sort_values(ascending=False).index).head(50)
    elif signal_type == "intensity":
        df = df.reindex(df["intensity_20d"].abs().sort_values(ascending=False).index).head(50)
    elif signal_type == "divergence":
        df = df[df["divergence"].notna()]
        df = df.reindex(df["intensity_20d"].abs().sort_values(ascending=False).index)
    rows = df.drop(columns=["as_of"]).to_dict(orient="records")
    return _round2({"as_of": _as_of(df), "rows": rows})


@router.get("/sector/heatmap")
async def get_sector_heatmap():
    """업종별 최신 성과 스냅샷 (1d/1w/1m/3m/YTD %, 구성 종목수, 시총 비중)."""
    df = _read("sector_perf.parquet")
    if df is None or df.empty:
        return {"as_of": None, "rows": []}
    rows = df.drop(columns=["as_of"]).to_dict(orient="records")
    return _round2({"as_of": _as_of(df), "rows": rows})


@router.get("/sector/rotation")
async def get_sector_rotation(months: int = 12):
    """업종 지수 체인 — 최근 N개월, 주간 마지막 값으로 다운샘플."""
    df = _read("sector_index.parquet", columns=["date", "market", "sector", "index_value", "as_of"])
    if df is None or df.empty:
        return {"as_of": None, "rows": []}
    cutoff = df["date"].max() - pd.DateOffset(months=months)
    df = df[df["date"] >= cutoff].sort_values("date").copy()
    df["week"] = df["date"].dt.to_period("W").astype(str)
    df = df.groupby(["market", "sector", "week"], as_index=False).last()
    df = _date_str(df.sort_values(["market", "sector", "date"]))
    return _round2(
        {
            "as_of": _as_of(df),
            "rows": df[["date", "market", "sector", "index_value"]].to_dict(orient="records"),
        }
    )


@router.get("/valuation")
async def get_valuation(market: str = "KOSPI"):
    """시장 밸류에이션 — 주간 다운샘플 전 기간 + 현재값·역사적 백분위."""
    df = _read("valuation_daily.parquet", filters=[("market", "==", market)])
    if df is None or df.empty:
        return {"market": market, "as_of": None, "rows": [], "current": None}
    df = df.sort_values("date")
    last = df.iloc[-1]
    current = {
        "per": last["per"],
        "pbr": last["pbr"],
        "div": last["div"],
        "pct_rank_per": last["pct_rank_per"],
        "pct_rank_pbr": last["pct_rank_pbr"],
    }
    wk = df.copy()
    wk["week"] = wk["date"].dt.to_period("W").astype(str)
    wk = _date_str(wk.groupby("week", as_index=False).last())
    return _round2(
        {
            "market": market,
            "as_of": _as_of(df),
            "rows": wk[["date", "per", "pbr", "div"]].to_dict(orient="records"),
            "current": current,
        }
    )


@router.get("/signals/study")
async def get_signals_study():
    """신호 이벤트 스터디 — 신호×지평선별 전방 초과성과 집계 (signal_study.parquet)."""
    df = _read("signal_study.parquet")
    if df is None or df.empty:
        return {"as_of": None, "rows": []}
    cols = [
        "signal_type",
        "horizon",
        "n_events",
        "mean_excess",
        "median_excess",
        "hit_rate",
        "avg_fwd_ret",
    ]
    return _round2({"as_of": _as_of(df), "rows": df[cols].to_dict(orient="records")})


@router.get("/spotlight")
async def get_spotlight():
    """오늘의 신호 종목 — 전시장 스캔 (spotlight.parquet의 얇은 리더).

    그룹 순서는 서빙 시점 signal_study의 20일 기준선 대비 중앙값 내림차순 —
    우위가 있는 신호가 먼저 보인다. parquet 부재 시 빈 그룹 (500 금지,
    attention과 같은 계약). 보유·관심 마킹 실패는 마킹 없이 진행한다.
    """
    df = _read("spotlight.parquet")
    if df is None or df.empty:
        return {"as_of": None, "groups": []}

    study = signal_stats.load_study()

    holding_ids, watch_ids = set(), set()
    try:
        hd = holdings_store.list_items()
        holding_ids = {int(x) for x in hd["meta_id"]} if not hd.empty else set()
        wl = watchlist_store.list_items()
        watch_ids = {int(x) for x in wl["meta_id"]} if not wl.empty else set()
    except Exception:
        pass

    md = meta_store.meta_df()
    kr = md[md["iso_code"] == "KR"]
    tk2meta = {r.ticker: int(r.meta_id) for r in kr.itertuples()}

    def _delta20(sig: str):
        if study is None:
            return None
        stats = signal_stats.excess_vs_baseline(study, sig, 20)
        return stats[1] if stats else None

    groups = []
    for sig in df["signal_type"].unique():
        sub = df[df["signal_type"] == sig].sort_values("rank")
        items = []
        for r in sub.itertuples():
            mid = tk2meta.get(r.ticker)
            mine = "holding" if mid in holding_ids else "watchlist" if mid in watch_ids else None
            items.append(
                {
                    "ticker": r.ticker,
                    "name": r.name,
                    "market": r.market,
                    "close": r.close,
                    "chg_pct": r.chg_pct,
                    "streak": int(r.streak) if pd.notna(r.streak) else None,
                    "intensity_20d": r.intensity_20d,
                    "ret_20d": r.ret_20d,
                    "hold_days": int(r.hold_days) if pd.notna(r.hold_days) else None,
                    "dist_pct": r.dist_pct,
                    "also_in": json.loads(r.also_in) if isinstance(r.also_in, str) else [],
                    "meta_id": mid,
                    "link": f"/stock/{mid}" if mid is not None else None,
                    "mine": mine,
                }
            )
        groups.append(
            {
                "signal_type": sig,
                "title": spotlight_mod.GROUP_TITLES.get(sig, sig),
                "evidence": signal_stats.evidence_phrase(sig, 20, df=study),
                "_delta": _delta20(sig),
                "items": items,
            }
        )
    groups.sort(key=lambda g: (g["_delta"] is None, -(g["_delta"] or 0)))
    for g in groups:
        g.pop("_delta")
    return _round2({"as_of": _as_of(df), "groups": groups})


@router.get("/factors")
async def get_factors():
    """팩터 렌즈 — 현재 스냅샷 + 누적지수 이력(최근 ~3년, 주간 다운샘플)."""
    cur = _read("factor_current.parquet")
    hist = _read("factor_returns.parquet", columns=["date", "factor", "cum_index", "as_of"])

    current = []
    if cur is not None and not cur.empty:
        current = cur[["factor", "ret_1d", "ret_1w", "ret_1m", "ret_ytd"]].to_dict(orient="records")

    history, as_of = [], None
    if hist is not None and not hist.empty:
        as_of = _as_of(hist)
        cutoff = hist["date"].max() - pd.DateOffset(years=3)
        h = hist[hist["date"] >= cutoff].copy()
        h["week"] = h["date"].dt.to_period("W").astype(str)
        h = h.groupby(["factor", "week"], as_index=False).last()
        h = _date_str(h.sort_values(["factor", "date"]))
        history = h[["date", "factor", "cum_index"]].to_dict(orient="records")
    if as_of is None and cur is not None and not cur.empty:
        as_of = _as_of(cur)

    return _round2({"as_of": as_of, "current": current, "history": history})


@lru_cache(maxsize=1)
def _universe_factor_pct():
    """현재 유동성 유니버스의 팩터별 종목 백분위(0-100) — 최신 거래일 기준.

    반환 (dict[factor -> Series(ticker->percentile)], as_of). 백분위 高 = 팩터 롱 방향
    (고모멘텀/저평가/소형/저변동). build_insights의 팩터 정의와 동일. 프로세스 내 캐시.
    """
    # 빌더가 떨어뜨린 스냅샷이 있으면 그걸 쓴다 — 520일 전종목 로드 회피.
    if storage.exists("insight/factor_pct_ticker.parquet"):
        df = storage.read_parquet("insight/factor_pct_ticker.parquet")
        pct = {f: df.set_index("ticker")[f].dropna() for f in FACTOR_NAMES}
        return pct, str(df["as_of"].iloc[0])

    from qdata import api as qdata_api

    start = (pd.Timestamp.today() - pd.Timedelta(days=520)).strftime("%Y-%m-%d")
    px = qdata_api.load_krx_prices(start=start, columns=["adj_close", "mktcap"])
    P = px.pivot(index="date", columns="ticker", values="adj_close").sort_index()
    M = px.pivot(index="date", columns="ticker", values="mktcap").sort_index()
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
    pct = {f: (scores[f].where(liquid).rank(pct=True) * 100).dropna() for f in FACTOR_NAMES}
    return pct, pd.Timestamp(last).strftime("%Y-%m-%d")


class FactorExposureRequest(BaseModel):
    meta_id: List[int] = Field(..., min_length=1, max_length=50)


@router.post("/factor-exposure")
async def post_factor_exposure(req: FactorExposureRequest):
    """주어진 종목(KR)의 팩터 노출 — 현재 유니버스 내 백분위 평균(0-100) + 편향 요약.

    US 종목은 스킵(KR 팩터 유니버스). 전부 스킵되면 note로 알린다.
    """
    mapping = meta_store.resolve(meta_ids=req.meta_id)
    kr = mapping[mapping["iso_code"] == "KR"]
    n_us = len(mapping) - len(kr)
    if kr.empty:
        return {"as_of": None, "exposures": [], "tilt": "", "note": "KR 종목 없음 — 전부 스킵됨"}

    pct, as_of = _universe_factor_pct()
    tickers = kr["ticker"].tolist()
    exposures, strengths = [], []
    for f in FACTOR_NAMES:
        vals = pct[f].reindex(tickers).dropna()
        p = float(vals.mean()) if not vals.empty else None
        exposures.append({"factor": f, "percentile": p})
        if p is not None:
            strengths.append((f, p))

    # tilt: 50에서 가장 먼 1-2 팩터를 방향 라벨로 (유의미한 편향만)
    strengths.sort(key=lambda fp: abs(fp[1] - 50), reverse=True)
    labels = [
        (TILT_LABELS[f][0] if p >= 50 else TILT_LABELS[f][1])
        for f, p in strengths[:2]
        if abs(p - 50) >= 5
    ]
    tilt = "·".join(labels) + " 편향" if labels else "뚜렷한 편향 없음"

    resp = {"as_of": as_of, "exposures": exposures, "tilt": tilt}
    if n_us:
        resp["note"] = f"US {n_us}개 종목 스킵됨 (KR만 계산)"
    return _round2(resp)


@router.get("/index")
async def get_index(days: int = 365):
    """KOSPI/KOSDAQ 지수 종가 — 앱 데이터가 아닌 qdata 레이크 직접 읽기."""
    start = (pd.Timestamp.today() - pd.Timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        from qdata import api as qdata_api

        idx = qdata_api.load_krx_index(start=start)
    except (FileNotFoundError, ImportError):
        return {"rows": []}
    idx = _date_str(idx)
    return _round2({"rows": idx[["date", "index", "close"]].to_dict(orient="records")})
