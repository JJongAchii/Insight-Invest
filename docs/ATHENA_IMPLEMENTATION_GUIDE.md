# AWS Athena 기반 아키텍처 가이드

## 🎯 Athena vs Trino: 재평가

### 당신의 요구사항 다시 보기
1. ✅ Pandas 제거 → Arrow/SQL 기반
2. ✅ 스키마 분산 → 여러 Iceberg 스키마
3. ✅ 크로스 스키마 조인 → SQL로 해결

### 🤔 Athena가 Trino보다 나은 점

| 항목 | Athena | Trino |
|------|--------|-------|
| **인프라 관리** | ✅✅✅ 완전 서버리스 | ❌ ECS 클러스터 관리 필요 |
| **비용** | ✅✅✅ $0.25/월 | ⚠️ $12-42/월 |
| **확장성** | ✅✅✅ 자동 무한 확장 | ⚠️ Worker 수동 조정 |
| **AWS 통합** | ✅✅✅ 네이티브 | ⚠️ 별도 설정 |
| **유지보수** | ✅✅✅ 없음 | ⚠️ 업그레이드, 모니터링 |
| **시작 비용** | ✅✅✅ $0 (사용한 만큼) | ❌ 최소 $12/월 |
| **응답 속도** | ⚠️ 3-5초 (콜드 스타트) | ✅ < 500ms |
| **실시간 쿼리** | ⚠️ 비동기 처리 | ✅ 동기 처리 |

### 💡 결론: **API 패턴에 따라 Athena가 더 나을 수 있음!**

```
실시간 대시보드 (초 단위 응답) → Trino
배치/분석 쿼리 (분 단위 응답) → Athena ⭐
비용 최우선 → Athena ⭐⭐⭐
```

---

## 🏗️ Athena 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│            FastAPI (API Layer)                          │
│  ┌───────────────────────────────────────────┐          │
│  │  import boto3                             │          │
│  │  athena = boto3.client('athena')         │          │
│  │  result = query_athena_async(sql)        │          │
│  └───────────────────────────────────────────┘          │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
      ┌──────────────────────┐
      │   AWS Athena         │
      │   (Serverless)       │
      │                      │
      │  - Query Planning    │
      │  - Auto Scaling      │
      │  - Arrow Format      │
      └──────┬───────────────┘
             │
     ┌───────┴──────────────────┐
     │                          │
     ▼                          ▼
┌─────────────┐        ┌──────────────┐
│  AWS Glue   │        │  S3 Iceberg  │
│  Catalog    │        │  (분산 스키마) │
│             │        │              │
│ - market_   │        │ market_data/ │
│   data      │        │ portfolio/   │
│ - portfolio │        │ analytics/   │
│ - analytics │        │ reference/   │
└─────────────┘        └──────────────┘
```

---

## 💻 Athena 구현 가이드

### 1. Glue Catalog 설정 (스키마 분산)

```bash
# 1. 여러 데이터베이스(스키마) 생성
aws glue create-database --database-input '{
  "Name": "market_data",
  "Description": "Stock market data"
}'

aws glue create-database --database-input '{
  "Name": "portfolio",
  "Description": "Portfolio data"
}'

aws glue create-database --database-input '{
  "Name": "analytics",
  "Description": "Analytics and metrics"
}'

aws glue create-database --database-input '{
  "Name": "reference",
  "Description": "Reference data"
}'
```

### 2. Iceberg 테이블 생성 (각 스키마별)

```python
# server/scripts/create_iceberg_tables_athena.py
import boto3
from pyiceberg.catalog import load_catalog

# Glue Catalog 연결
catalog = load_catalog(
    "glue",
    **{
        "type": "glue",
        "s3.region": "ap-northeast-2",
        "warehouse": "s3://insight-invest-datalake/warehouse"
    }
)

