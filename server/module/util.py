import pandas as pd
from typing import Optional
from datetime import date



def resample_data(price: pd.DataFrame, freq: str = "M", type: str = "head") -> pd.DataFrame:
    """resampling daily data"""
    if type == "head":
        res_price = price.groupby([price.index.year, price.index.month]).head(1)
    elif type == "tail":
        res_price = price.groupby([price.index.year, price.index.month]).tail(1)
    
    if freq == "Y":
        max_date_value = res_price.iloc[-1]
        if type == "head":
            res_price = res_price[res_price.index.month == 1]
        elif type == "tail":
            res_price = res_price[res_price.index.month == 12]
        res_price = res_price.append(max_date_value)
    return res_price


def store_nav_results(func):
    """Decorator for storing nav results"""
    weights_results = {}
    nav_results = {}
    
    def wrapper(
        weight: pd.DataFrame,
        strategy_name: Optional[str] = None,
        price: Optional[pd.DataFrame] = None,
        start_date: ... = None,
        end_date: ... = None,
    ):
        weights, nav = func(weight, price, start_date, end_date)
        
        if strategy_name:
            params = f"{strategy_name}"
        else:
            params = f"strategy_{wrapper.count}"
            wrapper.count += 1

        weights_results[params] = weights
        nav_results[params] = nav
        
        return weights_results, nav_results
    
    def delete_strategy(strategy_name: str):
        """Delete a specific strategy by name."""
        if strategy_name in weights_results:
            del weights_results[strategy_name]
        if strategy_name in nav_results:
            del nav_results[strategy_name]

    def clear_strategies():
        """Clear all saved strategies."""
        weights_results.clear()
        nav_results.clear()
    
    wrapper.delete_strategy = delete_strategy
    wrapper.clear_strategies = clear_strategies
    wrapper.count = 1
    return wrapper


def calculate_nav(
    weight: pd.DataFrame,
    price: Optional[pd.DataFrame] = None,
    fx: Optional[pd.DataFrame] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    currency: ... = None,
) -> pd.DataFrame:
    """
    Calculate the net asset value (NAV) and portfolio holdings 
    based on the provided weight DataFrame and price data.

    Args:
        weight (pd.DataFrame): DataFrame containing the portfolio weights with tickers as columns and dates as index.
        price (Optional[pd.DataFrame], optional): DataFrame containing the price data. Defaults to None, which retrieves prices from a database.
        fx (Optional[pd.DataFrame], optional): DataFrame containing the foreign exchange rates. Defaults to None.
        start_date (Optional[Union[str, pd.Timestamp]], optional): Start date of the analysis. Defaults to None, which uses the earliest date in the weight DataFrame.
        end_date (Optional[Union[str, pd.Timestamp]], optional): End date of the analysis. Defaults to None, which uses the latest date in the price data.
        currency (Optional[str], optional): Currency for converting prices. Defaults to None, which means that either "KRW" or "USD" will be used.

    Returns:
        pd.DataFrame: A tuple containing the portfolio holdings (book) DataFrame and the NAV (nav) DataFrame.
    """
    
    weight.columns = [str(column).zfill(6) if isinstance(column, int) else column for column in weight.columns]
    
    #get price from database within tickers
    # if price is None:
    #     price = db.get_price(tuple(weight.columns))
    
    start_date = start_date or weight.index[0]
    start_date = pd.to_datetime(start_date)
    price.index = pd.to_datetime(price.index)
    weight.index = pd.to_datetime(weight.index)

    
    price = price.loc[start_date:end_date]
    weight = weight.loc[start_date:end_date]
    
    # if currency is not None:
    #     price = price_apply_fx(price=price, fx=fx, currency=currency)
    
    book = pd.DataFrame(columns=["Date", "ticker", "weights"])
    nav = pd.DataFrame([[start_date, 1000]], columns=["Date", "value"])
    
    rebal_list = weight.index.unique()
    
    for i, rebal_date in enumerate(rebal_list):
        
        last_nav = nav.value.iloc[-1]
        
        rebal_weights = weight[weight.index == rebal_date].stack()
        rebal_weights.index = rebal_weights.index.droplevel(0)
        
        if i == len(rebal_list) - 1:
            next_rebal = price.index[-1]
        else:
            next_rebal = rebal_list[i+1]

        price_slice = price[(price.index >= rebal_date) & (price.index <= next_rebal)][rebal_weights.index]
        if price_slice.empty:
            continue
        price_returns = price_slice / price_slice.iloc[0]
        price_weights = price_returns.multiply(rebal_weights, axis=1)
        
        cash = last_nav * (1 - rebal_weights.sum())

        weights = price_weights.div(price_weights.sum(axis=1), axis=0)[:-1]
        value = last_nav * price_weights.sum(axis=1) + cash
        value = value[1:].reset_index()
        value.columns = ["Date", "value"]
        
        weights = weights.stack().reset_index()
        weights.columns = ["Date", "ticker", "weights"]
        
        book = book.append(weights)
        nav = nav.append(value)
        
    book = book.set_index("Date")
    nav = nav.set_index("Date")

    return book, nav


