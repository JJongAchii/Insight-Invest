"""
TbNav (MySQL) → portfolio.portfolio_nav (Iceberg) 마이그레이션 스크립트
"""

import logging
import sys
from pathlib import Path

import pandas as pd

# Add server directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.client import session_local
from db.models import TbNav
from module.data_lake.portfolio_writer import save_nav_to_iceberg

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def migrate_nav():
    """
    MySQL TbNav 테이블의 모든 데이터를 Iceberg portfolio.portfolio_nav로 마이그레이션
    """
    with session_local() as session:
        # 모든 port_id 조회
        port_ids = session.query(TbNav.port_id).distinct().all()
        port_ids = [p[0] for p in port_ids]

        logger.info(f"총 {len(port_ids)}개 포트폴리오 NAV 마이그레이션 시작")

        success_count = 0
        fail_count = 0

        for port_id in port_ids:
            try:
                # MySQL에서 NAV 조회
                nav_records = (
                    session.query(TbNav.trade_date, TbNav.value)
                    .filter(TbNav.port_id == port_id)
                    .order_by(TbNav.trade_date)
                    .all()
                )

                if not nav_records:
                    logger.warning(f"port_id={port_id}: NAV 데이터 없음 - 스킵")
                    continue

                # pandas Series로 변환 (index: trade_date, value: nav)
                nav_series = pd.Series(
                    [r.value for r in nav_records],
                    index=[r.trade_date for r in nav_records],
                )

                # Iceberg에 저장
                save_nav_to_iceberg(port_id=port_id, nav=nav_series)

                logger.info(f"✅ port_id={port_id}: {len(nav_records)}개 레코드 마이그레이션 완료")
                success_count += 1

            except Exception as e:
                logger.error(f"❌ port_id={port_id}: 마이그레이션 실패 - {e}", exc_info=True)
                fail_count += 1

        logger.info("=" * 60)
        logger.info(f"NAV 마이그레이션 완료: 성공={success_count}, 실패={fail_count}")
        logger.info("=" * 60)


if __name__ == "__main__":
    migrate_nav()
