# Insight-Invest 배포 가이드

## 📋 목차

1. [사전 준비](#사전-준비)
2. [초기 설정](#초기-설정)
3. [API 서버 배포](#api-서버-배포)
4. [Scheduled Jobs 배포](#scheduled-jobs-배포)
5. [모니터링 설정](#모니터링-설정)
6. [배포 확인](#배포-확인)
7. [트러블슈팅](#트러블슈팅)

---

## 🎯 사전 준비

### 필수 도구 설치

```bash
# AWS CLI 설치 (macOS)
brew install awscli

# AWS Copilot CLI 설치
brew install aws/tap/copilot-cli

# 설치 확인
aws --version
copilot --version
```

### AWS 자격 증명 설정

```bash
# AWS 자격 증명 구성
aws configure

# 입력 항목:
# - AWS Access Key ID
# - AWS Secret Access Key
# - Default region: ap-northeast-2
# - Default output format: json
```

---

## 🚀 초기 설정

### 1. Copilot 앱 초기화 (최초 1회만)

```bash
cd /Users/achii/Python_project/Insight-Invest

# Copilot 앱 생성 (이미 있다면 스킵)
copilot app init insight-invest

# 환경 생성 (이미 있다면 스킵)
copilot env init --name dev --profile default
copilot env deploy --name dev
```

### 2. 데이터베이스 URL 설정

```bash
# RDS 연결 정보를 Secrets Manager에 저장
# 형식: postgresql://username:password@host:5432/database
copilot secret init \
  --name DATABASE_URL \
  --values dev=postgresql://user:pass@rds-host:5432/dbname
```

---

## 🌐 API 서버 배포

### 옵션 1: GitHub Actions로 자동 배포 (권장)

```bash
# main 브랜치에 push하면 자동 배포
git add .
git commit -m "Deploy API server"
git push origin main

# GitHub Actions에서 배포 진행 상황 확인:
# https://github.com/your-repo/actions
```

### 옵션 2: 수동 배포

```bash
cd /Users/achii/Python_project/Insight-Invest

# API 서비스 초기화 (최초 1회만)
copilot svc init \
  --name api \
  --svc-type "Load Balanced Web Service" \
  --dockerfile ./server/Dockerfile

# API 서비스 배포
copilot svc deploy --name api --env dev

# 배포 상태 확인
copilot svc status --name api --env dev

# 서비스 URL 확인
copilot svc show --name api
```

---

## ⏰ Scheduled Jobs 배포

### 1. US Market Price Updater

```bash
# Job 초기화 (최초 1회만)
copilot job init \
  --name us-price-updater \
  --dockerfile ./server/Dockerfile \
  --schedule "0 9 * * TUE-SAT"

# Job 배포
copilot job deploy --name us-price-updater --env dev

# 상태 확인
copilot job status --name us-price-updater --env dev
```

### 2. KR Market Price Updater

```bash
# Job 초기화 (최초 1회만)
copilot job init \
  --name kr-price-updater \
  --dockerfile ./server/Dockerfile \
  --schedule "0 21 * * MON-FRI"

# Job 배포
copilot job deploy --name kr-price-updater --env dev

# 상태 확인
copilot job status --name kr-price-updater --env dev
```

### 3. Macro Data Updater

```bash
# Job 초기화 (최초 1회만)
copilot job init \
  --name macro-updater \
  --dockerfile ./server/Dockerfile \
  --schedule "0 23 * * SUN-FRI"

# Job 배포
copilot job deploy --name macro-updater --env dev

# 상태 확인
copilot job status --name macro-updater --env dev
```

### 수동으로 Job 실행 (테스트용)

```bash
# 특정 Job을 즉시 실행
copilot job run \
  --name us-price-updater \
  --env dev

# 로그 확인
copilot job logs \
  --name us-price-updater \
  --env dev \
  --follow
```

---

## 📊 모니터링 설정

### 1. CloudWatch 알림 설정

```bash
cd /Users/achii/Python_project/Insight-Invest

# 실행 권한 부여
chmod +x scripts/setup-monitoring.sh

# 모니터링 설정 (이메일 주소 입력)
./scripts/setup-monitoring.sh --email your-email@example.com

# 이메일 확인하여 구독 승인!
```

### 2. CloudWatch Dashboard 배포

```bash
# 환경 재배포 (대시보드 포함)
copilot env deploy --name dev

# Dashboard URL 확인
aws cloudformation describe-stacks \
  --stack-name insight-invest-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`DashboardURL`].OutputValue' \
  --output text
```

### 3. 로그 확인

```bash
# API 서버 로그
copilot svc logs --name api --env dev --follow

# US Price Updater 로그
copilot job logs --name us-price-updater --env dev --since 24h

# KR Price Updater 로그
copilot job logs --name kr-price-updater --env dev --since 24h

# Macro Updater 로그
copilot job logs --name macro-updater --env dev --since 24h
```

---

## ✅ 배포 확인

### 1. API 서버 헬스 체크

```bash
# API URL 가져오기
API_URL=$(copilot svc show --name api --json | jq -r '.routes[0].url')

# 헬스 체크
curl https://$API_URL/health

# 예상 응답:
# {"status":"healthy"}

# Root 엔드포인트 확인
curl https://$API_URL/

# 예상 응답:
# {"status":"healthy","service":"insight-invest-api","version":"2.0.0"}
```

### 2. Scheduled Jobs 확인

```bash
# 모든 Job 상태 확인
copilot job ls

# 각 Job의 다음 실행 시간 확인
aws events describe-rule \
  --name insight-invest-dev-us-price-updater \
  --query 'ScheduleExpression'

# EventBridge 규칙 목록
aws events list-rules \
  --name-prefix insight-invest-dev
```

### 3. 데이터베이스 연결 확인

```bash
# API를 통해 데이터 조회 테스트
curl https://$API_URL/api/meta

# 응답이 있으면 DB 연결 성공!
```

---

## 🔄 업데이트 배포

### 코드 변경 후 재배포

```bash
# 1. GitHub으로 푸시 (자동 배포)
git add .
git commit -m "Update feature X"
git push origin main

# 2. 또는 수동 배포
copilot svc deploy --name api --env dev
copilot job deploy --name us-price-updater --env dev
copilot job deploy --name kr-price-updater --env dev
copilot job deploy --name macro-updater --env dev
```

### 롤백

```bash
# 이전 버전으로 롤백
git revert HEAD
git push origin main

# 또는 특정 커밋으로 롤백
git reset --hard <commit-hash>
git push -f origin main
```

---

## 🛠️ 트러블슈팅

### Job이 실행되지 않음

```bash
# 1. Job 상태 확인
copilot job status --name us-price-updater --env dev

# 2. EventBridge 규칙 확인
aws events describe-rule --name insight-invest-dev-us-price-updater

# 3. 규칙이 활성화되어 있는지 확인
aws events list-rules --query 'Rules[?State==`DISABLED`]'

# 4. 수동으로 Job 실행하여 테스트
copilot job run --name us-price-updater --env dev
```

### Job 실행 실패

```bash
# 1. 최근 로그 확인
copilot job logs --name us-price-updater --env dev --since 1h

# 2. CloudWatch Logs에서 상세 로그 확인
aws logs tail /copilot/insight-invest-dev-us-price-updater --follow

# 3. 에러 패턴 검색
aws logs filter-log-events \
  --log-group-name /copilot/insight-invest-dev-us-price-updater \
  --filter-pattern "ERROR"
```

### 데이터베이스 연결 실패

```bash
# 1. SECRET 확인
copilot secret list

# 2. DATABASE_URL 재설정
copilot secret init --name DATABASE_URL --overwrite

# 3. 보안 그룹 확인 (ECS 태스크가 RDS에 접근 가능한지)
aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=*insight-invest*"
```

### 메모리 부족 / 타임아웃

```bash
# manifest.yml 수정
# copilot/jobs/us-price-updater/manifest.yml

# 리소스 증가
cpu: 512      # 256 → 512
memory: 1024  # 512 → 1024
timeout: 45m  # 30m → 45m

# 재배포
copilot job deploy --name us-price-updater --env dev
```

### API 응답 느림

```bash
# 1. API 서버 리소스 확인
copilot svc show --name api

# 2. 스케일 아웃
# copilot/api/manifest.yml 수정
count:
  range: 1-3
  cpu_percentage: 70

# 3. 재배포
copilot svc deploy --name api --env dev
```

---

## 🗑️ 리소스 삭제

### 전체 삭제

```bash
# 주의: 모든 리소스가 삭제됩니다!

# 1. 서비스 삭제
copilot svc delete --name api --env dev

# 2. Job 삭제
copilot job delete --name us-price-updater --env dev
copilot job delete --name kr-price-updater --env dev
copilot job delete --name macro-updater --env dev

# 3. 환경 삭제
copilot env delete --name dev

# 4. 앱 삭제
copilot app delete
```

---

## 📚 참고 자료

### 공식 문서
- [AWS Copilot CLI](https://aws.github.io/copilot-cli/)
- [AWS ECS Best Practices](https://docs.aws.amazon.com/AmazonECS/latest/bestpracticesguide/)
- [EventBridge Cron Expressions](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-create-rule-schedule.html)

### 유용한 명령어

```bash
# 모든 서비스/Job 목록
copilot app show

# 특정 서비스 상세 정보
copilot svc show --name api --json

# 비용 확인 (AWS Cost Explorer)
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-01-31 \
  --granularity MONTHLY \
  --metrics "BlendedCost"

# CloudWatch 알람 목록
aws cloudwatch describe-alarms \
  --alarm-name-prefix insight-invest

# SNS 구독 확인
aws sns list-subscriptions
```

---

## 🔐 보안 체크리스트

- [ ] DATABASE_URL이 Secrets Manager에 안전하게 저장됨
- [ ] RDS가 private subnet에 위치
- [ ] 보안 그룹이 최소 권한으로 설정됨
- [ ] API에 rate limiting 설정 (필요시)
- [ ] CloudWatch Logs 암호화 활성화
- [ ] IAM 역할이 최소 권한 원칙 준수

---

## 📞 지원

문제가 발생하면:
1. 로그 확인: `copilot svc/job logs`
2. AWS Console에서 CloudWatch Logs 확인
3. GitHub Issues에 문의

---

**Happy Deploying! 🚀**
