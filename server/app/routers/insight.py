"""KR 인사이트 API — scripts/build_insights.py가 만든 사전계산 parquet의 얇은 리더.

{APP_DATA}/insight/*.parquet을 pyarrow filters 푸시다운으로 읽기만 한다 —
무거운 집계는 전부 로컬 빌더 몫. 파일이 없으면 빈 payload (regime 패턴).
금액 단위는 원 그대로 반환 — 억 단위 환산은 클라이언트 책임.
"""

import math
import os
import sys
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Query

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../../../")))
from datastore import storage

router = APIRouter(prefix="/insight", tags=["Insight"])


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

    cols = ["rank", "ticker", "name", "market", "net_value", "net_volume", "close", "chg_pct", "mktcap"]
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
