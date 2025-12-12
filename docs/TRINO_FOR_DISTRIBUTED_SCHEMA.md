# 스키마 분산 + 크로스 조인 환경에서의 쿼리 엔진 선택

## 🎯 요구사항 재정의

### 핵심 요구사항
1. **Pandas 제거**: Arrow 네이티브 또는 SQL 기반 처리
2. **스키마 분산**: 여러 Iceberg 스키마로 분리
3. **크로스 스키마 조인**: 분산된 테이블 간 JOIN 빈번

### 예시 스키마 구조
```
s3://insight-invest-datalake/warehouse/
├── market_data/
│   ├── us_stocks/
│   │   ├── tb_price
│   │   └── tb_volume
│   └── kr_stocks/
│       ├── tb_price
│       └── tb_volume
├── portfolio/
│   ├── tb_portfolio
│   ├── tb_nav
│   └── tb_rebalance
├── analytics/
│   ├── tb_metrics
│   └── tb_signals
└── reference/
    ├── tb_meta
    └── tb_macro
```

---

## 🔄 요구사항 변경에 따른 재평가

### 이전 추천 (FastAPI + PyIceberg)의 문제점

```python
# ❌ 문제 1: Pandas 의존도 높음
df = table.scan().to_pandas()  # Pandas DataFrame 반환

# ❌ 문제 2: 크로스 스키마 조인 어려움
# 스키마가 다르면 각각 스캔 후 Pandas로 조인
us_df = us_table.scan().to_pandas()
kr_df = kr_table.scan().to_pandas()
result = pd.merge(us_df, kr_df)  # 비효율적

# ❌ 문제 3: 단일 머신 처리
# 분산 처리 불가, 대용량 조인 시 메모리 부족
```

---

## 🏆 새로운 추천: Trino (★★★★★)

### 이유

#### 1. **Arrow 네이티브 지원** - Pandas 불필요

```python
from trino.dbapi import connect
import pyarrow as pa

conn = connect(
    host='trino-coordinator',
    port=8080,
    catalog='iceberg',
    schema='market_data',
)

cursor = conn.cursor()
cursor.execute("""
    SELECT ticker, trade_date, adj_close
    FROM market_data.us_stocks.tb_price
    WHERE trade_date >= DATE '2024-01-01'
""")

# ✅ Arrow Table로 직접 반환 (Pandas 없음!)
arrow_table = cursor.fetch_arrow_table()

# Arrow → JSON (FastAPI 응답)
result = arrow_table.to_pylist()

# 또는 Arrow → Parquet → S3 (배치 처리)
import pyarrow.parquet as pq
pq.write_table(arrow_table, 's3://bucket/result.parquet')
```

#### 2. **크로스 스키마 조인 최적화**

```sql
-- ✅ 여러 스키마의 테이블을 자유롭게 JOIN
SELECT
    p.ticker,
    p.trade_date,
    p.adj_close,
    n.value as portfolio_value,
    m.sharpe,
    r.weight
FROM market_data.us_stocks.tb_price p
JOIN portfolio.tb_nav n
    ON p.trade_date = n.trade_date
JOIN analytics.tb_metrics m
    ON n.port_id = m.port_id
JOIN portfolio.tb_rebalance r
    ON p.trade_date = r.rebal_date
    AND p.meta_id = r.meta_id
WHERE p.trade_date >= DATE '2024-01-01'
```

Trino는 자동으로:
- 조인 순서 최적화
- 파티션 프루닝
- 푸시다운 필터링
- 분산 처리

#### 3. **분산 처리**

```yaml
# Trino 클러스터 구성
Coordinator: 1대 (쿼리 계획 수립)
Workers: 2-5대 (실제 데이터 처리, Auto-scaling)

# 대용량 조인도 분산 처리
- Worker 1: 파티션 1-10 처리
- Worker 2: 파티션 11-20 처리
- Worker 3: 파티션 21-30 처리
```

#### 4. **여러 카탈로그 동시 접근**

