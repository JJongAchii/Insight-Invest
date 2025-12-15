"""
Portfolio Optimization API Endpoints

Provides:
- Efficient frontier calculation (Mean-Variance Optimization)
- Maximum Sharpe ratio portfolio
- Minimum volatility portfolio
- Risk Parity portfolio
"""

import logging
import os
import sys
from typing import Dict

from fastapi import APIRouter, HTTPException

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../../../")))

from app import schemas
from module.backtest import Backtest
from module.metrics import covariance_matrix, expected_returns
from module.optimization import MeanVarianceOptimizer, RiskParityOptimizer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/optimization", tags=["Optimization"])


def _get_price_data(
    meta_id: list,
    start_date=None,
    end_date=None,
    lookback_period: int = 252,
):
    """
    Fetch and prepare price data for optimization.

    Args:
        meta_id: List of meta_ids
        start_date: Optional start date filter
        end_date: Optional end date filter
        lookback_period: Number of days to use for estimation

    Returns:
        Price DataFrame (index: date, columns: tickers)

    Raises:
        HTTPException: If insufficient data
    """
    bt = Backtest()
    price = bt.data(meta_id=meta_id, start_date=start_date, end_date=end_date)

    if price.empty:
        raise HTTPException(status_code=404, detail="No price data found for given assets")

    # Use lookback period
    price_slice = price.tail(lookback_period)

    if len(price_slice) < 60:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient data for optimization. "
            f"Found {len(price_slice)} days, minimum 60 required.",
        )

    # Check for missing data
    missing_pct = price_slice.isna().sum() / len(price_slice)
    problematic = missing_pct[missing_pct > 0.1].index.tolist()
    if problematic:
        logger.warning(f"Assets with >10% missing data: {problematic}")

    # Forward fill then backward fill missing values
    price_slice = price_slice.ffill().bfill()

    return price_slice


