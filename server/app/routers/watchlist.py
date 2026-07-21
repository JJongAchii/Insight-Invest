"""관심종목 API — {APP_DATA}/watchlist.parquet CRUD + 시세·수급 enrich.

GET은 meta 조인 후 KR은 qdata KRX 패널(최근 종가·등락률)과
insight/flows_signals.parquet(20일 수급), US는 datastore 가격 최근 2점으로 채운다.
enrich 소스가 없어도 항목은 None으로 응답한다.
"""

import logging
import os
import sys
from datetime import date, timedelta
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../../../")))

from datastore import meta, storage
from datastore import watchlist as watchlist_store
from datastore.prices import read_price_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/watchlist", tags=["Watchlist"])


class WatchlistAddRequest(BaseModel):
    meta_id: int
    note: Optional[str] = ""


def _none_if_na(v):
    try:
        return None if pd.isna(v) else v
    except (TypeError, ValueError):
        return v


def _kr_latest_prices(tickers: list[str]) -> dict:
    """{ticker: (close, chg_pct)} — KRX 패널 최근일, 한 번의 호출."""
    out: dict = {}
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
        logger.warning("watchlist KR price enrich 실패", exc_info=True)
    return out


def _kr_flows(tickers: list[str]) -> dict:
    """{ticker: {investor: net_20d}} — insight/flows_signals.parquet."""
    out: dict = {}
    try:
        sig = storage.read_parquet(
            "insight",
            "flows_signals.parquet",
            columns=["ticker", "investor", "net_20d"],
            filters=[("ticker", "in", tickers)],
        )
        for r in sig.itertuples():
            out.setdefault(r.ticker, {})[r.investor] = (
                float(r.net_20d) if pd.notna(r.net_20d) else None
            )
    except Exception:
        logger.debug("watchlist flows enrich 실패 (flows_signals 부재 가능)")
    return out


def _us_latest_prices(meta_ids: list[int]) -> dict:
    """{meta_id: (adj_close, chg_pct)} — 최근 2점으로 등락률(%) 산출."""
    out: dict = {}
    try:
        df = read_price_data(
            "US", meta_ids=meta_ids, start_date=date.today() - timedelta(days=30)
        )
        if df.empty:
            return out
        for mid, g in df.groupby("meta_id"):
            g = g.sort_values("trade_date")["adj_close"].dropna()
            if g.empty:
                continue
            last = float(g.iloc[-1])
            chg = None
            if len(g) >= 2 and g.iloc[-2] != 0:
                chg = (last / float(g.iloc[-2]) - 1.0) * 100.0
            out[int(mid)] = (last, chg)
    except Exception:
        logger.warning("watchlist US price enrich 실패", exc_info=True)
    return out


@router.get("")
def get_watchlist():
    """관심종목 목록 + 최근 시세·등락률·20일 수급."""
    items = watchlist_store.list_items()
    if items.empty:
        return {"items": [], "count": 0}

    md = meta.meta_df()[["meta_id", "ticker", "name", "iso_code", "security_type"]]
    df = items.merge(md, on="meta_id", how="left")

    kr = df[df["iso_code"] == "KR"]
    us = df[df["iso_code"] == "US"]
    kr_px = _kr_latest_prices(kr["ticker"].dropna().tolist()) if not kr.empty else {}
    kr_fl = _kr_flows(kr["ticker"].dropna().tolist()) if not kr.empty else {}
    us_px = _us_latest_prices([int(x) for x in us["meta_id"]]) if not us.empty else {}

    out = []
    for r in df.itertuples():
        latest_price = chg_pct = frgn = inst = None
        if r.iso_code == "KR":
            latest_price, chg_pct = kr_px.get(r.ticker, (None, None))
            flows = kr_fl.get(r.ticker, {})
            frgn, inst = flows.get("frgn"), flows.get("inst")
        elif r.iso_code == "US":
            latest_price, chg_pct = us_px.get(int(r.meta_id), (None, None))
        added_at = r.added_at
        out.append(
            {
                "meta_id": int(r.meta_id),
                "ticker": _none_if_na(r.ticker),
                "name": _none_if_na(r.name),
                "iso_code": _none_if_na(r.iso_code),
                "security_type": _none_if_na(r.security_type),
                "added_at": added_at.isoformat() if pd.notna(added_at) else None,
                "note": _none_if_na(r.note),
                "latest_price": latest_price,
                "chg_pct": chg_pct,
                "frgn_net_20d": frgn,
                "inst_net_20d": inst,
            }
        )
    return {"items": out, "count": len(out)}


@router.post("")
def add_to_watchlist(request: WatchlistAddRequest):
    md = meta.meta_df()
    if not (md["meta_id"] == request.meta_id).any():
        raise HTTPException(status_code=404, detail=f"meta_id {request.meta_id} not found")
    watchlist_store.add(request.meta_id, note=request.note or "")
    return {"count": int(len(watchlist_store.list_items()))}


@router.delete("/{meta_id}")
def remove_from_watchlist(meta_id: int):
    watchlist_store.remove(meta_id)
    return {"count": int(len(watchlist_store.list_items()))}
