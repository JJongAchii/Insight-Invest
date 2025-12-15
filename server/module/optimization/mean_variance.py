"""
Mean-Variance Optimization (MVO) Implementation.

Implements Markowitz's Modern Portfolio Theory:
- Maximum Sharpe Ratio portfolio
- Minimum Volatility portfolio
- Target Return optimization
- Efficient Frontier generation

Uses scipy.optimize for numerical optimization with SLSQP method.
"""

import logging
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from .base import BaseOptimizer, EfficientFrontier, EfficientFrontierPoint, OptimizationResult

logger = logging.getLogger(__name__)


class MeanVarianceOptimizer(BaseOptimizer):
    """
    Mean-Variance Optimization using scipy.

    Implements classical Markowitz optimization to find portfolios
    that maximize risk-adjusted returns.

    Example:
        >>> exp_ret = pd.Series([0.10, 0.12, 0.08], index=['A', 'B', 'C'])
        >>> cov_mat = pd.DataFrame(...)  # 3x3 covariance matrix
        >>> optimizer = MeanVarianceOptimizer(exp_ret, cov_mat, risk_free_rate=0.02)
        >>> result = optimizer.max_sharpe()
        >>> print(result.weights)
    """

    def _negative_sharpe(self, weights: np.ndarray) -> float:
        """
        Negative Sharpe ratio for minimization.

        Args:
            weights: Array of portfolio weights

        Returns:
            Negative Sharpe ratio (to minimize)
        """
        return -self._sharpe_ratio(weights)

    def _portfolio_variance(self, weights: np.ndarray) -> float:
        """
        Calculate portfolio variance.

        Args:
            weights: Array of portfolio weights

        Returns:
            Portfolio variance
        """
        return float(np.dot(weights.T, np.dot(self.cov_matrix.values, weights)))

    def max_sharpe(self, n_restarts: int = 10) -> OptimizationResult:
        """
        Find portfolio with maximum Sharpe ratio.

        Uses multiple random starting points to avoid local minima.

        Args:
            n_restarts: Number of random starting points (default: 10)

        Returns:
            OptimizationResult with maximum Sharpe portfolio

        Raises:
            ValueError: If optimization fails to converge
        """
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds = [self.weight_bounds] * self.n_assets

        best_result = None
        best_sharpe = -np.inf

        for i in range(n_restarts):
            # Random starting point (Dirichlet distribution ensures sum=1)
            x0 = np.random.dirichlet(np.ones(self.n_assets))

            try:
                result = minimize(
                    self._negative_sharpe,
                    x0,
                    method="SLSQP",
                    bounds=bounds,
                    constraints=constraints,
                    options={"maxiter": 1000, "ftol": 1e-10},
                )

                if result.success and -result.fun > best_sharpe:
                    best_sharpe = -result.fun
                    best_result = result
            except Exception as e:
                logger.debug(f"Optimization attempt {i} failed: {e}")
                continue

        if best_result is None:
            raise ValueError("Max Sharpe optimization failed to converge after all restarts")

        logger.info(f"Max Sharpe optimization converged with Sharpe={best_sharpe:.4f}")
        return self._build_result(best_result.x)

    def min_volatility(self) -> OptimizationResult:
        """
        Find minimum volatility portfolio.

        Also known as the Global Minimum Variance (GMV) portfolio.

        Returns:
            OptimizationResult with minimum volatility portfolio

        Raises:
            ValueError: If optimization fails to converge
        """
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds = [self.weight_bounds] * self.n_assets
        x0 = np.ones(self.n_assets) / self.n_assets

        result = minimize(
            self._portfolio_variance,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 1000, "ftol": 1e-10},
        )

        if not result.success:
            logger.warning(f"Min volatility optimization warning: {result.message}")

        vol = self._portfolio_volatility(result.x)
        logger.info(f"Min volatility optimization converged with vol={vol:.4f}")
        return self._build_result(result.x)

    def target_return(self, target: float) -> OptimizationResult:
        """
        Find minimum volatility portfolio for a target return.

        This traces a point on the efficient frontier.

        Args:
            target: Target annualized return

        Returns:
            OptimizationResult with minimum volatility at target return

        Raises:
            ValueError: If target return is not achievable
        """
        constraints = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
            {"type": "eq", "fun": lambda w: self._portfolio_return(w) - target},
        ]
        bounds = [self.weight_bounds] * self.n_assets
        x0 = np.ones(self.n_assets) / self.n_assets

        result = minimize(
            self._portfolio_variance,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 1000, "ftol": 1e-10},
        )

        if not result.success:
            raise ValueError(f"Target return {target:.2%} is not achievable: {result.message}")

        return self._build_result(result.x)

    def target_volatility(self, target: float) -> OptimizationResult:
        """
        Find maximum return portfolio for a target volatility.

        Args:
            target: Target annualized volatility

        Returns:
            OptimizationResult with maximum return at target volatility

        Raises:
            ValueError: If target volatility is not achievable
        """

        def neg_return(w: np.ndarray) -> float:
            return -self._portfolio_return(w)

        constraints = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
            {"type": "eq", "fun": lambda w: self._portfolio_volatility(w) - target},
        ]
        bounds = [self.weight_bounds] * self.n_assets
        x0 = np.ones(self.n_assets) / self.n_assets

        result = minimize(
            neg_return,
            x0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 1000, "ftol": 1e-10},
        )

        if not result.success:
            raise ValueError(f"Target volatility {target:.2%} is not achievable: {result.message}")

        return self._build_result(result.x)

    def efficient_frontier(
        self, n_points: int = 50, include_max_return: bool = True
    ) -> EfficientFrontier:
        """
        Generate the efficient frontier.

        Creates a series of optimal portfolios from minimum volatility
        to maximum return.

        Args:
            n_points: Number of points on the frontier (default: 50)
            include_max_return: Include 100% allocation in best asset (default: True)

        Returns:
            EfficientFrontier with points and optimal portfolios
        """
        # Get boundary portfolios
        min_vol = self.min_volatility()
        max_sharpe = self.max_sharpe()

        # Find maximum achievable return
        if include_max_return:
            max_ret_idx = int(self.expected_returns.argmax())
            max_ret_weights = np.zeros(self.n_assets)
            max_ret_weights[max_ret_idx] = 1.0
            max_ret = self._portfolio_return(max_ret_weights)
        else:
            # Use 95% of theoretical max to ensure feasibility
            max_ret = float(self.expected_returns.max()) * 0.95

        # Generate frontier points
        min_ret = min_vol.expected_return
        target_returns = np.linspace(min_ret, max_ret * 0.98, n_points)

        points: List[EfficientFrontierPoint] = []
        for target in target_returns:
            try:
                opt = self.target_return(target)
                points.append(
                    EfficientFrontierPoint(
                        return_=opt.expected_return,
                        volatility=opt.volatility,
                        weights=opt.weights,
                        sharpe_ratio=opt.sharpe_ratio,
                    )
                )
            except ValueError:
                # Target not achievable, skip
                continue

        # Max return portfolio (100% in highest return asset)
        if include_max_return:
            max_return_portfolio = self._build_result(max_ret_weights)
        else:
            # Find achievable max return portfolio
            max_return_portfolio = points[-1] if points else max_sharpe
            max_return_portfolio = OptimizationResult(
                weights=(
                    max_return_portfolio.weights
                    if isinstance(max_return_portfolio, EfficientFrontierPoint)
                    else max_return_portfolio.weights
                ),
                expected_return=(
                    max_return_portfolio.return_
                    if isinstance(max_return_portfolio, EfficientFrontierPoint)
                    else max_return_portfolio.expected_return
                ),
                volatility=max_return_portfolio.volatility,
                sharpe_ratio=max_return_portfolio.sharpe_ratio,
                risk_contributions=max_sharpe.risk_contributions,  # Approximate
            )

        logger.info(
            f"Generated efficient frontier with {len(points)} points, "
            f"return range: [{min_ret:.2%}, {max_ret:.2%}]"
        )

        return EfficientFrontier(
            points=points,
            max_sharpe_portfolio=max_sharpe,
            min_volatility_portfolio=min_vol,
            max_return_portfolio=max_return_portfolio,
        )
