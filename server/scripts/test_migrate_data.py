"""
Pandas 없이 PostgreSQL → Arrow → Iceberg
"""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pyarrow as pa
from pyiceberg.catalog import load_catalog
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

print("=" * 60)
print("🚀 테스트 마이그레이션 (Arrow 네이티브)")
print("=" * 60)

# 1. PostgreSQL에서 데이터 읽기
print("\n1️⃣ PostgreSQL에서 데이터 조회 중...")

# RDS 연결 (Copilot secret 사용 + SSL)
database_url = os.getenv("DATABASE_URL")

if not database_url:
    raise ValueError(
        "DATABASE_URL 환경변수가 없습니다!\n"
        "명령어에 --env-vars DATABASE_URL='...' 옵션을 추가하세요."
    )

# SSL 연결 추가
rds_engine = create_engine(database_url, connect_args={"sslmode": "require"}, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=rds_engine)

end_date = datetime.now().date() - timedelta(days=1000)
start_date = end_date - timedelta(days=30)

print(f"   기간: {start_date} ~ {end_date}")

with SessionLocal() as session:
    sql = f"""
    SELECT
        p.meta_id,
        p.trade_date,
        m.ticker,
        m.name,
        p.close,
        p.adj_close,
        p.gross_return
    FROM tb_price p
    JOIN tb_meta m ON p.meta_id = m.meta_id
    WHERE p.trade_date >= '{start_date}'
      AND p.trade_date <= '{end_date}'
      AND m.iso_code = 'US'
    ORDER BY p.trade_date, p.meta_id
    LIMIT 1000
    """

    result = session.execute(text(sql))
    rows = result.fetchall()

    print(f"✅ PostgreSQL에서 {len(rows)} rows 읽기 완료")

if len(rows) == 0:
    print("\n⚠️ 데이터가 없습니다.")
    exit(0)

# 2. Arrow Table로 직접 변환 (Pandas 없음!)
print("\n2️⃣ Arrow Table로 직접 변환 중...")

# 데이터를 컬럼별로 분리
data = {
    "meta_id": [row[0] for row in rows],
    "trade_date": [row[1] for row in rows],
    "ticker": [row[2] for row in rows],
    "name": [row[3] for row in rows],
    "close": [row[4] for row in rows],
    "adj_close": [row[5] for row in rows],
    "gross_return": [row[6] for row in rows],
}

# Arrow 스키마 정의
arrow_schema = pa.schema(
    [
        pa.field("meta_id", pa.int32(), nullable=False),
        pa.field("trade_date", pa.date32(), nullable=False),
        pa.field("ticker", pa.string(), nullable=True),
        pa.field("name", pa.string(), nullable=True),
        pa.field("close", pa.float64(), nullable=True),
        pa.field("adj_close", pa.float64(), nullable=True),
        pa.field("gross_return", pa.float64(), nullable=True),
    ]
)

# Arrow Table 생성 (Pandas 없음!)
arrow_table = pa.table(data, schema=arrow_schema)

print(f"✅ Arrow Table 생성 완료 ({len(arrow_table)} rows)")
print(f"   메모리 사용: {arrow_table.nbytes / 1024 / 1024:.2f} MB")

# 3. Iceberg에 쓰기
print("\n3️⃣ Iceberg 테이블에 쓰기 중...")

catalog = load_catalog(
    "glue",
    **{
        "type": "glue",
        "s3.region": "ap-northeast-2",
        "warehouse": "s3://insight-invest-datalake/warehouse",
    },
)

table = catalog.load_table("market.us_stocks_price")
table.append(arrow_table)

print(f"✅ Iceberg에 {len(arrow_table)} rows 쓰기 완료!")

# 4. 검증
print("\n4️⃣ 검증 중...")
scan = table.scan()

# Arrow Table로 직접 읽기 (Pandas 없음!)
result_table = scan.to_arrow()

print(f"✅ Iceberg에서 {len(result_table)} rows 읽기 성공!")

# 샘플 출력 (Arrow Table을 직접 출력)
print(f"\n📊 데이터 샘플 (처음 5개):")
print(result_table.slice(0, 5).to_pydict())

print("\n" + "=" * 60)
print("🎉 Arrow 네이티브 마이그레이션 완료!")
print("=" * 60)
print("\n💡 Pandas 사용 안 함! 100% Arrow 네이티브!")
