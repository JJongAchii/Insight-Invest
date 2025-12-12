"""
매크로 데이터 마이그레이션 (PostgreSQL → Iceberg)
"""

import os
import sys
from datetime import date, datetime

from dateutil.relativedelta import relativedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pyarrow as pa
from pyiceberg.catalog import load_catalog
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

print("=" * 70)
print("🚀 매크로 데이터 마이그레이션 (Arrow 네이티브)")
print("=" * 70)

# RDS 연결
database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise ValueError("DATABASE_URL 환경변수가 없습니다!")

rds_engine = create_engine(database_url, connect_args={"sslmode": "require"}, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=rds_engine)

# Iceberg 연결
catalog = load_catalog(
    "glue",
    **{
        "type": "glue",
        "s3.region": "ap-northeast-2",
        "warehouse": "s3://insight-invest-datalake/warehouse",
    },
)
table = catalog.load_table("market.macro_data")

# 마이그레이션 기간 설정
START_DATE = date(1800, 1, 1)
END_DATE = date(2025, 12, 1)

# Arrow 스키마 정의
arrow_schema = pa.schema(
    [
        pa.field("macro_id", pa.int32(), nullable=False),
        pa.field("base_date", pa.date32(), nullable=False),
        pa.field("value", pa.float64(), nullable=True),
        pa.field("fred_series_id", pa.string(), nullable=True),
    ]
)

print(f"\n📅 마이그레이션 기간: {START_DATE} ~ {END_DATE}")
print(f"💾 대상 테이블: market.macro_data")
print("\n" + "=" * 70)

# 월별 배치 처리
current_date = START_DATE
batch_num = 0
total_rows = 0
failed_batches = []

while current_date < END_DATE:
    batch_num += 1
    month_start = current_date
    month_end = current_date + relativedelta(months=1) - relativedelta(days=1)

    try:
        print(f"\n[배치 {batch_num}] {month_start.strftime('%Y-%m')} 처리 중...")

        # PostgreSQL에서 데이터 조회
        with SessionLocal() as session:
            sql = f"""
            SELECT
                d.macro_id,
                d.base_date,
                d.value,
                m.fred as fred_series_id
            FROM tb_macro_data d
            JOIN tb_macro m ON d.macro_id = m.macro_id
            WHERE d.base_date >= '{month_start}'
              AND d.base_date <= '{month_end}'
            ORDER BY d.base_date, d.macro_id
            """

            result = session.execute(text(sql))
            rows = result.fetchall()

        row_count = len(rows)

        if row_count == 0:
            print(f"   ⚠️  데이터 없음 (스킵)")
        else:
            # Arrow Table로 변환
            data = {
                "macro_id": [row[0] for row in rows],
                "base_date": [row[1] for row in rows],
                "value": [row[2] for row in rows],
                "fred_series_id": [row[3] for row in rows],
            }

            arrow_table = pa.table(data, schema=arrow_schema)

            # Iceberg에 쓰기
            table.append(arrow_table)

            total_rows += row_count
            print(f"   ✅ {row_count:,} rows 완료 (누적: {total_rows:,})")

    except Exception as e:
        print(f"   ❌ 에러 발생: {str(e)}")
        failed_batches.append({"month": month_start.strftime("%Y-%m"), "error": str(e)})

    # 다음 월로 이동
    current_date = current_date + relativedelta(months=1)

# 최종 결과
print("\n" + "=" * 70)
print("🎉 마이그레이션 완료!")
print("=" * 70)
print(f"\n총 마이그레이션 rows: {total_rows:,}")
print(f"처리한 배치 수: {batch_num}")
print(f"실패한 배치 수: {len(failed_batches)}")

if failed_batches:
    print("\n⚠️ 실패한 배치:")
    for batch in failed_batches:
        print(f"  - {batch['month']}: {batch['error']}")
else:
    print("\n✅ 모든 배치 성공!")

print("\n💡 Pandas 사용 안 함! 100% Arrow 네이티브!")
