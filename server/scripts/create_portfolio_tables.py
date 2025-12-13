"""
포트폴리오 Iceberg 테이블 생성 스크립트
"""

import logging

from module.data_lake.iceberg_client import iceberg_client
from module.etl.config import (
    PORTFOLIO_METRICS_SCHEMA,
    PORTFOLIO_NAV_SCHEMA,
    PORTFOLIO_REBALANCE_SCHEMA,
    TABLE_PORTFOLIO_METRICS,
    TABLE_PORTFOLIO_NAV,
    TABLE_PORTFOLIO_REBALANCE,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_portfolio_tables():
    """
    3개의 포트폴리오 Iceberg 테이블 생성:
    - market.portfolio_nav
    - market.portfolio_rebalance
    - market.portfolio_metrics
    """

    tables_to_create = [
        {
            "name": TABLE_PORTFOLIO_NAV,
            "schema": PORTFOLIO_NAV_SCHEMA,
            "partition_spec": None,  # 파티션 없음 (데이터 크기 작음)
            "description": "Portfolio Net Asset Value (NAV) time series",
        },
        {
            "name": TABLE_PORTFOLIO_REBALANCE,
            "schema": PORTFOLIO_REBALANCE_SCHEMA,
            "partition_spec": None,
            "description": "Portfolio rebalancing weights",
        },
        {
            "name": TABLE_PORTFOLIO_METRICS,
            "schema": PORTFOLIO_METRICS_SCHEMA,
            "partition_spec": None,
            "description": "Portfolio performance metrics",
        },
    ]

    for table_config in tables_to_create:
        table_name = table_config["name"]

        # 이미 존재하는지 확인
        if iceberg_client.table_exists(table_name):
            logger.info(f"테이블 {table_name} 이미 존재 - 스킵")
            continue

        # 테이블 생성
        logger.info(f"테이블 {table_name} 생성 중...")
        try:
            table = iceberg_client.create_table(
                table_name=table_name,
                schema=table_config["schema"],
                partition_spec=table_config["partition_spec"],
            )
            logger.info(f"✅ 테이블 {table_name} 생성 완료")
            logger.info(f"   설명: {table_config['description']}")
            logger.info(f"   위치: {table.location()}")
        except Exception as e:
            logger.error(f"❌ 테이블 {table_name} 생성 실패: {e}", exc_info=True)
            raise

    logger.info("=" * 60)
    logger.info("모든 포트폴리오 테이블 생성 완료")
    logger.info("=" * 60)


if __name__ == "__main__":
    create_portfolio_tables()
