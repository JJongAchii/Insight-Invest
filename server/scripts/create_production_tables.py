"""
프로덕션 Iceberg 테이블 생성
- market.us_stocks_price
- market.kr_stocks_price
- market.macro_data
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from pyiceberg.catalog import load_catalog
from pyiceberg.partitioning import PartitionField, PartitionSpec
from pyiceberg.schema import Schema
from pyiceberg.transforms import MonthTransform, YearTransform
from pyiceberg.types import (
    DateType,
    DoubleType,
    IntegerType,
    LongType,
    NestedField,
    StringType,
    TimestampType,
)

print("=" * 60)
print("🚀 프로덕션 Iceberg 테이블 생성")
print("=" * 60)

# Glue Catalog 연결
print("\n📦 AWS Glue Catalog 연결 중...")
catalog = load_catalog(
    "glue",
    **{
        "type": "glue",
        "s3.region": "ap-northeast-2",
        "warehouse": "s3://insight-invest-datalake/warehouse",
    },
)
print("✅ 연결 성공!")


# 테이블 생성 함수
def create_table_if_not_exists(table_name, schema, partition_spec, description=""):
    """테이블이 없으면 생성"""
    try:
        table = catalog.load_table(table_name)
        print(f"ℹ️  {table_name} - 이미 존재함")
        return table
    except:
        table = catalog.create_table(
            identifier=table_name,
            schema=schema,
            partition_spec=partition_spec,
            properties={
                "write.format.default": "parquet",
                "write.parquet.compression-codec": "zstd",
                "write.parquet.row-group-size": "134217728",  # 128 MB
            },
        )
        print(f"✅ {table_name} - 생성 완료!")
        print(f"   위치: {table.location()}")
        if description:
            print(f"   설명: {description}")
        return table


# 1. US 주식 가격 테이블
print("\n1️⃣ market.us_stocks_price 생성 중...")
us_price_schema = Schema(
    NestedField(1, "meta_id", IntegerType(), required=True),
    NestedField(2, "trade_date", DateType(), required=True),
    NestedField(3, "ticker", StringType(), required=False),
    NestedField(4, "name", StringType(), required=False),
    NestedField(5, "close", DoubleType(), required=False),
    NestedField(6, "adj_close", DoubleType(), required=False),
    NestedField(7, "gross_return", DoubleType(), required=False),
    NestedField(8, "volume", LongType(), required=False),
    NestedField(9, "updated_at", TimestampType(), required=False),
)

us_price_partition = PartitionSpec(
    PartitionField(
        source_id=2, field_id=1000, transform=MonthTransform(), name="trade_month"  # trade_date
    )
)

create_table_if_not_exists(
    "market.us_stocks_price", us_price_schema, us_price_partition, "미국 주식 일별 가격 데이터"
)

# 2. KR 주식 가격 테이블
print("\n2️⃣ market.kr_stocks_price 생성 중...")
kr_price_schema = Schema(
    NestedField(1, "meta_id", IntegerType(), required=True),
    NestedField(2, "trade_date", DateType(), required=True),
    NestedField(3, "ticker", StringType(), required=False),
    NestedField(4, "name", StringType(), required=False),
    NestedField(5, "close", DoubleType(), required=False),
    NestedField(6, "adj_close", DoubleType(), required=False),
    NestedField(7, "gross_return", DoubleType(), required=False),
    NestedField(8, "volume", LongType(), required=False),
    NestedField(9, "updated_at", TimestampType(), required=False),
)

kr_price_partition = PartitionSpec(
    PartitionField(
        source_id=2, field_id=1000, transform=MonthTransform(), name="trade_month"  # trade_date
    )
)

create_table_if_not_exists(
    "market.kr_stocks_price", kr_price_schema, kr_price_partition, "한국 주식 일별 가격 데이터"
)

# 3. 매크로 경제 데이터 테이블
print("\n3️⃣ market.macro_data 생성 중...")
macro_schema = Schema(
    NestedField(1, "macro_id", IntegerType(), required=True),
    NestedField(2, "base_date", DateType(), required=True),
    NestedField(3, "value", DoubleType(), required=False),
    NestedField(4, "fred_series_id", StringType(), required=False),
    NestedField(5, "updated_at", TimestampType(), required=False),
)

macro_partition = PartitionSpec(
    PartitionField(
        source_id=2, field_id=1000, transform=MonthTransform(), name="base_month"  # base_date
    )
)

create_table_if_not_exists(
    "market.macro_data", macro_schema, macro_partition, "매크로 경제 지표 데이터"
)

# 4. 포트폴리오 NAV 테이블
print("\n4️⃣ portfolio.tb_nav 생성 중...")
nav_schema = Schema(
    NestedField(1, "trade_date", DateType(), required=True),
    NestedField(2, "port_id", IntegerType(), required=True),
    NestedField(3, "value", DoubleType(), required=True),
    NestedField(4, "updated_at", TimestampType(), required=False),
)

nav_partition = PartitionSpec(
    PartitionField(
        source_id=1, field_id=1000, transform=MonthTransform(), name="trade_month"  # trade_date
    )
)

create_table_if_not_exists("portfolio.nav", nav_schema, nav_partition, "포트폴리오 순자산 가치")

# 5. 리밸런싱 테이블
print("\n5️⃣ portfolio.tb_rebalance 생성 중...")
rebalance_schema = Schema(
    NestedField(1, "rebal_date", DateType(), required=True),
    NestedField(2, "port_id", IntegerType(), required=True),
    NestedField(3, "meta_id", IntegerType(), required=True),
    NestedField(4, "weight", DoubleType(), required=True),
    NestedField(5, "updated_at", TimestampType(), required=False),
)

rebalance_partition = PartitionSpec(
    PartitionField(
        source_id=1, field_id=1000, transform=YearTransform(), name="rebal_year"  # rebal_date
    )
)

create_table_if_not_exists(
    "portfolio.rebalance", rebalance_schema, rebalance_partition, "포트폴리오 리밸런싱 가중치"
)

print("\n" + "=" * 60)
print("🎉 모든 프로덕션 테이블 생성 완료!")
print("=" * 60)
print("\n📋 생성된 테이블:")
print("  1. market.us_stocks_price (월별 파티션)")
print("  2. market.kr_stocks_price (월별 파티션)")
print("  3. market.macro_data (월별 파티션)")
print("  4. portfolio.tb_nav (월별 파티션)")
print("  5. portfolio.tb_rebalance (연별 파티션)")
