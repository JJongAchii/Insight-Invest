"""
레거시 포트폴리오 테이블 삭제 스크립트

TbNav, TbRebalance, TbMetrics 테이블이 Iceberg로 이관되어 삭제됨

실행 방법:
    python scripts/drop_legacy_portfolio_tables.py

주의:
    - 이 스크립트는 데이터를 영구적으로 삭제합니다
    - 실행 전 Iceberg 마이그레이션이 완료되었는지 확인하세요
"""

import logging
import sys
from pathlib import Path

# Add server directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.client import engine
from sqlalchemy import text

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 화이트리스트: 삭제할 테이블 목록 (하드코딩으로 안전)
TABLES_TO_DROP = ["tb_nav", "tb_rebalance", "tb_metrics"]


def confirm_drop():
    """사용자 확인"""
    print("\n" + "=" * 60)
    print("WARNING: 다음 테이블을 삭제합니다:")
    for table in TABLES_TO_DROP:
        print(f"  - {table}")
    print("\n이 작업은 되돌릴 수 없습니다!")
    print("=" * 60 + "\n")

    response = input("계속하시겠습니까? (yes/no): ")
    return response.lower() == "yes"


def drop_tables():
    """테이블 삭제 실행"""
    if not confirm_drop():
        logger.info("작업이 취소되었습니다.")
        return

    with engine.connect() as conn:
        for table in TABLES_TO_DROP:
            # 테이블 이름 검증 (화이트리스트에 있는지 재확인)
            if table not in TABLES_TO_DROP:
                logger.error(f"알 수 없는 테이블: {table}")
                continue

            try:
                # DROP TABLE IF EXISTS는 테이블이 없어도 에러 없이 처리
                conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
                conn.commit()
                logger.info(f"✅ 테이블 삭제 완료: {table}")

            except Exception as e:
                logger.error(f"❌ 테이블 삭제 실패: {table} - {e}")
                raise

    logger.info("\n" + "=" * 60)
    logger.info("모든 레거시 포트폴리오 테이블 삭제 완료")
    logger.info("=" * 60)


if __name__ == "__main__":
    drop_tables()