# 1. market_data 스키마의 테이블
def create_market_data_tables():
    """주가 데이터 테이블"""

    # US 주식 가격
    catalog.create_table(
        identifier="market_data.us_stocks_price",
        schema=Schema(
            NestedField(1, "meta_id", IntegerType(), required=True),
            NestedField(2, "trade_date", DateType(), required=True),
            NestedField(3, "close", FloatType()),
            NestedField(4, "adj_close", FloatType()),
            NestedField(5, "gross_return", FloatType()),
        ),
        partition_spec=PartitionSpec(
            PartitionField(
                source_id=2,
                field_id=1000,
                transform=MonthTransform(),
                name="trade_month"
            )
        ),
        properties={
            "write.format.default": "parquet",
            "write.parquet.compression-codec": "zstd",
        }
    )

    # KR 주식 가격
    catalog.create_table(
        identifier="market_data.kr_stocks_price",
        schema=...,  # 동일
        partition_spec=...,
    )

# 2. portfolio 스키마의 테이블
def create_portfolio_tables():
    """포트폴리오 관련 테이블"""

    catalog.create_table(
        identifier="portfolio.tb_nav",
        schema=Schema(
            NestedField(1, "trade_date", DateType(), required=True),
            NestedField(2, "port_id", IntegerType(), required=True),
            NestedField(3, "value", FloatType(), required=True),
        ),
        partition_spec=PartitionSpec(
            PartitionField(
                source_id=1,
                field_id=1000,
                transform=MonthTransform(),
                name="trade_month"
            )
        )
    )

    catalog.create_table(
        identifier="portfolio.tb_rebalance",
        schema=Schema(
            NestedField(1, "rebal_date", DateType(), required=True),
            NestedField(2, "port_id", IntegerType(), required=True),
            NestedField(3, "meta_id", IntegerType(), required=True),
            NestedField(4, "weight", FloatType(), required=True),
        ),
        partition_spec=PartitionSpec(
            PartitionField(
                source_id=1,
                field_id=1000,
                transform=YearTransform(),
                name="rebal_year"
            )
        )
    )

# 3. analytics 스키마의 테이블
def create_analytics_tables():
    """분석 메트릭 테이블"""

    catalog.create_table(
        identifier="analytics.tb_metrics",
        schema=Schema(
            NestedField(1, "port_id", IntegerType(), required=True),
            NestedField(2, "calculation_date", DateType(), required=True),
            NestedField(3, "sharpe", FloatType()),
            NestedField(4, "mdd", FloatType()),
            NestedField(5, "ann_ret", FloatType()),
            NestedField(6, "ann_vol", FloatType()),
        )
    )
```

### 3. Athena 클라이언트 (Python)

```python
# server/db/athena_client.py
import boto3
import time
import pyarrow as pa
import pyarrow.parquet as pq
from typing import List, Dict, Optional
from functools import lru_cache
import os

