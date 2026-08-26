"""관심종목 API — {APP_DATA}/watchlist.parquet CRUD + 시세·수급 enrich.

GET은 meta 조인 후 KR은 자산 유형에 맞는 qdata KRX 종목/ETF 패널(최근 종가·등락률)과
insight/flows_signals.parquet(20일 수급), US는 datastore 가격 최근 2점으로 채운다.
enrich 소스가 없어도 항목은 None으로 응답한다.
"""

import logging
import os
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../../../")))

from datastore import meta, storage
from datastore import watchlist as watchlist_store
from datastore.prices import read_price_data

logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")

router = APIRouter(prefix="/watchlist", tags=["Watchlist"])


class WatchlistAddRequest(BaseModel):
    meta_id: int
    note: str | None = ""


class WatchlistUpdateRequest(BaseModel):
    note: str = ""
    thesis: str = ""
    catalyst: str = ""
    invalidation: str = ""
    review_date: date | None = None
    alerts_enabled: bool = False
    alert_price_above: float | None = Field(None, gt=0)
    alert_price_below: float | None = Field(None, gt=0)
    alert_change_pct: float | None = Field(None, ge=0.1, le=100)


def _none_if_na(v):
    try:
        return None if pd.isna(v) else v
    except (TypeError, ValueError):
        return v


def _kr_latest_prices(meta_ids: list[int]) -> dict:
    """{meta_id: (close, previous_close, chg_pct, as_of)} — KRX 최근 2점.

    ``read_price_data``가 통합 마스터의 ``security_type``으로 일반 종목과 ETF를
    각 qdata 패널에 라우팅한다. 모든 KR ticker를 종목 패널로 보내면 ETF가 조용히
    누락되므로 여기서 별도 소스를 직접 선택하지 않는다.
    """
    out: dict = {}
    try:
        start = (datetime.now(KST).date() - timedelta(days=14)).isoformat()
        px = read_price_data("KR", meta_ids=meta_ids, start_date=start)
        if px.empty:
            return out
        for meta_id, group in px.sort_values("trade_date").groupby("meta_id"):
            rows = group.dropna(subset=["close"])
            if rows.empty:
                continue
            last = rows.iloc[-1]
            previous = float(rows.iloc[-2]["close"]) if len(rows) >= 2 else None
            latest_return = last.get("gross_return")
            chg_pct = (
                float(latest_return) * 100.0
                if pd.notna(latest_return)
                else (
                    (float(last["close"]) / previous - 1.0) * 100.0
                    if previous not in (None, 0.0)
                    else None
                )
            )
            out[int(meta_id)] = (
                float(last["close"]),
                previous,
                chg_pct,
                pd.Timestamp(last["trade_date"]).strftime("%Y-%m-%d"),
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
    except Exception:  # noqa: BLE001 - optional enrich source must not fail the watchlist
        logger.debug("watchlist flows enrich 실패 (flows_signals 부재 가능)")
    return out


def _us_latest_prices(meta_ids: list[int]) -> dict:
    """US 현재·직전 raw close와 기업행동 보정 일간 수익률을 반환한다."""
    out: dict = {}
    try:
        df = read_price_data(
            "US",
            meta_ids=meta_ids,
            start_date=datetime.now(KST).date() - timedelta(days=30),
        )
        if df.empty:
            return out
        for mid, group in df.groupby("meta_id"):
            price_column = (
                "close"
                if "close" in group.columns and group["close"].notna().any()
                else "adj_close"
            )
            valid = group.sort_values("trade_date").dropna(subset=[price_column])
            if valid.empty:
                continue
            values = valid[price_column]
            last = float(values.iloc[-1])
            chg = None
            latest_return = valid.iloc[-1].get("gross_return")
            if pd.notna(latest_return):
                chg = float(latest_return) * 100.0
            elif len(values) >= 2 and values.iloc[-2] != 0:
                # 구형 파일이나 첫 배치의 수익률 결측에만 가격비 폴백한다.
                chg = (last / float(values.iloc[-2]) - 1.0) * 100.0
            previous = float(values.iloc[-2]) if len(values) >= 2 else None
            out[int(mid)] = (
                last,
                previous,
                chg,
                pd.Timestamp(valid["trade_date"].iloc[-1]).strftime("%Y-%m-%d"),
            )
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
    kr_px = _kr_latest_prices([int(x) for x in kr["meta_id"]]) if not kr.empty else {}
    kr_stocks = kr[
        ~kr["security_type"].astype(str).str.upper().eq("ETF")
    ]
    kr_fl = (
        _kr_flows(kr_stocks["ticker"].dropna().tolist())
        if not kr_stocks.empty
        else {}
    )
    us_px = _us_latest_prices([int(x) for x in us["meta_id"]]) if not us.empty else {}

    out = []
    for r in df.itertuples():
        latest_price = previous_price = chg_pct = price_as_of = frgn = inst = None
        if r.iso_code == "KR":
            latest_price, previous_price, chg_pct, price_as_of = kr_px.get(
                int(r.meta_id), (None, None, None, None)
            )
            flows = kr_fl.get(r.ticker, {})
            frgn, inst = flows.get("frgn"), flows.get("inst")
        elif r.iso_code == "US":
            latest_price, previous_price, chg_pct, price_as_of = us_px.get(
                int(r.meta_id), (None, None, None, None)
            )
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
                "thesis": _none_if_na(r.thesis),
                "catalyst": _none_if_na(r.catalyst),
                "invalidation": _none_if_na(r.invalidation),
                "review_date": (
                    pd.Timestamp(r.review_date).strftime("%Y-%m-%d")
                    if _none_if_na(r.review_date) is not None
                    else None
                ),
                "latest_price": latest_price,
                "previous_price": previous_price,
                "chg_pct": chg_pct,
                "price_as_of": price_as_of,
                "frgn_net_20d": frgn,
                "inst_net_20d": inst,
                "alerts_enabled": bool(_none_if_na(r.alerts_enabled) or False),
                "alert_price_above": _none_if_na(r.alert_price_above),
                "alert_price_below": _none_if_na(r.alert_price_below),
                "alert_change_pct": _none_if_na(r.alert_change_pct),
            }
        )
    return {"items": out, "count": len(out)}


@router.post("")
def add_to_watchlist(request: WatchlistAddRequest):
    md = meta.meta_df()
    if not (md["meta_id"] == request.meta_id).any():
        raise HTTPException(status_code=404, detail=f"meta_id {request.meta_id} not found")
    watchlist_store.add(request.meta_id, note=request.note or "")
    return {"count": len(watchlist_store.list_items())}


@router.put("/{meta_id}")
def update_watchlist_item(meta_id: int, request: WatchlistUpdateRequest):
    updated = watchlist_store.update(
        meta_id,
        note=request.note,
        thesis=request.thesis,
        catalyst=request.catalyst,
        invalidation=request.invalidation,
        review_date=request.review_date,
        alerts_enabled=request.alerts_enabled,
        alert_price_above=request.alert_price_above,
        alert_price_below=request.alert_price_below,
        alert_change_pct=request.alert_change_pct,
    )
    if not updated:
        raise HTTPException(status_code=404, detail=f"meta_id {meta_id} not in watchlist")
    return {"count": len(watchlist_store.list_items())}


@router.delete("/{meta_id}")
def remove_from_watchlist(meta_id: int):
    watchlist_store.remove(meta_id)
    return {"count": len(watchlist_store.list_items())}
