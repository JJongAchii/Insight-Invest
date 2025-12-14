from datetime import date
from typing import Optional, Tuple, Union

import pandas as pd
import polars as pl

from . import metrics


def resample_data(price: pd.DataFrame, freq: str = "M", type: str = "head") -> pd.DataFrame:
    """
    Resample daily price data to monthly or yearly frequency.

    Uses Polars internally for better performance on large datasets.

    Args:
        price: Daily price DataFrame (index: date, columns: tickers)
        freq: Frequency - "M" for monthly, "Y" for yearly
        type: "head" for first day of period, "tail" for last day

    Returns:
        Resampled DataFrame with first/last day of each period
    """
    # Convert pandas to polars (reset index to get date as column)
    df_reset = price.reset_index()
    date_col = df_reset.columns[0]  # Get the date column name (could be 'index' or other)
    pl_df = pl.from_pandas(df_reset)

    # Rename date column for consistency
    pl_df = pl_df.rename({date_col: "trade_date"})

    # Ensure trade_date is Date type
    if pl_df["trade_date"].dtype == pl.String:
        pl_df = pl_df.with_columns(pl.col("trade_date").str.to_date())
    elif pl_df["trade_date"].dtype == pl.Datetime:
        pl_df = pl_df.with_columns(pl.col("trade_date").dt.date())

    # Add year and month columns for grouping
    pl_df = pl_df.with_columns(
        [
            pl.col("trade_date").dt.year().alias("_year"),
            pl.col("trade_date").dt.month().alias("_month"),
        ]
    )

    # Get first or last row per year-month group
    if type == "head":
        res_df = pl_df.group_by(["_year", "_month"]).first().sort("trade_date")
    elif type == "tail":
        res_df = pl_df.group_by(["_year", "_month"]).last().sort("trade_date")
    else:
        raise ValueError(f"type must be 'head' or 'tail', got '{type}'")

    # Handle yearly frequency
    if freq == "Y":
        max_date_row = res_df.tail(1)  # Keep last row
        if type == "head":
            res_df = res_df.filter(pl.col("_month") == 1)
        elif type == "tail":
            res_df = res_df.filter(pl.col("_month") == 12)
        # Concat max_date_row if not already included
        res_df = pl.concat([res_df, max_date_row]).unique(subset=["trade_date"]).sort("trade_date")

    # Remove helper columns and convert back to pandas
    res_df = res_df.drop(["_year", "_month"])
    res_pd = res_df.to_pandas()

    # Restore original index structure
    res_pd = res_pd.set_index("trade_date")
    res_pd.index = pd.to_datetime(res_pd.index)

    return res_pd


def store_nav_results(func):
    """Decorator for storing nav results"""
    weights_results = {}
    nav_results = {}
    metrics_results = {}

    def wrapper(
        weight: pd.DataFrame,
        strategy_name: Optional[str] = None,
        price: Optional[pd.DataFrame] = None,
        start_date: ... = None,
        end_date: ... = None,
    ):
        weights, nav, metrics = func(weight, price, start_date, end_date)

        if strategy_name:
            params = f"{strategy_name}"
        else:
            params = f"strategy_{wrapper.count}"
            wrapper.count += 1

        weights_results[params] = weights
        nav_results[params] = nav
        metrics_results[params] = metrics

        return weights_results, nav_results, metrics_results

    def delete_strategy(strategy_name: str):
        """Delete a specific strategy by name."""
        if strategy_name in weights_results:
            del weights_results[strategy_name]
        if strategy_name in nav_results:
            del nav_results[strategy_name]
        if strategy_name in metrics_results:
            del metrics_results[strategy_name]

    def clear_strategies():
        """Clear all saved strategies."""
        weights_results.clear()
        nav_results.clear()
        metrics_results.clear()

    wrapper.delete_strategy = delete_strategy
    wrapper.clear_strategies = clear_strategies
    wrapper.count = 1
    return wrapper