class AthenaClient:
    """
    Athena 클라이언트 (Arrow 네이티브, Pandas 없음!)
    """

    def __init__(self):
        self.client = boto3.client('athena', region_name='ap-northeast-2')
        self.s3_output = 's3://insight-invest-athena-results/'
        self.database = 'market_data'  # 기본 데이터베이스

    def execute_query(
        self,
        sql: str,
        database: str = None,
        wait: bool = True
    ) -> str:
        """
        Athena 쿼리 실행

        Args:
            sql: SQL 쿼리
            database: 데이터베이스 (스키마)
            wait: 완료 대기 여부

        Returns:
            query_execution_id
        """
        response = self.client.start_query_execution(
            QueryString=sql,
            QueryExecutionContext={
                'Database': database or self.database
            },
            ResultConfiguration={
                'OutputLocation': self.s3_output,
                'EncryptionConfiguration': {
                    'EncryptionOption': 'SSE_S3'
                }
            }
        )

        query_id = response['QueryExecutionId']

        if wait:
            self._wait_for_query(query_id)

        return query_id

    def _wait_for_query(
        self,
        query_id: str,
        max_attempts: int = 60
    ):
        """쿼리 완료 대기 (최대 60초)"""

        for attempt in range(max_attempts):
            response = self.client.get_query_execution(
                QueryExecutionId=query_id
            )

            state = response['QueryExecution']['Status']['State']

            if state == 'SUCCEEDED':
                return
            elif state in ['FAILED', 'CANCELLED']:
                reason = response['QueryExecution']['Status'].get(
                    'StateChangeReason', 'Unknown'
                )
                raise Exception(f"Query {state}: {reason}")

            time.sleep(1)

        raise TimeoutError(f"Query timeout after {max_attempts}s")

    def get_results_arrow(self, query_id: str) -> pa.Table:
        """
        쿼리 결과를 Arrow Table로 반환 (Pandas 없음!)
        """
        # S3에서 결과 파일 경로 가져오기
        response = self.client.get_query_execution(
            QueryExecutionId=query_id
        )

        output_location = response['QueryExecution']['ResultConfiguration']['OutputLocation']

        # S3에서 Parquet 파일 읽기 (Athena는 결과를 Parquet로 저장)
        # Arrow로 직접 읽기!
        import s3fs
        fs = s3fs.S3FileSystem()

        with fs.open(output_location.replace('s3://', ''), 'rb') as f:
            table = pq.read_table(f)

        return table

    def query_to_arrow(self, sql: str, database: str = None) -> pa.Table:
        """
        SQL 실행 → Arrow Table 반환 (원스톱)
        """
        query_id = self.execute_query(sql, database, wait=True)
        return self.get_results_arrow(query_id)

    def query_to_json(self, sql: str, database: str = None) -> List[Dict]:
        """
        SQL 실행 → JSON 반환 (FastAPI용)
        """
        arrow_table = self.query_to_arrow(sql, database)
        return arrow_table.to_pylist()

    def query_to_parquet(
        self,
        sql: str,
        output_path: str,
        database: str = None
    ):
        """
        SQL 실행 → Parquet 저장 (대용량 배치)
        """
        arrow_table = self.query_to_arrow(sql, database)
        pq.write_table(arrow_table, output_path, compression='zstd')


# 싱글톤 인스턴스
@lru_cache(maxsize=1)
def get_athena_client() -> AthenaClient:
    return AthenaClient()
```

### 4. FastAPI 통합 (Pandas 없음!)

```python
# server/app/routers/price_athena.py
from fastapi import APIRouter, Query, HTTPException
from typing import List, Dict
from db.athena_client import get_athena_client

router = APIRouter(prefix="/api/v2/price", tags=["price-v2-athena"])

athena = get_athena_client()


@router.get("/daily")
def get_daily_prices(
    ticker: str,
    start_date: str,
    end_date: str = None,
) -> List[Dict]:
    """
    일별 가격 조회 (Athena + Arrow)
    ✅ Pandas 없음
    ✅ 크로스 스키마 조인 (market_data + reference)
    """

    sql = f"""
    SELECT
        p.trade_date,
        p.close,
        p.adj_close,
        p.gross_return,
        m.ticker,
        m.name,
        m.sector
    FROM market_data.us_stocks_price p
    JOIN reference.tb_meta m
        ON p.meta_id = m.meta_id
    WHERE m.ticker = '{ticker}'
      AND p.trade_date >= DATE '{start_date}'
    """

    if end_date:
        sql += f" AND p.trade_date <= DATE '{end_date}'"

    sql += " ORDER BY p.trade_date"

    # Arrow → JSON (Pandas 없음!)
    return athena.query_to_json(sql, database='market_data')


@router.get("/aggregate")
def get_aggregate_stats(
    tickers: List[str] = Query(...),
    start_date: str = Query(...),
) -> List[Dict]:
    """
    집계 통계 (Athena 분산 처리)
    ✅ Pandas 없음
    ✅ 크로스 스키마 조인
    """

    ticker_list = "','".join(tickers)

    sql = f"""
    SELECT
        m.ticker,
        m.name,
        m.sector,
        COUNT(*) as trading_days,
        AVG(p.adj_close) as avg_price,
        STDDEV(p.adj_close) as price_std,
        AVG(p.gross_return) as avg_return,
        STDDEV(p.gross_return) as volatility,
        MIN(p.adj_close) as min_price,
        MAX(p.adj_close) as max_price
    FROM market_data.us_stocks_price p
    JOIN reference.tb_meta m
        ON p.meta_id = m.meta_id
    WHERE m.ticker IN ('{ticker_list}')
      AND p.trade_date >= DATE '{start_date}'
    GROUP BY m.ticker, m.name, m.sector
    ORDER BY m.ticker
    """

    return athena.query_to_json(sql, database='market_data')


