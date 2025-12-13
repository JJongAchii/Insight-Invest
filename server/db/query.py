import logging

import pandas as pd
import sqlalchemy as sa
from sqlalchemy.orm import Query

from .client import session_local
from .models import *

logger = logging.getLogger(__name__)


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

    # MySQL에 저장
    result = TbRebalance.insert(rebal_w)

    # Iceberg에도 저장
    try:
        from module.data_lake.portfolio_writer import save_rebalance_to_iceberg

        save_rebalance_to_iceberg(port_id=port_id, weights=weights)
        logger.info(f"Rebalance saved to both MySQL and Iceberg: port_id={port_id}")
    except Exception as e:
        logger.error(f"Failed to save Rebalance to Iceberg: {e}", exc_info=True)
        # MySQL 저장은 성공했으므로 에러를 발생시키지 않음

    return result


def upload_nav(
    port_name: str,
    nav: pd.Series,
):
    port_id = TbPortfolio.query(port_name=port_name).first().port_id
    value = nav.reset_index()
    value.columns = ["trade_date", "value"]
    value["port_id"] = port_id

    # MySQL에 저장
    result = TbNav.insert(value)

    # Iceberg에도 저장
    try:
        from module.data_lake.portfolio_writer import save_nav_to_iceberg

        save_nav_to_iceberg(port_id=port_id, nav=nav)
        logger.info(f"NAV saved to both MySQL and Iceberg: port_id={port_id}")
    except Exception as e:
        logger.error(f"Failed to save NAV to Iceberg: {e}", exc_info=True)
        # MySQL 저장은 성공했으므로 에러를 발생시키지 않음

    return result


def upload_metrics(
    port_name: str,
    metrics: pd.DataFrame,
):
    port_id = TbPortfolio.query(port_name=port_name).first().port_id
    metrics.columns = [
        "strategy",
        "ann_ret",
        "ann_vol",
        "sharpe",
        "mdd",
        "skew",
        "kurt",
        "var",
        "cvar",
    ]
    metrics["port_id"] = port_id

    # MySQL에 저장
    result = TbMetrics.insert(metrics)

    # Iceberg에도 저장
    try:
        from module.data_lake.portfolio_writer import save_metrics_to_iceberg

        # DataFrame을 딕셔너리로 변환 (첫 번째 row만 사용)
        metrics_dict = metrics.iloc[0][
            ["ann_ret", "ann_vol", "sharpe", "mdd", "skew", "kurt", "var", "cvar"]
        ].to_dict()
        save_metrics_to_iceberg(port_id=port_id, metrics=metrics_dict)
        logger.info(f"Metrics saved to both MySQL and Iceberg: port_id={port_id}")
    except Exception as e:
        logger.error(f"Failed to save Metrics to Iceberg: {e}", exc_info=True)
        # MySQL 저장은 성공했으므로 에러를 발생시키지 않음

    return result


def get_port_summary():
    with session_local() as session:
        query = (
            session.query(
                TbPortfolio.port_id,
                TbPortfolio.port_name,
                TbStrategy.strategy_name,
                TbMetrics.ann_ret,
                TbMetrics.ann_vol,
                TbMetrics.sharpe,
            )
            .join(TbStrategy, TbStrategy.strategy_id == TbPortfolio.strategy_id)
            .join(TbMetrics, TbMetrics.port_id == TbPortfolio.port_id)
        )

        return read_sql_query(query=query)


def get_monthly_nav():
    with session_local() as session:
        subq = (
            session.query(
                TbNav.port_id,
                sa.func.extract("year", TbNav.trade_date).label("year"),
                sa.func.extract("month", TbNav.trade_date).label("month"),
                sa.func.max(TbNav.trade_date).label("last_trade_date"),
            )
            .group_by("year", "month", TbNav.port_id)
            .subquery()
        )

        query = (
            session.query(TbNav.port_id, TbNav.trade_date, TbNav.value)
            .join(
                subq,
                sa.and_(
                    subq.c.last_trade_date == TbNav.trade_date, subq.c.port_id == TbNav.port_id
                ),
            )
            .order_by(subq.c.year, subq.c.month)
        )

        return read_sql_query(query=query)


def get_port_id_info(port_id: int):
    with session_local() as session:
        query = (
            session.query(
                TbPortfolio.port_id,
                TbPortfolio.port_name,
                TbStrategy.strategy_name,
                TbMetrics.ann_ret,
                TbMetrics.ann_vol,
                TbMetrics.sharpe,
                TbMetrics.mdd,
                TbMetrics.skew,
                TbMetrics.kurt,
                TbMetrics.var,
                TbMetrics.cvar,
            )
            .join(TbStrategy, TbStrategy.strategy_id == TbPortfolio.strategy_id)
            .join(TbMetrics, TbMetrics.port_id == TbPortfolio.port_id)
            .filter(TbPortfolio.port_id == port_id)
        )

        return read_sql_query(query=query)


def get_port_id_rebal(port_id: int):
    with session_local() as session:
        query = (
            session.query(
                TbRebalance.rebal_date,
                TbRebalance.port_id,
                TbMeta.ticker,
                TbMeta.name,
                TbRebalance.weight,
            )
            .join(TbMeta, TbMeta.meta_id == TbRebalance.meta_id)
            .filter(TbRebalance.port_id == port_id)
        )

        return read_sql_query(query=query)


def get_port_start_end_date(port_id: int):
    with session_local() as session:
        query = session.query(
            sa.func.min(TbNav.trade_date).label("start_date"),
            sa.func.max(TbNav.trade_date).label("end_date"),
        ).filter(TbNav.port_id == port_id)

        return read_sql_query(query=query)


def get_last_updated_price(market: str):
    with session_local() as session:
        subq = (
            session.query(
                TbPrice.meta_id, sa.func.max(TbPrice.trade_date).label("max_dt")
            ).group_by(TbPrice.meta_id)
        ).subquery()

        query = (
            session.query(
                TbMeta.meta_id,
                TbMeta.ticker,
                TbMeta.iso_code,
                subq.c.max_dt,
                TbPrice.adj_close,
            )
            .outerjoin(subq, subq.c.meta_id == TbMeta.meta_id)
            .outerjoin(
                TbPrice,
                sa.and_(TbPrice.meta_id == TbMeta.meta_id, TbPrice.trade_date == subq.c.max_dt),
            )
            .filter(TbMeta.iso_code == market)
        )

        data = read_sql_query(query=query)

    return data


def get_last_updated_macro():
    with session_local() as session:
        subq = (
            session.query(
                TbMacroData.macro_id, sa.func.max(TbMacroData.base_date).label("max_dt")
            ).group_by(TbMacroData.macro_id)
        ).subquery()

        query = (
            session.query(
                TbMacro.macro_id,
                TbMacro.fred,
                subq.c.max_dt,
            )
            .outerjoin(subq, subq.c.macro_id == TbMacro.macro_id)
            .outerjoin(
                TbMacroData,
                sa.and_(
                    TbMacroData.macro_id == TbMacro.macro_id, TbMacroData.base_date == subq.c.max_dt
                ),
            )
        )

        data = read_sql_query(query=query)

    return data


def get_macro_data():
    with session_local() as session:
        query = (
            session.query(
                TbMacroData.base_date,
                TbMacroData.macro_id,
                TbMacro.fred,
                TbMacroData.value,
            )
            .join(TbMacro, TbMacro.macro_id == TbMacroData.macro_id)
            .filter(TbMacroData.base_date >= "1980-01-01")
            .order_by(TbMacroData.base_date)
        )

        return read_sql_query(query=query)