def calculate_nav(
    weight: pd.DataFrame,
    price: Optional[pd.DataFrame] = None,
    start_date: Optional[Union[str, pd.Timestamp]] = None,
    end_date: Optional[Union[str, pd.Timestamp]] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Calculate the net asset value (NAV) and portfolio holdings
    based on the provided weight DataFrame and price data.

    Args:
        weight (pd.DataFrame): DataFrame containing the portfolio weights with tickers as columns and dates as index.
        price (Optional[pd.DataFrame], optional): DataFrame containing the price data. Must be provided.
        start_date (Optional[Union[str, pd.Timestamp]], optional): Start date of the analysis. Defaults to the earliest date in the weight DataFrame.
        end_date (Optional[Union[str, pd.Timestamp]], optional): End date of the analysis. Defaults to the latest date in the price data.

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]: A tuple containing the portfolio holdings (book) DataFrame and the NAV (nav) DataFrame.
    """
    if price is None:
        raise ValueError("Price data must be provided.")

    # Ensure the ticker symbols are strings with leading zeros if necessary
    weight.columns = [
        str(column).zfill(6) if isinstance(column, int) else str(column)
        for column in weight.columns
    ]

    # Convert indices to datetime
    weight.index = pd.to_datetime(weight.index)
    price.index = pd.to_datetime(price.index)

    # Determine start and end dates
    start_date = pd.to_datetime(start_date or weight.index.min())
    end_date = pd.to_datetime(end_date or price.index.max())

    # Filter data based on the date range
    weight = weight.loc[start_date:end_date]
    price = price.loc[start_date:end_date]

    if weight.empty:
        raise ValueError("No weight data after filtering by dates.")
    if price.empty:
        raise ValueError("No price data after filtering by dates.")

    # Initialize NAV and book lists
    nav_list = [{"Date": start_date, "value": 1000}]
    book_list = []

    # Get sorted unique rebalancing dates
    rebal_dates = sorted(weight.index.unique())

    nav_value = 1000  # Initial NAV

    for i, rebal_date in enumerate(rebal_dates):
        # Get weights for the rebalancing date
        rebal_weights = weight.loc[rebal_date]
        if isinstance(rebal_weights, pd.DataFrame):
            rebal_weights = rebal_weights.mean()  # Average weights if multiple entries
        rebal_weights = rebal_weights.dropna()

        # Determine the next rebalancing date
        next_rebal = rebal_dates[i + 1] if i + 1 < len(rebal_dates) else end_date

        # Slice price data between rebalancing dates
        price_slice = price.loc[rebal_date:next_rebal, rebal_weights.index]
        if price_slice.empty:
            continue

        # Calculate price relatives
        price_returns = price_slice.div(price_slice.iloc[0])

        # Calculate weighted returns
        weighted_returns = price_returns.multiply(rebal_weights, axis=1)

        # Calculate cash position
        cash = nav_value * (1 - rebal_weights.sum())

        # Calculate portfolio values
        portfolio_values = nav_value * weighted_returns.sum(axis=1) + cash

        # Update NAV list
        nav_value = portfolio_values.iloc[-1]
        nav_list.extend(
            [{"Date": date, "value": val} for date, val in portfolio_values.iloc[1:].items()]
        )

        # Calculate weights over time
        weights_over_time = weighted_returns.div(weighted_returns.sum(axis=1), axis=0).iloc[:-1]
        weights_stacked = weights_over_time.stack().reset_index()
        weights_stacked.columns = ["Date", "ticker", "weights"]
        book_list.append(weights_stacked)

    # Combine all weights and NAV data
    book = pd.concat(book_list, ignore_index=True).set_index("Date")
    nav = pd.DataFrame(nav_list).drop_duplicates("Date").set_index("Date")

    return book, nav


def result_metrics(nav: pd.DataFrame) -> pd.Series:
    """
    Display the performance metrics calculated from the provided DataFrame.

    Args:
        nav (pd.DataFrame): The DataFrame containing the net asset values (NAV) data.
    """
    ann_returns = metrics.ann_returns(nav)
    ann_volatilities = metrics.ann_volatilities(nav)
    sharpe_ratios = metrics.sharpe_ratios(nav)
    max_drawdowns = metrics.max_drawdowns(nav)
    skewness = metrics.skewness(nav)
    kurtosis = metrics.kurtosis(nav)
    value_at_risk = metrics.value_at_risk(nav)
    conditional_value_at_risk = metrics.conditional_value_at_risk(nav)

    # Prepare the data as a dict with numeric values (formatting done on frontend)
    data = {
        "ann_returns": round(ann_returns.values[0] * 100, 2),
        "ann_volatilities": round(ann_volatilities.values[0] * 100, 2),
        "sharpe_ratios": round(sharpe_ratios.values[0], 2),
        "max_drawdowns": round(max_drawdowns.values[0] * 100, 2),
        "skewness": round(skewness.values[0], 2),
        "kurtosis": round(kurtosis.values[0], 2),
        "value_at_risk": round(value_at_risk.values[0] * 100, 2),
        "conditional_value_at_risk": round(conditional_value_at_risk.values[0] * 100, 2),
    }

    # Convert to Series
    metrics_series = pd.Series(data)

    return metrics_series


@store_nav_results
def backtest_result(
    weight: pd.DataFrame,
    price: pd.DataFrame,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    book, nav = calculate_nav(weight=weight, price=price, start_date=start_date, end_date=end_date)

    metrics = result_metrics(nav=nav)

    return weight, nav, metrics
