from typing import Optional, List, Dict, Tuple
import numpy as np
import pandas as pd



def to_pri_return(price_df: pd.DataFrame) -> pd.DataFrame:
    """calculate price return of asset price dataframe

    Args:
        price_df (pd.DataFrame): _description_

    Returns:
        pd.DataFrame: price return of asset
    """
    return price_df.pct_change()


def to_log_return(price_df: pd.DataFrame) -> pd.DataFrame:
    """calculate logrithmic return of asset price dataframe

    Args:
        price_df (pd.DataFrame): _description_

    Returns:
        pd.DataFrame: logrithmic return of asset
    """
    return to_pri_return(price_df=price_df).apply(np.log1p)


def numofyears(price_df: pd.DataFrame) -> pd.Series:
    """_summary_

    Args:
        price_df (pd.DataFrame): _description_

    Returns:
        pd.Series: _description_
    """
    
    return price_df.count() / 252


def ann_factor(price_df: pd.DataFrame) -> pd.Series:
    """calculate annualization factor for price dataframe.

    Args:
        price_df (pd.DataFrame): _description_

    Returns:
        pd.Series: annualization factor.
    """
    return price_df.count() / numofyears(price_df=price_df)


def cum_returns(price_df: pd.DataFrame) -> pd.Series:
    """calculate cumulative returns of price dataframe.

    Args:
        price_df (pd.DataFrame): _description_

    Returns:
        pd.Series: cumulative return
    """
    return to_pri_return(price_df=price_df).add(1).prod()


def ann_returns(price_df: pd.DataFrame) -> pd.Series:
    return cum_returns(price_df=price_df) ** (
        1 / numofyears(price_df=price_df)
    ) - 1


def ann_variances(price_df: pd.DataFrame) -> pd.Series:
    return to_pri_return(price_df=price_df).var() * ann_factor(price_df=price_df)


def ann_volatilities(price_df: pd.DataFrame) -> pd.Series:
    return ann_variances(price_df=price_df) ** 0.5


def ann_semi_variances(price_df: pd.DataFrame) -> pd.Series:
    pri_return_df = to_pri_return(price_df=price_df)
    return pri_return_df[pri_return_df >= 0].var() * ann_factor(price_df=price_df)


def ann_semi_volatilies(price_df: pd.DataFrame) -> pd.Series:
    return ann_semi_variances(price_df=price_df) ** 0.5


def to_drawdown(price_df: pd.DataFrame) -> pd.DataFrame:
    return price_df / price_df.expanding().max() - 1


def max_drawdowns(price_df: pd.DataFrame) -> pd.Series:
    return to_drawdown(price_df=price_df).min()


def expected_returns(price_df: pd.DataFrame, method: str = "empirical") -> pd.Series:

    if method.lower() == "empirical":
        return ann_returns(price_df=price_df)
    raise ValueError(f"method {method} is not supported.")


def covariance_matrix(
    price_df: pd.DataFrame, method: str = "empirical", **kwargs
) -> pd.DataFrame:

    if method.lower() == "empirical":
        return to_pri_return(price_df=price_df).cov() * ann_factor(price_df=price_df)
    if method.lower() == "exponential":
        return to_pri_return(price_df=price_df).ewm(**kwargs).cov().unstack().iloc[
            -1
        ].unstack() * ann_factor(price_df=price_df)
    raise ValueError(f"method {method} is not supported.")


def sharpe_ratios(price_df: pd.DataFrame, risk_free: float = 0.0) -> pd.Series:

    # return (ann_returns(price_df=price_df) - risk_free) / ann_volatilities(
    #     price_df=price_df
    # )
    return (to_pri_return(price_df=price_df).mean() / to_pri_return(price_df=price_df).std() * (252 ** 0.5))


def sortino_ratios(price_df: pd.DataFrame) -> pd.Series:

    return ann_returns(price_df=price_df) / ann_semi_volatilies(price_df=price_df)


def omega_ratios(price_df: pd.DataFrame, required_retrun: float = 0.0) -> pd.Series:

    period_rr = (1 + required_retrun) ** (1 / numofyears(price_df=price_df)) - 1
    pri_return_df = to_pri_return(price_df=price_df)
    return (
        pri_return_df[pri_return_df >= period_rr].sum()
        / pri_return_df[pri_return_df < period_rr].sum()
    )


def calmar_ratio(price_df: pd.DataFrame) -> pd.Series:

    return ann_returns(price_df=price_df) / abs(max_drawdowns(price_df=price_df))


def tail_ratio(price_df: pd.DataFrame, alpha: float = 0.05) -> pd.Series:

    pri_return_df = to_pri_return(price_df=price_df)
    return pri_return_df.quantile(q=alpha) / pri_return_df.quantile(q=1 - alpha)


def skewness(price_df: pd.DataFrame) -> pd.Series:
    return to_pri_return(price_df=price_df).skew()


def kurtosis(price_df: pd.DataFrame) -> pd.Series:
    return to_pri_return(price_df=price_df).kurt()


def value_at_risk(price_df: pd.DataFrame, alpha: float = 0.05) -> pd.Series:
    return to_pri_return(price_df=price_df).quantile(q=alpha)


def expected_shortfall(price_df: pd.DataFrame, alpha: float = 0.05) -> pd.Series:

    var = value_at_risk(price_df=price_df, alpha=alpha)
    pri_return_df = to_pri_return(price_df=price_df)
    return pri_return_df[pri_return_df <= var].mean()


def conditional_value_at_risk(price_df: pd.DataFrame, alpha: float = 0.05) -> pd.Series:
    return expected_shortfall(price_df=price_df, alpha=alpha)