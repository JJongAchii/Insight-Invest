"""
Base classes and data structures for portfolio optimization.

This module provides the foundational classes for portfolio optimization:
- OptimizationResult: Stores optimization results
- EfficientFrontierPoint: Single point on the efficient frontier
- EfficientFrontier: Complete efficient frontier with optimal portfolios
- BaseOptimizer: Abstract base class for optimizers
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


@dataclass
class OptimizationResult:
    """
    Result of portfolio optimization.

    Attributes:
        weights: Dictionary mapping ticker to weight (0.0 - 1.0)
        expected_return: Annualized expected return
        volatility: Annualized volatility (standard deviation)
        sharpe_ratio: Sharpe ratio given the risk-free rate
        risk_contributions: Dictionary mapping ticker to risk contribution
    """

    weights: Dict[str, float]
    expected_return: float
    volatility: float
    sharpe_ratio: float
    risk_contributions: Dict[str, float]

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "weights": self.weights,
            "expected_return": self.expected_return,
            "volatility": self.volatility,
            "sharpe_ratio": self.sharpe_ratio,
            "risk_contributions": self.risk_contributions,
        }


@dataclass
class EfficientFrontierPoint:
    """
    Single point on the efficient frontier.

    Attributes:
        return_: Expected return at this point
        volatility: Volatility at this point
        weights: Portfolio weights at this point
        sharpe_ratio: Sharpe ratio at this point
    """

    return_: float
    volatility: float
    weights: Dict[str, float]
    sharpe_ratio: float

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "return": self.return_,
            "volatility": self.volatility,
            "weights": self.weights,
            "sharpe_ratio": self.sharpe_ratio,
        }


@dataclass
class EfficientFrontier:
    """
    Complete efficient frontier with optimal portfolios.

    Attributes:
        points: List of points along the efficient frontier
        max_sharpe_portfolio: Portfolio with maximum Sharpe ratio
        min_volatility_portfolio: Portfolio with minimum volatility
        max_return_portfolio: Portfolio with maximum return (100% in best asset)
    """

    points: List[EfficientFrontierPoint]
    max_sharpe_portfolio: OptimizationResult
    min_volatility_portfolio: OptimizationResult
    max_return_portfolio: OptimizationResult

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "frontier_points": [p.to_dict() for p in self.points],
            "max_sharpe": self.max_sharpe_portfolio.to_dict(),
            "min_volatility": self.min_volatility_portfolio.to_dict(),
            "max_return": self.max_return_portfolio.to_dict(),
        }


class BaseOptimizer:
    """
    Base class for portfolio optimizers.

    Provides common portfolio metrics calculations used by all optimizers.

    Args:
        expected_returns: Series of annualized expected returns (index: tickers)
        cov_matrix: Annualized covariance matrix (DataFrame)
        risk_free_rate: Annual risk-free rate (default: 0.0)
        weight_bounds: (min_weight, max_weight) per asset (default: (0.0, 1.0))
    """

    def __init__(
        self,
        expected_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        risk_free_rate: float = 0.0,
        weight_bounds: Tuple[float, float] = (0.0, 1.0),
    ):
        self.expected_returns = expected_returns
        self.cov_matrix = cov_matrix
        self.risk_free_rate = risk_free_rate
        self.weight_bounds = weight_bounds
        self.tickers = expected_returns.index.tolist()
        self.n_assets = len(self.tickers)

        # Validate inputs
        if self.n_assets < 2:
            raise ValueError("At least 2 assets required for optimization")
        if not all(t in cov_matrix.columns for t in self.tickers):
            raise ValueError("Covariance matrix must contain all tickers")

    def _portfolio_return(self, weights: np.ndarray) -> float:
        """
        Calculate portfolio expected return.

        Args:
            weights: Array of portfolio weights

        Returns:
            Annualized expected return
        """
        return float(np.dot(weights, self.expected_returns.values))

    def _portfolio_volatility(self, weights: np.ndarray) -> float:
        """
        Calculate portfolio volatility (standard deviation).

        Args:
            weights: Array of portfolio weights

        Returns:
            Annualized volatility
        """
        variance = np.dot(weights.T, np.dot(self.cov_matrix.values, weights))
        return float(np.sqrt(variance))

    def _sharpe_ratio(self, weights: np.ndarray) -> float:
        """
        Calculate Sharpe ratio.

        Args:
            weights: Array of portfolio weights

        Returns:
            Sharpe ratio (excess return / volatility)
        """
        ret = self._portfolio_return(weights)
        vol = self._portfolio_volatility(weights)
        if vol <= 0:
            return 0.0
        return (ret - self.risk_free_rate) / vol

    def _risk_contributions(self, weights: np.ndarray) -> np.ndarray:
        """
        Calculate marginal risk contribution of each asset.

        Risk contribution of asset i = w_i * (Sigma * w)_i / sigma_p

        Args:
            weights: Array of portfolio weights

        Returns:
            Array of risk contributions (sum equals portfolio volatility)
        """
        portfolio_vol = self._portfolio_volatility(weights)
        if portfolio_vol <= 0:
            return np.zeros(self.n_assets)

        marginal_contrib = np.dot(self.cov_matrix.values, weights)
        risk_contrib = weights * marginal_contrib / portfolio_vol
        return risk_contrib

    def _build_result(self, weights: np.ndarray) -> OptimizationResult:
        """
        Build OptimizationResult from weight array.

        Args:
            weights: Array of portfolio weights

        Returns:
            OptimizationResult with all metrics
        """
        risk_contrib = self._risk_contributions(weights)
        return OptimizationResult(
            weights=dict(zip(self.tickers, weights.tolist())),
            expected_return=self._portfolio_return(weights),
            volatility=self._portfolio_volatility(weights),
            sharpe_ratio=self._sharpe_ratio(weights),
            risk_contributions=dict(zip(self.tickers, risk_contrib.tolist())),
        )
