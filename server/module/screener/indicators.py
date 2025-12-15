"""
Technical Indicators for Stock Screening.

Calculates various technical indicators for screening and ranking stocks:
- Momentum indicators (returns over different periods)
- Volatility measures
- Drawdown analysis
- Price relative to 52-week high/low
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class IndicatorResult:
    """Result of indicator calculation for a single ticker."""

    ticker: str
    meta_id: int
    # Price info
    current_price: float
    # Momentum
    return_1m: float  # 1-month return
    return_3m: float  # 3-month return
    return_6m: float  # 6-month return
    return_12m: float  # 12-month return
    return_ytd: float  # Year-to-date return
    # Volatility
    volatility_1m: float  # 1-month annualized volatility
    volatility_3m: float  # 3-month annualized volatility
    # Drawdown
    mdd: float  # Maximum drawdown (all-time)
    mdd_1y: float  # Maximum drawdown (1-year)
    current_drawdown: float  # Current drawdown from peak
    # 52-week analysis
    high_52w: float  # 52-week high price
    low_52w: float  # 52-week low price
    pct_from_high: float  # % from 52-week high (negative)
    pct_from_low: float  # % from 52-week low (positive)

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "ticker": self.ticker,
            "meta_id": self.meta_id,
            "current_price": round(self.current_price, 2),
            "return_1m": round(self.return_1m * 100, 2),
            "return_3m": round(self.return_3m * 100, 2),
            "return_6m": round(self.return_6m * 100, 2),
            "return_12m": round(self.return_12m * 100, 2),
            "return_ytd": round(self.return_ytd * 100, 2),
            "volatility_1m": round(self.volatility_1m * 100, 2),
            "volatility_3m": round(self.volatility_3m * 100, 2),
            "mdd": round(self.mdd * 100, 2),
            "mdd_1y": round(self.mdd_1y * 100, 2),
            "current_drawdown": round(self.current_drawdown * 100, 2),
            "high_52w": round(self.high_52w, 2),
            "low_52w": round(self.low_52w, 2),
            "pct_from_high": round(self.pct_from_high * 100, 2),
            "pct_from_low": round(self.pct_from_low * 100, 2),
        }


class TechnicalIndicators:
    """
    Calculate technical indicators for a set of stocks.

    Example:
        >>> price_df = pd.DataFrame(...)  # index: date, columns: tickers
        >>> ticker_meta = {"AAPL": 1, "GOOGL": 2}
        >>> indicators = TechnicalIndicators(price_df, ticker_meta)
        >>> results = indicators.calculate_all()
    """

    # Trading days in various periods
    DAYS_1M = 21
    DAYS_3M = 63
    DAYS_6M = 126
    DAYS_12M = 252
    DAYS_52W = 252

    def __init__(
        self,
        price_df: pd.DataFrame,
        ticker_meta: Dict[str, int],
    ):
        """
        Initialize with price data.

        Args:
            price_df: DataFrame with date index and ticker columns (adj_close prices)
            ticker_meta: Dict mapping ticker to meta_id
        """
        self.price_df = price_df.sort_index()
        self.ticker_meta = ticker_meta
        self.returns_df = self.price_df.pct_change()

    def _calculate_period_return(self, ticker: str, days: int) -> float:
        """Calculate return over specified period."""
        prices = self.price_df[ticker].dropna()
        if len(prices) < days + 1:
            return np.nan
        return (prices.iloc[-1] / prices.iloc[-days - 1]) - 1

    def _calculate_ytd_return(self, ticker: str) -> float:
        """Calculate year-to-date return."""
        prices = self.price_df[ticker].dropna()
        if prices.empty:
            return np.nan

        current_year = prices.index[-1].year
        year_start = prices.index[prices.index.year == current_year]

        if len(year_start) < 2:
            return np.nan

        first_price = prices.loc[year_start[0]]
        last_price = prices.iloc[-1]
        return (last_price / first_price) - 1

    def _calculate_volatility(self, ticker: str, days: int) -> float:
        """Calculate annualized volatility over specified period."""
        returns = self.returns_df[ticker].dropna()
        if len(returns) < days:
            return np.nan
        period_returns = returns.iloc[-days:]
        return period_returns.std() * np.sqrt(252)

    def _calculate_drawdown(self, prices: pd.Series) -> pd.Series:
        """Calculate drawdown series."""
        rolling_max = prices.expanding().max()
        drawdown = (prices - rolling_max) / rolling_max
        return drawdown

    def _calculate_mdd(self, ticker: str, days: Optional[int] = None) -> float:
        """Calculate maximum drawdown."""
        prices = self.price_df[ticker].dropna()
        if prices.empty:
            return np.nan

        if days:
            prices = prices.iloc[-days:] if len(prices) >= days else prices

        drawdown = self._calculate_drawdown(prices)
        return drawdown.min()

    def _calculate_52w_stats(self, ticker: str) -> Dict:
        """Calculate 52-week high/low statistics."""
        prices = self.price_df[ticker].dropna()

        if len(prices) < self.DAYS_52W:
            period_prices = prices
        else:
            period_prices = prices.iloc[-self.DAYS_52W :]

        if period_prices.empty:
            return {
                "high_52w": np.nan,
                "low_52w": np.nan,
                "pct_from_high": np.nan,
                "pct_from_low": np.nan,
            }

        high_52w = period_prices.max()
        low_52w = period_prices.min()
        current = prices.iloc[-1]

        return {
            "high_52w": high_52w,
            "low_52w": low_52w,
            "pct_from_high": (current - high_52w) / high_52w,  # negative
            "pct_from_low": (current - low_52w) / low_52w,  # positive
        }

    def calculate_for_ticker(self, ticker: str) -> Optional[IndicatorResult]:
        """Calculate all indicators for a single ticker."""
        if ticker not in self.price_df.columns:
            logger.warning(f"Ticker {ticker} not found in price data")
            return None

        prices = self.price_df[ticker].dropna()
        if len(prices) < self.DAYS_1M:
            logger.warning(f"Insufficient data for {ticker}: {len(prices)} days")
            return None

        stats_52w = self._calculate_52w_stats(ticker)
        current_dd = self._calculate_drawdown(prices).iloc[-1]

        return IndicatorResult(
            ticker=ticker,
            meta_id=self.ticker_meta.get(ticker, 0),
            current_price=prices.iloc[-1],
            return_1m=self._calculate_period_return(ticker, self.DAYS_1M),
            return_3m=self._calculate_period_return(ticker, self.DAYS_3M),
            return_6m=self._calculate_period_return(ticker, self.DAYS_6M),
            return_12m=self._calculate_period_return(ticker, self.DAYS_12M),
            return_ytd=self._calculate_ytd_return(ticker),
            volatility_1m=self._calculate_volatility(ticker, self.DAYS_1M),
            volatility_3m=self._calculate_volatility(ticker, self.DAYS_3M),
            mdd=self._calculate_mdd(ticker),
            mdd_1y=self._calculate_mdd(ticker, self.DAYS_12M),
            current_drawdown=current_dd,
            high_52w=stats_52w["high_52w"],
            low_52w=stats_52w["low_52w"],
            pct_from_high=stats_52w["pct_from_high"],
            pct_from_low=stats_52w["pct_from_low"],
        )

    def calculate_all(self) -> List[IndicatorResult]:
        """Calculate indicators for all tickers."""
        results = []
        for ticker in self.price_df.columns:
            result = self.calculate_for_ticker(ticker)
            if result:
                results.append(result)

        logger.info(f"Calculated indicators for {len(results)} tickers")
        return results
