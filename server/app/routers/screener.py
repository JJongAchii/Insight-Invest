"""
Stock Screener API Endpoints.

Provides:
- Scan stocks based on technical criteria (using pre-calculated indicators)
- Get detailed indicators for individual stocks
- Find 52-week highs and lows
"""

import logging
import os
import sys
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import and_, select

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../../../")))

import db
from app import schemas
from module.backtest import Backtest
from module.screener import StockScreener

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/screener", tags=["Screener"])


def _query_indicators(
    iso_code: str,
    criteria: Optional[schemas.ScreenerRequest] = None,
    sort_by: str = "return_3m",
    ascending: bool = False,
    limit: int = 100,
) -> Tuple[int, List[Dict]]:
    """
    Query pre-calculated indicators from database.

    Args:
        iso_code: Country code (US, KR)
        criteria: Filter criteria
        sort_by: Field to sort by
        ascending: Sort order
        limit: Maximum results to return

    Returns:
        Tuple of (total_count, results)
    """
    with db.session_local() as session:
        # Build base query with join to TbMeta
        stmt = (
            select(
                db.TbScreenerIndicators,
                db.TbMeta.ticker,
                db.TbMeta.name,
                db.TbMeta.sector,
                db.TbMeta.iso_code,
            )
            .join(db.TbMeta, db.TbScreenerIndicators.meta_id == db.TbMeta.meta_id)
            .where(db.TbMeta.iso_code == iso_code)
        )

        # Apply filters if criteria provided
        if criteria:
            filters = []

            # Momentum filters (values in DB are decimals, criteria are percentages)
            if criteria.return_1m_min is not None:
                filters.append(db.TbScreenerIndicators.return_1m >= criteria.return_1m_min / 100)
            if criteria.return_1m_max is not None:
                filters.append(db.TbScreenerIndicators.return_1m <= criteria.return_1m_max / 100)

            if criteria.return_3m_min is not None:
                filters.append(db.TbScreenerIndicators.return_3m >= criteria.return_3m_min / 100)
            if criteria.return_3m_max is not None:
                filters.append(db.TbScreenerIndicators.return_3m <= criteria.return_3m_max / 100)

            if criteria.return_6m_min is not None:
                filters.append(db.TbScreenerIndicators.return_6m >= criteria.return_6m_min / 100)
            if criteria.return_6m_max is not None:
                filters.append(db.TbScreenerIndicators.return_6m <= criteria.return_6m_max / 100)

            if criteria.return_12m_min is not None:
                filters.append(db.TbScreenerIndicators.return_12m >= criteria.return_12m_min / 100)
            if criteria.return_12m_max is not None:
                filters.append(db.TbScreenerIndicators.return_12m <= criteria.return_12m_max / 100)

            # Volatility filter
            if criteria.volatility_min is not None:
                filters.append(
                    db.TbScreenerIndicators.volatility_3m >= criteria.volatility_min / 100
                )
            if criteria.volatility_max is not None:
                filters.append(
                    db.TbScreenerIndicators.volatility_3m <= criteria.volatility_max / 100
                )

            # MDD filter (MDD is negative, so >= means less severe)
            if criteria.mdd_max is not None:
                filters.append(db.TbScreenerIndicators.mdd_1y >= criteria.mdd_max / 100)

            # Current drawdown filter
            if criteria.current_drawdown_max is not None:
                filters.append(
                    db.TbScreenerIndicators.current_drawdown >= criteria.current_drawdown_max / 100
                )

            # 52-week filters
            if criteria.pct_from_high_min is not None:
                filters.append(
                    db.TbScreenerIndicators.pct_from_high >= criteria.pct_from_high_min / 100
                )
            if criteria.pct_from_high_max is not None:
                filters.append(
                    db.TbScreenerIndicators.pct_from_high <= criteria.pct_from_high_max / 100
                )

            if filters:
                stmt = stmt.where(and_(*filters))

        # Get total count (before limit)
        count_stmt = (
            select(db.TbScreenerIndicators.meta_id)
            .join(db.TbMeta, db.TbScreenerIndicators.meta_id == db.TbMeta.meta_id)
            .where(db.TbMeta.iso_code == iso_code)
        )
        total_count = len(session.execute(count_stmt).all())

        # Apply sorting
        sort_column = getattr(db.TbScreenerIndicators, sort_by, None)
        if sort_column is not None:
            if ascending:
                stmt = stmt.order_by(sort_column.asc().nulls_last())
            else:
                stmt = stmt.order_by(sort_column.desc().nulls_last())

        # Apply limit
        stmt = stmt.limit(limit)

        # Execute query
        rows = session.execute(stmt).all()

        # Format results
        results = []
        for row in rows:
            ind = row[0]  # TbScreenerIndicators
            results.append(
                {
                    "ticker": row.ticker,
                    "meta_id": ind.meta_id,
                    "name": row.name or "",
                    "sector": row.sector or "",
                    "iso_code": row.iso_code,
                    "current_price": round(ind.current_price, 2) if ind.current_price else 0,
                    "return_1m": round(ind.return_1m * 100, 2) if ind.return_1m else 0,
                    "return_3m": round(ind.return_3m * 100, 2) if ind.return_3m else 0,
                    "return_6m": round(ind.return_6m * 100, 2) if ind.return_6m else 0,
                    "return_12m": round(ind.return_12m * 100, 2) if ind.return_12m else 0,
                    "return_ytd": round(ind.return_ytd * 100, 2) if ind.return_ytd else 0,
                    "volatility_1m": round(ind.volatility_1m * 100, 2) if ind.volatility_1m else 0,
                    "volatility_3m": round(ind.volatility_3m * 100, 2) if ind.volatility_3m else 0,
                    "mdd": round(ind.mdd * 100, 2) if ind.mdd else 0,
                    "mdd_1y": round(ind.mdd_1y * 100, 2) if ind.mdd_1y else 0,
                    "current_drawdown": (
                        round(ind.current_drawdown * 100, 2) if ind.current_drawdown else 0
                    ),
                    "high_52w": round(ind.high_52w, 2) if ind.high_52w else 0,
                    "low_52w": round(ind.low_52w, 2) if ind.low_52w else 0,
                    "pct_from_high": round(ind.pct_from_high * 100, 2) if ind.pct_from_high else 0,
                    "pct_from_low": round(ind.pct_from_low * 100, 2) if ind.pct_from_low else 0,
                }
            )

        return total_count, results


