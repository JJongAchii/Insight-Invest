"""
첫 번째 Iceberg 테이블 생성 테스트
"""

import os
import sys

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pyiceberg.catalog import load_catalog
from pyiceberg.partitioning import PartitionField, PartitionSpec
from pyiceberg.schema import Schema
from pyiceberg.transforms import MonthTransform
from pyiceberg.types import DateType, DoubleType, IntegerType, NestedField, StringType

print("=" * 60)
print("🚀 Iceberg 테이블 생성 테스트")
print("=" * 60)

# 1. Glue Catalog 연결
print("\n1️⃣ AWS Glue Catalog 연결 중...")
catalog = load_catalog(
    "glue",
    **{
        "type": "glue",
        "s3.region": "ap-northeast-2",
        "warehouse": "s3://insight-invest-datalake/warehouse",
    },
)
print("✅ Glue Catalog 연결 성공!")

# 2. 테스트 테이블 생성
print("\n2️⃣ 테스트 테이블 생성 중...")

table_name = "market.test_price"

# 스키마 정의
schema = Schema(
    NestedField(1, "meta_id", IntegerType(), required=True),
    NestedField(2, "trade_date", DateType(), required=True),
    NestedField(3, "ticker", StringType(), required=False),
    NestedField(4, "adj_close", DoubleType(), required=False),
)

# 파티션 설정 (월별)
partition_spec = PartitionSpec(
    PartitionField(
        source_id=2, field_id=1000, transform=MonthTransform(), name="trade_month"  # trade_date
    )
)

# 테이블 생성
try:
    table = catalog.create_table(
        identifier=table_name,
        schema=schema,
        partition_spec=partition_spec,
        properties={
            "write.format.default": "parquet",
            "write.parquet.compression-codec": "zstd",
        },
    )
    print(f"✅ 테이블 생성 성공: {table_name}")
    print(f"   S3 위치: {table.location()}")

except Exception as e:
    if "already exists" in str(e).lower():
        print(f"ℹ️ 테이블이 이미 존재합니다: {table_name}")
        table = catalog.load_table(table_name)
    else:
        raise

# 3. 테스트 데이터 추가
print("\n3️⃣ 테스트 데이터 추가 중...")

from datetime import date

import pandas as pd
import pyarrow as pa

test_data = pd.DataFrame(
    {
        "meta_id": [1, 1, 2, 2],
        "trade_date": [date(2024, 11, 1), date(2024, 11, 2), date(2024, 11, 1), date(2024, 11, 2)],
        "ticker": ["AAPL", "AAPL", "GOOGL", "GOOGL"],
        "adj_close": [180.5, 182.3, 140.2, 141.8],
    }
)

# Iceberg 스키마에 맞춰 Arrow 스키마 명시
arrow_schema = pa.schema(
    [
        pa.field("meta_id", pa.int32(), nullable=False),  # required int
        pa.field("trade_date", pa.date32(), nullable=False),  # required date
        pa.field("ticker", pa.string(), nullable=True),  # optional string
        pa.field("adj_close", pa.float64(), nullable=True),  # optional double
    ]
)

# 명시적 스키마로 Arrow Table 생성
arrow_table = pa.Table.from_pandas(test_data, schema=arrow_schema)

# Arrow Table로 append
table.append(arrow_table)
print(f"✅ {len(test_data)} rows 추가 완료!")

# 4. 검증
print("\n4️⃣ 데이터 검증 중...")
scan = table.scan()
result_df = scan.to_pandas()
print(f"✅ 테이블에서 읽기 성공: {len(result_df)} rows")
print("\n📊 데이터 샘플:")
print(result_df)

print("\n" + "=" * 60)
print("🎉 테스트 완료! Iceberg 테이블이 정상 작동합니다!")
print("=" * 60)