# def result_metrics(nav: pd.DataFrame) -> None:
#     """
#     Display the performance metrics calculated from the provided DataFrame.

#     Args:
#         nav (pd.DataFrame): The DataFrame containing the net asset values (NAV) data.
#     """
#     ann_returns = metrics.ann_returns(nav)
#     ann_volatilities = metrics.ann_volatilities(nav)
#     sharpe_ratios = metrics.sharpe_ratios(nav)
#     max_drawdowns = metrics.max_drawdowns(nav)
#     skewness = metrics.skewness(nav)
#     kurtosis = metrics.kurtosis(nav)
#     value_at_risk = metrics.value_at_risk(nav)
#     conditional_value_at_risk = metrics.conditional_value_at_risk(nav)
    
#     # Prepare the data as a list 
#     data = [
#         ["Annualized Returns", [f"{value * 100:.2f}%" for value in ann_returns.values]],
#         ["Annualized Volatilities", [f"{value * 100:.2f}%" for value in ann_volatilities.values]],
#         ["Sharpe Ratios", [f"{value:.2f}" for value in sharpe_ratios.values]],
#         ["Max DrawDowns", [f"{value * 100:.2f}%" for value in max_drawdowns.values]],
#         ["Skewness", [f"{value:.2f}" for value in skewness.values]],
#         ["Kurtosis", [f"{value:.2f}" for value in kurtosis.values]],
#         ["Value at Risk", [f"{value * 100:.2f}%" for value in value_at_risk.values]],
#         ["Conditional Value at Risk", [f"{value * 100:.2f}%" for value in conditional_value_at_risk.values]]
#     ]
    
#     data = [[label] + values for label, values in data]
#     print(tabulate(data, headers=["Metrics"] + nav.columns.tolist(), tablefmt="fancy_grid"))
    
#     # Plot NAV over time
#     plt.figure(figsize=(10, 6))
#     for column in nav.columns:
#         plt.plot(nav.index, nav[column], label=column)
#     plt.xlabel('Date')
#     plt.ylabel('Net Asset Value (NAV)')
#     plt.title('Net Asset Value Over Time')
#     plt.legend()
#     plt.grid(True)
#     plt.show()
    
#     results = pd.DataFrame({
#         'Ann_Return': [metrics.ann_returns(nav[ticker]) for ticker in nav],
#         'Ann_Volatility': [metrics.ann_volatilities(nav[ticker]) for ticker in nav],
#         'Sharpe_Ratio': [metrics.sharpe_ratios(nav[ticker]) for ticker in nav],
#         'Max_Drawdown': [metrics.max_drawdowns(nav[ticker]) for ticker in nav],
#         'Skewness': [metrics.skewness(nav[ticker]) for ticker in nav],
#         'Kurtosis': [metrics.kurtosis(nav[ticker]) for ticker in nav],
#         'Value_at_Risk': [metrics.value_at_risk(nav[ticker]) for ticker in nav],
#         'Conditional_Value_at_Risk': [metrics.conditional_value_at_risk(nav[ticker]) for ticker in nav]
#     }, index=nav.columns)
    
#     return results


@store_nav_results
def backtest_result(
    weight: pd.DataFrame,
    price: pd.DataFrame,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
):
    book, nav = calculate_nav(
        weight=weight,
        price=price,
        start_date=start_date,
        end_date=end_date
    )
    
    return  weight, nav
    