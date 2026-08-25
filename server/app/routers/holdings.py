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

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../../../"))
)

from qdata import api as qdata_api

from datastore import fx
from datastore import holdings as holdings_store
from datastore import meta, portfolio_ledger
from datastore.prices import read_price_data
from module import portfolio_risk

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/holdings", tags=["Holdings"])

_META_COLS = ["meta_id", "ticker", "name", "iso_code", "security_type", "sector"]


class HoldingRequest(BaseModel):
    meta_id: int
    shares: float
    avg_cost: float
    currency: Optional[str] = None
    target_weight: Optional[float] = None
    note: Optional[str] = ""
    thesis: Optional[str] = ""
    invalidation: Optional[str] = ""
    review_date: Optional[date] = None


class HoldingMetadataRequest(BaseModel):
    target_weight: Optional[float] = None
    note: str = ""
    thesis: str = ""
    invalidation: str = ""
    review_date: Optional[date] = None


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
        px = qdata_api.load_krx_prices(
            start=start, tickers=tickers, columns=["close", "chg_pct"]
        )
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
    """{meta_id: (raw close, 기업행동 보정 chg_pct)}."""
    out: dict = {}
    if not meta_ids:
        return out
    try:
        df = read_price_data(
            "US", meta_ids=meta_ids, start_date=date.today() - timedelta(days=30)
        )
        if df.empty:
            return out
        for mid, g in df.groupby("meta_id"):
            price_column = (
                "close"
                if "close" in g.columns and g["close"].notna().any()
                else "adj_close"
            )
            s = g.sort_values("trade_date")[price_column].dropna()
            if s.empty:
                continue
            last = float(s.iloc[-1])
            chg = None
            valid = g.sort_values("trade_date").dropna(subset=[price_column])
            latest_return = valid.iloc[-1].get("gross_return")
            if pd.notna(latest_return):
                chg = float(latest_return) * 100.0
            elif len(s) >= 2 and s.iloc[-2] != 0:
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
    """[meta_id, ticker, iso_code,(security_type)] → 최신 가격 맵.

    소스별로 라우팅: KR 종목/ETF/US. 숫자 ID 대역이 아니라 마스터 유형을 쓴다.
    """
    out: dict = {}
    if df.empty:
        return out
    if "security_type" not in df.columns:
        types = meta.meta_df()[["meta_id", "security_type"]]
        before = len(df)
        df = df.merge(types, on="meta_id", how="left", validate="many_to_one")
        if len(df) != before or df["security_type"].isna().any():
            raise ValueError("가격 라우팅용 security_type 조인 실패")
    kr = df[df["iso_code"] == "KR"]
    is_etf = kr["security_type"].astype(str).str.upper().eq("ETF")
    kr_stock = kr[~is_etf]
    kr_etf = kr[is_etf]
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
        "priced_positions": 0,
        "unpriced_positions": 0,
        "valuation_complete": True,
        "sector_alloc": [],
        "market_alloc": [],
        "asset_alloc": [],
        "top_weight": None,
        "top3_weight": None,
        "hhi": None,
        "effective_positions": None,
        "target_total": None,
    }


# ---------- 엔드포인트 ----------