@router.post("/efficient-frontier", response_model=schemas.EfficientFrontierResponse)
async def calculate_efficient_frontier(request: schemas.OptimizationRequest):
    """
    Calculate the efficient frontier for given assets.

    Returns:
        - Efficient frontier points (return, volatility, weights)
        - Maximum Sharpe ratio portfolio
        - Minimum volatility portfolio
        - Individual asset statistics
    """
    logger.info(
        f"Efficient frontier request: meta_id={request.meta_id}, "
        f"lookback={request.lookback_period}, rf={request.risk_free_rate}"
    )

    try:
        # Get price data
        price = _get_price_data(
            meta_id=request.meta_id,
            start_date=request.start_date,
            end_date=request.end_date,
            lookback_period=request.lookback_period,
        )

        # Calculate expected returns and covariance
        exp_ret = expected_returns(price)
        cov_mat = covariance_matrix(price)

        # Validate weight bounds
        if request.min_weight >= request.max_weight:
            raise HTTPException(status_code=400, detail="min_weight must be less than max_weight")

        # Run optimization
        optimizer = MeanVarianceOptimizer(
            expected_returns=exp_ret,
            cov_matrix=cov_mat,
            risk_free_rate=request.risk_free_rate,
            weight_bounds=(request.min_weight, request.max_weight),
        )

        frontier = optimizer.efficient_frontier(n_points=request.n_points)

        # Build response
        frontier_points = [
            schemas.FrontierPoint(
                return_=p.return_,
                volatility=p.volatility,
                sharpe_ratio=p.sharpe_ratio,
                weights=p.weights,
            )
            for p in frontier.points
        ]

        asset_stats: Dict[str, schemas.AssetStats] = {}
        for ticker in exp_ret.index:
            asset_stats[ticker] = schemas.AssetStats(
                expected_return=float(exp_ret[ticker]),
                volatility=float(cov_mat.loc[ticker, ticker] ** 0.5),
            )

        logger.info(
            f"Efficient frontier calculated: {len(frontier_points)} points, "
            f"max_sharpe={frontier.max_sharpe_portfolio.sharpe_ratio:.4f}"
        )

        return schemas.EfficientFrontierResponse(
            frontier_points=frontier_points,
            max_sharpe=schemas.OptimizedPortfolio(
                weights=frontier.max_sharpe_portfolio.weights,
                expected_return=frontier.max_sharpe_portfolio.expected_return,
                volatility=frontier.max_sharpe_portfolio.volatility,
                sharpe_ratio=frontier.max_sharpe_portfolio.sharpe_ratio,
                risk_contributions=frontier.max_sharpe_portfolio.risk_contributions,
            ),
            min_volatility=schemas.OptimizedPortfolio(
                weights=frontier.min_volatility_portfolio.weights,
                expected_return=frontier.min_volatility_portfolio.expected_return,
                volatility=frontier.min_volatility_portfolio.volatility,
                sharpe_ratio=frontier.min_volatility_portfolio.sharpe_ratio,
                risk_contributions=frontier.min_volatility_portfolio.risk_contributions,
            ),
            asset_stats=asset_stats,
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Optimization value error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Efficient frontier calculation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")


@router.post("/risk-parity", response_model=schemas.RiskParityResponse)
async def calculate_risk_parity(request: schemas.OptimizationRequest):
    """
    Calculate risk parity portfolio.

    Risk parity allocates weights so each asset contributes
    equally to the total portfolio risk.

    Returns:
        Portfolio weights and metrics with equal risk contributions
    """
    logger.info(
        f"Risk parity request: meta_id={request.meta_id}, " f"lookback={request.lookback_period}"
    )

    try:
        # Get price data
        price = _get_price_data(
            meta_id=request.meta_id,
            start_date=request.start_date,
            end_date=request.end_date,
            lookback_period=request.lookback_period,
        )

        # Calculate expected returns and covariance
        exp_ret = expected_returns(price)
        cov_mat = covariance_matrix(price)

        # Run optimization
        optimizer = RiskParityOptimizer(
            expected_returns=exp_ret,
            cov_matrix=cov_mat,
            risk_free_rate=request.risk_free_rate,
            min_weight=max(request.min_weight, 0.01),  # Ensure minimum 1%
        )

        result = optimizer.optimize()

        logger.info(
            f"Risk parity calculated: vol={result.volatility:.4f}, "
            f"sharpe={result.sharpe_ratio:.4f}"
        )

        return schemas.RiskParityResponse(
            weights=result.weights,
            expected_return=result.expected_return,
            volatility=result.volatility,
            sharpe_ratio=result.sharpe_ratio,
            risk_contributions=result.risk_contributions,
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Risk parity value error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Risk parity calculation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")


@router.post("/max-sharpe", response_model=schemas.OptimizedPortfolio)
async def calculate_max_sharpe(request: schemas.OptimizationRequest):
    """
    Calculate maximum Sharpe ratio portfolio only.

    Faster than full efficient frontier when only the optimal portfolio is needed.
    """
    logger.info(f"Max Sharpe request: meta_id={request.meta_id}")

    try:
        price = _get_price_data(
            meta_id=request.meta_id,
            start_date=request.start_date,
            end_date=request.end_date,
            lookback_period=request.lookback_period,
        )

        exp_ret = expected_returns(price)
        cov_mat = covariance_matrix(price)

        optimizer = MeanVarianceOptimizer(
            expected_returns=exp_ret,
            cov_matrix=cov_mat,
            risk_free_rate=request.risk_free_rate,
            weight_bounds=(request.min_weight, request.max_weight),
        )

        result = optimizer.max_sharpe()

        return schemas.OptimizedPortfolio(
            weights=result.weights,
            expected_return=result.expected_return,
            volatility=result.volatility,
            sharpe_ratio=result.sharpe_ratio,
            risk_contributions=result.risk_contributions,
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Max Sharpe calculation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")


@router.post("/min-volatility", response_model=schemas.OptimizedPortfolio)
async def calculate_min_volatility(request: schemas.OptimizationRequest):
    """
    Calculate minimum volatility portfolio only.

    Also known as the Global Minimum Variance (GMV) portfolio.
    """
    logger.info(f"Min volatility request: meta_id={request.meta_id}")

    try:
        price = _get_price_data(
            meta_id=request.meta_id,
            start_date=request.start_date,
            end_date=request.end_date,
            lookback_period=request.lookback_period,
        )

        exp_ret = expected_returns(price)
        cov_mat = covariance_matrix(price)

        optimizer = MeanVarianceOptimizer(
            expected_returns=exp_ret,
            cov_matrix=cov_mat,
            risk_free_rate=request.risk_free_rate,
            weight_bounds=(request.min_weight, request.max_weight),
        )

        result = optimizer.min_volatility()

        return schemas.OptimizedPortfolio(
            weights=result.weights,
            expected_return=result.expected_return,
            volatility=result.volatility,
            sharpe_ratio=result.sharpe_ratio,
            risk_contributions=result.risk_contributions,
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Min volatility calculation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")