def _query_highs_lows(iso_code: str, threshold: float = 5.0) -> Tuple[List[Dict], List[Dict]]:
    """
    Query stocks near 52-week highs and lows.

    Args:
        iso_code: Country code
        threshold: % threshold from high/low

    Returns:
        Tuple of (new_highs, new_lows)
    """
    threshold_decimal = threshold / 100

    with db.session_local() as session:
        # Query for highs (pct_from_high >= -threshold)
        highs_stmt = (
            select(
                db.TbScreenerIndicators,
                db.TbMeta.ticker,
                db.TbMeta.name,
                db.TbMeta.sector,
                db.TbMeta.iso_code,
            )
            .join(db.TbMeta, db.TbScreenerIndicators.meta_id == db.TbMeta.meta_id)
            .where(
                and_(
                    db.TbMeta.iso_code == iso_code,
                    db.TbScreenerIndicators.pct_from_high >= -threshold_decimal,
                    db.TbScreenerIndicators.pct_from_high.isnot(None),
                )
            )
            .order_by(db.TbScreenerIndicators.pct_from_high.desc())
            .limit(50)
        )

        # Query for lows (pct_from_low <= threshold)
        lows_stmt = (
            select(
                db.TbScreenerIndicators,
                db.TbMeta.ticker,
                db.TbMeta.name,
                db.TbMeta.sector,
                db.TbMeta.iso_code,
            )
            .join(db.TbMeta, db.TbScreenerIndicators.meta_id == db.TbMeta.meta_id)
            .where(
                and_(
                    db.TbMeta.iso_code == iso_code,
                    db.TbScreenerIndicators.pct_from_low <= threshold_decimal,
                    db.TbScreenerIndicators.pct_from_low.isnot(None),
                )
            )
            .order_by(db.TbScreenerIndicators.pct_from_low.asc())
            .limit(50)
        )

        def format_row(row):
            ind = row[0]
            return {
                "ticker": row.ticker,
                "meta_id": ind.meta_id,
                "name": row.name or "",
                "sector": row.sector or "",
                "iso_code": row.iso_code,
                "current_price": round(ind.current_price, 2) if ind.current_price else 0,
                "return_1m": round(ind.return_1m * 100, 2) if ind.return_1m else 0,
                "return_3m": round(ind.return_3m * 100, 2) if ind.return_3m else 0,
                "return_6m": round(ind.return_6m * 100, 2) if ind.return_6m else 0,
                "return_12m": round(ind.return_12m * 100, 2) if ind.return_12m else 0,
                "return_ytd": round(ind.return_ytd * 100, 2) if ind.return_ytd else 0,
                "volatility_1m": round(ind.volatility_1m * 100, 2) if ind.volatility_1m else 0,
                "volatility_3m": round(ind.volatility_3m * 100, 2) if ind.volatility_3m else 0,
                "mdd": round(ind.mdd * 100, 2) if ind.mdd else 0,
                "mdd_1y": round(ind.mdd_1y * 100, 2) if ind.mdd_1y else 0,
                "current_drawdown": (
                    round(ind.current_drawdown * 100, 2) if ind.current_drawdown else 0
                ),
                "high_52w": round(ind.high_52w, 2) if ind.high_52w else 0,
                "low_52w": round(ind.low_52w, 2) if ind.low_52w else 0,
                "pct_from_high": round(ind.pct_from_high * 100, 2) if ind.pct_from_high else 0,
                "pct_from_low": round(ind.pct_from_low * 100, 2) if ind.pct_from_low else 0,
            }

        highs = [format_row(row) for row in session.execute(highs_stmt).all()]
        lows = [format_row(row) for row in session.execute(lows_stmt).all()]

        return highs, lows


