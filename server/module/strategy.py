"""
Portfolio Strategy Implementations

This module contains strategy classes for portfolio allocation:
- EqualWeight: Simple 1/N allocation
- Momentum: top-N absolute momentum allocation (generalized)
- DualMomentum: Momentum(4, 12) backward-compat alias
- FixedWeight: constant custom weights at each rebalance

Uses Polars internally for better performance on large datasets.
"""

from datetime import timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import polars as pl

from .util import resample_data


def cal_monthly_momentum(price: pd.DataFrame, lookback_months: int = 12) -> Optional[pd.DataFrame]:
    """
    Calculate momentum over the last `lookback_months` months for each asset.

    Uses the last (lookback_months + 1) month-end rows.

    Args:
        price: Daily price DataFrame (index: date, columns: tickers)
        lookback_months: Momentum lookback window in months

    Returns:
        DataFrame with momentum values, or None if insufficient data
    """
    n_rows = lookback_months + 1
    price_tail = resample_data(price=price, freq="M", type="tail")[-n_rows:]

    if len(price_tail) < n_rows:
        return None

    # Use Polars for vectorized momentum calculation
    pl_df = pl.from_pandas(price_tail.reset_index())
    date_col = pl_df.columns[0]
    ticker_cols = [col for col in pl_df.columns if col != date_col]

    # Get last row values
    last_values = pl_df.tail(1).select(ticker_cols).to_numpy().flatten()

    # Calculate momentum: (last / each) - 1
    momentum_exprs = [
        ((pl.lit(last_values[i]) / pl.col(col)) - 1).alias(col) for i, col in enumerate(ticker_cols)
    ]

    momentum_df = pl_df.select([pl.col(date_col)] + momentum_exprs)

    # Convert back to pandas with proper index
    result = momentum_df.to_pandas()
    result = result.set_index(date_col)
    result.index = pd.to_datetime(result.index)

    return result


def binary_from_momentum(momentum: pd.DataFrame) -> pd.DataFrame:
    """
    Convert momentum to binary signals (1 if positive, 0 otherwise).

    Uses Polars for vectorized binary conversion.
    """
    # Use Polars for vectorized operation
    pl_df = pl.from_pandas(momentum.reset_index())
    date_col = pl_df.columns[0]
    ticker_cols = [col for col in pl_df.columns if col != date_col]

    # Binary conversion: 1 if > 0, else 0
    binary_exprs = [pl.when(pl.col(col) > 0).then(1).otherwise(0).alias(col) for col in ticker_cols]

    result_df = pl_df.select([pl.col(date_col)] + binary_exprs)

    # Convert back to pandas
    result = result_df.to_pandas()
    result = result.set_index(date_col)
    result.index = pd.to_datetime(result.index)

    return result


def absolute_momentum(price: pd.DataFrame, lookback_months: int = 12) -> Optional[pd.Series]:
    """
    Calculate absolute momentum score for each asset.

    Args:
        price: Daily price DataFrame
        lookback_months: Momentum lookback window in months

    Returns:
        Series with momentum scores, or None if insufficient data
    """
    monthly_mmt = cal_monthly_momentum(price=price, lookback_months=lookback_months)

    if monthly_mmt is None:
        return None

    abs_mmt = binary_from_momentum(momentum=monthly_mmt)[:-1]
    abs_mmt_score = abs_mmt.mean()

    return abs_mmt_score


class EqualWeight:
    """Equal Weight strategy: allocate 1/N to each asset."""

    def simulate(self, price: pd.DataFrame, freq: str = "M") -> pd.DataFrame:
        """
        Generate equal weight allocations for each rebalancing date.

        Args:
            price: Daily price DataFrame (index: date, columns: tickers)
            freq: Rebalance frequency ("M", "Q", "Y") — rebal dates are the
                first trading day of each period

        Returns:
            Weight DataFrame (index: rebal_date, columns: tickers)
        """
        weights = resample_data(price=price, freq=freq, type="head").copy()
        weights[:] = 1 / len(price.columns)
        return weights


class Momentum:
    """
    Top-N absolute momentum strategy (generalized Dual Momentum).

    Selects the top `top_n` assets by absolute momentum score computed over the
    last `lookback_months` months and normalizes the scores to sum to 1.
    Uses Polars for efficient data aggregation.
    """

    def __init__(self, top_n: int = 4, lookback_months: int = 12) -> None:
        self.top_n = top_n
        self.lookback_months = lookback_months

    def simulate(self, price: pd.DataFrame, freq: str = "M") -> pd.DataFrame:
        """
        Generate momentum allocations for each rebalancing date.

        Uses Polars for efficient concat and pivot operations.

        Args:
            price: Daily price DataFrame (index: date, columns: tickers)
            freq: Rebalance frequency ("M", "Q", "Y") — rebal dates are the
                first trading day of each period

        Returns:
            Weight DataFrame (index: rebal_date, columns: tickers)
        """
        rebal_dates = resample_data(price=price, freq=freq, type="head").index

        # Collect weights as list of dicts for Polars efficiency
        weights_records: List[dict] = []

        for rebal_date in rebal_dates:
            yesterday = rebal_date - timedelta(days=1)
            price_slice = price[:yesterday]

            if price_slice.empty:
                continue

            abs_mmt_score = absolute_momentum(
                price=price_slice, lookback_months=self.lookback_months
            )

            if abs_mmt_score is None:
                continue

            # Select top N assets by momentum score
            top_score = abs_mmt_score.nlargest(self.top_n)

            # Normalize weights to sum to 1
            weight_sum = top_score.sum()
            for ticker, weight in top_score.items():
                weights_records.append(
                    {
                        "rebal_date": rebal_date,
                        "ticker": ticker,
                        "weights": weight / weight_sum if weight_sum > 0 else 0,
                    }
                )

        if not weights_records:
            return pd.DataFrame()

        # Use Polars for efficient pivot
        pl_df = pl.DataFrame(weights_records)
        pivot_df = pl_df.pivot(on="ticker", index="rebal_date", values="weights")

        # Convert back to pandas with proper index
        result = pivot_df.to_pandas()
        result = result.set_index("rebal_date")
        result.index = pd.to_datetime(result.index)

        return result


class DualMomentum(Momentum):
    """Backward-compat alias: Dual Momentum = Momentum(top_n=4, lookback_months=12)."""

    def __init__(self) -> None:
        super().__init__(top_n=4, lookback_months=12)


class FixedWeight:
    """
    Fixed (constant) weight strategy.

    At each rebalance date emits the given constant weights for tickers present
    in the price columns. Weights are NOT renormalized — any residual stays cash.
    """

    def __init__(self, weights: Dict[str, float]) -> None:
        self.weights = weights

    def simulate(self, price: pd.DataFrame, freq: str = "M") -> pd.DataFrame:
        """
        Generate constant weight allocations for each rebalancing date.

        Args:
            price: Daily price DataFrame (index: date, columns: tickers)
            freq: Rebalance frequency ("M", "Q", "Y") — rebal dates are the
                first trading day of each period

        Returns:
            Weight DataFrame (index: rebal_date, columns: tickers present in price)
        """
        rebal_dates = resample_data(price=price, freq=freq, type="head").index
        cols = [t for t in self.weights if t in price.columns]
        return pd.DataFrame(
            {t: [float(self.weights[t])] * len(rebal_dates) for t in cols}, index=rebal_dates
        )
