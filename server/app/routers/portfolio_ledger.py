"""거래·현금흐름 불변 이벤트 원장 API."""

from datetime import date, datetime, timezone
from typing import Literal, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from datastore import fx, holdings as holdings_store, meta
from datastore import portfolio_ledger as ledger
from datastore.prices import read_price_data
from module.portfolio_performance import TwrResult, calculate_twr

router = APIRouter(prefix="/portfolio-ledger", tags=["Portfolio Ledger"])


class LedgerEventRequest(BaseModel):
    idempotency_key: str = Field(..., min_length=8, max_length=100)
    event_type: Literal["BUY", "SELL", "DEPOSIT", "WITHDRAW", "DIVIDEND", "FEE", "FX"]
    occurred_at: date
    meta_id: Optional[int] = None
    shares: Optional[float] = Field(None, gt=0)
    price: Optional[float] = Field(None, gt=0)
    currency: str = Field("KRW", pattern="^(KRW|USD)$")
    amount: Optional[float] = Field(None, gt=0)
    fees: float = Field(0, ge=0)
    counter_currency: Optional[str] = Field(None, pattern="^(KRW|USD)$")
    counter_amount: Optional[float] = Field(None, gt=0)
    note: str = Field("", max_length=1000)
    thesis: str = Field("", max_length=4000)
    invalidation: str = Field("", max_length=4000)
    review_date: Optional[date] = None


def _validate(request: LedgerEventRequest):
    if request.event_type in {"BUY", "SELL"}:
        if request.meta_id is None or request.shares is None or request.price is None:
            raise HTTPException(status_code=400, detail="BUY/SELL에는 종목·수량·체결가가 필요합니다")
    if request.event_type in {"DEPOSIT", "WITHDRAW", "DIVIDEND", "FEE", "FX"} and request.amount is None:
        raise HTTPException(status_code=400, detail=f"{request.event_type}에는 금액이 필요합니다")
    if request.event_type == "FX" and (not request.counter_currency or request.counter_amount is None):
        raise HTTPException(status_code=400, detail="FX에는 상대 통화와 수취 금액이 필요합니다")


def _summary() -> dict:
    events = ledger.list_events()
    cash = ledger.cash_balances()
    usdkrw = None
    try:
        series = fx.usdkrw()
        usdkrw = float(series.iloc[-1]) if not series.empty else None
    except Exception:
        pass
    cash_krw = cash.get("KRW", 0.0)
    if usdkrw is not None:
        cash_krw += cash.get("USD", 0.0) * usdkrw
    else:
        cash_krw = None if cash.get("USD") else cash_krw
    twr = _calculate_twr(events)
    return {
        "events_count": len(events),
        "started_at": pd.Timestamp(events["occurred_at"].min()).strftime("%Y-%m-%d") if not events.empty else None,
        "cash_balances": cash,
        "cash_value_krw": cash_krw,
        "realized_pnl": ledger.realized_pnl(),
        "opening_positions": len(ledger.opening_positions()) if ledger.has_events() else 0,
        "twr": twr.value,
        "twr_as_of": twr.as_of,
        "twr_periods": twr.periods,
        "twr_note": twr.note,
        "cost_basis": "이동평균법",
    }


def _calculate_twr(events: pd.DataFrame) -> TwrResult:
    if events.empty:
        return TwrResult(None, None, 0, "원장 이벤트가 없어 계산하지 않습니다.")
    opening = ledger.opening_positions()
    ids = set(int(value) for value in opening["meta_id"].dropna())
    ids.update(int(value) for value in events["meta_id"].dropna())
    if not ids:
        return TwrResult(None, None, 0, "평가할 보유 자산이 없습니다.")
    md = meta.meta_df()
    mapping = md[md["meta_id"].isin(ids)][["meta_id", "iso_code"]]
    if len(mapping) != len(ids):
        return TwrResult(None, None, 0, "종목 메타데이터가 불완전합니다.")
    start = pd.Timestamp(events["occurred_at"].min()) - pd.Timedelta(days=14)
    frames = []
    try:
        for iso_code in ("KR", "US"):
            meta_ids = [int(value) for value in mapping[mapping["iso_code"] == iso_code]["meta_id"]]
            if not meta_ids:
                continue
            frame = read_price_data(
                iso_code,
                meta_ids=meta_ids,
                start_date=start.date(),
                end_date=date.today(),
            )
            if not frame.empty:
                frames.append(frame[["trade_date", "meta_id", "adj_close"]])
        if not frames:
            return TwrResult(None, None, 0, "일별 평가 가격을 불러오지 못했습니다.")
        prices = pd.concat(frames, ignore_index=True).pivot_table(
            index="trade_date", columns="meta_id", values="adj_close", aggfunc="last"
        )
        prices.index = pd.to_datetime(prices.index)
        prices = prices.sort_index().ffill()
        needs_usd = bool((mapping["iso_code"] == "US").any()) or bool(
            (events["currency"] == "USD").any()
        )
        rates = fx.usdkrw() if needs_usd else pd.Series(1.0, index=prices.index)
        return calculate_twr(
            events,
            opening,
            prices,
            {
                int(row.meta_id): "USD" if row.iso_code == "US" else "KRW"
                for row in mapping.itertuples(index=False)
            },
            rates,
        )
    except Exception:
        return TwrResult(None, None, 0, "가격 또는 환율 이력을 불러오지 못해 계산하지 않습니다.")


@router.get("")
def get_ledger():
    events = ledger.list_events()
    md = meta.meta_df()[["meta_id", "ticker", "name"]]
    if not events.empty:
        events = events.merge(md, on="meta_id", how="left")
    rows = []
    for row in events.sort_values(["occurred_at", "created_at"], ascending=False).itertuples(index=False):
        rows.append({
            "event_id": row.event_id,
            "occurred_at": pd.Timestamp(row.occurred_at).strftime("%Y-%m-%d"),
            "created_at": pd.Timestamp(row.created_at).isoformat(),
            "event_type": row.event_type,
            "meta_id": None if pd.isna(row.meta_id) else int(row.meta_id),
            "ticker": None if pd.isna(row.ticker) else row.ticker,
            "name": None if pd.isna(row.name) else row.name,
            "shares": None if pd.isna(row.shares) else float(row.shares),
            "price": None if pd.isna(row.price) else float(row.price),
            "currency": row.currency,
            "amount": None if pd.isna(row.amount) else float(row.amount),
            "fees": float(row.fees or 0),
            "counter_currency": None if pd.isna(row.counter_currency) else row.counter_currency,
            "counter_amount": None if pd.isna(row.counter_amount) else float(row.counter_amount),
            "realized_pnl_native": None if pd.isna(row.realized_pnl_native) else float(row.realized_pnl_native),
            "note": row.note or "",
        })
    return {"events": rows, "summary": _summary()}


@router.post("")
def add_ledger_event(request: LedgerEventRequest):
    _validate(request)
    if request.meta_id is not None:
        md = meta.meta_df()
        hit = md[md["meta_id"] == request.meta_id]
        if hit.empty:
            raise HTTPException(status_code=404, detail="종목을 찾을 수 없습니다")
        expected = "KRW" if hit.iloc[0]["iso_code"] == "KR" else "USD"
        if request.event_type in {"BUY", "SELL", "DIVIDEND"} and request.currency != expected:
            raise HTTPException(status_code=400, detail=f"이 종목의 거래 통화는 {expected}입니다")
    try:
        event_id, created = ledger.record(request.model_dump(), holdings_store.list_items())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"event_id": event_id, "created": created, "summary": _summary()}