@router.post("/scan", response_model=schemas.ScreenerResponse)
async def scan_stocks(request: schemas.ScreenerRequest):
    """
    Scan stocks based on technical criteria.

    Uses pre-calculated indicators stored in database for instant response.
    Indicators are updated daily after market close.

    Note:
        - iso_code is required
        - Returns all stocks matching criteria (no market cap limit)
    """
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
        # Query from pre-calculated table
        total_count, results = _query_indicators(
            iso_code=request.iso_code,
            criteria=request,
            sort_by=request.sort_by.value,
            ascending=request.ascending,
            limit=request.limit,
        )

        # Get highs and lows
        new_highs, new_lows = _query_highs_lows(request.iso_code)

        logger.info(
            f"Screener completed: {total_count} total, {len(results)} returned, "
            f"{len(new_highs)} near highs, {len(new_lows)} near lows"
        )

        return schemas.ScreenerResponse(
            total_count=total_count,
            filtered_count=len(results),
            results=[schemas.ScreenerStock(**r) for r in results],
            new_highs=[schemas.ScreenerStock(**r) for r in new_highs[:20]],
            new_lows=[schemas.ScreenerStock(**r) for r in new_lows[:20]],
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

    Note: This endpoint calculates indicators in real-time for the latest data.
    """
    logger.info(f"Getting indicators for meta_id={meta_id}")

    try:
        # First try to get from pre-calculated table
        with db.session_local() as session:
            stmt = (
                select(
                    db.TbScreenerIndicators,
                    db.TbMeta.ticker,
                    db.TbMeta.name,
                    db.TbMeta.sector,
                    db.TbMeta.iso_code,
                )
                .join(db.TbMeta, db.TbScreenerIndicators.meta_id == db.TbMeta.meta_id)
                .where(db.TbScreenerIndicators.meta_id == meta_id)
            )
            row = session.execute(stmt).first()

        if row:
            ind = row[0]
            return schemas.ScreenerStock(
                ticker=row.ticker,
                meta_id=ind.meta_id,
                name=row.name or "",
                sector=row.sector or "",
                iso_code=row.iso_code,
                current_price=round(ind.current_price, 2) if ind.current_price else 0,
                return_1m=round(ind.return_1m * 100, 2) if ind.return_1m else 0,
                return_3m=round(ind.return_3m * 100, 2) if ind.return_3m else 0,
                return_6m=round(ind.return_6m * 100, 2) if ind.return_6m else 0,
                return_12m=round(ind.return_12m * 100, 2) if ind.return_12m else 0,
                return_ytd=round(ind.return_ytd * 100, 2) if ind.return_ytd else 0,
                volatility_1m=round(ind.volatility_1m * 100, 2) if ind.volatility_1m else 0,
                volatility_3m=round(ind.volatility_3m * 100, 2) if ind.volatility_3m else 0,
                mdd=round(ind.mdd * 100, 2) if ind.mdd else 0,
                mdd_1y=round(ind.mdd_1y * 100, 2) if ind.mdd_1y else 0,
                current_drawdown=(
                    round(ind.current_drawdown * 100, 2) if ind.current_drawdown else 0
                ),
                high_52w=round(ind.high_52w, 2) if ind.high_52w else 0,
                low_52w=round(ind.low_52w, 2) if ind.low_52w else 0,
                pct_from_high=round(ind.pct_from_high * 100, 2) if ind.pct_from_high else 0,
                pct_from_low=round(ind.pct_from_low * 100, 2) if ind.pct_from_low else 0,
            )

        # Fallback to real-time calculation if not in pre-calculated table
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

        bt = Backtest()
        price_df = bt.data(meta_id=[meta_id])

        if price_df.empty:
            raise HTTPException(status_code=404, detail="No price data available for this stock")

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
    iso_code: str = Query(..., description="Filter by country (US, KR) - required"),
    threshold: float = Query(5.0, ge=0, le=20, description="% threshold from high/low"),
):
    """
    Get stocks near 52-week highs and lows.

    Uses pre-calculated indicators for instant response.

    Args:
        iso_code: Filter by country (required)
        threshold: How close to high/low (default 5%)
    """
    logger.info(f"Getting highs/lows: iso_code={iso_code}, threshold={threshold}%")

    try:
        new_highs, new_lows = _query_highs_lows(iso_code, threshold)

        logger.info(f"Found {len(new_highs)} near highs, {len(new_lows)} near lows")

        return {
            "new_highs": [schemas.ScreenerStock(**r) for r in new_highs],
            "new_lows": [schemas.ScreenerStock(**r) for r in new_lows],
            "threshold_pct": threshold,
        }

    except Exception as e:
        logger.error(f"Get highs/lows failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get highs/lows: {str(e)}")


@router.get("/stats")
async def get_screener_stats():
    """
    Get screener statistics (total stocks, last update time).
    """
    try:
        with db.session_local() as session:
            # Count by country
            stmt = select(db.TbMeta.iso_code, db.TbScreenerIndicators.calculated_date).join(
                db.TbMeta, db.TbScreenerIndicators.meta_id == db.TbMeta.meta_id
            )
            rows = session.execute(stmt).all()

        if not rows:
            return {
                "total_stocks": 0,
                "by_country": {},
                "last_updated": None,
                "message": "No pre-calculated data available. Run the calculation job first.",
            }

        by_country: Dict[str, int] = {}
        last_date = None
        for row in rows:
            by_country[row.iso_code] = by_country.get(row.iso_code, 0) + 1
            if last_date is None or row.calculated_date > last_date:
                last_date = row.calculated_date

        return {
            "total_stocks": len(rows),
            "by_country": by_country,
            "last_updated": last_date.isoformat() if last_date else None,
        }

    except Exception as e:
        logger.error(f"Get stats failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")
