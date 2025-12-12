"""
ETL Step 3: 데이터 적재 (Load)
- Iceberg 테이블에 적재 (Delete + Append)
- tb_meta 업데이트 (min_date, max_date)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/../..")

from datetime import date, datetime, timedelta
from typing import Tuple

import pyarrow as pa
from module.etl.config import TABLE_KR_STOCKS, TABLE_US_STOCKS
from pyiceberg.catalog import load_catalog
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


def load_to_iceberg(
    iso_code: str, arrow_table: pa.Table, target_date: date, database_url: str
) -> int:
    """
    Iceberg 테이블에 적재 + 메타데이터 업데이트

    Args:
        iso_code: "US" 또는 "KR"
        arrow_table: Transform된 데이터
        target_date: 대상 날짜
        database_url: PostgreSQL 연결 URL

    Returns:
        적재된 row 수
    """
    print(f"\n{'='*70}")
    print(f"💾 [{iso_code}] {target_date} 데이터 적재")
    print(f"{'='*70}")

    # 1. Iceberg 카탈로그 연결
    print("\n1️⃣ Iceberg 연결 중...")

    try:
        catalog = load_catalog(
            "glue",
            **{
                "type": "glue",
                "s3.region": "ap-northeast-2",
                "warehouse": "s3://insight-invest-datalake/warehouse",
            },
        )

        table_name = TABLE_US_STOCKS if iso_code == "US" else TABLE_KR_STOCKS
        table = catalog.load_table(table_name)

        print(f"   ✅ {table_name} 연결 완료")

    except Exception as e:
        print(f"   ❌ Iceberg 연결 실패: {e}")
        raise

    # 2. 중복 방지는 Step2에서 완료됨 (skip delete)
    print(f"\n2️⃣ 중복 체크 건너뜀 (Step2에서 처리됨)")
    print(f"   ℹ️  Step2가 이미 신규 데이터만 필터링")

    # 3. 신규 데이터 추가 (실패 시 롤백 불가 - Iceberg 특성)
    print(f"\n3️⃣ 신규 데이터 추가 중...")

    try:
        table.append(arrow_table)
        print(f"   ✅ {len(arrow_table)} rows 추가 완료")
    except Exception as e:
        print(f"   ❌ Iceberg 적재 실패: {e}")
        raise  # 메타데이터 업데이트 방지를 위해 예외 전파

    # 4. tb_meta 업데이트 (실제 적재된 날짜 범위 기준)
    print(f"\n4️⃣ 메타데이터 업데이트 중...")

    try:
        updated_count = update_meta_dates(arrow_table, database_url)
        print(f"   ✅ {updated_count} 종목 업데이트")
    except Exception as e:
        print(f"   ⚠️  메타데이터 업데이트 실패: {e}")
        print(f"   ℹ️  Iceberg 데이터는 적재되었으나 메타데이터 불일치 가능")
        # 메타데이터 실패해도 적재는 성공으로 처리

    return len(arrow_table)


def update_meta_dates(arrow_table: pa.Table, database_url: str) -> int:
    """
    tb_meta의 min_date, max_date 업데이트 (종목별 실제 날짜 범위 기준)

    Returns:
        업데이트된 종목 수
    """
    import pandas as pd

    # Arrow Table에서 종목별 날짜 범위 계산
    df = arrow_table.select(["meta_id", "trade_date"]).to_pandas()

    if df.empty:
        return 0

    # 종목별 min/max 날짜
    date_ranges = df.groupby("meta_id")["trade_date"].agg(["min", "max"]).reset_index()
    date_ranges.columns = ["meta_id", "min_date", "max_date"]

    engine = create_engine(database_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine)

    updated_count = 0
    failed_count = 0

    with SessionLocal() as session:
        try:
            # 종목별로 업데이트 (실제 날짜 범위 반영)
            for _, row in date_ranges.iterrows():
                try:
                    meta_id = int(row["meta_id"])

                    # date 객체로 변환
                    if hasattr(row["min_date"], "date"):
                        min_dt = row["min_date"].date()
                    else:
                        min_dt = row["min_date"]

                    if hasattr(row["max_date"], "date"):
                        max_dt = row["max_date"].date()
                    else:
                        max_dt = row["max_date"]

                    sql = text(
                        """
                        UPDATE tb_meta
                        SET
                            min_date = CASE
                                WHEN min_date IS NULL THEN :min_date
                                ELSE LEAST(min_date, :min_date)
                            END,
                            max_date = CASE
                                WHEN max_date IS NULL THEN :max_date
                                ELSE GREATEST(max_date, :max_date)
                            END
                        WHERE meta_id = :meta_id
                    """
                    )

                    result = session.execute(
                        sql, {"meta_id": meta_id, "min_date": min_dt, "max_date": max_dt}
                    )
                    updated_count += result.rowcount

                except Exception as e:
                    print(f"      ⚠️  meta_id {row['meta_id']} 업데이트 실패: {str(e)[:50]}...")
                    failed_count += 1
                    continue

            session.commit()

        except Exception as e:
            session.rollback()
            print(f"   ❌ 트랜잭션 실패: {e}")
            raise

    engine.dispose()

    if failed_count > 0:
        print(f"   ⚠️  {failed_count} 종목 업데이트 실패")

    return updated_count


if __name__ == "__main__":
    """
    테스트 실행
    """
    print("=" * 70)
    print("🚀 Step 3: Load (테스트)")
    print("=" * 70)

    # Step 2에서 Transform된 데이터 받아야 함
    # 여기서는 직접 테스트 불가 (daily_etl.py에서 통합 실행)

    print("\n⚠️  Step 3는 daily_etl.py에서 Step 2 결과와 함께 실행됩니다.")
    print("   단독 테스트는 불가능합니다.")
