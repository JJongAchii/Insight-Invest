"""
Stock Screener API Endpoints.

Provides:
- Scan stocks based on technical criteria
- Get detailed indicators for individual stocks
- Find 52-week highs and lows
"""

import logging
import os
import sys
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../../../")))

import db
from app import schemas
from module.backtest import Backtest
from module.screener import StockScreener
from module.screener.screener import ScreenerCriteria, SortField

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/screener", tags=["Screener"])


def _get_meta_info(
    iso_code: Optional[str] = None,
) -> Tuple[List[int], Dict[str, int], Dict[str, Dict]]:
    """
    Get meta information from database.

    Returns:
        Tuple of (meta_ids, ticker_to_meta_id, ticker_info)
    """
    with db.session_local() as session:
        stmt = select(
            db.TbMeta.meta_id,
            db.TbMeta.ticker,
            db.TbMeta.name,
            db.TbMeta.sector,
            db.TbMeta.iso_code,
        )
        if iso_code:
            stmt = stmt.where(db.TbMeta.iso_code == iso_code)

        results = session.execute(stmt).all()

    meta_ids = [r.meta_id for r in results]
    ticker_meta = {r.ticker: r.meta_id for r in results}
    ticker_info = {
        r.ticker: {
            "name": r.name or "",
            "sector": r.sector or "",
            "iso_code": r.iso_code,
        }
        for r in results
    }

    return meta_ids, ticker_meta, ticker_info


def _build_criteria(request: schemas.ScreenerRequest) -> Optional[ScreenerCriteria]:
    """Build screening criteria from request."""
    # Check if any filters are set
    has_filters = any(
        [
            request.return_1m_min is not None or request.return_1m_max is not None,
            request.return_3m_min is not None or request.return_3m_max is not None,
            request.return_6m_min is not None or request.return_6m_max is not None,
            request.return_12m_min is not None or request.return_12m_max is not None,
            request.volatility_min is not None or request.volatility_max is not None,
            request.mdd_max is not None,
            request.current_drawdown_max is not None,
            request.pct_from_high_min is not None or request.pct_from_high_max is not None,
        ]
    )

    if not has_filters:
        return None

    def make_range(
        min_val: Optional[float], max_val: Optional[float]
    ) -> Optional[Tuple[float, float]]:
        if min_val is None and max_val is None:
            return None
        return (
            min_val if min_val is not None else -float("inf"),
            max_val if max_val is not None else float("inf"),
        )

    return ScreenerCriteria(
        return_1m_range=make_range(request.return_1m_min, request.return_1m_max),
        return_3m_range=make_range(request.return_3m_min, request.return_3m_max),
        return_6m_range=make_range(request.return_6m_min, request.return_6m_max),
        return_12m_range=make_range(request.return_12m_min, request.return_12m_max),
        volatility_range=make_range(request.volatility_min, request.volatility_max),
        mdd_max=request.mdd_max,
        current_drawdown_max=request.current_drawdown_max,
        pct_from_high_range=make_range(request.pct_from_high_min, request.pct_from_high_max),
    )


