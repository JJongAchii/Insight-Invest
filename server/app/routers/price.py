"""
Price data router for stock search features.

Provides endpoints for:
- Price history for individual stocks
- Summary statistics (YTD, 1Y return, volatility, etc.)
- Sparkline data for table view
- Comparison data for multiple stocks
"""

import logging
import math
from datetime import date, timedelta
from typing import Dict, List, Optional

import datastore
import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/price", tags=["Price"])


def _calculate_metrics(prices: pd.Series) -> Dict[str, Optional[float]]:
    """
    Calculate performance metrics from price series.

    Args:
        prices: Series of adjusted close prices indexed by date

    Returns:
        Dictionary with calculated metrics
    """
    if prices.empty or len(prices) < 2:
        return {
            "ytd_return": None,
            "return_1y": None,
            "return_3m": None,
            "volatility": None,
            "sharpe": None,
            "mdd": None,
        }

    # Ensure index is datetime for proper comparison
    prices = prices.copy()
    prices.index = pd.to_datetime(prices.index)
    prices = prices.sort_index()
    returns = prices.pct_change().dropna()

    # Calculate returns
    latest_price = prices.iloc[-1]
    today = prices.index[-1]

    # YTD return
    ytd_start = pd.Timestamp(date(today.year, 1, 1))
    ytd_prices = prices[prices.index >= ytd_start]
    ytd_return = (latest_price / ytd_prices.iloc[0] - 1) if len(ytd_prices) > 0 else None

    # 1Y return
    one_year_ago = today - pd.Timedelta(days=365)
    year_prices = prices[prices.index >= one_year_ago]
    return_1y = (latest_price / year_prices.iloc[0] - 1) if len(year_prices) > 0 else None

    # 3M return
    three_months_ago = today - pd.Timedelta(days=90)
    three_month_prices = prices[prices.index >= three_months_ago]
    return_3m = (
        (latest_price / three_month_prices.iloc[0] - 1) if len(three_month_prices) > 0 else None
    )

    # Annualized volatility (252 trading days)
    volatility = returns.std() * np.sqrt(252) if len(returns) > 1 else None

    # Sharpe ratio (assuming risk-free rate of 4%)
    risk_free_rate = 0.04
    if return_1y is not None and volatility is not None and volatility > 0:
        sharpe = (return_1y - risk_free_rate) / volatility
    else:
        sharpe = None

    # Maximum drawdown
    cummax = prices.cummax()
    drawdown = (prices - cummax) / cummax
    mdd = drawdown.min() if len(drawdown) > 0 else None

    return {
        "ytd_return": float(ytd_return) if ytd_return is not None else None,
        "return_1y": float(return_1y) if return_1y is not None else None,
        "return_3m": float(return_3m) if return_3m is not None else None,
        "volatility": float(volatility) if volatility is not None else None,
        "sharpe": float(sharpe) if sharpe is not None else None,
        "mdd": float(mdd) if mdd is not None else None,
    }