```sql
-- ✅ Iceberg + PostgreSQL + S3를 한 쿼리에서!
SELECT
    i.trade_date,
    i.adj_close,
    pg.name,
    pg.sector
FROM iceberg.market_data.tb_price i
JOIN postgresql.public.tb_meta pg
    ON i.meta_id = pg.meta_id
WHERE i.trade_date >= CURRENT_DATE - INTERVAL '30' DAY
```

```properties
# catalog/iceberg.properties
connector.name=iceberg
iceberg.catalog.type=glue

# catalog/postgresql.properties
connector.name=postgresql
connection-url=jdbc:postgresql://rds-endpoint:5432/insight_invest
connection-user=admin
connection-password=secret

# catalog/s3.properties (원시 데이터)
connector.name=hive
hive.metastore=glue
```

#### 5. **Iceberg 고급 기능 완벽 지원**

```sql
-- ✅ Time Travel
SELECT *
FROM market_data.tb_price
FOR TIMESTAMP AS OF TIMESTAMP '2024-01-01 00:00:00'

-- ✅ Incremental Read
SELECT *
FROM market_data.tb_price
FOR VERSION AS OF 123456789

-- ✅ Schema Evolution
ALTER TABLE market_data.tb_price
ADD COLUMN new_field DOUBLE

-- ✅ Partition Evolution
ALTER TABLE market_data.tb_price
SET TBLPROPERTIES (
    'write.distribution-mode'='hash'
)
```

---

## 📊 재평가: Trino vs Athena vs PyIceberg

| 요구사항 | Trino | Athena | PyIceberg |
|---------|-------|--------|-----------|
| **Pandas 제거** | ✅✅✅ Arrow 네이티브 | ✅✅ PyArrow 가능 | ❌ Pandas 중심 |
| **크로스 스키마 조인** | ✅✅✅ 최적화 | ✅✅ 가능 | ❌ 수동 조인 |
| **분산 처리** | ✅✅✅ 자동 | ✅✅ 자동 | ❌ 단일 머신 |
| **복잡한 SQL** | ✅✅✅ 완벽 | ✅✅ 대부분 | ❌ 제한적 |
| **실시간 조회** | ✅✅✅ 즉시 | ⚠️ 3-5초 | ✅✅ 즉시 |
| **비용** | ⚠️ $2-7/월 | ✅✅ $0.25/월 | ✅✅✅ $0.15/월 |
| **복잡도** | ⚠️ 높음 | ✅ 낮음 | ✅✅ 낮음 |

---

## 🎯 최종 추천: Trino (★★★★★)

### 당신의 요구사항에는 Trino가 최적입니다!

```
┌────────────────────────────────────────────────────────┐
│         Trino 기반 아키텍처 (추천)                      │
└────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│       FastAPI (API Layer)               │
│  from trino.dbapi import connect        │
│  arrow_table = cursor.fetch_arrow_table()│
└──────────────┬──────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│     Trino Cluster (Query Engine)         │
│  ┌────────────────────────────────────┐  │
│  │  Coordinator (1 task)              │  │
│  │  - Query Planning                  │  │
│  │  - Cross-schema JOIN optimization  │  │
│  └────────────────────────────────────┘  │
│  ┌────────────────────────────────────┐  │
│  │  Workers (2-5 tasks, auto-scale)   │  │
│  │  - Distributed Processing          │  │
│  │  - Arrow Format                    │  │
│  └────────────────────────────────────┘  │
└──────────────┬───────────────────────────┘
               │
       ┌───────┴──────────────────┐
       │                          │
       ▼                          ▼
┌──────────────┐          ┌──────────────┐
│  AWS Glue    │          │ PostgreSQL   │
│  Catalog     │          │ Catalog      │
└──────┬───────┘          └──────┬───────┘
       │                          │
       ▼                          ▼
┌──────────────┐          ┌──────────────┐
│  S3 Iceberg  │          │  RDS         │
│  (분산 스키마) │          │  (메타데이터) │
│              │          │              │
│  market_data/│          │  tb_meta     │
│  portfolio/  │          │  tb_strategy │
│  analytics/  │          └──────────────┘
│  reference/  │
└──────────────┘
```

---

## 💻 구현 예시

### 1. Trino 설정 (ECS on Fargate)

