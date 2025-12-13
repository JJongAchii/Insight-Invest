"""
TbMetrics (MySQL) → portfolio.portfolio_metrics (Iceberg) 마이그레이션 스크립트
"""

import logging
import sys
from pathlib import Path

# Add server directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.client import session_local
from db.models import TbMetrics
from module.data_lake.portfolio_writer import save_metrics_to_iceberg

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def migrate_metrics():
    """
    MySQL TbMetrics 테이블의 모든 데이터를 Iceberg portfolio.portfolio_metrics로 마이그레이션
    """
    with session_local() as session:
        # 모든 metrics 조회
        metrics_records = session.query(TbMetrics).all()

        logger.info(f"총 {len(metrics_records)}개 포트폴리오 Metrics 마이그레이션 시작")

        success_count = 0
        fail_count = 0

        for record in metrics_records:
            port_id = record.port_id

            try:
                # Metrics 딕셔너리 생성
                metrics_dict = {
                    "ann_ret": record.ann_ret,
                    "ann_vol": record.ann_vol,
                    "sharpe": record.sharpe,
                    "mdd": record.mdd,
                    "skew": record.skew,
                    "kurt": record.kurt,
                    "var": record.var,
                    "cvar": record.cvar,
                }

                # Iceberg에 저장
                save_metrics_to_iceberg(port_id=port_id, metrics=metrics_dict)

                logger.info(
                    f"✅ port_id={port_id}: Metrics 마이그레이션 완료 "
                    f"(sharpe={metrics_dict['sharpe']:.3f})"
                )
                success_count += 1

            except Exception as e:
                logger.error(f"❌ port_id={port_id}: 마이그레이션 실패 - {e}", exc_info=True)
                fail_count += 1

        logger.info("=" * 60)
        logger.info(f"Metrics 마이그레이션 완료: 성공={success_count}, 실패={fail_count}")
        logger.info("=" * 60)


if __name__ == "__main__":
    migrate_metrics()