def _kr_summary_extras(ticker: str) -> Dict:
    """KR 종목 부가 정보 — 최근일 거래대금·시총, 최신 PER/PBR/배당수익률, 20일 수급.

    소스별 독립 try/except — 어떤 소스가 없어도 (fundamental 백필 중 등) None으로 응답.
    """
    extras: Dict = {
        "value": None,
        "mktcap": None,
        "per": None,
        "pbr": None,
        "div": None,
        "flows_recent": None,
    }
    start = (date.today() - timedelta(days=14)).isoformat()

    try:
        from qdata import api as qdata_api

        px = qdata_api.load_krx_prices(start=start, tickers=[ticker], columns=["value", "mktcap"])
        if not px.empty:
            row = px.sort_values("date").iloc[-1]
            extras["value"] = float(row["value"]) if pd.notna(row["value"]) else None
            extras["mktcap"] = float(row["mktcap"]) if pd.notna(row["mktcap"]) else None
    except Exception:
        logger.warning(f"KR price extras 조회 실패: {ticker}", exc_info=True)

    try:
        from qdata import api as qdata_api

        fund = qdata_api.load_krx_fundamental(
            start=start, tickers=[ticker], columns=["per", "pbr", "div"]
        )
        if not fund.empty:
            row = fund.sort_values("date").iloc[-1]
            # KRX는 PER/PBR=0을 결측(적자·산출불가) 표기로 사용 — 0은 None 처리
            per = float(row["per"]) if pd.notna(row["per"]) else 0.0
            pbr = float(row["pbr"]) if pd.notna(row["pbr"]) else 0.0
            extras["per"] = per if per > 0 else None
            extras["pbr"] = pbr if pbr > 0 else None
            extras["div"] = float(row["div"]) if pd.notna(row["div"]) else None
    except Exception:
        logger.debug(f"KR fundamental 조회 실패 (미수집 가능): {ticker}")

    try:
        from datastore import storage

        sig = storage.read_parquet(
            "insight",
            "flows_signals.parquet",
            columns=["ticker", "investor", "net_20d"],
            filters=[("ticker", "==", ticker)],
        )
        if not sig.empty:
            net = sig.set_index("investor")["net_20d"]
            extras["flows_recent"] = {
                "frgn_net_20d": float(net["frgn"]) if "frgn" in net.index else None,
                "inst_net_20d": float(net["inst"]) if "inst" in net.index else None,
            }
    except Exception:
        logger.debug(f"flows_signals 조회 실패: {ticker}")

    return extras


_EMPTY_EXTRAS: Dict = {
    "value": None,
    "mktcap": None,
    "per": None,
    "pbr": None,
    "div": None,
    "flows_recent": None,
}


_US_FUNDAMENTAL_TAGS = {
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
    ),
    "net_income": ("NetIncomeLoss",),
    "assets": ("Assets",),
    "equity": (
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
}
_US_DURATION_FACTS = {"revenue", "net_income", "operating_cash_flow"}


def _latest_annual_fact(df: pd.DataFrame, key: str) -> Optional[dict]:
    """현재 시점에 공개된 최신 연간 SEC 사실과 직전 연도 증감을 고른다.

    SEC는 같은 기간을 정정 제출할 수 있으므로 ddate별 최신 filed를 남긴다. 태그
    변천(Revenues ↔ RevenueFromContract...)은 최신 회계기간을 우선하고 같은 날이면
    위의 우선순위를 쓴다.
    """
    tags = _US_FUNDAMENTAL_TAGS[key]
    part = df[df["tag"].isin(tags)].copy()
    if key in _US_DURATION_FACTS:
        part = part[part["qtrs"] == 4]
    else:
        part = part[part["qtrs"] == 0]
    part = part[(part["uom"] == "USD") & part["ddate"].notna() & part["filed"].notna()]
    if part.empty:
        return None
    priority = {tag: idx for idx, tag in enumerate(tags)}
    part["_priority"] = part["tag"].map(priority).fillna(len(tags))
    part = part.sort_values(["ddate", "filed", "_priority"])
    # 정정 제출은 최신 filed, 같은 기간의 태그 중에는 정의한 우선순위가 앞선 것.
    by_period = (
        part.sort_values(["ddate", "filed", "_priority"], ascending=[True, True, False])
        .groupby("ddate", as_index=False)
        .tail(1)
        .sort_values("ddate")
    )
    current = by_period.iloc[-1]
    previous = by_period.iloc[-2] if len(by_period) >= 2 else None
    value = float(current["value"])
    yoy = None
    if previous is not None and float(previous["value"]) != 0:
        yoy = (value / float(previous["value"]) - 1.0) * 100.0
    return {
        "key": key,
        "value": value,
        "yoy_pct": yoy if yoy is None or math.isfinite(yoy) else None,
        "period": pd.Timestamp(current["ddate"]).strftime("%Y-%m-%d"),
        "filed": pd.Timestamp(current["filed"]).strftime("%Y-%m-%d"),
        "unit": str(current["uom"]),
        "tag": str(current["tag"]),
    }