@router.get("/portfolio-performance")
def get_portfolio_performance(
    port_id: int,
    start_date: str,
) -> List[Dict]:
    """
    복잡한 크로스 스키마 조인 (3개 스키마)
    ✅ market_data + portfolio + analytics
    ✅ Athena가 자동 최적화
    """

    sql = f"""
    WITH daily_portfolio AS (
        SELECT
            p.trade_date,
            SUM(p.adj_close * r.weight) as portfolio_value
        FROM market_data.us_stocks_price p
        JOIN portfolio.tb_rebalance r
            ON p.meta_id = r.meta_id
            AND p.trade_date >= r.rebal_date
        WHERE r.port_id = {port_id}
          AND p.trade_date >= DATE '{start_date}'
        GROUP BY p.trade_date
    )
    SELECT
        dp.trade_date,
        dp.portfolio_value,
        n.value as nav_value,
        m.sharpe,
        m.mdd,
        m.ann_ret,
        m.ann_vol
    FROM daily_portfolio dp
    JOIN portfolio.tb_nav n
        ON dp.trade_date = n.trade_date
        AND n.port_id = {port_id}
    LEFT JOIN analytics.tb_metrics m
        ON m.port_id = {port_id}
        AND m.calculation_date = dp.trade_date
    ORDER BY dp.trade_date
    """

    return athena.query_to_json(sql, database='market_data')


@router.get("/cross-market-analysis")
def cross_market_analysis(
    us_ticker: str,
    kr_ticker: str,
    start_date: str,
) -> List[Dict]:
    """
    미국 vs 한국 주식 비교 (크로스 테이블 조인)
    ✅ us_stocks_price + kr_stocks_price 조인
    """

    sql = f"""
    SELECT
        us.trade_date,
        us.adj_close as us_price,
        kr.adj_close as kr_price,
        us.gross_return as us_return,
        kr.gross_return as kr_return,
        CORR(us.gross_return, kr.gross_return) OVER (
            ORDER BY us.trade_date
            ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
        ) as rolling_correlation_20d
    FROM (
        SELECT p.trade_date, p.adj_close, p.gross_return
        FROM market_data.us_stocks_price p
        JOIN reference.tb_meta m ON p.meta_id = m.meta_id
        WHERE m.ticker = '{us_ticker}'
          AND p.trade_date >= DATE '{start_date}'
    ) us
    FULL OUTER JOIN (
        SELECT p.trade_date, p.adj_close, p.gross_return
        FROM market_data.kr_stocks_price p
        JOIN reference.tb_meta m ON p.meta_id = m.meta_id
        WHERE m.ticker = '{kr_ticker}'
          AND p.trade_date >= DATE '{start_date}'
    ) kr
    ON us.trade_date = kr.trade_date
    ORDER BY us.trade_date
    """

    return athena.query_to_json(sql, database='market_data')
```

### 5. 비동기 쿼리 패턴 (3-5초 지연 해결)

```python
# server/app/routers/price_athena_async.py
from fastapi import APIRouter, BackgroundTasks, HTTPException
from typing import Dict
import uuid
from db.athena_client import get_athena_client

router = APIRouter(prefix="/api/v2/query", tags=["async-query"])

athena = get_athena_client()

# 쿼리 결과 캐시 (Redis 또는 메모리)
query_cache: Dict[str, Dict] = {}


@router.post("/submit")
def submit_query(sql: str) -> Dict:
    """
    비동기 쿼리 제출

    Returns:
        {"query_id": "uuid", "status": "RUNNING"}
    """
    # Athena 쿼리 시작 (대기 안 함)
    athena_query_id = athena.execute_query(sql, wait=False)

    # 고유 ID 생성
    query_id = str(uuid.uuid4())

    # 캐시에 저장
    query_cache[query_id] = {
        "athena_query_id": athena_query_id,
        "status": "RUNNING",
        "result": None
    }

    return {
        "query_id": query_id,
        "status": "RUNNING"
    }