```yaml
# copilot/trino/manifest.yml
name: trino-coordinator
type: Backend Service

image:
  build:
    dockerfile: ./trino/Dockerfile
    context: ./trino

cpu: 1024      # 1 vCPU
memory: 2048   # 2 GB

count:
  range: 1-1   # Coordinator는 1개만

env:
  DISCOVERY_URI: http://trino-coordinator:8080

network:
  vpc:
    placement: private

---
name: trino-worker
type: Backend Service

image:
  build:
    dockerfile: ./trino/Dockerfile.worker
    context: ./trino

cpu: 1024      # 1 vCPU
memory: 2048   # 2 GB

count:
  range:
    min: 2
    max: 5
    cpu_percentage: 70  # Auto-scaling

env:
  DISCOVERY_URI: http://trino-coordinator:8080
```

### 2. Trino Catalog 설정

```dockerfile
# trino/Dockerfile
FROM trinodb/trino:435

# Catalog 설정 복사
COPY catalog/iceberg.properties /etc/trino/catalog/
COPY catalog/postgresql.properties /etc/trino/catalog/
COPY config.properties /etc/trino/
```

```properties
# catalog/iceberg.properties
connector.name=iceberg
iceberg.catalog.type=glue
hive.metastore.glue.region=ap-northeast-2
hive.metastore.glue.catalogid=YOUR_AWS_ACCOUNT_ID

# 여러 스키마 지원
iceberg.namespace=market_data,portfolio,analytics,reference
```

```properties
# catalog/postgresql.properties
connector.name=postgresql
connection-url=jdbc:postgresql://rds-endpoint:5432/insight_invest
connection-user=${ENV:RDS_USER}
connection-password=${ENV:RDS_PASSWORD}
```

### 3. FastAPI 통합 (Arrow 네이티브)

```python
# server/db/trino_client.py
from trino.dbapi import connect
from trino.auth import BasicAuthentication
import pyarrow as pa
from functools import lru_cache
from typing import List, Dict
import os

@lru_cache(maxsize=1)
def get_trino_connection():
    """Trino 연결 (재사용)"""
    return connect(
        host=os.getenv("TRINO_HOST", "trino-coordinator"),
        port=8080,
        user="api-server",
        catalog="iceberg",
        schema="market_data",
    )


def query_to_arrow(sql: str) -> pa.Table:
    """
    Trino 쿼리 실행 → Arrow Table 반환
    Pandas 없이 Arrow 네이티브 처리!
    """
    conn = get_trino_connection()
    cursor = conn.cursor()
    cursor.execute(sql)

    # Arrow Table로 직접 변환
    return cursor.fetch_arrow_table()


def query_to_json(sql: str) -> List[Dict]:
    """Arrow → JSON (FastAPI 응답용)"""
    arrow_table = query_to_arrow(sql)
    return arrow_table.to_pylist()


def query_to_parquet(sql: str, output_path: str):
    """Arrow → Parquet (배치 처리용)"""
    arrow_table = query_to_arrow(sql)

    import pyarrow.parquet as pq
    pq.write_table(arrow_table, output_path, compression='zstd')
```

### 4. API 라우터 (Pandas 없음!)