def _us_fundamentals(ticker: str) -> dict:
    """Massive 티커→CIK 다리와 SEC as-filed 사실로 현재 핵심 재무를 구성한다."""
    from qdata import api as qdata_api

    today = date.today().isoformat()
    refs = qdata_api.load_us_tickers(asof=today)
    hit = refs[(refs["ticker"] == ticker) & refs["cik"].notna()]
    if hit.empty:
        return {"available": False, "note": "Massive 티커 참조에서 CIK를 찾지 못했습니다."}
    # 동일 티커가 한 빈티지에 중복이면 active 우선. 티커는 영구키가 아니므로 asof를
    # 명시하지 않은 현재 매핑을 임의로 과거에 적용하지 않는다.
    if "active" in hit.columns:
        hit = hit.sort_values("active")
    cik = int(hit.iloc[-1]["cik"])
    facts = qdata_api.load_sec_fundamental(
        start=(date.today() - timedelta(days=365 * 5)).isoformat(),
        end=today,
        ciks=[cik],
        tags=sorted({tag for tags in _US_FUNDAMENTAL_TAGS.values() for tag in tags}),
    )
    if facts.empty:
        return {"available": False, "cik": cik, "note": "공개된 SEC 연간 재무 사실이 없습니다."}
    annual = facts[facts["form"].astype(str).str.startswith("10-K")]
    if "fp" in annual.columns:
        annual = annual[annual["fp"].fillna("FY") == "FY"]
    rows = [fact for key in _US_FUNDAMENTAL_TAGS if (fact := _latest_annual_fact(annual, key))]
    if not rows:
        return {"available": False, "cik": cik, "note": "비교 가능한 연간 USD 사실이 없습니다."}
    return {
        "available": True,
        "ticker": ticker,
        "cik": cik,
        "as_of": max(row["filed"] for row in rows),
        "facts": rows,
        "note": "SEC 제출 원문 기준이며, filed 날짜 이후에만 알 수 있었던 값입니다.",
    }


