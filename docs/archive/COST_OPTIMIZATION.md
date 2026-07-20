# 비용 최적화 가이드

## 💰 현재 비용 구조 분석

### 월별 예상 비용 (기존 설계)

| 항목                          | 월 비용     | 필수 여부 | 절감 가능?     |
| ----------------------------- | ----------- | --------- | -------------- |
| **ECS Fargate (API)**         | ~$13        | ✅ 필수   | ⚠️ 최소화 가능 |
| **Application Load Balancer** | ~$16        | ❌ 선택   | ✅ 제거 가능   |
| **RDS (db.t3.micro)**         | ~$15        | ✅ 필수   | ⚠️ 최소화 가능 |
| **Scheduled Jobs**            | ~$1         | ✅ 필수   | ⚠️ 최소화 가능 |
| **CloudWatch Logs (5 GB)**    | ~$2.50      | ⚠️ 중요   | ✅ 절감 가능   |
| **Data Transfer**             | ~$1         | ✅ 필수   | -              |
| **총계**                      | **~$48.50** |           |                |

---

## 🎯 비용 절감 전략

### 옵션 1: 최소 비용 모드 (추천)

**목표**: 월 $20 이하

#### 제거할 항목

1. **Application Load Balancer 제거** (-$16/월) ✅

   - Public IP로 직접 접근
   - 단점: Auto-scaling 불가, SSL 수동 관리

2. **CloudWatch 최소화** (-$1.50/월) ✅
   - Log retention: 30일 → 3일
   - 필수 로그만 수집
   - 대시보드 제거

#### 최적화할 항목

3. **RDS 다운그레이드** (-$7/월)

   - db.t3.micro → db.t4g.micro (ARM 기반)
   - 또는 RDS 대신 서버 내 PostgreSQL 사용

4. **ECS 리소스 최소화** (-$3/월)
   - CPU: 256 → 256 (유지)
   - Memory: 512 MB → 512 MB (유지)
   - 실행 시간 최적화

#### 결과

```
ECS Fargate (API)        : $10   (최적화)
RDS (db.t4g.micro)       : $8    (다운그레이드)
Scheduled Jobs           : $1    (유지)
CloudWatch Logs (1 GB)   : $1    (축소)
Data Transfer            : $1    (유지)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
총 월 비용: ~$21/월 (기존 대비 -56%)
```

---

### 옵션 2: 극한 절감 모드

**목표**: 월 $10 이하

#### 아키텍처 변경

1. **AWS를 버리고 저렴한 대안 사용**

   - **Railway** / **Render** / **Fly.io**
   - 월 $5-10으로 API + DB + Scheduled Jobs 모두 운영 가능

2. **또는 AWS 프리티어 최대 활용**
   - EC2 t2.micro (프리티어 750시간/월)
   - RDS 프리티어 (db.t2.micro, 750시간/월)
   - 첫 12개월 무료!

---

## 🔧 구체적인 절감 방법

### 1. ALB 제거하기

#### Before (현재 설계)

```
Internet → ALB → ECS Tasks
비용: $16/월
```

#### After (ALB 제거)

```
Internet → ECS Task (Public IP)
비용: $0
```

#### 변경 방법

**copilot/api/manifest.yml 수정:**

```yaml
name: api
type: Backend Service # Load Balanced Web Service → Backend Service

# http 섹션 제거 (ALB 사용 안함)
# http:
#   path: "/"

image:
  build: server/Dockerfile
  port: 8000

cpu: 256
memory: 512
count: 1

# Public IP로 접근 가능하도록 설정
network:
  vpc:
    placement: public # public subnet에 배치
```

**장점**:

- ✅ 월 $16 절감
- ✅ 구조 단순화

**단점**:

- ❌ Auto-scaling 불가
- ❌ SSL/TLS 수동 관리 필요
- ❌ Health check 기반 자동 복구 없음
- ❌ IP 주소가 재시작 시 변경될 수 있음

**권장**: 프로토타입/개발 단계에서는 OK, 프로덕션에서는 ALB 사용 권장

---

### 2. CloudWatch 비용 최소화

#### 현재 설정 (비용: ~$2.50/월)

- Log retention: 30일
- 5 GB 로그
- Dashboard, Alarms 포함

#### 최소 비용 설정 (비용: ~$0.50/월)

**copilot/jobs/\*/manifest.yml 수정:**

```yaml
# 로그 보존 기간 축소
logging:
  retention: 3 # 30일 → 3일

# 또는 아예 로그 비활성화 (비추천)
# logging:
#   retention: 1
```