@router.get("/status/{query_id}")
def get_query_status(query_id: str) -> Dict:
    """
    쿼리 상태 확인

    Returns:
        {"status": "RUNNING" | "SUCCEEDED" | "FAILED"}
    """
    if query_id not in query_cache:
        raise HTTPException(404, "Query not found")

    cached = query_cache[query_id]
    athena_query_id = cached["athena_query_id"]

    # Athena 상태 확인
    response = athena.client.get_query_execution(
        QueryExecutionId=athena_query_id
    )

    state = response['QueryExecution']['Status']['State']

    # 캐시 업데이트
    cached["status"] = state

    return {
        "query_id": query_id,
        "status": state
    }


@router.get("/result/{query_id}")
def get_query_result(query_id: str) -> List[Dict]:
    """
    쿼리 결과 조회

    Returns:
        결과 데이터 (Arrow → JSON)
    """
    if query_id not in query_cache:
        raise HTTPException(404, "Query not found")

    cached = query_cache[query_id]

    # 이미 캐시된 결과가 있으면 반환
    if cached["result"]:
        return cached["result"]

    # 상태 확인
    status_response = get_query_status(query_id)

    if status_response["status"] == "RUNNING":
        raise HTTPException(202, "Query still running")
    elif status_response["status"] == "FAILED":
        raise HTTPException(500, "Query failed")

    # 결과 조회 (Arrow → JSON)
    athena_query_id = cached["athena_query_id"]
    result = athena.get_results_arrow(athena_query_id).to_pylist()

    # 캐시에 저장
    cached["result"] = result

    return result


# 사용 예시 (Frontend)
"""
1. 쿼리 제출
POST /api/v2/query/submit
Body: {"sql": "SELECT ..."}
Response: {"query_id": "abc-123", "status": "RUNNING"}

2. 상태 폴링 (1초마다)
GET /api/v2/query/status/abc-123
Response: {"status": "RUNNING"}

3. 완료 후 결과 조회
GET /api/v2/query/result/abc-123
Response: [{"trade_date": "2024-01-01", ...}]
"""
```

### 6. 백테스트 모듈 (Arrow 네이티브)

```python
# server/module/backtest_athena.py
from db.athena_client import get_athena_client
import pyarrow as pa
import pyarrow.compute as pc
from typing import Dict

athena = get_athena_client()