```python
# server/app/routers/price_trino.py
from fastapi import APIRouter, Query
from typing import List
from db.trino_client import query_to_json, query_to_arrow

router = APIRouter(prefix="/api/v2/price", tags=["price-v2"])


@router.get("/daily")
def get_daily_prices(
    ticker: str,
    start_date: str,
    end_date: str = None,
):
    """
    일별 가격 조회
    ✅ Pandas 없음
    ✅ 크로스 카탈로그 조인 (Iceberg + PostgreSQL)
    """

    sql = f"""
    SELECT
        pg.ticker,
        pg.name,
        pg.sector,
        ice.trade_date,
        ice.adj_close,
        ice.close,
        ice.gross_return
    FROM iceberg.market_data.tb_price ice
    JOIN postgresql.public.tb_meta pg
        ON ice.meta_id = pg.meta_id
    WHERE pg.ticker = '{ticker}'
      AND ice.trade_date >= DATE '{start_date}'
    """

    if end_date:
        sql += f" AND ice.trade_date <= DATE '{end_date}'"

    sql += " ORDER BY ice.trade_date"

    # Arrow → JSON (Pandas 없음!)
    return query_to_json(sql)


@router.get("/aggregate")
def get_aggregate_stats(
    tickers: List[str] = Query(...),
    start_date: str = Query(...),
):
    """
    집계 쿼리 - Trino의 분산 처리 활용
    ✅ Pandas 없음
    ✅ 크로스 스키마 조인
    """

    ticker_list = "','".join(tickers)

    sql = f"""
    SELECT
        pg.ticker,
        pg.name,
        pg.sector,
        AVG(ice.adj_close) as avg_price,
        STDDEV(ice.adj_close) as price_std,
        AVG(ice.gross_return) as avg_return,
        STDDEV(ice.gross_return) as volatility,
        COUNT(*) as trading_days
    FROM iceberg.market_data.tb_price ice
    JOIN postgresql.public.tb_meta pg
        ON ice.meta_id = pg.meta_id
    WHERE pg.ticker IN ('{ticker_list}')
      AND ice.trade_date >= DATE '{start_date}'
    GROUP BY pg.ticker, pg.name, pg.sector
    ORDER BY pg.ticker
    """

    return query_to_json(sql)


@router.get("/portfolio-performance")
def get_portfolio_performance(
    port_id: int,
    start_date: str,
):
    """
    복잡한 크로스 스키마 조인
    ✅ market_data + portfolio + analytics
    ✅ Trino가 자동으로 최적화
    """

    sql = f"""
    WITH price_data AS (
        SELECT
            p.trade_date,
            p.meta_id,
            p.adj_close,
            r.weight
        FROM iceberg.market_data.tb_price p
        JOIN iceberg.portfolio.tb_rebalance r
            ON p.meta_id = r.meta_id
            AND p.trade_date >= r.rebal_date
        WHERE r.port_id = {port_id}
          AND p.trade_date >= DATE '{start_date}'
    ),
    daily_returns AS (
        SELECT
            trade_date,
            SUM(adj_close * weight) as portfolio_value
        FROM price_data
        GROUP BY trade_date
    )
    SELECT
        dr.trade_date,
        dr.portfolio_value,
        n.value as nav_value,
        m.sharpe,
        m.mdd
    FROM daily_returns dr
    JOIN iceberg.portfolio.tb_nav n
        ON dr.trade_date = n.trade_date
        AND n.port_id = {port_id}
    LEFT JOIN iceberg.analytics.tb_metrics m
        ON m.port_id = {port_id}
    ORDER BY dr.trade_date
    """

    return query_to_json(sql)
```

### 5. 백테스트 모듈 (Arrow 네이티브)

```python
# server/module/backtest_arrow.py
from db.trino_client import query_to_arrow
import pyarrow.compute as pc
import pyarrow as pa

class BacktestArrow:
    """
    Arrow 기반 백테스트 (Pandas 없음!)
    """

    def data(self, meta_ids: List[int], start_date: str) -> pa.Table:
        """
        가격 데이터 조회 → Arrow Table
        """
        meta_id_list = ','.join(map(str, meta_ids))

        sql = f"""
        SELECT
            meta_id,
            trade_date,
            adj_close
        FROM iceberg.market_data.tb_price
        WHERE meta_id IN ({meta_id_list})
          AND trade_date >= DATE '{start_date}'
        ORDER BY trade_date
        """

        return query_to_arrow(sql)

    def calculate_returns(self, price_table: pa.Table) -> pa.Table:
        """
        수익률 계산 (Arrow Compute)
        """
        # Arrow Compute로 벡터 연산
        adj_close = price_table['adj_close']

        # LAG 계산 (이전 값)
        prev_close = pc.shift(adj_close, 1)

        # 수익률 = (현재 - 이전) / 이전
        returns = pc.divide(
            pc.subtract(adj_close, prev_close),
            prev_close
        )

        # 새 컬럼 추가
        return price_table.append_column('returns', returns)

    def aggregate_metrics(self, returns_table: pa.Table) -> Dict:
        """
        메트릭 계산 (Arrow Compute)
        """
        returns = returns_table['returns']

        return {
            'mean_return': pc.mean(returns).as_py(),
            'std_return': pc.stddev(returns).as_py(),
            'sharpe': pc.divide(
                pc.mean(returns),
                pc.stddev(returns)
            ).as_py() * (252 ** 0.5),  # Annualized
        }
```

