"""
포트폴리오 백테스팅 결과를 Iceberg 테이블에서 조회하는 모듈
"""

import logging
from typing import List, Optional

import pandas as pd
from module.data_lake.iceberg_client import iceberg_client
from module.etl.config import (
    TABLE_BENCHMARK_METRICS,
    TABLE_BENCHMARK_NAV,
    TABLE_PORTFOLIO_METRICS,
    TABLE_PORTFOLIO_NAV,
    TABLE_PORTFOLIO_REBALANCE,
)
from pyiceberg.expressions import EqualTo

logger = logging.getLogger(__name__)


def get_portfolio_nav(port_id: int) -> pd.DataFrame:
    """
    포트폴리오 NAV를 Iceberg 테이블에서 조회

    Args:
        port_id: 포트폴리오 ID

    Returns:
        DataFrame with columns: [trade_date, value]

    Example:
        >>> nav = get_portfolio_nav(port_id=1)
        >>> print(nav.head())
           trade_date  value
        0  2024-01-01  100.0
        1  2024-01-02  101.0
    """
    try:
        table = iceberg_client.get_table(TABLE_PORTFOLIO_NAV)

        # PyIceberg scan with row_filter (서버사이드 필터링)
        df = table.scan(
            row_filter=EqualTo("port_id", port_id),
            selected_fields=["trade_date", "value"],
        ).to_pandas()

        # Sort
        df = df.sort_values("trade_date")

        logger.info(f"NAV 조회 완료: port_id={port_id}, records={len(df)}")
        return df.reset_index(drop=True)

    except Exception as e:
        logger.error(f"NAV 조회 실패: port_id={port_id}, error={e}", exc_info=True)
        raise


def get_portfolio_rebalance(port_id: int) -> pd.DataFrame:
    """
    포트폴리오 리밸런싱 가중치를 Iceberg 테이블에서 조회

    Args:
        port_id: 포트폴리오 ID

    Returns:
        DataFrame with columns: [rebal_date, port_id, ticker, name, weight]
        (MySQL fallback과 동일한 형식)

    Example:
        >>> rebal = get_portfolio_rebalance(port_id=1)
        >>> print(rebal.head())
          rebal_date  port_id ticker  name      weight
        0 2024-01-01        1    SPY  SPDR...    0.25
        1 2024-01-01        1    QQQ  Invesco..  0.25
    """
    try:
        table = iceberg_client.get_table(TABLE_PORTFOLIO_REBALANCE)

        # PyIceberg scan with row_filter (서버사이드 필터링)
        df = table.scan(
            row_filter=EqualTo("port_id", port_id),
            selected_fields=["rebal_date", "port_id", "ticker", "weight", "meta_id"],
        ).to_pandas()

        if df.empty:
            logger.info(f"Rebalance 조회 완료: port_id={port_id}, records=0")
            return pd.DataFrame(columns=["rebal_date", "port_id", "ticker", "name", "weight"])

        # TbMeta에서 name 조인 (MySQL)
        try:
            import db

            meta_df = db.TbMeta.query_df()
            ticker_to_name = dict(zip(meta_df["ticker"], meta_df["name"]))
            df["name"] = df["ticker"].map(ticker_to_name).fillna("")
        except Exception as e:
            logger.warning(f"TbMeta 조인 실패, name 빈 문자열로 설정: {e}")
            df["name"] = ""

        # Sort
        df = df.sort_values(["rebal_date", "ticker"])

        # MySQL fallback과 동일한 컬럼 순서로 반환
        result_df = df[["rebal_date", "port_id", "ticker", "name", "weight"]]

        logger.info(f"Rebalance 조회 완료: port_id={port_id}, records={len(result_df)}")
        return result_df.reset_index(drop=True)

    except Exception as e:
        logger.error(f"Rebalance 조회 실패: port_id={port_id}, error={e}", exc_info=True)
        raise