class BacktestAthena:
    """
    Athena + Arrow 기반 백테스트 (Pandas 없음!)
    """

    def get_price_data(
        self,
        meta_ids: List[int],
        start_date: str,
        end_date: str = None
    ) -> pa.Table:
        """
        가격 데이터 조회 → Arrow Table
        """
        meta_id_list = ','.join(map(str, meta_ids))

        sql = f"""
        SELECT
            meta_id,
            trade_date,
            adj_close
        FROM market_data.us_stocks_price
        WHERE meta_id IN ({meta_id_list})
          AND trade_date >= DATE '{start_date}'
        """

        if end_date:
            sql += f" AND trade_date <= DATE '{end_date}'"

        sql += " ORDER BY trade_date, meta_id"

        return athena.query_to_arrow(sql)

    def calculate_returns(self, price_table: pa.Table) -> pa.Table:
        """
        수익률 계산 (Arrow Compute, Pandas 없음!)
        """
        # Arrow Compute로 벡터 연산
        adj_close = price_table['adj_close']

        # meta_id별로 그룹화하여 이전 값 계산
        # (Arrow의 window function 활용)

        # 간단한 버전: 전체 shift (실제로는 그룹별 처리 필요)
        prev_close = pc.shift(adj_close, 1)

        # 수익률 = (현재 - 이전) / 이전
        returns = pc.divide(
            pc.subtract(adj_close, prev_close),
            prev_close
        )

        # 새 컬럼 추가
        return price_table.append_column('returns', returns)

    def calculate_portfolio_value(
        self,
        price_table: pa.Table,
        weights: Dict[int, float]  # {meta_id: weight}
    ) -> pa.Table:
        """
        포트폴리오 가치 계산 (Arrow)
        """
        # Arrow로 가중 평균 계산
        meta_ids = price_table['meta_id'].to_pylist()
        adj_closes = price_table['adj_close'].to_numpy()

        # 가중치 적용
        weighted_prices = []
        for meta_id, price in zip(meta_ids, adj_closes):
            weight = weights.get(meta_id, 0)
            weighted_prices.append(price * weight)

        # Arrow Array로 변환
        portfolio_values = pa.array(weighted_prices)

        return price_table.append_column('portfolio_value', portfolio_values)

    def calculate_metrics(self, returns_table: pa.Table) -> Dict:
        """
        성과 메트릭 계산 (Arrow Compute)
        """
        returns = returns_table['returns']

        # Athena에서 직접 계산하는 것이 더 효율적!
        sql = f"""
        WITH returns_data AS (
            SELECT
                returns,
                SUM(returns) OVER (ORDER BY trade_date) as cumulative_return
            FROM ({self.get_returns_query()})
        )
        SELECT
            AVG(returns) * 252 as annualized_return,
            STDDEV(returns) * SQRT(252) as annualized_volatility,
            AVG(returns) / STDDEV(returns) * SQRT(252) as sharpe_ratio,
            MIN(cumulative_return) as max_drawdown
        FROM returns_data
        """

        result = athena.query_to_json(sql)
        return result[0] if result else {}
```

---

## 💰 비용 상세 분석

### Athena 가격 구조

```
기본 비용: $5 per TB scanned
압축/파티션 최적화 시: $0.25/월 예상

예시:
- 1GB 데이터 스캔: $0.005
- 10GB 데이터 스캔: $0.05
- 100GB 데이터 스캔: $0.50

월 100회 쿼리 × 평균 50MB 스캔:
→ 100 × 50MB = 5GB = 0.005TB
→ 0.005TB × $5 = $0.025/월

파티션 프루닝으로 70% 감소:
→ $0.025 × 0.3 = $0.0075/월

실제 예상: $0.25/월 (여유 포함)
```

### 최종 비용 비교

```
┌────────────────────────────────────────────┐
│  구성 요소          │ Athena   │ Trino     │
├────────────────────────────────────────────┤
│  RDS (메타)         │ $14.43   │ $14.43    │
│  S3 + Glue          │ $0.15    │ $0.15     │
│  Query Engine       │ $0.25    │ $12.60    │
├────────────────────────────────────────────┤
│  총계               │ $14.83   │ $27.18    │
├────────────────────────────────────────────┤
│  현재 대비 절감     │ 44%      │ -3%       │
└────────────────────────────────────────────┘

Athena: 비용 절감 + 서버리스
Trino: 더 빠른 응답 + 더 강력한 기능
```

---

## 🎯 Athena vs Trino 최종 선택 가이드

### Athena를 선택해야 할 때 ⭐⭐⭐⭐⭐

```
✅ 비용이 최우선
✅ 인프라 관리 하고 싶지 않음
✅ 서버리스 선호
✅ 3-5초 지연 허용 가능
✅ 쿼리 빈도 낮음 (< 1000회/일)
✅ 배치/분석 위주
✅ AWS 네이티브 통합 선호
```

### Trino를 선택해야 할 때

```
✅ 즉시 응답 필요 (< 500ms)
✅ 실시간 대시보드
✅ 쿼리 빈도 높음 (> 10000회/일)
✅ 복잡한 최적화 필요
✅ 여러 데이터 소스 동시 접근 (Kafka, Cassandra 등)
✅ 관리 리소스 있음
```

---

## 🚀 Athena 구현 체크리스트

### Phase 1: 설정 (1-2일)

```bash
# 1. S3 버킷 생성
aws s3 mb s3://insight-invest-datalake
aws s3 mb s3://insight-invest-athena-results

