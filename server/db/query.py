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
    """포트폴리오 리밸런싱 가중치를 Iceberg에 저장 (MySQL 제거)"""
    port_id = TbPortfolio.query(port_name=port_name).first().port_id

    from module.data_lake.portfolio_writer import save_rebalance_to_iceberg

    save_rebalance_to_iceberg(port_id=port_id, weights=weights)
    logger.info(f"Rebalance saved to Iceberg: port_id={port_id}")

    return port_id


def upload_nav(
    port_name: str,
    nav: pd.Series,
):
    """포트폴리오 NAV를 Iceberg에 저장 (MySQL 제거)"""
    port_id = TbPortfolio.query(port_name=port_name).first().port_id

    from module.data_lake.portfolio_writer import save_nav_to_iceberg

    save_nav_to_iceberg(port_id=port_id, nav=nav)
    logger.info(f"NAV saved to Iceberg: port_id={port_id}")

    return port_id


def upload_metrics(
    port_name: str,
    metrics: pd.DataFrame,
):
    """포트폴리오 성과지표를 Iceberg에 저장 (MySQL 제거)"""
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

    from module.data_lake.portfolio_writer import save_metrics_to_iceberg

    # DataFrame을 딕셔너리로 변환 (첫 번째 row만 사용)
    metrics_dict = metrics.iloc[0][
        ["ann_ret", "ann_vol", "sharpe", "mdd", "skew", "kurt", "var", "cvar"]
    ].to_dict()
    save_metrics_to_iceberg(port_id=port_id, metrics=metrics_dict)
    logger.info(f"Metrics saved to Iceberg: port_id={port_id}")

    return port_id


def get_port_summary():
    """포트폴리오 요약 조회 (MySQL 메타데이터 + Iceberg 성과지표)"""
    # MySQL에서 포트폴리오 메타데이터 조회
    with session_local() as session:
        query = session.query(
            TbPortfolio.port_id,
            TbPortfolio.port_name,
            TbStrategy.strategy_name,
        ).join(TbStrategy, TbStrategy.strategy_id == TbPortfolio.strategy_id)

        portfolio_df = read_sql_query(query=query)

    if portfolio_df.empty:
        return portfolio_df

    # Iceberg에서 성과지표 조회
    try:
        from module.data_lake.iceberg_client import iceberg_client
        from module.etl.config import TABLE_PORTFOLIO_METRICS

        table = iceberg_client.get_table(TABLE_PORTFOLIO_METRICS)
        metrics_df = table.scan(
            selected_fields=["port_id", "ann_ret", "ann_vol", "sharpe"]
        ).to_pandas()

        # 병합
        result = portfolio_df.merge(metrics_df, on="port_id", how="left")
        return result

    except Exception as e:
        logger.warning(f"Iceberg Metrics 조회 실패, MySQL fallback: {e}")
        # MySQL fallback
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
    """월별 NAV 조회 (Iceberg → MySQL fallback)"""
    try:
        from module.data_lake.iceberg_client import iceberg_client
        from module.etl.config import TABLE_PORTFOLIO_NAV

        table = iceberg_client.get_table(TABLE_PORTFOLIO_NAV)
        nav_df = table.scan(selected_fields=["port_id", "trade_date", "value"]).to_pandas()

        if nav_df.empty:
            raise ValueError("No NAV data in Iceberg")

        # 월별 마지막 거래일 NAV 추출
        nav_df["trade_date"] = pd.to_datetime(nav_df["trade_date"])
        nav_df["year_month"] = nav_df["trade_date"].dt.to_period("M")

        # 각 포트폴리오별 월별 마지막 거래일 찾기
        idx = nav_df.groupby(["port_id", "year_month"])["trade_date"].idxmax()
        monthly_nav = nav_df.loc[idx, ["port_id", "trade_date", "value"]]
        monthly_nav = monthly_nav.sort_values(["port_id", "trade_date"])

        return monthly_nav.reset_index(drop=True)

    except Exception as e:
        logger.warning(f"Iceberg NAV 조회 실패, MySQL fallback: {e}")
        # MySQL fallback
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
                        subq.c.last_trade_date == TbNav.trade_date,
                        subq.c.port_id == TbNav.port_id,
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