@router.get("/sparklines")
def get_sparklines(
    meta_ids: str = Query(..., description="Comma-separated meta_ids"),
):
    """
    Get 30-day sparkline data for multiple stocks.

    Args:
        meta_ids: Comma-separated list of meta_ids

    Returns:
        Dictionary mapping meta_id to list of normalized prices (0-100 scale)
    """
    try:
        meta_id_list = [int(x.strip()) for x in meta_ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid meta_ids format")

    if not meta_id_list:
        return {"sparklines": {}}

    # Get meta info to determine iso_code
    meta_df = datastore.meta_df()
    meta_info = meta_df[meta_df["meta_id"].isin(meta_id_list)][["meta_id", "iso_code"]]

    if meta_info.empty:
        return {"sparklines": {}}

    # Fetch price data (last 30 days)
    end_date = date.today()
    start_date = end_date - timedelta(days=45)  # Extra days to ensure 30 trading days

    sparklines = {}

    for iso_code in meta_info["iso_code"].unique():
        iso_meta_ids = meta_info[meta_info["iso_code"] == iso_code]["meta_id"].tolist()

        price_df = datastore.read_price_data(
            iso_code=iso_code,
            meta_ids=iso_meta_ids,
            start_date=start_date,
            end_date=end_date,
        )

        if price_df.empty:
            continue

        # Process each stock
        for meta_id in iso_meta_ids:
            stock_prices = price_df[price_df["meta_id"] == meta_id].sort_values("trade_date")

            if stock_prices.empty:
                sparklines[str(meta_id)] = []
                continue

            # Take last 30 data points
            stock_prices = stock_prices.tail(30)
            prices = stock_prices["adj_close"].values

            if len(prices) < 2:
                sparklines[str(meta_id)] = []
                continue

            # Normalize to 0-100 scale
            min_price = prices.min()
            max_price = prices.max()

            if max_price > min_price:
                normalized = ((prices - min_price) / (max_price - min_price) * 100).tolist()
            else:
                normalized = [50.0] * len(prices)

            sparklines[str(meta_id)] = [round(x, 1) for x in normalized]

    return {"sparklines": sparklines}


@router.get("/compare")
def get_compare_data(
    meta_ids: str = Query(..., description="Comma-separated meta_ids (max 5)"),
    period: str = Query("1y", description="Period: 1m, 3m, 6m, 1y, all"),
):
    """
    Get comparison data for multiple stocks.

    Args:
        meta_ids: Comma-separated list of meta_ids (max 5)
        period: Time period for comparison

    Returns:
        Normalized price series and metrics for each stock
    """
    try:
        meta_id_list = [int(x.strip()) for x in meta_ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid meta_ids format")

    if len(meta_id_list) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 stocks allowed for comparison")

    if not meta_id_list:
        return {"stocks": [], "normalized_prices": []}

    # Determine date range
    end_date = date.today()
    period_days = {
        "1m": 30,
        "3m": 90,
        "6m": 180,
        "1y": 365,
        "all": 365 * 5,
    }
    start_date = end_date - timedelta(days=period_days.get(period, 365))

    # Get meta info
    meta_df = datastore.meta_df()
    meta_info = meta_df[meta_df["meta_id"].isin(meta_id_list)]

    if meta_info.empty:
        return {"stocks": [], "normalized_prices": []}

    # Collect price data
    all_prices = {}

    for iso_code in meta_info["iso_code"].unique():
        iso_meta_ids = meta_info[meta_info["iso_code"] == iso_code]["meta_id"].tolist()

        price_df = datastore.read_price_data(
            iso_code=iso_code,
            meta_ids=iso_meta_ids,
            start_date=start_date,
            end_date=end_date,
        )

        if price_df.empty:
            continue

        for meta_id in iso_meta_ids:
            stock_prices = price_df[price_df["meta_id"] == meta_id].sort_values("trade_date")
            if not stock_prices.empty:
                all_prices[meta_id] = stock_prices

    # Build response
    stocks = []
    for meta_id in meta_id_list:
        meta_row = meta_info[meta_info["meta_id"] == meta_id]
        if meta_row.empty:
            continue

        stock_data = {
            "meta_id": int(meta_id),
            "ticker": meta_row.iloc[0]["ticker"],
            "name": meta_row.iloc[0]["name"],
            "sector": meta_row.iloc[0]["sector"],
            "iso_code": meta_row.iloc[0]["iso_code"],
        }

        if meta_id in all_prices:
            prices = all_prices[meta_id].set_index("trade_date")["adj_close"]
            metrics = _calculate_metrics(prices)
            stock_data["metrics"] = metrics
        else:
            stock_data["metrics"] = {
                "ytd_return": None,
                "return_1y": None,
                "return_3m": None,
                "volatility": None,
                "sharpe": None,
                "mdd": None,
            }

        stocks.append(stock_data)

    # Build normalized price series (base = 100)
    if all_prices:
        # Find common dates
        all_dates = set()
        for prices_df in all_prices.values():
            all_dates.update(prices_df["trade_date"].tolist())
        all_dates = sorted(all_dates)

        normalized_prices = []
        for trade_date in all_dates:
            point = {
                "date": (
                    trade_date.isoformat() if hasattr(trade_date, "isoformat") else str(trade_date)
                )
            }

            for meta_id, prices_df in all_prices.items():
                ticker = meta_info[meta_info["meta_id"] == meta_id].iloc[0]["ticker"]
                date_prices = prices_df[prices_df["trade_date"] == trade_date]

                if not date_prices.empty:
                    # Normalize to base 100
                    first_price = prices_df["adj_close"].iloc[0]
                    current_price = date_prices["adj_close"].iloc[0]
                    normalized = (current_price / first_price) * 100 if first_price > 0 else 100
                    point[ticker] = round(normalized, 2)

            normalized_prices.append(point)
    else:
        normalized_prices = []

    return {
        "stocks": stocks,
        "normalized_prices": normalized_prices,
    }


@router.get("/{meta_id}")
def get_price_history(
    meta_id: int,
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
):
    """
    Get price history for a single stock.

    Args:
        meta_id: Stock meta_id
        start_date: Optional start date filter
        end_date: Optional end date filter

    Returns:
        List of price records with trade_date, adj_close, gross_return
    """
    # Get meta info
    meta_df = datastore.meta_df()
    meta_row = meta_df[meta_df["meta_id"] == meta_id]

    if meta_row.empty:
        raise HTTPException(status_code=404, detail=f"Stock with meta_id {meta_id} not found")

    iso_code = meta_row.iloc[0]["iso_code"]

    # Default to 1 year of data
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=365)

    price_df = datastore.read_price_data(
        iso_code=iso_code,
        meta_ids=[meta_id],
        start_date=start_date,
        end_date=end_date,
    )

    if price_df.empty:
        return {"prices": [], "meta": meta_row.iloc[0].to_dict()}

    price_df = price_df.sort_values("trade_date")

    # Convert to records
    prices = []
    for _, row in price_df.iterrows():
        prices.append(
            {
                "trade_date": (
                    row["trade_date"].isoformat()
                    if hasattr(row["trade_date"], "isoformat")
                    else str(row["trade_date"])
                ),
                "adj_close": float(row["adj_close"]) if pd.notna(row["adj_close"]) else None,
                "gross_return": (
                    float(row["gross_return"]) if pd.notna(row.get("gross_return")) else None
                ),
            }
        )

    return {
        "prices": prices,
        "meta": {
            "meta_id": int(meta_row.iloc[0]["meta_id"]),
            "ticker": meta_row.iloc[0]["ticker"],
            "name": meta_row.iloc[0]["name"],
            "sector": meta_row.iloc[0]["sector"],
            "iso_code": iso_code,
            "marketcap": (
                int(meta_row.iloc[0]["marketcap"])
                if pd.notna(meta_row.iloc[0]["marketcap"])
                else None
            ),
        },
    }


def _build_summary(meta_id: int, meta_row: pd.Series) -> Dict:
    """Summary statistics payload for a single stock (shared by /price/{id}/summary and /stock/{id})."""
    iso_code = meta_row["iso_code"]

    # Get 1+ year of data for calculations
    end_date = date.today()
    start_date = end_date - timedelta(days=400)

    price_df = datastore.read_price_data(
        iso_code=iso_code,
        meta_ids=[meta_id],
        start_date=start_date,
        end_date=end_date,
    )

    extras = _kr_summary_extras(meta_row["ticker"]) if iso_code == "KR" else dict(_EMPTY_EXTRAS)

    if price_df.empty:
        return {
            "meta_id": meta_id,
            "ticker": meta_row["ticker"],
            "name": meta_row["name"],
            "metrics": {
                "ytd_return": None,
                "return_1y": None,
                "return_3m": None,
                "volatility": None,
                "sharpe": None,
                "mdd": None,
            },
            "latest_price": None,
            "latest_date": None,
            **extras,
        }

    price_df = price_df.sort_values("trade_date")
    prices = price_df.set_index("trade_date")["adj_close"]

    metrics = _calculate_metrics(prices)

    return {
        "meta_id": meta_id,
        "ticker": meta_row["ticker"],
        "name": meta_row["name"],
        "metrics": metrics,
        "latest_price": float(price_df["adj_close"].iloc[-1]),
        "latest_date": (
            price_df["trade_date"].iloc[-1].isoformat()
            if hasattr(price_df["trade_date"].iloc[-1], "isoformat")
            else str(price_df["trade_date"].iloc[-1])
        ),
        **extras,
    }


@router.get("/{meta_id}/summary")
def get_price_summary(meta_id: int):
    """
    Get summary statistics for a single stock.

    Args:
        meta_id: Stock meta_id

    Returns:
        Summary statistics including YTD, 1Y return, volatility, Sharpe, MDD
    """
    meta_df = datastore.meta_df()
    meta_row = meta_df[meta_df["meta_id"] == meta_id]

    if meta_row.empty:
        raise HTTPException(status_code=404, detail=f"Stock with meta_id {meta_id} not found")

    return _build_summary(meta_id, meta_row.iloc[0])


# ---------- /stock — 종목 상세 페이지 복합 엔드포인트 ----------

stock_router = APIRouter(prefix="/stock", tags=["Stock"])


@stock_router.get("/{meta_id}/fundamentals")
def get_stock_fundamentals(meta_id: int):
    """US 보통주의 현재 시점 SEC 연간 핵심 재무. KR/ETF는 기존 요약을 사용한다."""
    meta_df = datastore.meta_df()
    hit = meta_df[meta_df["meta_id"] == meta_id]
    if hit.empty:
        raise HTTPException(status_code=404, detail=f"Stock with meta_id {meta_id} not found")
    row = hit.iloc[0]
    if row["iso_code"] != "US":
        return {"available": False, "note": "KR 종목은 KRX PER·PBR·배당수익률을 제공합니다."}
    if str(row.get("security_type", "")).upper() == "ETF":
        return {"available": False, "note": "ETF에는 기업 재무제표를 적용하지 않습니다."}
    try:
        return _us_fundamentals(str(row["ticker"]))
    except (FileNotFoundError, KeyError):
        logger.debug("US fundamental 데이터 부재: %s", row["ticker"], exc_info=True)
        return {
            "available": False,
            "note": "SEC 또는 Massive 참조 데이터가 아직 발행되지 않았습니다.",
        }
    except Exception:
        logger.warning("US fundamental 조회 실패: %s", row["ticker"], exc_info=True)
        return {"available": False, "note": "재무 데이터를 불러오지 못했습니다."}


@stock_router.get("/{meta_id}")
def get_stock_detail(meta_id: int):
    """
    Composite payload for the stock detail page: meta + summary + watchlist flag.

    Price history and flows stay on their existing endpoints.
    """
    meta_df = datastore.meta_df()
    meta_rows = meta_df[meta_df["meta_id"] == meta_id]

    if meta_rows.empty:
        raise HTTPException(status_code=404, detail=f"Stock with meta_id {meta_id} not found")

    row = meta_rows.iloc[0]

    in_watchlist = False
    try:
        from datastore import watchlist as watchlist_store

        wl = watchlist_store.list_items()
        in_watchlist = bool((wl["meta_id"] == meta_id).any()) if not wl.empty else False
    except Exception:
        logger.debug(f"watchlist 조회 실패: {meta_id}")

    holding = None
    try:
        from datastore import holdings as holdings_store

        hd = holdings_store.list_items()
        hrow = hd[hd["meta_id"] == meta_id] if not hd.empty else hd
        if not hrow.empty:
            h = hrow.iloc[0]
            opened_at = h["opened_at"]
            holding = {
                "shares": float(h["shares"]) if pd.notna(h["shares"]) else None,
                "avg_cost": float(h["avg_cost"]) if pd.notna(h["avg_cost"]) else None,
                "currency": h["currency"] if pd.notna(h["currency"]) else None,
                "opened_at": opened_at.isoformat() if pd.notna(opened_at) else None,
                "note": h["note"] if pd.notna(h["note"]) else None,
            }
    except Exception:
        logger.debug(f"holdings 조회 실패: {meta_id}")

    def _na(v):
        try:
            return None if pd.isna(v) else v
        except (TypeError, ValueError):
            return v

    return {
        "meta": {
            "meta_id": int(row["meta_id"]),
            "ticker": row["ticker"],
            "name": row["name"],
            "sector": _na(row["sector"]),
            "iso_code": row["iso_code"],
            "security_type": _na(row["security_type"]),
            "marketcap": int(row["marketcap"]) if pd.notna(row["marketcap"]) else None,
        },
        "summary": _build_summary(meta_id, row),
        "in_watchlist": in_watchlist,
        "holding": holding,
    }
