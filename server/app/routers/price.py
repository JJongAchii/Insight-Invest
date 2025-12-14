"""
Price data router for stock search features.

Provides endpoints for:
- Price history for individual stocks
- Summary statistics (YTD, 1Y return, volatility, etc.)
- Sparkline data for table view
- Comparison data for multiple stocks
"""

import logging
from datetime import date, timedelta
from typing import Dict, List, Optional

import db
import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from module.data_lake.iceberg_client import iceberg_client

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

    prices = prices.sort_index()
    returns = prices.pct_change().dropna()

    # Calculate returns
    latest_price = prices.iloc[-1]
    today = prices.index[-1]

    # YTD return
    ytd_start = date(today.year, 1, 1)
    ytd_prices = prices[prices.index >= pd.Timestamp(ytd_start)]
    ytd_return = (latest_price / ytd_prices.iloc[0] - 1) if len(ytd_prices) > 0 else None

    # 1Y return
    one_year_ago = today - timedelta(days=365)
    year_prices = prices[prices.index >= pd.Timestamp(one_year_ago)]
    return_1y = (latest_price / year_prices.iloc[0] - 1) if len(year_prices) > 0 else None

    # 3M return
    three_months_ago = today - timedelta(days=90)
    three_month_prices = prices[prices.index >= pd.Timestamp(three_months_ago)]
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
    meta_df = db.TbMeta.query_df()
    meta_info = meta_df[meta_df["meta_id"].isin(meta_id_list)][["meta_id", "iso_code"]]

    if meta_info.empty:
        return {"sparklines": {}}

    # Fetch price data (last 30 days)
    end_date = date.today()
    start_date = end_date - timedelta(days=45)  # Extra days to ensure 30 trading days

    sparklines = {}

    for iso_code in meta_info["iso_code"].unique():
        iso_meta_ids = meta_info[meta_info["iso_code"] == iso_code]["meta_id"].tolist()

        price_df = iceberg_client.read_price_data(
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
    meta_df = db.TbMeta.query_df()
    meta_row = meta_df[meta_df["meta_id"] == meta_id]

    if meta_row.empty:
        raise HTTPException(status_code=404, detail=f"Stock with meta_id {meta_id} not found")

    iso_code = meta_row.iloc[0]["iso_code"]

    # Default to 1 year of data
    if end_date is None:
        end_date = date.today()
    if start_date is None:
        start_date = end_date - timedelta(days=365)

    price_df = iceberg_client.read_price_data(
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


@router.get("/{meta_id}/summary")
def get_price_summary(meta_id: int):
    """
    Get summary statistics for a single stock.

    Args:
        meta_id: Stock meta_id

    Returns:
        Summary statistics including YTD, 1Y return, volatility, Sharpe, MDD
    """
    # Get meta info
    meta_df = db.TbMeta.query_df()
    meta_row = meta_df[meta_df["meta_id"] == meta_id]

    if meta_row.empty:
        raise HTTPException(status_code=404, detail=f"Stock with meta_id {meta_id} not found")

    iso_code = meta_row.iloc[0]["iso_code"]

    # Get 1+ year of data for calculations
    end_date = date.today()
    start_date = end_date - timedelta(days=400)

    price_df = iceberg_client.read_price_data(
        iso_code=iso_code,
        meta_ids=[meta_id],
        start_date=start_date,
        end_date=end_date,
    )

    if price_df.empty:
        return {
            "meta_id": meta_id,
            "ticker": meta_row.iloc[0]["ticker"],
            "name": meta_row.iloc[0]["name"],
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
        }

    price_df = price_df.sort_values("trade_date")
    prices = price_df.set_index("trade_date")["adj_close"]

    metrics = _calculate_metrics(prices)

    return {
        "meta_id": meta_id,
        "ticker": meta_row.iloc[0]["ticker"],
        "name": meta_row.iloc[0]["name"],
        "metrics": metrics,
        "latest_price": float(price_df["adj_close"].iloc[-1]),
        "latest_date": (
            price_df["trade_date"].iloc[-1].isoformat()
            if hasattr(price_df["trade_date"].iloc[-1], "isoformat")
            else str(price_df["trade_date"].iloc[-1])
        ),
    }


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
    meta_df = db.TbMeta.query_df()
    meta_info = meta_df[meta_df["meta_id"].isin(meta_id_list)]

    if meta_info.empty:
        return {"stocks": [], "normalized_prices": []}

    # Collect price data
    all_prices = {}

    for iso_code in meta_info["iso_code"].unique():
        iso_meta_ids = meta_info[meta_info["iso_code"] == iso_code]["meta_id"].tolist()

        price_df = iceberg_client.read_price_data(
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
