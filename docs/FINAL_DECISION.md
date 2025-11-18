# 🎯 최종 인프라 결정

## 📋 요구사항 정리

```
✅ 기존 AWS 계속 사용
✅ GitHub Actions 자동 배포
✅ Airflow 추가 예정
✅ Redis 사용 예정
✅ docker-compose 편리함 유지
✅ RDS 스냅샷 활용
✅ 비용 절약
```

---

## 🏆 최종 추천: **AWS Copilot**

### 선택 이유

| 요구사항            | 충족 여부 | 설명                           |
| ------------------- | --------- | ------------------------------ |
| AWS 유지            | ✅        | ECS Fargate 기반, AWS 네이티브 |
| GitHub Actions      | ✅        | 공식 지원, 설정 간단           |
| Airflow             | ✅        | Multi-service 지원             |
| Redis               | ✅        | ElastiCache 자동 연결          |
| docker-compose 경험 | ✅        | manifest가 거의 유사           |
| RDS 스냅샷          | ✅        | 바로 활용 가능                 |
| 비용                | ✅        | $30-50/월 (예측 가능)          |

---

## 💰 최종 비용 비교

### 옵션 1: Railway (추천했던 것)

```
장점: 가장 쉬움
단점: AWS 벗어남, RDS 스냅샷 활용 어려움
비용: $20-30/월
결론: AWS 유지 요구사항에 맞지 않음 ❌
```

### 옵션 2: AWS Lightsail

```
장점: AWS, 저렴
단점: Airflow 불가능, docker-compose 불가능
비용: $25/월
결론: Airflow 요구사항에 맞지 않음 ❌
```

### 옵션 3: AWS ECS Fargate (직접)

```
장점: 완전한 제어
단점: 너무 복잡함 (수십 개 리소스 수동 설정)
비용: $40-60/월
결론: 학습 곡선 너무 가파름 ⚠️
```

### 옵션 4: **AWS Copilot** ✅

```
장점:
- AWS 생태계 완전 통합
- docker-compose 같은 편리함
- GitHub Actions 쉬움
- Airflow, Redis 완벽 지원
- RDS 스냅샷 바로 활용

단점:
- Railway보다는 약간 복잡 (하지만 ECS보다 훨씬 쉬움)

비용: $30-50/월

결론: 모든 요구사항 충족! 🎉
```

---

## 🔄 마이그레이션 플랜

### Phase 1: 로컬 개발 환경 (지금)

```bash
docker-compose up
# FastAPI + PostgreSQL + Redis 테스트
```

### Phase 2: AWS Copilot 설정 (Day 1)

```bash
brew install aws/tap/copilot-cli
copilot app init insight-invest
copilot env init --name dev
```

### Phase 3: 서비스 배포 (Day 2-3)

```bash
copilot svc init --name api
copilot svc deploy --name api --env dev
```

### Phase 4: RDS 복원 (Day 3)

```bash
aws rds restore-db-instance-from-db-snapshot
# 기존 스냅샷 활용
```

### Phase 5: GitHub Actions (Day 4)

```yaml
# .github/workflows/deploy.yml
# 자동 배포 설정
```

### Phase 6: Airflow 추가 (Day 5-7)

```bash
copilot svc init --name airflow-web
copilot svc init --name airflow-scheduler
```

---

## 📊 비교 매트릭스

|                    | Lightsail | Railway    | ECS 직접   | **Copilot** |
| ------------------ | --------- | ---------- | ---------- | ----------- |
| **AWS 유지**       | ✅        | ❌         | ✅         | ✅          |
| **쉬움**           | ⭐⭐⭐    | ⭐⭐⭐⭐⭐ | ⭐         | ⭐⭐⭐⭐    |
| **Airflow**        | ❌        | ✅         | ✅         | ✅          |
| **docker-compose** | ❌        | ✅         | ❌         | ⭐⭐⭐⭐    |
| **GitHub Actions** | ⭐⭐⭐    | ⭐⭐⭐⭐⭐ | ⭐⭐       | ⭐⭐⭐⭐⭐  |
| **RDS 스냅샷**     | ✅        | ⚠️         | ✅         | ✅          |
| **비용**           | $25       | $20-30     | $40-60     | $30-50      |
| **확장성**         | ⭐⭐      | ⭐⭐⭐⭐   | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐  |

**총점: Copilot 승!** 🏆

---

## ✅ 최종 결정

### **AWS Copilot 선택!**

**이유:**

1. ✅ **AWS 생태계 완전 유지**

   - 기존 RDS 스냅샷 바로 활용
   - CloudWatch, IAM 자동 통합
   - AWS 크레딧 사용 가능

2. ✅ **GitHub Actions 완벽 지원**

   - 공식 가이드 존재
   - 간단한 workflow
   - 자동 배포 완성

3. ✅ **Airflow + Redis 지원**

   - Multi-service 아키텍처
   - ElastiCache 쉽게 연결
   - Service Discovery 자동

4. ✅ **적절한 복잡도**

   - Railway만큼은 아니지만 충분히 쉬움
   - ECS 직접 설정보다 10배 쉬움
   - docker-compose 경험 유사

5. ✅ **비용 예측 가능**
   - Dev: $30-35/월
   - Prod: $45-50/월
   - 필요한 것만 사용

---

## 🚀 시작하기

### 지금 바로:

```bash
# 1. 로컬 테스트
docker-compose up --build

# 2. Copilot 설치
brew install aws/tap/copilot-cli

# 3. 초기화
copilot app init insight-invest
```

### 다음 문서 참고:

- `AWS_COPILOT_DEPLOYMENT.md` - 상세 가이드
- `DOCKER_COMPOSE_GUIDE.md` - 로컬 개발
- `MIGRATION_CHECKLIST.md` - 체크리스트

---

## 📞 요약

```
요구사항: AWS + GitHub Actions + Airflow + Redis
최종 선택: AWS Copilot
예상 비용: $30-50/월
예상 시간: 3-4시간 (초기 설정)
난이도: 중간 (Railway < Copilot < ECS)
```

**준비되셨나요?** 🚀

다음 단계:

1. 로컬 docker-compose 테스트
2. AWS Copilot 설치
3. Dev 환경 배포
4. GitHub Actions 설정

어디서부터 시작할까요?
