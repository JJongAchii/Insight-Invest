"""
포트폴리오 백테스팅 결과를 Iceberg 테이블에 저장하는 모듈
"""

import logging
from datetime import datetime
from typing import Dict

import pandas as pd
import pyarrow as pa
from module.data_lake.iceberg_client import iceberg_client
from module.etl.config import (
    PORTFOLIO_METRICS_SCHEMA,
    PORTFOLIO_NAV_SCHEMA,
    PORTFOLIO_REBALANCE_SCHEMA,
    TABLE_PORTFOLIO_METRICS,
    TABLE_PORTFOLIO_NAV,
    TABLE_PORTFOLIO_REBALANCE,
)

logger = logging.getLogger(__name__)


def save_nav_to_iceberg(port_id: int, nav: pd.Series) -> None:
    """
    포트폴리오 NAV를 Iceberg 테이블에 저장

    Args:
        port_id: 포트폴리오 ID
        nav: NAV 시계열 데이터 (index: trade_date, value: nav 값)

    Example:
        >>> nav = pd.Series([100, 101, 102], index=pd.to_datetime(['2024-01-01', '2024-01-02', '2024-01-03']))
        >>> save_nav_to_iceberg(port_id=1, nav=nav)
    """
    try:
        # DataFrame 생성
        df = nav.reset_index()
        df.columns = ["trade_date", "value"]
        df["port_id"] = port_id
        df["updated_at"] = datetime.now()

        # 날짜 타입 변환
        df["trade_date"] = pd.to_datetime(df["trade_date"])

        # Arrow Table 변환
        arrow_table = pa.Table.from_pandas(df, schema=PORTFOLIO_NAV_SCHEMA)

        # Iceberg 적재
        table = iceberg_client.get_table(TABLE_PORTFOLIO_NAV)
        table.append(arrow_table)

        logger.info(
            f"NAV 저장 완료: port_id={port_id}, records={len(df)}, "
            f"date_range={df['trade_date'].min()} ~ {df['trade_date'].max()}"
        )

    except Exception as e:
        logger.error(f"NAV 저장 실패: port_id={port_id}, error={e}", exc_info=True)
        raise


def save_rebalance_to_iceberg(port_id: int, weights: pd.DataFrame) -> None:
    """
    포트폴리오 리밸런싱 가중치를 Iceberg 테이블에 저장

    Args:
        port_id: 포트폴리오 ID
        weights: 리밸런싱 가중치 DataFrame (index: rebal_date, columns: tickers, values: weights)

    Example:
        >>> weights = pd.DataFrame({
        ...     'SPY': [0.25, 0.30],
        ...     'QQQ': [0.25, 0.20],
        ... }, index=pd.to_datetime(['2024-01-01', '2024-02-01']))
        >>> save_rebalance_to_iceberg(port_id=1, weights=weights)
    """
    try:
        # DataFrame reshape (wide → long format)
        rebal_w = weights.stack().reset_index()
        rebal_w.columns = ["rebal_date", "ticker", "weight"]
        rebal_w["port_id"] = port_id
        rebal_w["meta_id"] = 0  # meta_id는 나중에 TbMeta 조인으로 채울 수 있음
        rebal_w["updated_at"] = datetime.now()

        # 날짜 타입 변환
        rebal_w["rebal_date"] = pd.to_datetime(rebal_w["rebal_date"])

        # Arrow Table 변환
        arrow_table = pa.Table.from_pandas(rebal_w, schema=PORTFOLIO_REBALANCE_SCHEMA)

        # Iceberg 적재
        table = iceberg_client.get_table(TABLE_PORTFOLIO_REBALANCE)
        table.append(arrow_table)

        logger.info(
            f"Rebalance 저장 완료: port_id={port_id}, records={len(rebal_w)}, "
            f"date_range={rebal_w['rebal_date'].min()} ~ {rebal_w['rebal_date'].max()}"
        )

    except Exception as e:
        logger.error(f"Rebalance 저장 실패: port_id={port_id}, error={e}", exc_info=True)
        raise


def save_metrics_to_iceberg(port_id: int, metrics: Dict[str, float]) -> None:
    """
    포트폴리오 성과 지표를 Iceberg 테이블에 저장

    Args:
        port_id: 포트폴리오 ID
        metrics: 성과 지표 딕셔너리
            {
                'ann_ret': 연간 수익률,
                'ann_vol': 연간 변동성,
                'sharpe': Sharpe Ratio,
                'mdd': Maximum Drawdown,
                'skew': Skewness,
                'kurt': Kurtosis,
                'var': Value at Risk,
                'cvar': Conditional VaR
            }

    Example:
        >>> metrics = {
        ...     'ann_ret': 0.15,
        ...     'ann_vol': 0.20,
        ...     'sharpe': 0.75,
        ...     'mdd': -0.25,
        ...     'skew': -0.5,
        ...     'kurt': 3.2,
        ...     'var': -0.05,
        ...     'cvar': -0.08
        ... }
        >>> save_metrics_to_iceberg(port_id=1, metrics=metrics)
    """
    try:
        # DataFrame 생성
        df = pd.DataFrame([metrics])
        df["port_id"] = port_id
        df["updated_at"] = datetime.now()

        # 필수 컬럼 확인 및 기본값 설정
        required_cols = ["ann_ret", "ann_vol", "sharpe", "mdd", "skew", "kurt", "var", "cvar"]
        for col in required_cols:
            if col not in df.columns:
                df[col] = None

        # Arrow Table 변환
        arrow_table = pa.Table.from_pandas(df, schema=PORTFOLIO_METRICS_SCHEMA)

        # Iceberg 적재
        table = iceberg_client.get_table(TABLE_PORTFOLIO_METRICS)
        table.append(arrow_table)

        logger.info(
            f"Metrics 저장 완료: port_id={port_id}, "
            f"sharpe={metrics.get('sharpe', None)}, mdd={metrics.get('mdd', None)}"
        )

    except Exception as e:
        logger.error(f"Metrics 저장 실패: port_id={port_id}, error={e}", exc_info=True)
        raise