---

## 💰 비용 분석 (Trino 포함)

### 최소 구성 (On-Demand)

```yaml
Coordinator: 1 task × 1 vCPU × 2GB × $0.04856/시간
  - 월 720시간 × $0.04856 = $35/월
  - Spot 사용 시: $10.5/월 (70% 할인)

Workers: 2 tasks × 1 vCPU × 2GB
  - 평균 가동률 10% (필요시만 스케일업)
  - 월 72시간 × 2 × $0.04856 = $7/월
  - Spot 사용 시: $2.1/월

총 Trino 비용:
  - On-Demand: $42/월
  - Spot (추천): $12.6/월
```

### 최종 비용 비교

| 항목 | PyIceberg | Athena | Trino (Spot) |
|------|-----------|--------|--------------|
| RDS (메타) | $14.43 | $14.43 | $14.43 |
| S3 + Glue | $0.15 | $0.15 | $0.15 |
| Query Engine | $0.00 | $0.25 | $12.60 |
| **총계** | **$14.58** | **$14.83** | **$27.18** |

### 비용 vs 가치

```
PyIceberg: $14.58/월
  ❌ Pandas 의존
  ❌ 크로스 스키마 조인 약함
  ❌ 분산 처리 불가

Athena: $14.83/월
  ✅ Pandas 불필요
  ✅ 크로스 스키마 조인 가능
  ⚠️ 비동기 처리 (3-5초 지연)

Trino: $27.18/월
  ✅✅ Arrow 네이티브
  ✅✅ 크로스 스키마 조인 최적화
  ✅✅ 분산 처리
  ✅✅ 즉시 응답
  ✅✅ 확장성

추가 비용 $12.60은 충분히 가치 있음! 🎯
```

---

## 🎯 최종 결론

### 당신의 요구사항:
1. ✅ Pandas 제거
2. ✅ 스키마 분산
3. ✅ 크로스 스키마 조인

### 최적 솔루션: **Trino** (★★★★★)

#### 이유:
- **Arrow 네이티브**: Pandas 완전 제거 가능
- **SQL 기반**: 복잡한 크로스 스키마 조인 최적화
- **분산 처리**: 데이터 증가해도 확장 가능
- **여러 카탈로그**: Iceberg + PostgreSQL + S3 동시 접근
- **Iceberg 완벽 지원**: Time Travel, Schema Evolution 등

#### 대안: **Athena** (★★★★)
- 비용이 더 중요하다면
- 3-5초 지연이 허용된다면
- 서버리스를 선호한다면

#### 비추천: **PyIceberg**
- Pandas 의존도 높음
- 크로스 스키마 조인 약함
- 당신의 요구사항에 맞지 않음

---

## 🚀 다음 단계

### 1. Trino POC (1-2주)
```bash
# Docker Compose로 로컬 테스트
docker-compose up trino

# 크로스 스키마 조인 테스트
trino-cli --execute "
  SELECT *
  FROM iceberg.market_data.tb_price p
  JOIN postgresql.public.tb_meta m
    ON p.meta_id = m.meta_id
  LIMIT 10
"
```

### 2. AWS ECS 배포
```bash
copilot svc init --name trino-coordinator
copilot svc init --name trino-worker
copilot svc deploy
```

### 3. FastAPI 통합
```python
# Arrow 기반 API 개발
from db.trino_client import query_to_json

@router.get("/price")
def get_price(ticker: str):
    return query_to_json(f"SELECT * FROM iceberg.market_data.tb_price WHERE ticker = '{ticker}'")
```

---

## 📚 참고 자료

- [Trino + Arrow Integration](https://trino.io/docs/current/develop/client-protocol.html#arrow)
- [Iceberg + Trino Best Practices](https://trino.io/docs/current/connector/iceberg.html)
- [Cross-Schema Joins in Trino](https://trino.io/docs/current/sql/select.html)
