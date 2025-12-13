"""
TbRebalance (MySQL) → portfolio.portfolio_rebalance (Iceberg) 마이그레이션 스크립트
"""

import logging
import sys
from pathlib import Path

import pandas as pd

# Add server directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.client import session_local
from db.models import TbMeta, TbRebalance
from module.data_lake.portfolio_writer import save_rebalance_to_iceberg

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def migrate_rebalance():
    """
    MySQL TbRebalance 테이블의 모든 데이터를 Iceberg portfolio.portfolio_rebalance로 마이그레이션
    """
    with session_local() as session:
        # 모든 port_id 조회
        port_ids = session.query(TbRebalance.port_id).distinct().all()
        port_ids = [p[0] for p in port_ids]

        logger.info(f"총 {len(port_ids)}개 포트폴리오 Rebalance 마이그레이션 시작")

        success_count = 0
        fail_count = 0

        for port_id in port_ids:
            try:
                # MySQL에서 Rebalance 조회 (ticker 조인)
                rebal_records = (
                    session.query(
                        TbRebalance.rebal_date,
                        TbMeta.ticker,
                        TbRebalance.weight,
                    )
                    .join(TbMeta, TbMeta.meta_id == TbRebalance.meta_id)
                    .filter(TbRebalance.port_id == port_id)
                    .order_by(TbRebalance.rebal_date, TbMeta.ticker)
                    .all()
                )

                if not rebal_records:
                    logger.warning(f"port_id={port_id}: Rebalance 데이터 없음 - 스킵")
                    continue

                # pandas DataFrame으로 변환 (wide format)
                # index: rebal_date, columns: tickers, values: weights
                rebal_df = pd.DataFrame(
                    [
                        {
                            "rebal_date": r.rebal_date,
                            "ticker": r.ticker,
                            "weight": r.weight,
                        }
                        for r in rebal_records
                    ]
                )

                # Long format → Wide format
                weights = rebal_df.pivot(
                    index="rebal_date", columns="ticker", values="weight"
                ).fillna(0.0)

                # Iceberg에 저장
                save_rebalance_to_iceberg(port_id=port_id, weights=weights)

                logger.info(
                    f"✅ port_id={port_id}: {len(rebal_records)}개 레코드 마이그레이션 완료"
                )
                success_count += 1

            except Exception as e:
                logger.error(f"❌ port_id={port_id}: 마이그레이션 실패 - {e}", exc_info=True)
                fail_count += 1

        logger.info("=" * 60)
        logger.info(f"Rebalance 마이그레이션 완료: 성공={success_count}, 실패={fail_count}")
        logger.info("=" * 60)


if __name__ == "__main__":
    migrate_rebalance()
