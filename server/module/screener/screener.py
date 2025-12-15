"""
Stock Screener Logic.

Filters and ranks stocks based on technical criteria.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .indicators import IndicatorResult, TechnicalIndicators

logger = logging.getLogger(__name__)


class SortField(str, Enum):
    """Fields available for sorting."""

    RETURN_1M = "return_1m"
    RETURN_3M = "return_3m"
    RETURN_6M = "return_6m"
    RETURN_12M = "return_12m"
    RETURN_YTD = "return_ytd"
    VOLATILITY_1M = "volatility_1m"
    VOLATILITY_3M = "volatility_3m"
    MDD = "mdd"
    MDD_1Y = "mdd_1y"
    CURRENT_DRAWDOWN = "current_drawdown"
    PCT_FROM_HIGH = "pct_from_high"
    PCT_FROM_LOW = "pct_from_low"


@dataclass
class ScreenerCriteria:
    """
    Screening criteria for filtering stocks.

    All criteria are optional. If None, no filter is applied.
    Ranges are inclusive: (min_value, max_value)
    """

    # Momentum filters (in percentage, e.g., 10.0 means 10%)
    return_1m_range: Optional[Tuple[float, float]] = None
    return_3m_range: Optional[Tuple[float, float]] = None
    return_6m_range: Optional[Tuple[float, float]] = None
    return_12m_range: Optional[Tuple[float, float]] = None

    # Volatility filters (in percentage)
    volatility_range: Optional[Tuple[float, float]] = None

    # Drawdown filters (in percentage, negative values)
    mdd_max: Optional[float] = None  # Max allowed MDD (e.g., -30 means no worse than -30%)
    current_drawdown_max: Optional[float] = None

    # 52-week filters (in percentage)
    pct_from_high_range: Optional[Tuple[float, float]] = None  # e.g., (-10, 0) = within 10% of high
    pct_from_low_min: Optional[float] = None  # Min % above 52-week low


@dataclass
class ScreenerResult:
    """Result of screening operation."""

    total_count: int
    filtered_count: int
    results: List[Dict]
    new_highs: List[Dict]  # Stocks near 52-week high
    new_lows: List[Dict]  # Stocks near 52-week low


class StockScreener:
    """
    Screen and rank stocks based on technical indicators.

    Example:
        >>> screener = StockScreener(price_df, ticker_meta)
        >>> criteria = ScreenerCriteria(return_3m_range=(0, 100))
        >>> results = screener.screen(criteria, sort_by=SortField.RETURN_3M)
    """

    def __init__(
        self,
        price_df: pd.DataFrame,
        ticker_meta: Dict[str, int],
        ticker_info: Optional[Dict[str, Dict]] = None,
    ):
        """
        Initialize screener.

        Args:
            price_df: DataFrame with date index and ticker columns
            ticker_meta: Dict mapping ticker to meta_id
            ticker_info: Optional dict with additional ticker info (name, sector, etc.)
        """
        self.indicators = TechnicalIndicators(price_df, ticker_meta)
        self.ticker_info = ticker_info or {}
        self._indicator_results: Optional[List[IndicatorResult]] = None

    def _get_indicators(self) -> List[IndicatorResult]:
        """Get or calculate indicators (cached)."""
        if self._indicator_results is None:
            self._indicator_results = self.indicators.calculate_all()
        return self._indicator_results

    def _passes_filter(self, result: IndicatorResult, criteria: ScreenerCriteria) -> bool:
        """Check if a result passes all filter criteria."""
        # Momentum filters
        if criteria.return_1m_range:
            val = result.return_1m * 100
            if pd.isna(val) or not (
                criteria.return_1m_range[0] <= val <= criteria.return_1m_range[1]
            ):
                return False

        if criteria.return_3m_range:
            val = result.return_3m * 100
            if pd.isna(val) or not (
                criteria.return_3m_range[0] <= val <= criteria.return_3m_range[1]
            ):
                return False

        if criteria.return_6m_range:
            val = result.return_6m * 100
            if pd.isna(val) or not (
                criteria.return_6m_range[0] <= val <= criteria.return_6m_range[1]
            ):
                return False

        if criteria.return_12m_range:
            val = result.return_12m * 100
            if pd.isna(val) or not (
                criteria.return_12m_range[0] <= val <= criteria.return_12m_range[1]
            ):
                return False

        # Volatility filter
        if criteria.volatility_range:
            val = result.volatility_3m * 100
            if pd.isna(val) or not (
                criteria.volatility_range[0] <= val <= criteria.volatility_range[1]
            ):
                return False

        # MDD filter
        if criteria.mdd_max is not None:
            val = result.mdd_1y * 100
            if pd.isna(val) or val < criteria.mdd_max:  # MDD is negative
                return False

        # Current drawdown filter
        if criteria.current_drawdown_max is not None:
            val = result.current_drawdown * 100
            if pd.isna(val) or val < criteria.current_drawdown_max:
                return False

        # 52-week high filter
        if criteria.pct_from_high_range:
            val = result.pct_from_high * 100
            if pd.isna(val) or not (
                criteria.pct_from_high_range[0] <= val <= criteria.pct_from_high_range[1]
            ):
                return False

        # 52-week low filter
        if criteria.pct_from_low_min is not None:
            val = result.pct_from_low * 100
            if pd.isna(val) or val < criteria.pct_from_low_min:
                return False

        return True

    def _enrich_result(self, result: IndicatorResult) -> Dict:
        """Enrich indicator result with additional info."""
        data = result.to_dict()

        # Add ticker info if available
        info = self.ticker_info.get(result.ticker, {})
        data["name"] = info.get("name", "")
        data["sector"] = info.get("sector", "")
        data["iso_code"] = info.get("iso_code", "")

        return data

    def screen(
        self,
        criteria: Optional[ScreenerCriteria] = None,
        sort_by: SortField = SortField.RETURN_3M,
        ascending: bool = False,
        limit: int = 100,
    ) -> ScreenerResult:
        """
        Screen stocks based on criteria.

        Args:
            criteria: Filtering criteria (None = no filter)
            sort_by: Field to sort by
            ascending: Sort order (False = descending, high to low)
            limit: Maximum number of results

        Returns:
            ScreenerResult with filtered and sorted stocks
        """
        all_results = self._get_indicators()
        total_count = len(all_results)

        # Apply filters
        if criteria:
            filtered = [r for r in all_results if self._passes_filter(r, criteria)]
        else:
            filtered = all_results

        # Sort
        sort_attr = sort_by.value
        filtered.sort(
            key=lambda x: (
                getattr(x, sort_attr)
                if not pd.isna(getattr(x, sort_attr))
                else (float("-inf") if not ascending else float("inf"))
            ),
            reverse=not ascending,
        )

        # Limit
        filtered = filtered[:limit]

        # Enrich results
        enriched = [self._enrich_result(r) for r in filtered]

        # Find new highs (within 5% of 52-week high)
        new_highs = [
            self._enrich_result(r)
            for r in all_results
            if not pd.isna(r.pct_from_high) and r.pct_from_high >= -0.05
        ]
        new_highs.sort(key=lambda x: x["pct_from_high"], reverse=True)

        # Find new lows (within 5% of 52-week low)
        new_lows = [
            self._enrich_result(r)
            for r in all_results
            if not pd.isna(r.pct_from_low) and r.pct_from_low <= 0.05
        ]
        new_lows.sort(key=lambda x: x["pct_from_low"])

        logger.info(
            f"Screened {total_count} stocks: {len(enriched)} passed filters, "
            f"{len(new_highs)} near highs, {len(new_lows)} near lows"
        )

        return ScreenerResult(
            total_count=total_count,
            filtered_count=len(enriched),
            results=enriched,
            new_highs=new_highs[:20],
            new_lows=new_lows[:20],
        )

    def get_ticker_indicators(self, ticker: str) -> Optional[Dict]:
        """Get detailed indicators for a single ticker."""
        result = self.indicators.calculate_for_ticker(ticker)
        if result:
            return self._enrich_result(result)
        return None
