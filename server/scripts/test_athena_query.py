"""
Athena로 Iceberg 테이블 쿼리 테스트
"""

import time

import boto3

print("=" * 60)
print("🔍 Athena 쿼리 테스트")
print("=" * 60)

# 1. Athena 클라이언트 생성
print("\n1️⃣ Athena 클라이언트 연결 중...")
athena = boto3.client("athena", region_name="ap-northeast-2")
print("✅ Athena 연결 성공!")

# 2. 쿼리 실행
print("\n2️⃣ SQL 쿼리 실행 중...")

sql = """
SELECT
    meta_id,
    trade_date,
    ticker,
    adj_close
FROM market.test_price
ORDER BY trade_date, meta_id
"""

response = athena.start_query_execution(
    QueryString=sql,
    QueryExecutionContext={"Database": "market"},
    ResultConfiguration={"OutputLocation": "s3://insight-invest-athena-results/"},
)

query_id = response["QueryExecutionId"]
print(f"✅ 쿼리 제출 완료! (ID: {query_id})")

# 3. 쿼리 완료 대기
print("\n3️⃣ 쿼리 실행 대기 중...")
for i in range(30):
    status = athena.get_query_execution(QueryExecutionId=query_id)
    state = status["QueryExecution"]["Status"]["State"]

    if state == "SUCCEEDED":
        print("✅ 쿼리 실행 성공!")

        # 실행 통계
        stats = status["QueryExecution"]["Statistics"]
        print(f"\n📊 실행 통계:")
        print(f"   데이터 스캔: {stats.get('DataScannedInBytes', 0) / 1024:.2f} KB")
        print(f"   실행 시간: {stats.get('EngineExecutionTimeInMillis', 0) / 1000:.2f}초")
        break
    elif state in ["FAILED", "CANCELLED"]:
        reason = status["QueryExecution"]["Status"].get("StateChangeReason", "Unknown")
        print(f"❌ 쿼리 실패: {reason}")
        exit(1)

    time.sleep(1)
    print(f"   대기 중... ({i+1}초)")

# 4. 결과 조회
print("\n4️⃣ 결과 조회 중...")
result = athena.get_query_results(QueryExecutionId=query_id)

# 컬럼명
columns = [col["Label"] for col in result["ResultSet"]["ResultSetMetadata"]["ColumnInfo"]]
print(f"\n📋 컬럼: {', '.join(columns)}")

# 데이터 (첫 번째 row는 헤더이므로 제외)
rows = result["ResultSet"]["Rows"][1:]
print(f"\n📊 결과 ({len(rows)} rows):")
print("-" * 60)

for row in rows:
    values = [field.get("VarCharValue", "NULL") for field in row["Data"]]
    print("  " + " | ".join(values))

print("\n" + "=" * 60)
print("🎉 Athena 쿼리 테스트 완료!")
print("=" * 60)
