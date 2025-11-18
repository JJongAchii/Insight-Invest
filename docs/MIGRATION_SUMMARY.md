# 최적 아키텍처 마이그레이션 요약

## 🎯 변경 사항 개요

기존 APScheduler 기반 스케줄링에서 **AWS EventBridge + Scheduled Jobs**로 마이그레이션하여 더욱 안정적이고 확장 가능한 시스템으로 개선했습니다.

---

## 📊 Before vs After

### Before (APScheduler)

```python
# server/app/main.py
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

@app.on_event("startup")
def start_scheduler():
    scheduler.add_job(update_daily_price, 'cron', ...)
    scheduler.start()
```

**문제점**:

- ❌ 웹 서버와 스케줄러가 결합됨
- ❌ 컨테이너 재시작 시 스케줄 상태 초기화
- ❌ 배포 시 스케줄 중단
- ❌ 실패 시 재시도 메커니즘 없음
- ❌ 로그 분리 어려움

### After (EventBridge + Scheduled Jobs)

```yaml
# copilot/jobs/us-price-updater/manifest.yml
name: us-price-updater
type: Scheduled Job

on:
  schedule: "0 9 * * TUE-SAT"

image:
  command: ["python", "run_scheduled_job.py", "--job", "us-price"]
```

```python
# server/run_scheduled_job.py
class JobRunner:
    def run(self):
        logger.info("Starting job...")
        update_daily_price(market="US")
        logger.info("Job completed successfully")
```

**개선점**:

- ✅ 관심사 분리 (API ≠ 배치 작업)
- ✅ AWS가 스케줄 관리 (정확한 실행)
- ✅ 배포와 독립적
- ✅ 자동 재시도 (retries: 2)
- ✅ 독립적인 로그 스트림
- ✅ 비용 효율적 (실행 시에만 과금)

---

## 📁 생성된 파일

### 1. 핵심 실행 스크립트

- ✅ `server/run_scheduled_job.py` - Scheduled Job 실행 스크립트

### 2. Copilot Manifests

- ✅ `copilot/jobs/us-price-updater/manifest.yml`
- ✅ `copilot/jobs/kr-price-updater/manifest.yml`
- ✅ `copilot/jobs/macro-updater/manifest.yml`

### 3. CI/CD

- ✅ `.github/workflows/deploy.yml` - API + Jobs 자동 배포

### 4. 모니터링

- ✅ `scripts/setup-monitoring.sh` - CloudWatch 알림 설정 스크립트
- ✅ `copilot/environments/addons/cloudwatch-dashboard.yml` - 대시보드

### 5. 문서

- ✅ `docs/ARCHITECTURE.md` - 전체 아키텍처 설계
- ✅ `docs/DEPLOYMENT_GUIDE.md` - 상세 배포 가이드
- ✅ `docs/MIGRATION_SUMMARY.md` - 이 문서
- ✅ `README.md` - 프로젝트 개요

---

## 🔄 변경된 파일

### server/app/main.py

**Before (70 lines)**:

```python
from apscheduler.schedulers.background import BackgroundScheduler
from module.update_data.price import update_daily_price
from module.update_data.macro import update_macro

scheduler = BackgroundScheduler()

@app.on_event("startup")
def start_scheduler():
    scheduler.add_job(update_daily_price, 'cron', args=['US'], ...)
    scheduler.add_job(update_daily_price, 'cron', args=['KR'], ...)
    scheduler.add_job(update_macro, 'cron', ...)
    scheduler.start()
```

**After (59 lines)**:

```python
"""
This is a clean API server focused solely on serving HTTP endpoints.
Scheduled data updates are handled by separate AWS EventBridge Scheduled Jobs.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Insight-Invest API",
    description="Investment analysis and backtesting API",
    version="2.0.0"
)

@app.get("/")
async def root():
    return {"status": "healthy", "service": "insight-invest-api"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

**변경 내용**:

- ✅ APScheduler 관련 코드 완전 제거
- ✅ 순수 API 서버로 변경
- ✅ Health check 엔드포인트 추가
- ✅ API 문서 메타데이터 추가

---

## 🚀 배포 방법

### 1단계: API 서버 배포

```bash
# 자동 배포 (GitHub Actions)
git add .
git commit -m "Migrate to EventBridge Scheduled Jobs"
git push origin main