@router.get("")
def get_holdings():
    """보유 포지션 + 평가·손익 요약."""
    items = (
        portfolio_ledger.current_positions()
        if portfolio_ledger.has_events()
        else holdings_store.list_items()
    )
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
    asset_agg: dict = {}

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
        stored_target = getattr(r, "target_weight", None)
        target_weight = float(stored_target) if pd.notna(stored_target) else None

        mv_krw = (
            mv_native * fxrate
            if (mv_native is not None and fxrate is not None)
            else None
        )
        cost_krw = cost_native * fxrate if fxrate is not None else None
        day_native = (
            shares * price * (chg / 100.0)
            if (price is not None and chg is not None)
            else None
        )
        day_krw = (
            day_native * fxrate
            if (day_native is not None and fxrate is not None)
            else None
        )

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
            asset_type = "ETF" if str(r.security_type).upper() == "ETF" else "Equity"
            asset_agg[asset_type] = asset_agg.get(asset_type, 0.0) + mv_krw
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
                "target_weight": target_weight,
                "thesis": _none_if_na(getattr(r, "thesis", "")) or "",
                "invalidation": _none_if_na(getattr(r, "invalidation", "")) or "",
                "review_date": (
                    pd.Timestamp(r.review_date).strftime("%Y-%m-%d")
                    if _none_if_na(getattr(r, "review_date", None)) is not None
                    else None
                ),
                "_mv_krw": mv_krw,
            }
        )

    # 2차: 비중 부여 + 반올림
    positions = []
    for p in raw:
        mv = p.pop("_mv_krw")
        weight = (
            mv / total_value_krw if (mv is not None and total_value_krw > 0) else None
        )
        target_weight = p["target_weight"]
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
                "target_weight": _r(target_weight, 4),
                "drift_pp": _r(
                    (
                        (weight - target_weight) * 100
                        if weight is not None and target_weight is not None
                        else None
                    ),
                    2,
                ),
                "thesis": p["thesis"],
                "invalidation": p["invalidation"],
                "review_date": p["review_date"],
            }
        )

    weights = []
    for pos in positions:
        if pos["market_value_krw"] is not None and total_value_krw > 0:
            weights.append(pos["market_value_krw"] / total_value_krw)

    hhi = sum(w * w for w in weights) if weights else None
    top_weight = max(weights) if weights else None
    top3_weight = sum(sorted(weights, reverse=True)[:3]) if weights else None
    effective_positions = 1 / hhi if hhi and hhi > 0 else None
    targets = [p["target_weight"] for p in positions if p["target_weight"] is not None]

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
    priced_positions = sum(p["market_value_krw"] is not None for p in positions)
    unpriced_positions = len(positions) - priced_positions
    summary = {
        "total_value_krw": _r(total_value_krw, 2),
        "total_cost_krw": _r(total_cost_krw, 2),
        "total_pnl_krw": _r(total_pnl_krw, 2),
        "total_pnl_pct": _r(total_pnl_pct, 4),
        "day_pnl_krw": _r(day_pnl_krw, 2),
        "n_positions": len(positions),
        "priced_positions": priced_positions,
        "unpriced_positions": unpriced_positions,
        "valuation_complete": unpriced_positions == 0,
        "sector_alloc": _alloc(sector_agg),
        "market_alloc": _market_alloc(market_agg),
        "asset_alloc": _market_alloc(asset_agg),
        "top_weight": _r(top_weight, 4),
        "top3_weight": _r(top3_weight, 4),
        "hhi": _r(hhi, 4),
        "effective_positions": _r(effective_positions, 1),
        "target_total": _r(sum(targets), 4) if targets else None,
    }
    return {"positions": positions, "summary": summary}


@router.post("")
def add_holding(request: HoldingRequest):
    if portfolio_ledger.has_events():
        raise HTTPException(
            status_code=409, detail="원장 시작 후 수량·평단은 거래 이벤트로 변경하세요"
        )
    md = meta.meta_df()
    row = md[md["meta_id"] == request.meta_id]
    if row.empty:
        raise HTTPException(
            status_code=404, detail=f"meta_id {request.meta_id} not found"
        )
    if request.target_weight is not None and not 0 <= request.target_weight <= 1:
        raise HTTPException(
            status_code=400, detail="target_weight must be between 0 and 1"
        )

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
        target_weight=request.target_weight,
        thesis=request.thesis or "",
        invalidation=request.invalidation or "",
        review_date=request.review_date,
    )
    return {"n_positions": int(len(holdings_store.list_items()))}