**CloudWatch 무료 한도:**

- 로그 수집: 월 5 GB 무료
- 로그 저장: 월 5 GB 무료
- 메트릭: 10개 무료
- 알람: 10개 무료
- Dashboard: 3개 무료

**결론**: CloudWatch 자체는 거의 비용이 안나옵니다! (무료 한도 내)

---

### 3. RDS 비용 절감

#### 옵션 A: ARM 기반 인스턴스 사용 (-50%)

```yaml
# RDS를 db.t4g (ARM) 시리즈로 변경
# copilot에서는 직접 제어 불가, AWS Console에서 변경

db.t3.micro → db.t4g.micro
비용: $15/월 → $8/월 (-47%)
```

#### 옵션 B: RDS 제거, 컨테이너 내 DB 사용 (비추천)

```dockerfile
# server/Dockerfile
FROM python:3.10-slim

# PostgreSQL 설치
RUN apt-get update && apt-get install -y postgresql postgresql-contrib

# 데이터 볼륨 마운트 필요
VOLUME /var/lib/postgresql/data
```

**단점**:

- ❌ 데이터 손실 위험
- ❌ 백업 수동 관리
- ❌ 확장성 제한

**권장하지 않음**

#### 옵션 C: 무료 DB 서비스 사용

**ElephantSQL (무료):**

- 20 MB 무료
- PostgreSQL
- 제한적이지만 테스트/프로토타입에는 충분

**Supabase (무료):**

- 500 MB 무료
- PostgreSQL
- 더 관대한 무료 한도

**Neon (무료):**

- 10 GB 무료
- PostgreSQL
- Serverless

---

### 4. ECS Fargate 비용 최적화

#### 현재 설정

```yaml
cpu: 256 # 0.25 vCPU
memory: 512 # 512 MB
```

**비용**:

- vCPU: $0.04048/시간 × 0.25 × 720h = ~$7.29
- Memory: $0.004445/GB/시간 × 0.5 × 720h = ~$1.60
- **총**: ~$8.89/월

#### 최소 설정 (변경 불가, 이미 최소값)

Fargate 최소 요구사항:

- CPU: 최소 256 (0.25 vCPU)
- Memory: 최소 512 MB

**더 줄일 수 없음** ⚠️

#### 대안: Spot Instances 적용 (-70%)

**Scheduled Jobs에만 적용 가능** (API 서버는 불가):

```yaml
# copilot/jobs/us-price-updater/manifest.yml
platform: linux/x86_64
capacityProviders:
  - FARGATE_SPOT # 70% 저렴
```

**절감액**:

- Jobs: $1/월 → $0.30/월 (-$0.70)

---

## 📊 최종 추천 구성

### 🥉 Bronze: 극한 절약 모드 (~$15/월)

```yaml
Architecture:
  API Server: Backend Service (ALB 없음)
  Database: ElephantSQL (무료) 또는 Neon (무료)
  Jobs: ECS Fargate Spot
  Monitoring: 최소한의 CloudWatch (3일 retention)

비용:
  - ECS API: $9
  - ECS Jobs (Spot): $0.30
  - Database: $0 (무료 서비스)
  - CloudWatch: $1
  - Data Transfer: $1
  ━━━━━━━━━━━━━━━━━━━
  총: ~$11.30/월
```

### 🥈 Silver: 균형 잡힌 구성 (~$25/월) ⭐ 추천

```yaml
Architecture:
  API Server: Backend Service (ALB 없음)
  Database: RDS db.t4g.micro
  Jobs: ECS Fargate Spot
  Monitoring: CloudWatch (7일 retention)

비용:
  - ECS API: $9
  - RDS db.t4g.micro: $8
  - ECS Jobs (Spot): $0.30
  - CloudWatch: $1
  - Data Transfer: $1
  ━━━━━━━━━━━━━━━━━━━
  총: ~$19.30/월
```

### 🥇 Gold: 프로덕션 권장 (~$48/월)

```yaml
Architecture:
  API Server: Load Balanced Web Service (ALB 포함)
  Database: RDS db.t3.micro
  Jobs: ECS Fargate (일반)
  Monitoring: CloudWatch Full (30일 retention, Dashboard, Alarms)

비용:
  - ECS API: $13
  - ALB: $16
  - RDS db.t3.micro: $15
  - ECS Jobs: $1
  - CloudWatch: $2.50
  - Data Transfer: $1
  ━━━━━━━━━━━━━━━━━━━
  총: ~$48.50/월
```

---