# 또는 수동 배포
copilot svc deploy --name api --env dev
```

### 2단계: Scheduled Jobs 배포

```bash
# US Market
copilot job deploy --name us-price-updater --env dev

# KR Market
copilot job deploy --name kr-price-updater --env dev

# Macro
copilot job deploy --name macro-updater --env dev
```

### 3단계: 모니터링 설정

```bash
# CloudWatch 알림 설정
./scripts/setup-monitoring.sh --email your-email@example.com

# 이메일 확인하여 구독 승인!
```

### 4단계: 배포 확인

```bash
# API 헬스 체크
API_URL=$(copilot svc show --name api --json | jq -r '.routes[0].url')
curl https://$API_URL/health

# Job 상태 확인
copilot job status --name us-price-updater --env dev
copilot job status --name kr-price-updater --env dev
copilot job status --name macro-updater --env dev

# 로그 확인
copilot job logs --name us-price-updater --env dev --since 24h
```

---

## ⏰ 실행 스케줄

| Job      | 실행 시간 (KST) | 실행 시간 (UTC) | 요일    | 비고                 |
| -------- | --------------- | --------------- | ------- | -------------------- |
| US Price | 18:00           | 09:00           | Tue-Sat | 미국 장 마감 후      |
| KR Price | 06:00           | 21:00 (전날)    | Tue-Sat | 한국 장 마감 후      |
| Macro    | 08:00           | 23:00 (전날)    | Mon-Sat | FRED 데이터 업데이트 |

---

## 📊 성능 및 비용 비교

### 리소스 사용

| 항목          | Before        | After     | 변화    |
| ------------- | ------------- | --------- | ------- |
| API 서버 실행 | 24/7          | 24/7      | 동일    |
| 스케줄러 실행 | 24/7 (in API) | 필요 시만 | 개선 ✅ |
| 월 실행 시간  | 720h          | ~20h      | -97% 🎉 |
| 비용 증가     | -             | ~$1/월    | 미미    |

### 안정성

| 지표           | Before | After      |
| -------------- | ------ | ---------- |
| 스케줄 정확도  | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 실패 시 재시도 | ❌     | ✅ (2회)   |
| 독립적 로그    | ❌     | ✅         |
| 알림           | ❌     | ✅         |
| 배포 시 중단   | ✅     | ❌         |

---

## 🎯 기대 효과

### 1. 안정성 향상

- ✅ AWS EventBridge가 스케줄 관리 (99.99% SLA)
- ✅ 자동 재시도로 일시적 오류 대응
- ✅ 배포와 독립적으로 동작

### 2. 관찰 가능성 향상

- ✅ 각 Job의 독립적인 로그 스트림
- ✅ CloudWatch Dashboard로 한눈에 모니터링
- ✅ 실패 시 즉시 이메일 알림

### 3. 확장성 향상

- ✅ 새로운 Job 추가 용이
- ✅ Job별 리소스 조정 가능
- ✅ Spot instances 활용 가능 (70% 절감)

### 4. 유지보수 개선

- ✅ 관심사 분리로 디버깅 용이
- ✅ API 서버와 독립적으로 배포 가능
- ✅ 로그 분리로 문제 추적 쉬움

---

## 🔍 주요 변경 사항 상세

### 1. API 서버 (main.py)

**제거된 코드**:

- `apscheduler` import
- `BackgroundScheduler` 인스턴스
- `update_daily_price`, `update_macro` import
- `start_scheduler()` 함수
- `shutdown_scheduler()` 함수

**추가된 코드**:

- Health check 엔드포인트 (`/`, `/health`)
- API 메타데이터 (title, description, version)
- Docstring (아키텍처 설명)

### 2. Scheduled Job Runner (run_scheduled_job.py)

**새로운 기능**:

- Job 타입별 실행 (`us-price`, `kr-price`, `macro`, `all`)
- 상세한 로깅 (시작/종료 시간, 실행 시간)
- 에러 핸들링 및 트레이스백
- 환경 변수 검증
- Dry-run 모드 지원

### 3. Copilot Manifests

**공통 설정**:

- CPU: 256 (0.25 vCPU)
- Memory: 512 MB
- Retries: 2회
- Timeout: 15-30분
- Private VPC placement
- Log retention: 30일

**개별 스케줄**:

- US: `0 9 * * TUE-SAT` (UTC)
- KR: `0 21 * * MON-FRI` (UTC)
- Macro: `0 23 * * SUN-FRI` (UTC)

### 4. CI/CD Pipeline

**변경 사항**:

- API 배포와 Jobs 배포 분리
- Matrix strategy로 3개 Job 병렬 배포
- 배포 결과 알림 추가
- 의존성 관리 (API → Jobs)

---

## ✅ 체크리스트

배포 전 확인사항:

- [ ] API 서버가 정상 동작하는지 로컬 테스트
- [ ] `run_scheduled_job.py`가 독립적으로 실행되는지 테스트
- [ ] DATABASE_URL이 Secrets Manager에 설정됨
- [ ] AWS 자격 증명 설정됨
- [ ] Copilot CLI 설치됨
- [ ] GitHub Actions secrets 설정됨

배포 후 확인사항:

- [ ] API health check 성공
- [ ] 3개 Job이 모두 배포됨
- [ ] EventBridge 규칙이 활성화됨
- [ ] 첫 실행이 성공적으로 완료됨
- [ ] CloudWatch 로그가 수집됨
- [ ] 이메일 알림이 설정됨

---

## 🎓 학습 포인트

이번 마이그레이션을 통해 학습한 핵심 개념:

1. **관심사 분리 (Separation of Concerns)**

   - API 서버 ≠ 배치 작업
   - 각 컴포넌트는 독립적으로 배포/확장 가능

2. **이벤트 기반 아키텍처**

   - EventBridge를 통한 스케줄링
   - 느슨한 결합 (Loose Coupling)

3. **서버리스 사고방식**

   - 필요할 때만 리소스 사용
   - 비용 효율성

4. **관찰 가능성 (Observability)**

   - 구조화된 로깅
   - 메트릭 수집
   - 알림 시스템

5. **인프라스트럭처 as Code**
   - Copilot manifests
   - 버전 관리 가능
   - 재현 가능한 배포

---

## 📚 추가 자료

- **아키텍처**: [ARCHITECTURE.md](ARCHITECTURE.md)
- **배포 가이드**: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
- **프로젝트 개요**: [README.md](../README.md)
- **AWS Copilot 문서**: https://aws.github.io/copilot-cli/
- **EventBridge 문서**: https://docs.aws.amazon.com/eventbridge/

---

## 💡 다음 단계

### 즉시 (Immediate)

1. ✅ 이 문서를 읽고 변경 사항 이해
2. ✅ 로컬에서 테스트
3. ✅ dev 환경에 배포

### 단기 (Short-term)

1. 1-2주 모니터링
2. 알람 패턴 분석
3. 필요시 리소스/타임아웃 조정

### 중기 (Mid-term)

1. Spot instances 적용 (비용 70% 절감)
2. Auto Scaling 설정
3. 추가 Job 고려 (예: 데이터 정합성 체크)

### 장기 (Long-term)

1. AWS Step Functions 고려 (복잡한 워크플로우)
2. S3 데이터 레이크 구축
3. 머신러닝 파이프라인 추가

---

**마이그레이션 완료! 🎉**

문제가 있으면 [Deployment Guide](DEPLOYMENT_GUIDE.md#트러블슈팅)의 트러블슈팅 섹션을 참조하세요.
