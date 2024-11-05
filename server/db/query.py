import pandas as pd
from sqlalchemy.orm import Query

from .client import session_local
from .models import *


def read_sql_query(query: Query, **kwargs) -> pd.DataFrame:
    """Read sql query

    Args:
        query (Query): sqlalchemy.Query

    Returns:
        pd.DataFrame: read the query into dataframe.
    """
    return pd.read_sql_query(
        sql=query.statement,
        con=query.session.bind,
        index_col=kwargs.get("index_col", None),
        parse_dates=kwargs.get("parse_dates", None),
    )

def get_meta_mapper() -> dict:
    mapper = {}

    with session_local() as session:
        query = session.query(TbMeta.ticker, TbMeta.meta_id)

        for rec in query.all():
            mapper[rec.ticker] = rec.meta_id

    return mapper

def create_portfolio(
    port_name: str,
    algorithm: str,
):
    strategy_id = TbStrategy.query(strategy=algorithm).first().strategy_id
    portfolio = {
        "port_name": port_name,
        "strategy_id": strategy_id,
    }
    
    return TbPortfolio.insert(portfolio)

def upload_universe(
    port_name: str,
    tickers: list,
):
    port_id = TbPortfolio.query(port_name=port_name).first().port_id
    universe = [{"port_id": port_id, "meta_id": ticker} for ticker in tickers]
    
    return TbUniverse.insert(universe)

def upload_rebalance(
    port_name: str,
    weights: pd.DataFrame,
):
    port_id = TbPortfolio.query(port_name=port_name).first().port_id
    
    rebal_w = weights.stack().reset_index()
    rebal_w.columns = ["rebal_date", "ticker", "weight"]
    rebal_w["meta_id"] = rebal_w.ticker.map(get_meta_mapper())
    rebal_w["port_id"] = port_id
    
    return TbRebalance.insert(rebal_w)

def upload_nav(
    port_name: str,
    nav: pd.Series,
):
    port_id = TbPortfolio.query(port_name=port_name).first().port_id
    value = nav.reset_index()
    value.columns = ["trade_date", "value"]
    value["port_id"] = port_id
    
    return TbNav.insert(value)
    
def upload_metrics(
    port_name: str,
    metrics: pd.DataFrame,
):
    port_id = TbPortfolio.query(port_name=port_name).first().port_id
    metrics.columns = ["strategy", "ann_ret", "ann_vol", "sharpe", "mdd", "skew", "kurt", "var", "cvar"]
    metrics["port_id"] = port_id
    
    return TbMetrics.insert(metrics)