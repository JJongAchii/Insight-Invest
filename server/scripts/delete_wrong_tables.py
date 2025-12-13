"""
잘못 생성된 market.db의 포트폴리오 테이블 삭제 스크립트
"""

import logging

from module.data_lake.iceberg_client import iceberg_client

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def delete_wrong_tables():
    """
    market.db에 잘못 생성된 포트폴리오 테이블 삭제
    """
    wrong_tables = [
        "market.portfolio_nav",
        "market.portfolio_rebalance",
        "market.portfolio_metrics",
    ]

    for table_name in wrong_tables:
        try:
            if iceberg_client.table_exists(table_name):
                logger.info(f"테이블 {table_name} 삭제 중...")
                iceberg_client.catalog.drop_table(table_name)
                logger.info(f"✅ 테이블 {table_name} 삭제 완료")
            else:
                logger.info(f"테이블 {table_name} 존재하지 않음 - 스킵")
        except Exception as e:
            logger.error(f"❌ 테이블 {table_name} 삭제 실패: {e}", exc_info=True)

    logger.info("=" * 60)
    logger.info("잘못 생성된 테이블 삭제 완료")
    logger.info("=" * 60)


if __name__ == "__main__":
    delete_wrong_tables()
