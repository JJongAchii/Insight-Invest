# Insight-Invest 최적 아키텍처 설계

## 🎯 설계 원칙

1. **관심사 분리 (Separation of Concerns)**

   - 웹 API 서버 ≠ 배치 작업
   - 각 컴포넌트는 독립적으로 배포/확장 가능

2. **안정성 (Reliability)**

   - 단일 실패 지점 제거
   - 자동 재시도 메커니즘
   - 실패 알림

3. **비용 효율성 (Cost Efficiency)**

   - 필요한 시간에만 리소스 사용
   - Auto Scaling으로 트래픽 대응
   - Spot instances 활용 (배치 작업)

4. **확장성 (Scalability)**

   - 수평적 확장 가능
   - 새로운 배치 작업 추가 용이

5. **관찰 가능성 (Observability)**
   - 중앙화된 로깅 (CloudWatch)
   - 메트릭 수집
   - 알림 시스템

---

## 🏛️ 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                        Internet                              │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
         ┌───────────────┐
         │  CloudFront   │ (Optional: CDN)
         │  or ALB       │
         └───────┬───────┘
                 │
                 ▼
    ┌────────────────────────┐
    │   ECS Service (API)    │
    │  ┌──────────────────┐  │
    │  │  FastAPI Server  │  │  ◄── 순수 API만 제공
    │  │  (Load Balanced) │  │      스케줄러 없음
    │  └──────────────────┘  │
    │   Auto Scaling: 1-3    │
    └────────────┬───────────┘
                 │
                 ├─────────────────────┐
                 │                     │
                 ▼                     ▼
        ┌────────────────┐    ┌──────────────┐
        │   RDS (PostgreSQL) │    │  S3 Bucket   │
        │   Database         │    │  (Optional)  │
        └────────────────┘    └──────────────┘

┌──────────────────────────────────────────────────────────────┐
│              AWS EventBridge (Scheduler)                      │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Rule 1: US Market Update  (Every Tue-Sat 09:00 UTC)   │ │
│  │  Rule 2: KR Market Update  (Every Mon-Fri 21:00 UTC)   │ │
│  │  Rule 3: Macro Update      (Every Sun-Fri 23:00 UTC)   │ │
│  └─────────────────────────────────────────────────────────┘ │
└───────┬──────────────┬──────────────┬────────────────────────┘
        │              │              │
        ▼              ▼              ▼
   ┌─────────┐   ┌─────────┐   ┌─────────┐
   │ECS Task │   │ECS Task │   │ECS Task │
   │US Price │   │KR Price │   │  Macro  │
   │ Update  │   │ Update  │   │ Update  │
   └────┬────┘   └────┬────┘   └────┬────┘
        │              │              │
        └──────────────┴──────────────┘
                       │
                       ▼
              ┌────────────────┐
              │   RDS Database │
              └────────────────┘

┌──────────────────────────────────────────────────────────────┐
│              Monitoring & Alerting                            │
│  ┌──────────────┐   ┌──────────────┐   ┌─────────────────┐  │
│  │  CloudWatch  │──▶│  SNS Topic   │──▶│ Email / Slack   │  │
│  │     Logs     │   │  (Alarms)    │   │  Notification   │  │
│  └──────────────┘   └──────────────┘   └─────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

## 📦 컴포넌트 상세

### 1. API Server (Load Balanced Web Service)

**역할**:

- RESTful API 엔드포인트 제공
- 프론트엔드 요청 처리
- 실시간 데이터 조회

**기술 스택**:

- FastAPI
- Uvicorn
- PostgreSQL (via SQLAlchemy)

**리소스**:

```yaml
cpu: 256 (0.25 vCPU)
memory: 512 MB
count: 1-3 (Auto Scaling)
```

**특징**:

- ✅ APScheduler 제거 (순수 API만)
- ✅ Stateless 설계
- ✅ 수평 확장 가능

---

### 2. Scheduled Jobs (ECS Scheduled Tasks)

#### 2-1. US Market Price Updater

**실행 시간**: 매일 18:00 KST (09:00 UTC)  
**요일**: 화-토 (미국 시장 거래일)  
**예상 소요 시간**: 10-15분

**작업 내용**:

1. 마지막 업데이트 날짜 조회
2. yfinance API로 US 주식 데이터 다운로드
3. 데이터 변환 및 정제
4. RDS에 저장

**재시도 정책**: 2회

---

#### 2-2. KR Market Price Updater

**실행 시간**: 매일 06:00 KST (21:00 UTC, 전날)  
**요일**: 화-토 (한국 시장 거래일)  
**예상 소요 시간**: 10-15분

**작업 내용**:

1. 마지막 업데이트 날짜 조회
2. yfinance API로 KR 주식 데이터 다운로드 (.KS suffix)
3. 데이터 변환 및 정제
4. RDS에 저장

**재시도 정책**: 2회

---

#### 2-3. Macro Data Updater

**실행 시간**: 매일 08:00 KST (23:00 UTC, 전날)  
**요일**: 월-토  
**예상 소요 시간**: 5-10분

**작업 내용**:

1. 마지막 업데이트 날짜 조회
2. FRED API로 매크로 데이터 다운로드
3. 데이터 변환 및 정제
4. RDS에 저장

**재시도 정책**: 2회

---

### 3. Database (RDS PostgreSQL)

**역할**:

- 주가 데이터 저장
- 메타 정보 관리
- 백테스트 결과 저장

**접근**:

- API Server: Read/Write
- Scheduled Jobs: Write Only

---

### 4. Monitoring & Alerting

**CloudWatch Logs**:

- API Server 로그
- Scheduled Jobs 실행 로그
- 에러 로그