## 🎯 즉시 적용 가능한 절감 방법

### 1단계: ALB 제거 (-$16/월)

```bash
# copilot/api/manifest.yml 수정
sed -i '' 's/type: Load Balanced Web Service/type: Backend Service/' copilot/api/manifest.yml

# http 섹션 주석 처리
# http:
#   path: "/"

# 재배포
copilot svc deploy --name api --env dev
```

### 2단계: CloudWatch Retention 축소 (-$1/월)

```bash
# 모든 Job manifest 수정
find copilot/jobs -name "manifest.yml" -exec sed -i '' 's/retention: 30/retention: 3/' {} \;

# 재배포
copilot job deploy --name us-price-updater --env dev
copilot job deploy --name kr-price-updater --env dev
copilot job deploy --name macro-updater --env dev
```

### 3단계: Spot Instances 적용 (-$0.70/월)

각 Job manifest에 추가:

```yaml
platform: linux/x86_64
capacityProviders:
  - FARGATE_SPOT
```

### 4단계: 무료 DB 고려 (-$15/월)

**Neon 사용 예시:**

1. https://neon.tech 가입
2. 무료 프로젝트 생성
3. Connection string 복사
4. Copilot secret 업데이트:

```bash
copilot secret init \
  --name DATABASE_URL \
  --values dev=postgresql://user:pass@ep-xxx.neon.tech/main
```

---

## ⚠️ 주의사항

### ALB 제거 시

1. **도메인 연결 복잡**:

   - ECS 태스크 IP가 변경될 수 있음
   - 수동으로 DNS 업데이트 필요

2. **HTTPS 설정**:

   - ALB가 없으면 SSL 인증서를 컨테이너에서 직접 관리
   - Let's Encrypt + Certbot 사용 필요

3. **고가용성 제한**:
   - 단일 인스턴스만 실행 (Auto-scaling 불가)
   - 장애 시 수동 복구

### 무료 DB 사용 시

1. **용량 제한**:

   - ElephantSQL: 20 MB
   - Neon: 10 GB
   - 데이터 증가 모니터링 필요

2. **성능 제한**:

   - Connection pool 제한
   - 쿼리 성능 저하 가능

3. **SLA 없음**:
   - 무료 서비스는 보장 없음
   - 백업 주의

---

## 🎬 실전 적용 예시

### 시나리오: 프로토타입 단계

**목표**: 최소 비용으로 기능 검증

```yaml
구성: Bronze 티어
비용: ~$11/월

변경사항:
1. ALB 제거
2. Neon (무료 DB) 사용
3. CloudWatch 3일 retention
4. Spot instances 사용

기대효과:
- 비용 77% 절감
- 기능은 동일
- 안정성 소폭 감소 (허용 가능)
```

### 시나리오: 초기 운영 단계

**목표**: 합리적인 비용으로 안정적 운영

```yaml
구성: Silver 티어 (추천)
비용: ~$19/월

변경사항:
1. ALB 제거
2. RDS db.t4g.micro
3. CloudWatch 7일 retention
4. Spot instances 사용

기대효과:
- 비용 60% 절감
- 충분한 안정성
- 확장 가능
```

---

## 📈 비용 증가 시나리오

| 사용자 수  | 구성                | 월 비용 |
| ---------- | ------------------- | ------- |
| < 100      | Bronze              | ~$11    |
| 100-1000   | Silver              | ~$19    |
| 1000-10000 | Gold                | ~$48    |
| 10000+     | Gold + Auto Scaling | ~$100+  |

---

## ✅ 결론 및 추천

### 당장 적용 (비용 무관심 → 비용 의식)

1. ✅ **ALB 제거** if 프로토타입 단계
   - 절감: $16/월
   - 영향: 중간
2. ✅ **CloudWatch Retention 축소** (30일 → 7일)
   - 절감: $1/월
   - 영향: 낮음
3. ✅ **Spot Instances 적용** (Jobs만)
   - 절감: $0.70/월
   - 영향: 거의 없음

**즉시 절감액**: ~$17.70/월 (-36%)

### 검토 후 적용

4. ⚠️ **무료 DB 사용** (Neon/Supabase)

   - 절감: $15/월
   - 영향: 중간-높음
   - 권장: 데이터 크기 확인 후 결정

5. ⚠️ **RDS 다운그레이드** (t3 → t4g)
   - 절감: $7/월
   - 영향: 낮음
   - 권장: 성능 테스트 후 적용

---

**최종 추천: Silver 티어 (~$19/월)**

비용과 안정성의 최적 균형점입니다.
