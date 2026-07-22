"""보유종목 API — {APP_DATA}/holdings.parquet CRUD + 실시간 평가·손익.

GET은 meta 조인 후 종목 거래통화 기준 최신가로 평가액·손익·비중을 계산한다.
KR은 qdata KRX 패널(종목/ETF), US는 datastore 가격 + USDKRW 환산.
enrich 소스가 없어도 항목은 None으로 응답한다 (소스별 try/except — 절대 500 없음).
"""

import logging
import math
import os
import sys
from datetime import date, timedelta
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../../../")))

from datastore import fx, meta
from datastore import holdings as holdings_store
from datastore.prices import KR_ETF_META_ID_MIN, read_price_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/holdings", tags=["Holdings"])

_META_COLS = ["meta_id", "ticker", "name", "iso_code", "security_type", "sector"]


class HoldingRequest(BaseModel):
    meta_id: int
    shares: float
    avg_cost: float
    currency: Optional[str] = None
    note: Optional[str] = ""


# ---------- 헬퍼 ----------


def _r(x, nd: int = 2) -> Optional[float]:
    """유한한 float만 round, 그 외 None."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return round(x, nd) if math.isfinite(x) else None


def _none_if_na(v):
    try:
        return None if pd.isna(v) else v
    except (TypeError, ValueError):
        return v


def _kr_stock_latest(tickers: list[str]) -> dict:
    """{ticker: (close, chg_pct)} — KRX 종목 패널 최근일, 한 번의 호출."""
    out: dict = {}
    if not tickers:
        return out
    try:
        from qdata import api as qdata_api

        start = (date.today() - timedelta(days=14)).isoformat()
        px = qdata_api.load_krx_prices(start=start, tickers=tickers, columns=["close", "chg_pct"])
        if px.empty:
            return out
        last = px.sort_values("date").groupby("ticker").tail(1)
        for r in last.itertuples():
            out[r.ticker] = (
                float(r.close) if pd.notna(r.close) else None,
                float(r.chg_pct) if pd.notna(r.chg_pct) else None,
            )
    except Exception:
        logger.warning("holdings KR 종목 시세 조회 실패", exc_info=True)
    return out


def _kr_etf_latest(tickers: list[str]) -> dict:
    """{ticker: (close, chg_pct)} — KRX ETF 패널 (chg_pct는 최근 2점 close 파생)."""
    out: dict = {}
    if not tickers:
        return out
    try:
        from qdata import api as qdata_api

        start = (date.today() - timedelta(days=14)).isoformat()
        px = qdata_api.load_krx_etf_prices(start=start, tickers=tickers)
        if px.empty:
            return out
        px = px.sort_values("date")
        for tk, g in px.groupby("ticker"):
            closes = g["close"].dropna()
            if closes.empty:
                continue
            last = float(closes.iloc[-1])
            chg = None
            if len(closes) >= 2 and closes.iloc[-2] != 0:
                chg = (last / float(closes.iloc[-2]) - 1.0) * 100.0
            out[tk] = (last, chg)
    except Exception:
        logger.warning("holdings KR ETF 시세 조회 실패", exc_info=True)
    return out


def _us_latest(meta_ids: list[int]) -> dict:
    """{meta_id: (adj_close, chg_pct)} — 최근 2점으로 등락률(%) 산출."""
    out: dict = {}
    if not meta_ids:
        return out
    try:
        df = read_price_data("US", meta_ids=meta_ids, start_date=date.today() - timedelta(days=30))
        if df.empty:
            return out
        for mid, g in df.groupby("meta_id"):
            s = g.sort_values("trade_date")["adj_close"].dropna()
            if s.empty:
                continue
            last = float(s.iloc[-1])
            chg = None
            if len(s) >= 2 and s.iloc[-2] != 0:
                chg = (last / float(s.iloc[-2]) - 1.0) * 100.0
            out[int(mid)] = (last, chg)
    except Exception:
        logger.warning("holdings US 시세 조회 실패", exc_info=True)
    return out


def _usdkrw_latest() -> Optional[float]:
    try:
        s = fx.usdkrw()
        return float(s.iloc[-1]) if not s.empty else None
    except Exception:
        logger.warning("USDKRW 조회 실패", exc_info=True)
        return None


def build_price_map(df: pd.DataFrame) -> dict:
    """[meta_id, ticker, iso_code] → {meta_id: (latest_price, day_chg_pct)}.

    소스별로 라우팅: KR 종목/ETF(meta_id≥900000)/US. attention 라우터도 공유한다.
    """
    out: dict = {}
    if df.empty:
        return out
    kr = df[df["iso_code"] == "KR"]
    kr_stock = kr[kr["meta_id"] < KR_ETF_META_ID_MIN]
    kr_etf = kr[kr["meta_id"] >= KR_ETF_META_ID_MIN]
    us = df[df["iso_code"] == "US"]

    if not kr_stock.empty:
        px = _kr_stock_latest(kr_stock["ticker"].dropna().tolist())
        for r in kr_stock.itertuples():
            if r.ticker in px:
                out[int(r.meta_id)] = px[r.ticker]
    if not kr_etf.empty:
        px = _kr_etf_latest(kr_etf["ticker"].dropna().tolist())
        for r in kr_etf.itertuples():
            if r.ticker in px:
                out[int(r.meta_id)] = px[r.ticker]
    if not us.empty:
        out.update(_us_latest([int(x) for x in us["meta_id"]]))
    return out


def _sector_label(iso_code, security_type, sector) -> str:
    """섹터 배분 그룹 라벨 — US는 자산성격, KR은 업종(결측→미분류)."""
    if iso_code == "US":
        return "US ETF" if str(security_type).upper() == "ETF" else "US Equity"
    if isinstance(sector, str) and sector.strip():
        return sector
    return "미분류"


def _empty_summary() -> dict:
    return {
        "total_value_krw": 0.0,
        "total_cost_krw": 0.0,
        "total_pnl_krw": 0.0,
        "total_pnl_pct": None,
        "day_pnl_krw": 0.0,
        "n_positions": 0,
        "sector_alloc": [],
        "market_alloc": [],
        "top_weight": None,
        "hhi": None,
    }


# ---------- 엔드포인트 ----------


@router.get("")
def get_holdings():
    """보유 포지션 + 평가·손익 요약."""
    items = holdings_store.list_items()
    if items.empty:
        return {"positions": [], "summary": _empty_summary()}

    md = meta.meta_df()[_META_COLS]
    df = items.merge(md, on="meta_id", how="left")

    price_map = build_price_map(df[["meta_id", "ticker", "iso_code"]])
    usdkrw = _usdkrw_latest()

    # 1차: 원값 계산 (반올림 전 — 비중·HHI 정확도용)
    raw = []
    total_value_krw = 0.0
    total_cost_krw = 0.0
    total_pnl_krw = 0.0
    day_pnl_krw = 0.0
    sector_agg: dict = {}
    market_agg: dict = {}

    for r in df.itertuples():
        mid = int(r.meta_id)
        price, chg = price_map.get(mid, (None, None))
        shares = float(r.shares)
        avg_cost = float(r.avg_cost)
        is_us = r.iso_code == "US"
        fxrate = usdkrw if is_us else 1.0

        mv_native = price * shares if price is not None else None
        cost_native = avg_cost * shares
        pnl_native = (price - avg_cost) * shares if price is not None else None
        pnl_pct = (price / avg_cost - 1.0) if (price is not None and avg_cost) else None

        mv_krw = mv_native * fxrate if (mv_native is not None and fxrate is not None) else None
        cost_krw = cost_native * fxrate if fxrate is not None else None
        day_native = shares * price * (chg / 100.0) if (price is not None and chg is not None) else None
        day_krw = day_native * fxrate if (day_native is not None and fxrate is not None) else None

        # 요약 누적 — 평가 가능한(가격 있는) 포지션만 손익 총계에 반영
        if mv_krw is not None:
            total_value_krw += mv_krw
            if cost_krw is not None:
                total_cost_krw += cost_krw
                total_pnl_krw += mv_krw - cost_krw
            sec = _sector_label(r.iso_code, r.security_type, r.sector)
            sector_agg[sec] = sector_agg.get(sec, 0.0) + mv_krw
            mkt = r.iso_code if r.iso_code in ("KR", "US") else "US"
            market_agg[mkt] = market_agg.get(mkt, 0.0) + mv_krw
        if day_krw is not None:
            day_pnl_krw += day_krw

        raw.append(
            {
                "meta_id": mid,
                "ticker": _none_if_na(r.ticker),
                "name": _none_if_na(r.name),
                "iso_code": _none_if_na(r.iso_code),
                "security_type": _none_if_na(r.security_type),
                "sector": _none_if_na(r.sector),
                "shares": shares,
                "avg_cost": avg_cost,
                "currency": _none_if_na(r.currency),
                "latest_price": price,
                "day_chg_pct": chg,
                "market_value_native": mv_native,
                "cost_value_native": cost_native,
                "unrealized_pnl_native": pnl_native,
                "unrealized_pnl_pct": pnl_pct,
                "market_value_krw": mv_krw,
                "_mv_krw": mv_krw,
            }
        )

    # 2차: 비중 부여 + 반올림
    positions = []
    for p in raw:
        mv = p.pop("_mv_krw")
        weight = mv / total_value_krw if (mv is not None and total_value_krw > 0) else None
        positions.append(
            {
                "meta_id": p["meta_id"],
                "ticker": p["ticker"],
                "name": p["name"],
                "iso_code": p["iso_code"],
                "security_type": p["security_type"],
                "sector": p["sector"],
                "shares": _r(p["shares"], 4),
                "avg_cost": _r(p["avg_cost"], 2),
                "currency": p["currency"],
                "latest_price": _r(p["latest_price"], 2),
                "day_chg_pct": _r(p["day_chg_pct"], 2),
                "market_value_native": _r(p["market_value_native"], 2),
                "cost_value_native": _r(p["cost_value_native"], 2),
                "unrealized_pnl_native": _r(p["unrealized_pnl_native"], 2),
                "unrealized_pnl_pct": _r(p["unrealized_pnl_pct"], 4),
                "market_value_krw": _r(p["market_value_krw"], 2),
                "weight": _r(weight, 4),
            }
        )

    weights = []
    for pos in positions:
        if pos["market_value_krw"] is not None and total_value_krw > 0:
            weights.append(pos["market_value_krw"] / total_value_krw)

    hhi = sum(w * w for w in weights) if weights else None
    top_weight = max(weights) if weights else None

    def _alloc(agg: dict) -> list:
        rows = [
            {"sector": k, "weight": _r(v / total_value_krw, 4)}
            for k, v in agg.items()
            if total_value_krw > 0
        ]
        return sorted(rows, key=lambda x: (x["weight"] is None, -(x["weight"] or 0)))

    def _market_alloc(agg: dict) -> list:
        rows = [
            {"label": k, "weight": _r(v / total_value_krw, 4)}
            for k, v in agg.items()
            if total_value_krw > 0
        ]
        return sorted(rows, key=lambda x: (x["weight"] is None, -(x["weight"] or 0)))

    total_pnl_pct = (total_pnl_krw / total_cost_krw) if total_cost_krw > 0 else None
    summary = {
        "total_value_krw": _r(total_value_krw, 2),
        "total_cost_krw": _r(total_cost_krw, 2),
        "total_pnl_krw": _r(total_pnl_krw, 2),
        "total_pnl_pct": _r(total_pnl_pct, 4),
        "day_pnl_krw": _r(day_pnl_krw, 2),
        "n_positions": len(positions),
        "sector_alloc": _alloc(sector_agg),
        "market_alloc": _market_alloc(market_agg),
        "top_weight": _r(top_weight, 4),
        "hhi": _r(hhi, 4),
    }
    return {"positions": positions, "summary": summary}


@router.post("")
def add_holding(request: HoldingRequest):
    md = meta.meta_df()
    row = md[md["meta_id"] == request.meta_id]
    if row.empty:
        raise HTTPException(status_code=404, detail=f"meta_id {request.meta_id} not found")

    currency = request.currency
    if not currency:
        iso = row.iloc[0]["iso_code"]
        currency = "KRW" if iso == "KR" else "USD"

    holdings_store.upsert(
        request.meta_id,
        shares=request.shares,
        avg_cost=request.avg_cost,
        currency=currency,
        note=request.note or "",
    )
    return {"n_positions": int(len(holdings_store.list_items()))}


@router.delete("/{meta_id}")
def remove_holding(meta_id: int):
    holdings_store.remove(meta_id)
    return {"n_positions": int(len(holdings_store.list_items()))}
