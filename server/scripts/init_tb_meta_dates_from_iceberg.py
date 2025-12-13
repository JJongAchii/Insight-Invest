"""
Athena로 min/max 날짜 빠르게 조회 후 PostgreSQL 업데이트
"""

import os
import sys
import time

import boto3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# DB 연결
database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise ValueError("DATABASE_URL 환경변수가 없습니다!")

engine = create_engine(database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

print("=" * 70)
print("🔄 Athena → PostgreSQL 메타데이터 초기화 (빠른 버전)")
print("=" * 70)

# Athena 클라이언트
athena = boto3.client("athena", region_name="ap-northeast-2")
s3_output = "s3://insight-invest-athena-results/"


def run_athena_query(query: str, database: str = "market"):
    """Athena 쿼리 실행"""
    print(f"   쿼리 실행 중...")
    response = athena.start_query_execution(
        QueryString=query,
        QueryExecutionContext={"Database": database},
        ResultConfiguration={"OutputLocation": s3_output},
    )
    query_id = response["QueryExecutionId"]

    # 대기
    for i in range(120):  # 최대 2분
        status_response = athena.get_query_execution(QueryExecutionId=query_id)
        status = status_response["QueryExecution"]["Status"]["State"]

        if status == "SUCCEEDED":
            break
        elif status in ["FAILED", "CANCELLED"]:
            reason = status_response["QueryExecution"]["Status"].get("StateChangeReason", "")
            raise Exception(f"Query {status}: {reason}")

        if i % 5 == 0:
            print(f"   대기 중... ({i}초)")
        time.sleep(1)

    # 결과 조회 (페이지네이션 처리)
    rows = []
    next_token = None
    headers = None

    while True:
        if next_token:
            result_response = athena.get_query_results(
                QueryExecutionId=query_id, NextToken=next_token
            )
        else:
            result_response = athena.get_query_results(QueryExecutionId=query_id)

        # 헤더 (첫 페이지만)
        if headers is None:
            headers = [
                col["Name"]
                for col in result_response["ResultSet"]["ResultSetMetadata"]["ColumnInfo"]
            ]
            result_rows = result_response["ResultSet"]["Rows"][1:]  # 첫 row는 헤더
        else:
            result_rows = result_response["ResultSet"]["Rows"]

        # 데이터
        for row in result_rows:
            row_data = {}
            for i, col in enumerate(row["Data"]):
                row_data[headers[i]] = col.get("VarCharValue")
            rows.append(row_data)

        # 다음 페이지
        next_token = result_response.get("NextToken")
        if not next_token:
            break

    return rows


# US 주식 min/max 조회
print("\n1️⃣ US 주식 min/max 조회 (Athena)...")
us_query = """
SELECT
    meta_id,
    MIN(trade_date) as min_date,
    MAX(trade_date) as max_date
FROM market.us_stocks_price
GROUP BY meta_id
"""

us_results = run_athena_query(us_query)
print(f"   ✅ US 주식: {len(us_results)} 종목")

# KR 주식 min/max 조회
print("\n2️⃣ KR 주식 min/max 조회 (Athena)...")
kr_query = """
SELECT
    meta_id,
    MIN(trade_date) as min_date,
    MAX(trade_date) as max_date
FROM market.kr_stocks_price
GROUP BY meta_id
"""

kr_results = run_athena_query(kr_query)
print(f"   ✅ KR 주식: {len(kr_results)} 종목")

# 통합
all_results = us_results + kr_results

# PostgreSQL 업데이트
print(f"\n3️⃣ PostgreSQL tb_meta 업데이트 중... ({len(all_results)} 종목)")

with SessionLocal() as session:
    updated_count = 0

    for row in all_results:
        sql = text(
            """
            UPDATE tb_meta
            SET min_date = :min_date,
                max_date = :max_date
            WHERE meta_id = :meta_id
        """
        )

        result = session.execute(
            sql,
            {
                "meta_id": int(row["meta_id"]),
                "min_date": row["min_date"],
                "max_date": row["max_date"],
            },
        )

        if result.rowcount > 0:
            updated_count += 1

    session.commit()
    print(f"   ✅ 업데이트 완료: {updated_count} 종목")

# 검증
print("\n4️⃣ 검증 중...")

with SessionLocal() as session:
    result = session.execute(
        text(
            """
        SELECT
            iso_code,
            COUNT(*) as total,
            COUNT(min_date) as has_min,
            COUNT(max_date) as has_max,
            MIN(min_date) as earliest,
            MAX(max_date) as latest
        FROM tb_meta
        GROUP BY iso_code
        ORDER BY iso_code
    """
        )
    )

    print("\n📊 tb_meta 현황:")
    print("=" * 70)
    for row in result:
        print(f"   {row.iso_code}:")
        print(f"      전체: {row.total} 종목")
        print(f"      min_date 있음: {row.has_min} 종목")
        print(f"      max_date 있음: {row.has_max} 종목")
        print(f"      최초 날짜: {row.earliest}")
        print(f"      최신 날짜: {row.latest}")

print("\n" + "=" * 70)
print("🎉 초기화 완료!")
print("=" * 70)