# 2. Glue 데이터베이스 생성
aws glue create-database --database-input '{"Name": "market_data"}'
aws glue create-database --database-input '{"Name": "portfolio"}'
aws glue create-database --database-input '{"Name": "analytics"}'

# 3. IAM 역할 설정
aws iam attach-role-policy \
  --role-name insight-invest-task-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonAthenaFullAccess
```

### Phase 2: 테이블 생성 (2-3일)

```python
# PyIceberg로 Iceberg 테이블 생성
python scripts/create_iceberg_tables_athena.py
```

### Phase 3: API 통합 (3-5일)

```python
# FastAPI에 Athena 클라이언트 통합
pip install boto3 pyarrow s3fs

# 라우터 추가
from app.routers import price_athena
app.include_router(price_athena.router)
```

### Phase 4: 테스트 (2-3일)

```python
# 쿼리 테스트
result = athena.query_to_json("""
    SELECT * FROM market_data.us_stocks_price
    LIMIT 10
""")

# 크로스 스키마 조인 테스트
result = athena.query_to_json("""
    SELECT *
    FROM market_data.us_stocks_price p
    JOIN portfolio.tb_nav n ON p.trade_date = n.trade_date
    LIMIT 10
""")
```

---

## 💡 Athena 최적화 팁

### 1. 파티션 프루닝

```sql
-- ❌ 나쁜 예: 전체 스캔
SELECT *
FROM market_data.us_stocks_price
WHERE meta_id = 123

-- ✅ 좋은 예: 파티션 필터
SELECT *
FROM market_data.us_stocks_price
WHERE trade_date >= DATE '2024-11-01'  -- 파티션 컬럼!
  AND trade_date < DATE '2024-12-01'
  AND meta_id = 123

-- 스캔량: 10GB → 300MB (97% 감소!)
```

### 2. 컬럼 프로젝션

```sql
-- ❌ 나쁜 예: 모든 컬럼
SELECT *
FROM market_data.us_stocks_price

-- ✅ 좋은 예: 필요한 컬럼만
SELECT trade_date, adj_close
FROM market_data.us_stocks_price

-- 스캔량: 1GB → 200MB (80% 감소!)
```

### 3. CTAS (Create Table As Select)

```sql
-- 자주 사용하는 쿼리는 미리 계산하여 저장
CREATE TABLE analytics.daily_portfolio_value
WITH (
  format = 'PARQUET',
  parquet_compression = 'ZSTD',
  partitioned_by = ARRAY['trade_date']
) AS
SELECT
  trade_date,
  port_id,
  SUM(adj_close * weight) as portfolio_value
FROM market_data.us_stocks_price p
JOIN portfolio.tb_rebalance r ON p.meta_id = r.meta_id
GROUP BY trade_date, port_id

-- 이후 빠른 조회
SELECT * FROM analytics.daily_portfolio_value
WHERE port_id = 1
```

---

## 🎓 학습 자료

- [Athena Iceberg Support](https://docs.aws.amazon.com/athena/latest/ug/querying-iceberg.html)
- [Athena Query Optimization](https://docs.aws.amazon.com/athena/latest/ug/performance-tuning.html)
- [PyArrow Documentation](https://arrow.apache.org/docs/python/)

---

## 🎯 최종 추천

### 당신의 프로젝트에는 **Athena가 더 나을 수 있습니다!**

#### 이유:
1. ✅ **Pandas 제거** 가능 (Arrow 네이티브)
2. ✅ **크로스 스키마 조인** 완벽 지원
3. ✅ **분산 처리** 자동
4. ✅ **비용** 월 $0.25 (Trino의 1/50)
5. ✅ **인프라 관리** 불필요 (서버리스)
6. ✅ **확장성** 무한
7. ⚠️ **응답 시간** 3-5초 (허용 가능하면 최고의 선택)

#### 선택 기준:
```
응답 시간 > 3초 허용 → Athena ⭐⭐⭐⭐⭐
응답 시간 < 500ms 필수 → Trino
```

대부분의 백테스트/분석 API는 3초 정도 충분하므로 **Athena 강력 추천**합니다! 🎉
