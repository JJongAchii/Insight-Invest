"""
Risk Parity Optimization Implementation.

Risk Parity allocates weights so that each asset contributes
equally to the total portfolio risk.

This approach:
- Ignores expected returns (uses only covariance)
- Equalizes risk contributions across all assets
- Typically results in higher allocations to lower-volatility assets

Uses scipy.optimize for numerical optimization with SLSQP method.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from .base import BaseOptimizer, OptimizationResult

logger = logging.getLogger(__name__)


class RiskParityOptimizer(BaseOptimizer):
    """
    Risk Parity Optimization using scipy.

    Finds portfolio weights that equalize each asset's contribution
    to total portfolio risk.

    Example:
        >>> exp_ret = pd.Series([0.10, 0.12, 0.08], index=['A', 'B', 'C'])
        >>> cov_mat = pd.DataFrame(...)  # 3x3 covariance matrix
        >>> optimizer = RiskParityOptimizer(exp_ret, cov_mat)
        >>> result = optimizer.optimize()
        >>> print(result.risk_contributions)  # Should be approximately equal
    """

    def __init__(
        self,
        expected_returns: pd.Series,
        cov_matrix: pd.DataFrame,
        risk_free_rate: float = 0.0,
        min_weight: float = 0.01,
    ):
        """
        Initialize Risk Parity optimizer.

        Args:
            expected_returns: Series of annualized expected returns
            cov_matrix: Annualized covariance matrix
            risk_free_rate: Annual risk-free rate (default: 0.0)
            min_weight: Minimum weight per asset to avoid zero allocations (default: 0.01)
        """
        # Use min_weight as lower bound to ensure meaningful allocations
        super().__init__(
            expected_returns=expected_returns,
            cov_matrix=cov_matrix,
            risk_free_rate=risk_free_rate,
            weight_bounds=(min_weight, 1.0),
        )
        self.min_weight = min_weight

    def _risk_budget_objective(self, weights: np.ndarray) -> float:
        """
        Risk budget objective function.

        Minimizes squared differences between actual and target risk contributions.
        For risk parity, target is equal contribution (sigma_p / n) for each asset.

        Args:
            weights: Array of portfolio weights

        Returns:
            Sum of squared deviations from target risk
        """
        sigma_p = self._portfolio_volatility(weights)
        if sigma_p <= 1e-10:
            return 1e10

        # Marginal risk contribution: d(sigma_p)/d(w_i) * w_i
        marginal_contrib = np.dot(self.cov_matrix.values, weights)

        # Risk contribution (absolute): w_i * (Sigma * w)_i / sigma_p
        risk_contrib = weights * marginal_contrib / sigma_p

        # Target: equal risk contribution (sigma_p / n for each)
        target_risk = sigma_p / self.n_assets

        # Sum of squared deviations from target
        return float(np.sum((risk_contrib - target_risk) ** 2))

    def _risk_budget_objective_log(self, log_weights: np.ndarray) -> float:
        """
        Risk budget objective with log-weights parameterization.

        Using log-weights ensures positive weights and improves
        numerical stability.

        Args:
            log_weights: Log of portfolio weights

        Returns:
            Sum of squared deviations from target risk
        """
        weights = np.exp(log_weights)
        weights = weights / weights.sum()  # Normalize
        return self._risk_budget_objective(weights)

    def optimize(self, n_restarts: int = 20, method: str = "slsqp") -> OptimizationResult:
        """
        Find risk parity portfolio.

        Uses multiple starting points to find global optimum.

        Args:
            n_restarts: Number of random starting points (default: 20)
            method: Optimization method, 'slsqp' or 'log' (default: 'slsqp')

        Returns:
            OptimizationResult with risk parity weights

        Raises:
            ValueError: If optimization fails to converge
        """
        if method == "log":
            return self._optimize_log(n_restarts)
        return self._optimize_slsqp(n_restarts)

    def _optimize_slsqp(self, n_restarts: int) -> OptimizationResult:
        """
        Optimize using SLSQP with direct weight constraints.
        """
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds = [(self.min_weight, 1.0)] * self.n_assets

        best_result = None
        best_obj = np.inf

        for i in range(n_restarts):
            # Random starting point
            x0 = np.random.dirichlet(np.ones(self.n_assets))

            try:
                result = minimize(
                    self._risk_budget_objective,
                    x0,
                    method="SLSQP",
                    bounds=bounds,
                    constraints=constraints,
                    options={"maxiter": 1000, "ftol": 1e-12},
                )

                if result.fun < best_obj:
                    best_obj = result.fun
                    best_result = result
            except Exception as e:
                logger.debug(f"SLSQP attempt {i} failed: {e}")
                continue

        if best_result is None:
            raise ValueError("Risk parity optimization failed to converge")

        weights = best_result.x
        # Normalize to ensure sum = 1
        weights = weights / weights.sum()

        # Verify risk parity achieved
        sigma_p = self._portfolio_volatility(weights)
        risk_contrib = self._risk_contributions(weights)
        risk_parity_error = np.std(risk_contrib / sigma_p) if sigma_p > 0 else 0

        logger.info(
            f"Risk parity optimization converged, "
            f"risk parity error: {risk_parity_error:.6f}, "
            f"objective: {best_obj:.10f}"
        )

        return self._build_result(weights)

    def _optimize_log(self, n_restarts: int) -> OptimizationResult:
        """
        Optimize using log-weight transformation (unconstrained optimization).

        This method can be more numerically stable for some problems.
        """
        best_weights = None
        best_obj = np.inf

        for i in range(n_restarts):
            # Random starting point in log space
            x0 = np.log(np.random.dirichlet(np.ones(self.n_assets)))

            try:
                result = minimize(
                    self._risk_budget_objective_log,
                    x0,
                    method="L-BFGS-B",
                    options={"maxiter": 1000, "ftol": 1e-12},
                )

                if result.fun < best_obj:
                    best_obj = result.fun
                    weights = np.exp(result.x)
                    weights = weights / weights.sum()
                    best_weights = weights
            except Exception as e:
                logger.debug(f"Log optimization attempt {i} failed: {e}")
                continue

        if best_weights is None:
            raise ValueError("Risk parity optimization failed to converge")

        logger.info(f"Risk parity (log) optimization converged, objective: {best_obj:.10f}")
        return self._build_result(best_weights)

    def optimize_with_budget(
        self, risk_budgets: Optional[np.ndarray] = None, n_restarts: int = 20
    ) -> OptimizationResult:
        """
        Find portfolio with custom risk budget.

        Allows specifying target risk contribution for each asset.

        Args:
            risk_budgets: Array of target risk percentages (must sum to 1).
                          If None, uses equal budgets (1/n).
            n_restarts: Number of random starting points

        Returns:
            OptimizationResult with specified risk budget
        """
        if risk_budgets is None:
            risk_budgets = np.ones(self.n_assets) / self.n_assets
        else:
            risk_budgets = np.array(risk_budgets)
            if not np.isclose(risk_budgets.sum(), 1.0):
                raise ValueError("Risk budgets must sum to 1")

        def custom_objective(weights: np.ndarray) -> float:
            sigma_p = self._portfolio_volatility(weights)
            if sigma_p <= 1e-10:
                return 1e10

            marginal_contrib = np.dot(self.cov_matrix.values, weights)
            risk_contrib = weights * marginal_contrib / sigma_p

            # Target: specified risk budget
            target_risk = risk_budgets * sigma_p

            return float(np.sum((risk_contrib - target_risk) ** 2))

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds = [(self.min_weight, 1.0)] * self.n_assets

        best_result = None
        best_obj = np.inf

        for i in range(n_restarts):
            x0 = np.random.dirichlet(np.ones(self.n_assets))

            try:
                result = minimize(
                    custom_objective,
                    x0,
                    method="SLSQP",
                    bounds=bounds,
                    constraints=constraints,
                    options={"maxiter": 1000, "ftol": 1e-12},
                )

                if result.fun < best_obj:
                    best_obj = result.fun
                    best_result = result
            except Exception:
                continue

        if best_result is None:
            raise ValueError("Custom risk budget optimization failed to converge")

        weights = best_result.x / best_result.x.sum()
        logger.info(f"Custom risk budget optimization converged, objective: {best_obj:.10f}")

        return self._build_result(weights)