def get_portfolio_metrics(port_id: int) -> pd.DataFrame:
    """
    포트폴리오 성과 지표를 Iceberg 테이블에서 조회

    Args:
        port_id: 포트폴리오 ID

    Returns:
        DataFrame with columns: [ann_ret, ann_vol, sharpe, mdd, skew, kurt, var, cvar]

    Example:
        >>> metrics = get_portfolio_metrics(port_id=1)
        >>> print(metrics.iloc[0])
        ann_ret    0.15
        ann_vol    0.20
        sharpe     0.75
        mdd       -0.25
        ...
    """
    try:
        table = iceberg_client.get_table(TABLE_PORTFOLIO_METRICS)

        # PyIceberg scan with row_filter (서버사이드 필터링)
        df = table.scan(
            row_filter=EqualTo("port_id", port_id),
            selected_fields=["ann_ret", "ann_vol", "sharpe", "mdd", "skew", "kurt", "var", "cvar"],
        ).to_pandas()

        logger.info(f"Metrics 조회 완료: port_id={port_id}, records={len(df)}")
        return df.reset_index(drop=True)

    except Exception as e:
        logger.error(f"Metrics 조회 실패: port_id={port_id}, error={e}", exc_info=True)
        raise


def get_all_portfolio_ids() -> List[int]:
    """
    Iceberg에 저장된 모든 포트폴리오 ID 목록 조회

    Returns:
        포트폴리오 ID 리스트
    """
    try:
        table = iceberg_client.get_table(TABLE_PORTFOLIO_NAV)
        df = table.scan(selected_fields=["port_id"]).to_pandas()
        return sorted(df["port_id"].unique().tolist())
    except Exception as e:
        logger.error(f"포트폴리오 ID 목록 조회 실패: {e}", exc_info=True)
        return []


def get_benchmark_nav(port_id: int) -> pd.DataFrame:
    """
    벤치마크 NAV를 Iceberg 테이블에서 조회

    Args:
        port_id: 포트폴리오 ID

    Returns:
        DataFrame with columns: [trade_date, value]

    Example:
        >>> nav = get_benchmark_nav(port_id=1)
        >>> print(nav.head())
           trade_date  value
        0  2024-01-01  100.0
        1  2024-01-02  101.5
    """
    try:
        table = iceberg_client.get_table(TABLE_BENCHMARK_NAV)

        # PyIceberg scan with row_filter (서버사이드 필터링)
        df = table.scan(
            row_filter=EqualTo("port_id", port_id),
            selected_fields=["trade_date", "value"],
        ).to_pandas()

        # Sort
        df = df.sort_values("trade_date")

        logger.info(f"Benchmark NAV 조회 완료: port_id={port_id}, records={len(df)}")
        return df.reset_index(drop=True)

    except Exception as e:
        logger.error(f"Benchmark NAV 조회 실패: port_id={port_id}, error={e}", exc_info=True)
        raise


def get_benchmark_metrics(port_id: int) -> pd.DataFrame:
    """
    벤치마크 성과 지표를 Iceberg 테이블에서 조회

    Args:
        port_id: 포트폴리오 ID

    Returns:
        DataFrame with columns: [ann_ret, ann_vol, sharpe, mdd, skew, kurt, var, cvar]

    Example:
        >>> metrics = get_benchmark_metrics(port_id=1)
        >>> print(metrics.iloc[0])
        ann_ret    0.12
        ann_vol    0.18
        sharpe     0.67
        mdd       -0.30
        ...
    """
    try:
        table = iceberg_client.get_table(TABLE_BENCHMARK_METRICS)

        # PyIceberg scan with row_filter (서버사이드 필터링)
        df = table.scan(
            row_filter=EqualTo("port_id", port_id),
            selected_fields=["ann_ret", "ann_vol", "sharpe", "mdd", "skew", "kurt", "var", "cvar"],
        ).to_pandas()

        logger.info(f"Benchmark Metrics 조회 완료: port_id={port_id}, records={len(df)}")
        return df.reset_index(drop=True)

    except Exception as e:
        logger.error(f"Benchmark Metrics 조회 실패: port_id={port_id}, error={e}", exc_info=True)
        raise