@router.post("/scan", response_model=schemas.ScreenerResponse)
async def scan_stocks(request: schemas.ScreenerRequest):
    """
    Scan stocks based on technical criteria.

    Returns filtered and sorted list of stocks with their indicators.
    Also returns lists of stocks near 52-week highs and lows.

    Note: iso_code is required to prevent timeout from processing too many stocks.
    """
    # Require iso_code to prevent timeout
    if not request.iso_code:
        raise HTTPException(
            status_code=400,
            detail="iso_code is required. Please select a country (US or KR).",
        )

    logger.info(
        f"Screener request: iso_code={request.iso_code}, "
        f"sort_by={request.sort_by}, limit={request.limit}"
    )

    try:
        # Get meta info
        meta_ids, ticker_meta, ticker_info = _get_meta_info(request.iso_code)

        if not meta_ids:
            raise HTTPException(status_code=404, detail="No stocks found for given criteria")

        # Fetch price data (1 year lookback)
        bt = Backtest()
        price_df = bt.data(meta_id=meta_ids)

        if price_df.empty:
            raise HTTPException(status_code=404, detail="No price data available")

        # Create screener
        screener = StockScreener(price_df, ticker_meta, ticker_info)

        # Build criteria
        criteria = _build_criteria(request)

        # Map sort field
        sort_field = SortField(request.sort_by.value)

        # Run screening
        result = screener.screen(
            criteria=criteria,
            sort_by=sort_field,
            ascending=request.ascending,
            limit=request.limit,
        )

        logger.info(
            f"Screener completed: {result.total_count} total, " f"{result.filtered_count} filtered"
        )

        return schemas.ScreenerResponse(
            total_count=result.total_count,
            filtered_count=result.filtered_count,
            results=[schemas.ScreenerStock(**r) for r in result.results],
            new_highs=[schemas.ScreenerStock(**r) for r in result.new_highs],
            new_lows=[schemas.ScreenerStock(**r) for r in result.new_lows],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Screener failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Screening failed: {str(e)}")


@router.get("/indicators/{meta_id}", response_model=schemas.ScreenerStock)
async def get_stock_indicators(meta_id: int):
    """
    Get detailed technical indicators for a single stock.
    """
    logger.info(f"Getting indicators for meta_id={meta_id}")

    try:
        # Get ticker info
        with db.session_local() as session:
            stmt = select(
                db.TbMeta.meta_id,
                db.TbMeta.ticker,
                db.TbMeta.name,
                db.TbMeta.sector,
                db.TbMeta.iso_code,
            ).where(db.TbMeta.meta_id == meta_id)

            result = session.execute(stmt).first()

        if not result:
            raise HTTPException(status_code=404, detail=f"Stock with meta_id={meta_id} not found")

        ticker_meta = {result.ticker: result.meta_id}
        ticker_info = {
            result.ticker: {
                "name": result.name or "",
                "sector": result.sector or "",
                "iso_code": result.iso_code,
            }
        }

        # Fetch price data
        bt = Backtest()
        price_df = bt.data(meta_id=[meta_id])

        if price_df.empty:
            raise HTTPException(status_code=404, detail="No price data available for this stock")

        # Calculate indicators
        screener = StockScreener(price_df, ticker_meta, ticker_info)
        indicators = screener.get_ticker_indicators(result.ticker)

        if not indicators:
            raise HTTPException(status_code=404, detail="Could not calculate indicators")

        return schemas.ScreenerStock(**indicators)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get indicators failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get indicators: {str(e)}")


@router.get("/highs-lows")
async def get_highs_and_lows(
    iso_code: Optional[str] = Query(None, description="Filter by country (US, KR)"),
    threshold: float = Query(5.0, ge=0, le=20, description="% threshold from high/low"),
):
    """
    Get stocks near 52-week highs and lows.

    Args:
        iso_code: Filter by country
        threshold: How close to high/low (default 5%)
    """
    logger.info(f"Getting highs/lows: iso_code={iso_code}, threshold={threshold}%")

    try:
        # Get meta info
        meta_ids, ticker_meta, ticker_info = _get_meta_info(iso_code)

        if not meta_ids:
            raise HTTPException(status_code=404, detail="No stocks found")

        # Fetch price data
        bt = Backtest()
        price_df = bt.data(meta_id=meta_ids)

        if price_df.empty:
            raise HTTPException(status_code=404, detail="No price data available")

        # Create screener and get results
        screener = StockScreener(price_df, ticker_meta, ticker_info)
        result = screener.screen(criteria=None, limit=500)

        # Filter by threshold
        threshold_decimal = threshold / 100
        new_highs = [r for r in result.new_highs if r["pct_from_high"] >= -threshold]
        new_lows = [r for r in result.new_lows if r["pct_from_low"] <= threshold]

        return {
            "new_highs": [schemas.ScreenerStock(**r) for r in new_highs],
            "new_lows": [schemas.ScreenerStock(**r) for r in new_lows],
            "threshold_pct": threshold,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get highs/lows failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get highs/lows: {str(e)}")
