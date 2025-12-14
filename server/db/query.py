import logging

import pandas as pd
import sqlalchemy as sa
from sqlalchemy.orm import Query

from .client import session_local
from .models import *

# Iceberg 클라이언트 (지연 import로 순환 참조 방지)
_iceberg_client = None


def _get_iceberg_client():
    global _iceberg_client
    if _iceberg_client is None:
        from module.data_lake.iceberg_client import iceberg_client

        _iceberg_client = iceberg_client
    return _iceberg_client


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
        logger.error(f"Iceberg Metrics 조회 실패: {e}")
        # Metrics 없이 반환 (빈 컬럼 추가)
        portfolio_df["ann_ret"] = None
        portfolio_df["ann_vol"] = None
        portfolio_df["sharpe"] = None
        return portfolio_df


def get_monthly_nav():
    """월별 NAV 조회 (Iceberg)"""
    from module.data_lake.iceberg_client import iceberg_client
    from module.etl.config import TABLE_PORTFOLIO_NAV

    table = iceberg_client.get_table(TABLE_PORTFOLIO_NAV)
    nav_df = table.scan(selected_fields=["port_id", "trade_date", "value"]).to_pandas()

    if nav_df.empty:
        return pd.DataFrame(columns=["port_id", "trade_date", "value"])

    # 월별 마지막 거래일 NAV 추출
    nav_df["trade_date"] = pd.to_datetime(nav_df["trade_date"])
    nav_df["year_month"] = nav_df["trade_date"].dt.to_period("M")

    # 각 포트폴리오별 월별 마지막 거래일 찾기
    idx = nav_df.groupby(["port_id", "year_month"])["trade_date"].idxmax()
    monthly_nav = nav_df.loc[idx, ["port_id", "trade_date", "value"]]
    monthly_nav = monthly_nav.sort_values(["port_id", "trade_date"])

    return monthly_nav.reset_index(drop=True)


def get_port_id_info(port_id: int):
    """포트폴리오 메타데이터 조회 (MySQL)

    Note: metrics는 Iceberg에서 별도 조회 (API에서 처리)
    """
    with session_local() as session:
        query = (
            session.query(
                TbPortfolio.port_id,
                TbPortfolio.port_name,
                TbStrategy.strategy_name,
            )
            .join(TbStrategy, TbStrategy.strategy_id == TbPortfolio.strategy_id)
            .filter(TbPortfolio.port_id == port_id)
        )

        return read_sql_query(query=query)


# NOTE: get_port_id_rebal() 제거됨 - Iceberg portfolio_reader.get_portfolio_rebalance() 사용


def get_port_start_end_date(port_id: int):
    """포트폴리오 시작/종료 날짜 조회 (Iceberg)"""
    from module.data_lake.iceberg_client import iceberg_client
    from module.etl.config import TABLE_PORTFOLIO_NAV
    from pyiceberg.expressions import EqualTo

    table = iceberg_client.get_table(TABLE_PORTFOLIO_NAV)
    nav_df = table.scan(
        row_filter=EqualTo("port_id", port_id),
        selected_fields=["trade_date"],
    ).to_pandas()

    if nav_df.empty:
        return pd.DataFrame(columns=["start_date", "end_date"])

    nav_df["trade_date"] = pd.to_datetime(nav_df["trade_date"])
    result = pd.DataFrame(
        {
            "start_date": [nav_df["trade_date"].min()],
            "end_date": [nav_df["trade_date"].max()],
        }
    )
    return result


def get_last_updated_price(market: str):
    """
    종목별 최신 가격 조회 (Iceberg)

    Args:
        market: "US" 또는 "KR"

    Returns:
        DataFrame [meta_id, ticker, iso_code, max_dt, adj_close]
    """
    iceberg = _get_iceberg_client()

    try:
        # Iceberg에서 최신 가격 조회
        latest_prices = iceberg.get_latest_prices(iso_code=market)

        if latest_prices.empty:
            logger.warning(f"Iceberg에서 {market} 가격 데이터를 찾을 수 없습니다")
            return pd.DataFrame(columns=["meta_id", "ticker", "iso_code", "max_dt", "adj_close"])

        # 컬럼명 맞추기 (기존 API 호환)
        latest_prices = latest_prices.rename(columns={"trade_date": "max_dt"})
        latest_prices["iso_code"] = market

        # 컬럼 순서 맞추기
        result = latest_prices[["meta_id", "ticker", "iso_code", "max_dt", "adj_close"]]

        logger.info(f"최신 가격 조회 (Iceberg): {len(result)} 종목 from {market}")
        return result

    except Exception as e:
        logger.error(f"Iceberg 최신 가격 조회 실패: {e}", exc_info=True)
        return pd.DataFrame(columns=["meta_id", "ticker", "iso_code", "max_dt", "adj_close"])


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