**CloudWatch Alarms**:

- Scheduled Job 실패
- API Server 응답 시간 > 3초
- RDS CPU > 80%
- ECS Task 실패

**SNS Notifications**:

- 이메일 알림
- Slack Webhook (선택사항)

---

## 🔄 데이터 플로우

### API 요청 플로우

```
Client (Browser/App)
      │
      ▼
  CloudFront/ALB
      │
      ▼
  ECS Task (FastAPI)
      │
      ├─► GET /api/meta → RDS → Response
      ├─► GET /api/price → RDS → Response
      └─► POST /api/backtest → Calculate → RDS → Response
```

### Scheduled Job 플로우

```
EventBridge Rule (Trigger)
      │
      ▼
ECS Task Start (Fargate)
      │
      ▼
run_price_update.py
      │
      ├─► 1. Check last update (RDS)
      ├─► 2. Download data (yfinance/FRED)
      ├─► 3. Transform data (pandas)
      └─► 4. Insert to RDS
      │
      ▼
ECS Task Complete
      │
      ├─► Success → CloudWatch Logs
      └─► Failure → CloudWatch Alarm → SNS
```

---

## 💰 비용 예상 (월간)

### ECS Fargate 비용

| 컴포넌트     | vCPU | Memory | 시간 | 비용/월     |
| ------------ | ---- | ------ | ---- | ----------- |
| API Server   | 0.25 | 512 MB | 720h | ~$13        |
| US Price Job | 0.25 | 512 MB | 7.5h | ~$0.41      |
| KR Price Job | 0.25 | 512 MB | 7.5h | ~$0.41      |
| Macro Job    | 0.25 | 512 MB | 5h   | ~$0.27      |
| **소계**     |      |        |      | **~$14.09** |

### 기타 AWS 서비스

| 서비스                    | 비용/월        |
| ------------------------- | -------------- |
| Application Load Balancer | ~$16           |
| RDS (db.t3.micro)         | ~$15           |
| EventBridge               | $0 (무료 한도) |
| CloudWatch Logs (5 GB)    | ~$2.50         |
| Data Transfer             | ~$1            |
| **소계**                  | **~$34.50**    |

### 총 예상 비용

```
월 총 비용: ~$48.59
연 총 비용: ~$583
```

**절감 가능**:

- Spot instances 사용: -70% (Scheduled Jobs만)
- Reserved Instances: -30% (1년 약정)
- RDS Reserved: -30%

---

## 🚀 배포 전략

### 1. Blue-Green Deployment (API Server)

```yaml
# Zero-downtime deployment
deployment:
  rolling: default
```

### 2. Scheduled Jobs

```yaml
# 실패 시 자동 재시도
retries: 2
timeout: 30m
```

### 3. CI/CD Pipeline (GitHub Actions)

```
Push to main
      │
      ▼
Run Tests
      │
      ├─► Unit Tests
      ├─► Integration Tests
      └─► Linting
      │
      ▼
Build Docker Image
      │
      ▼
Push to ECR
      │
      ▼
Deploy to ECS
      │
      ├─► API Server (Rolling update)
      └─► Scheduled Jobs (Update task definition)
      │
      ▼
Health Check
      │
      ├─► Success → Complete
      └─► Failure → Rollback
```

---

## 📈 확장 계획

### Phase 1: 현재 (MVP)

- API Server: 1 task
- Scheduled Jobs: 3개
- Manual monitoring

### Phase 2: 성장 단계

- API Server: Auto Scaling (1-3 tasks)
- Scheduled Jobs: 5-10개
- CloudWatch Alarms + SNS
- 데이터 캐싱 (ElastiCache)

### Phase 3: 스케일 업

- API Server: Auto Scaling (3-10 tasks)
- Scheduled Jobs: 20+ 개
- CloudWatch Dashboard
- S3 데이터 레이크
- AWS Step Functions (복잡한 워크플로우)

---

## 🔒 보안

### Network Security

- VPC with private subnets
- Security Groups (least privilege)
- RDS in private subnet

### Secrets Management

- AWS Systems Manager Parameter Store
- No hardcoded credentials
- Rotation policy

### IAM Roles

- Task Execution Role (ECR, CloudWatch)
- Task Role (RDS, S3)
- Principle of least privilege

---

## 📊 모니터링 메트릭

### API Server

- Request count
- Response time (p50, p95, p99)
- Error rate (4xx, 5xx)
- CPU/Memory utilization

### Scheduled Jobs

- Execution count
- Success/Failure rate
- Execution duration
- Data processed (rows)

### Database

- Connection count
- Query duration
- CPU/Memory utilization
- Storage usage

---

## 🎯 성공 지표 (KPI)

| 지표                 | 목표       | 측정 방법         |
| -------------------- | ---------- | ----------------- |
| API 가용성           | > 99.9%    | CloudWatch        |
| API 응답 시간 (p95)  | < 500ms    | CloudWatch        |
| Scheduled Job 성공률 | > 99%      | CloudWatch        |
| 데이터 최신성        | < 1일 지연 | Custom metric     |
| 월 비용              | < $60      | AWS Cost Explorer |

---

## 🔄 운영 프로세스

### Daily

- CloudWatch 대시보드 확인
- 에러 로그 검토

### Weekly

- Cost 리뷰
- Performance 리뷰
- 알람 패턴 분석

### Monthly

- 용량 계획
- 보안 패치
- 백업 검증

---

## 📚 참고 문서

- [AWS ECS Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/)
- [AWS Copilot CLI](https://aws.github.io/copilot-cli/)
- [Twelve-Factor App](https://12factor.net/)
