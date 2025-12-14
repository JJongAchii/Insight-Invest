"""
Portfolio Strategy Implementations

This module contains strategy classes for portfolio allocation:
- EqualWeight: Simple 1/N allocation
- DualMomentum: Momentum-based dynamic allocation
"""

from datetime import timedelta
from typing import List, Optional

import numpy as np
import pandas as pd

from .util import resample_data


def cal_monthly_momentum(price: pd.DataFrame) -> Optional[pd.DataFrame]:
    """
    Calculate 12-month momentum for each asset.

    Args:
        price: Daily price DataFrame (index: date, columns: tickers)

    Returns:
        DataFrame with momentum values, or None if insufficient data
    """
    price_tail = resample_data(price=price, freq="M", type="tail")[-13:]

    if len(price_tail) < 13:
        return None

    monthly_momentum = price_tail.iloc[-1].div(price_tail) - 1

    return monthly_momentum


def binary_from_momentum(momentum: pd.DataFrame) -> pd.DataFrame:
    """Convert momentum to binary signals (1 if positive, 0 otherwise)."""
    return momentum.apply(lambda x: np.where(x > 0, 1, 0))


def absolute_momentum(price: pd.DataFrame) -> Optional[pd.Series]:
    """
    Calculate absolute momentum score for each asset.

    Args:
        price: Daily price DataFrame

    Returns:
        Series with momentum scores, or None if insufficient data
    """
    monthly_mmt = cal_monthly_momentum(price=price)

    if monthly_mmt is None:
        return None

    abs_mmt = binary_from_momentum(momentum=monthly_mmt)[:-1]
    abs_mmt_score = abs_mmt.mean()

    return abs_mmt_score


class EqualWeight:
    """Equal Weight strategy: allocate 1/N to each asset."""

    def simulate(self, price: pd.DataFrame) -> pd.DataFrame:
        """
        Generate equal weight allocations for each rebalancing date.

        Args:
            price: Daily price DataFrame (index: date, columns: tickers)

        Returns:
            Weight DataFrame (index: rebal_date, columns: tickers)
        """
        weights = resample_data(price=price).copy()
        weights[:] = 1 / len(price.columns)
        return weights


class DualMomentum:
    """
    Dual Momentum strategy.

    Selects top 4 assets by absolute momentum score and allocates equally.
    """

    def simulate(self, price: pd.DataFrame) -> pd.DataFrame:
        """
        Generate dual momentum allocations for each rebalancing date.

        Args:
            price: Daily price DataFrame (index: date, columns: tickers)

        Returns:
            Weight DataFrame (index: rebal_date, columns: tickers)
        """
        rebal_dates = resample_data(price=price, freq="M", type="head").index

        # Collect weights in a list, then concat once at end (O(n) instead of O(n²))
        weights_list: List[pd.DataFrame] = []

        for rebal_date in rebal_dates:
            yesterday = rebal_date - timedelta(days=1)
            price_slice = price[:yesterday]

            if price_slice.empty:
                continue

            abs_mmt_score = absolute_momentum(price=price_slice)

            if abs_mmt_score is None:
                continue

            # Select top 4 assets by momentum score
            dual_mmt_score = abs_mmt_score.nlargest(4)

            # Normalize weights to sum to 1
            weights = dual_mmt_score.div(dual_mmt_score.sum()).reset_index()
            weights.columns = ["ticker", "weights"]
            weights["rebal_date"] = rebal_date

            weights_list.append(weights)

        if not weights_list:
            return pd.DataFrame()

        # Single concat at end - O(n) instead of O(n²)
        weights_df = pd.concat(weights_list, axis=0, ignore_index=True)

        return weights_df.pivot(index="rebal_date", columns="ticker", values="weights")