@router.put("/{meta_id}/metadata")
def update_holding_metadata(meta_id: int, request: HoldingMetadataRequest):
    if request.target_weight is not None and not 0 <= request.target_weight <= 1:
        raise HTTPException(
            status_code=400, detail="target_weight must be between 0 and 1"
        )
    if portfolio_ledger.has_events():
        try:
            portfolio_ledger.upsert_position_metadata(meta_id, request.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    else:
        item = holdings_store.list_items()
        hit = item[item["meta_id"] == meta_id]
        if hit.empty:
            raise HTTPException(status_code=404, detail="보유 종목을 찾을 수 없습니다")
        row = hit.iloc[0]
        holdings_store.upsert(
            meta_id,
            shares=float(row["shares"]),
            avg_cost=float(row["avg_cost"]),
            currency=str(row["currency"]),
            note=request.note,
            target_weight=request.target_weight,
            thesis=request.thesis,
            invalidation=request.invalidation,
            review_date=request.review_date,
        )
    return {"n_positions": int(len(portfolio_ledger.current_positions()))}


@router.delete("/{meta_id}")
def remove_holding(meta_id: int):
    if portfolio_ledger.has_events():
        raise HTTPException(
            status_code=409, detail="원장 시작 후 보유 수량은 매도 이벤트로 변경하세요"
        )
    holdings_store.remove(meta_id)
    return {"n_positions": int(len(holdings_store.list_items()))}


# ---------- 위험 요약 ----------

RISK_HISTORY_START = "2019-06-03"  # covid_2020 창 + 워밍업 여유
STALE_CAL_DAYS = 7  # 패널 마지막 날짜보다 이보다 오래 뒤처지면 동결 의심
HALT_ROWS = 5  # 최근 N행 거래량 합 0 → 거래정지 의심 (spotlight와 같은 취지, 여기는 최근 5일 합 기준)


def _recent_kr_volume(tickers: list) -> pd.DataFrame:
    """최근 ~3주 KR 거래량 패널 (일자×티커). 실패 시 빈 프레임 — 경고만 포기."""
    try:
        start = (pd.Timestamp.today() - pd.Timedelta(days=21)).strftime("%Y-%m-%d")
        px = qdata_api.load_krx_prices(start=start, tickers=tickers, columns=["volume"])
        return px.pivot(index="date", columns="ticker", values="volume")
    except Exception:
        logger.debug("risk 거래량 조회 실패 — 정지 경고 생략", exc_info=True)
        return pd.DataFrame()


def _risk_price_history(assets: pd.DataFrame) -> pd.DataFrame:
    """KR·US 공통 split-adjusted 위험 패널을 구성한다.

    양 시장 모두 분할 등 기업행동만 조정하고 현금분배는 포함하지 않는다. US의
    총수익 ``adj_close``는 이 목적에 쓰지 않는다. 전환 전 US 앱 파일처럼
    ``split_adj_close``가 없으면 raw/총수익으로 폴백하지 않고 해당 종목을 제외한다.
    """
    frames = []
    for iso_code, group in assets.groupby("iso_code"):
        history = read_price_data(
            str(iso_code),
            meta_ids=[int(value) for value in group["meta_id"]],
            start_date=date.fromisoformat(RISK_HISTORY_START),
            end_date=date.today(),
        )
        price_column = "split_adj_close" if iso_code == "US" else "adj_close"
        if history.empty or price_column not in history.columns:
            continue
        if iso_code == "KR" and "return_basis" in history.columns:
            history = history[
                ~history["return_basis"].eq("raw_price_return_ex_cash_distributions")
            ]
        history = history[["trade_date", "ticker", price_column]].copy()
        history = history.rename(columns={price_column: "risk_price"})
        history["risk_price"] = pd.to_numeric(history["risk_price"], errors="coerce")
        history.loc[history["risk_price"] <= 0, "risk_price"] = pd.NA
        frames.append(history.dropna(subset=["risk_price"]))
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    if combined.duplicated(["trade_date", "ticker"]).any():
        raise ValueError("위험 가격 패널에 중복 date/ticker가 있습니다")
    out = combined.pivot(index="trade_date", columns="ticker", values="risk_price")
    out.index = pd.to_datetime(out.index)
    out = out.sort_index()
    out.attrs["return_basis"] = "split_adjusted_price_return_ex_cash_distributions_krw"
    return out


@router.get("/risk")
def get_holdings_risk():
    """보유 조합의 역사적 위험 요약 — 현재 비중 고정 가정 (module/portfolio_risk).

    판단 라벨 없음 — 수치·전제·데이터 경고만. holdings 비면 empty, 공통 이력
    부족이면 insufficient. 어느 경로든 500을 내지 않는다.
    """
    items = (
        portfolio_ledger.current_positions()
        if portfolio_ledger.has_events()
        else holdings_store.list_items()
    )
    if items.empty:
        return {"empty": True}

    md = meta.meta_df()[_META_COLS]
    df = items.merge(md, on="meta_id", how="left")
    price_map = build_price_map(df[["meta_id", "ticker", "iso_code"]])
    usdkrw = _usdkrw_latest()

    warnings: list = []
    mv: dict = {}
    tickers_iso: dict = {}
    names: dict = {}
    for r in df.itertuples():
        ticker = _none_if_na(r.ticker)
        price, _chg = price_map.get(int(r.meta_id), (None, None))
        fxrate = usdkrw if r.iso_code == "US" else 1.0
        if ticker is None or price is None or fxrate is None:
            warnings.append(
                {
                    "kind": "no_price",
                    "ticker": ticker,
                    "detail": "가격 조회 실패 — 위험 계산에서 제외",
                }
            )
            continue
        mv[ticker] = mv.get(ticker, 0.0) + float(r.shares) * price * fxrate
        tickers_iso[ticker] = r.iso_code
        names[ticker] = _none_if_na(r.name) or ticker

    total = sum(mv.values())
    if not mv or total <= 0:
        return {"empty": True, "reason": "평가 가능한 포지션 없음"}
    weights = {t: v / total for t, v in mv.items()}
    original_weights = weights.copy()

    try:
        prices = _risk_price_history(df)
    except Exception:
        logger.warning("risk 가격 이력 로드 실패", exc_info=True)
        return {"empty": True, "reason": "가격 이력 로드 실패"}
    prices = prices[[c for c in prices.columns if c in weights]]
    missing = sorted(set(weights) - set(prices.columns))
    for t in missing:
        warnings.append(
            {"kind": "no_history", "ticker": t, "detail": "가격 이력 없음 — 제외"}
        )
        weights.pop(t)
    if not weights:
        return {
            "empty": True,
            "reason": "가격 이력 있는 포지션 없음",
            "warnings": warnings,
            "coverage": {
                "n_assets": 0,
                "total_assets": len(mv),
                "weight": 0.0,
            },
        }
    covered_weight = sum(original_weights[t] for t in weights)
    total_w = sum(weights.values())
    weights = {t: w / total_w for t, w in weights.items()}

    if any(tickers_iso.get(t) == "US" for t in weights):
        try:
            prices = fx.to_krw(prices, tickers_iso)
        except Exception:
            # 환산 불가면 US를 빼고 진행 — 통화가 섞인 패널을 조용히 쓰지 않는다
            logger.warning("risk 환율 변환 실패 — US 제외", exc_info=True)
            for t in [t for t, iso in tickers_iso.items() if iso == "US"]:
                if t in weights:
                    warnings.append(
                        {
                            "kind": "no_fx",
                            "ticker": t,
                            "detail": "환율 조회 실패 — 위험 계산에서 제외",
                        }
                    )
                    weights.pop(t)
            prices = prices[[c for c in prices.columns if c in weights]]
            if not weights:
                return {
                    "empty": True,
                    "reason": "환율 조회 실패로 평가 가능한 포지션 없음",
                    "warnings": warnings,
                    "coverage": {
                        "n_assets": 0,
                        "total_assets": len(mv),
                        "weight": 0.0,
                    },
                }
            covered_weight = sum(original_weights[t] for t in weights)
            total_w = sum(weights.values())
            weights = {t: w / total_w for t, w in weights.items()}

    # 데이터 품질 경고 — 조용히 계산하지 않는다 (동결·정지는 위험 과소평가 방향)
    panel_end = prices.index.max()
    for t in prices.columns:
        last = prices[t].last_valid_index()
        if last is not None and (panel_end - last).days > STALE_CAL_DAYS:
            warnings.append(
                {
                    "kind": "stale",
                    "ticker": t,
                    "detail": f"가격 이력이 {last.date()}에서 멈춤 — 이후 변동 미반영",
                }
            )
    kr = [t for t, iso in tickers_iso.items() if iso == "KR" and t in prices.columns]
    vol = _recent_kr_volume(kr)
    for t in kr:
        if (
            t in vol.columns
            and len(vol) >= HALT_ROWS
            and float(vol[t].tail(HALT_ROWS).sum()) == 0
        ):
            warnings.append(
                {
                    "kind": "halted",
                    "ticker": t,
                    "detail": "최근 5일 거래량 0 — 동결 가격이 변동성·상관을 과소평가",
                }
            )

    report = portfolio_risk.build_report(prices, weights)
    if report.get("insufficient"):
        return {
            "insufficient": True,
            "overlap_days": report["overlap_days"],
            "warnings": warnings,
            "coverage": {
                "n_assets": len(weights),
                "total_assets": len(mv),
                "weight": _r(covered_weight, 4),
            },
        }
    if report["overlap_days"] < 250:
        warnings.append(
            {
                "kind": "short_history",
                "ticker": None,
                "detail": f"공통 가격 이력 {report['overlap_days']}일 — 최근 상장 종목이 분석 구간을 절단",
            }
        )

    corr = report["corr"]
    corr_payload = None
    if corr is not None:
        order = list(corr.columns)
        corr_payload = {
            "tickers": order,
            "names": [names.get(t, t) for t in order],
            "values": [[_r(corr.loc[a, b], 2) for b in order] for a in order],
        }

    return {
        "ann_vol": _r(report["ann_vol"], 1),
        "max_drawdown": _r(report["max_drawdown"], 1),
        "mdd_from": report["mdd_from"],
        "mdd_to": report["mdd_to"],
        "avg_pair_corr": _r(report["avg_pair_corr"], 2),
        "diversification_ratio": _r(report["diversification_ratio"], 2),
        "risk_contributions": [
            {
                **row,
                "name": names.get(row["ticker"], row["ticker"]),
                "weight": _r(row["weight"], 4),
                "asset_ann_vol": _r(row["asset_ann_vol"], 1),
                "risk_share": _r(row["risk_share"], 4),
                "risk_contribution_pct": _r(row["risk_contribution_pct"], 1),
            }
            for row in report["risk_contributions"]
        ],
        "corr": corr_payload,
        "scenarios": [
            {**s, "ret_pct": _r(s["ret_pct"], 1)} for s in report["scenarios"]
        ],
        "warnings": warnings,
        "coverage": {
            "n_assets": len(weights),
            "total_assets": len(mv),
            "weight": _r(covered_weight, 4),
        },
        "basis": {
            "n_assets": len(weights),
            "total_assets": len(mv),
            "coverage_weight": _r(covered_weight, 4),
            "weights_as_of": date.today().isoformat(),
            "overlap_days": report["overlap_days"],
            "window": report["window"],
            "return_basis": "split_adjusted_price_return_ex_cash_distributions_krw",
        },
    }
