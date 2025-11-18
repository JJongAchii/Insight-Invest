# 🚀 AWS Copilot 배포 가이드 (최종 추천)

## 🎯 왜 AWS Copilot?

**당신의 요구사항:**

- ✅ 기존 AWS 계속 사용
- ✅ GitHub Actions 자동 배포
- ✅ Airflow + Redis + FastAPI
- ✅ docker-compose 같은 간편함
- ✅ RDS 스냅샷 활용

**AWS Copilot = 모든 요구사항 충족!**

---

## 🏗️ AWS Copilot이란?

```
AWS Copilot = docker-compose의 경험 + AWS ECS의 강력함

docker-compose up  →  copilot deploy
                     (실제로는 ECS Fargate에 배포)
```

**자동으로 해주는 것:**

- VPC, Subnet, Security Group 생성
- Load Balancer 설정
- ECS Cluster, Service, Task 생성
- CloudWatch Logs 설정
- IAM Role 설정
- Auto Scaling 설정

---

## 💰 예상 비용 (AWS Copilot)

```
개발 환경:
- ECS Fargate (0.25 vCPU, 0.5GB): $8/월
- RDS db.t3.micro: $15/월
- ElastiCache (Redis) t3.micro: $12/월
────────────────────────────
총: ~$35/월

프로덕션 환경:
- ECS Fargate (0.5 vCPU, 1GB) x 2: $30/월
- RDS db.t3.small: $30/월
- ElastiCache t3.small: $25/월
- Load Balancer: $16/월
────────────────────────────
총: ~$100/월
```

**장점:**

- 기존 RDS 스냅샷 그대로 활용 (복원 비용만)
- AWS 크레딧 있으면 활용 가능
- 필요한 것만 켜고 끌 수 있음

---

## 🚀 빠른 시작 (5단계)

### Step 1: AWS Copilot CLI 설치

```bash
# Mac
brew install aws/tap/copilot-cli

# 확인
copilot --version
```

### Step 2: AWS 자격 증명 확인

```bash
# 이미 설정되어 있는지 확인
aws sts get-caller-identity

# 없다면
aws configure
```

### Step 3: 프로젝트 초기화

```bash
cd /Users/achii/Python_project/Insight-Invest

# Copilot 애플리케이션 생성
copilot app init insight-invest

# 환경 생성 (dev, prod 등)
copilot env init --name dev --profile default --default-config
```

### Step 4: 서비스 정의

```bash
# API 서비스 생성
copilot svc init \
  --name api \
  --svc-type "Load Balanced Web Service" \
  --dockerfile ./server/Dockerfile

# Airflow Webserver 서비스
copilot svc init \
  --name airflow-web \
  --svc-type "Load Balanced Web Service" \
  --dockerfile ./airflow/Dockerfile

# Airflow Scheduler (내부 서비스)
copilot svc init \
  --name airflow-scheduler \
  --svc-type "Backend Service" \
  --dockerfile ./airflow/Dockerfile
```

### Step 5: 배포!

```bash
# 환경 배포 (VPC, Subnet 등 생성)
copilot env deploy --name dev

# 서비스 배포
copilot svc deploy --name api --env dev
copilot svc deploy --name airflow-web --env dev
copilot svc deploy --name airflow-scheduler --env dev

# 상태 확인
copilot svc status --name api
```

**끝!** 🎉

---

## 📝 Copilot Manifest 파일

Copilot은 `copilot/` 폴더에 manifest 파일을 자동 생성합니다.

### `copilot/api/manifest.yml`

```yaml
name: api
type: Load Balanced Web Service

image:
  build:
    dockerfile: ./server/Dockerfile
    context: ./server
  port: 8000

cpu: 256 # 0.25 vCPU
memory: 512 # 512 MB

http:
  path: "/"
  healthcheck:
    path: /health
    success_codes: "200"
    healthy_threshold: 2
    unhealthy_threshold: 3
    interval: 30s
    timeout: 10s

variables:
  ENVIRONMENT: production
  TZ: Asia/Seoul

secrets:
  DATABASE_URL: /copilot/${COPILOT_APPLICATION_NAME}/${COPILOT_ENVIRONMENT_NAME}/secrets/DATABASE_URL
  FRED_API_KEY: /copilot/${COPILOT_APPLICATION_NAME}/${COPILOT_ENVIRONMENT_NAME}/secrets/FRED_API_KEY

environments:
  dev:
    count: 1
    cpu: 256
    memory: 512
  prod:
    count: 2
    cpu: 512
    memory: 1024
    http:
      alias: api.yourdomain.com
```

### `copilot/airflow-web/manifest.yml`

```yaml
name: airflow-web
type: Load Balanced Web Service

image:
  build:
    dockerfile: ./airflow/Dockerfile
    context: ./airflow
  port: 8080

cpu: 512
memory: 1024

http:
  path: "/"
  healthcheck:
    path: /health
    success_codes: "200"

variables:
  AIRFLOW__CORE__EXECUTOR: LocalExecutor

secrets:
  AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: /copilot/${COPILOT_APPLICATION_NAME}/${COPILOT_ENVIRONMENT_NAME}/secrets/AIRFLOW_DB_URL
```

---

## 🔐 Secrets 관리 (AWS Systems Manager)

```bash
# DATABASE_URL 저장
copilot secret init \
  --name DATABASE_URL \
  --values dev=postgresql://user:pass@rds-endpoint/db

# FRED API Key 저장
copilot secret init \
  --name FRED_API_KEY \
  --values dev=your_api_key

# 확인
aws ssm get-parameter \
  --name /copilot/insight-invest/dev/secrets/DATABASE_URL \
  --with-decryption
```

---

## 🗄️ RDS 연결

### 옵션 1: 기존 RDS 스냅샷 복원

```bash
# 1. 스냅샷 확인
aws rds describe-db-snapshots \
  --db-instance-identifier your-old-db

# 2. 스냅샷에서 복원
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier insight-invest-db \
  --db-snapshot-identifier your-snapshot-name \
  --db-instance-class db.t3.micro

# 3. 엔드포인트 확인
aws rds describe-db-instances \
  --db-instance-identifier insight-invest-db \
  --query 'DBInstances[0].Endpoint.Address'

# 4. Copilot Secret에 저장
copilot secret init \
  --name DATABASE_URL \
  --values dev=postgresql://user:pass@<endpoint>:5432/dbname
```

-- postgresql://achii_admin:Hyun0824!@insight-invest-db.cv2sc66yy0h9.ap-northeast-2.rds.amazonaws.com:5432/insight_invest?sslmode=require

### 옵션 2: Copilot으로 새 RDS 생성

```yaml
# copilot/api/manifest.yml에 추가
storage:
  volumes:
    myEFSVolume:
      path: "/data"
      efs: true

  # Aurora Serverless 추가
  databases:
    postgres:
      engine: postgres
      version: 14
      initial_db: insight_invest
```

```bash
# 배포하면 자동으로 RDS 생성
copilot svc deploy --name api --env dev
```

---

## 📦 Redis (ElastiCache) 추가

### `copilot/addons/redis.yml`

```yaml
Parameters:
  App:
    Type: String
  Env:
    Type: String
  Name:
    Type: String

Resources:
  RedisSubnetGroup:
    Type: AWS::ElastiCache::SubnetGroup
    Properties:
      Description: Redis Subnet Group
      SubnetIds:
        - !Ref PrivateSubnet1
        - !Ref PrivateSubnet2

  RedisSecurityGroup:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: Redis Security Group
      VpcId: !Ref VPC
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 6379
          ToPort: 6379
          SourceSecurityGroupId: !Ref ServiceSecurityGroup

  RedisCluster:
    Type: AWS::ElastiCache::CacheCluster
    Properties:
      CacheNodeType: cache.t3.micro
      Engine: redis
      NumCacheNodes: 1
      VpcSecurityGroupIds:
        - !Ref RedisSecurityGroup
      CacheSubnetGroupName: !Ref RedisSubnetGroup

Outputs:
  RedisEndpoint:
    Value: !GetAtt RedisCluster.RedisEndpoint.Address
    Export:
      Name: !Sub ${App}-${Env}-RedisEndpoint
```

---

## 🔄 GitHub Actions 자동 배포

### `.github/workflows/deploy-aws-copilot.yml`

```yaml
name: Deploy to AWS (Copilot)

on:
  push:
    branches:
      - main
    paths:
      - "server/**"
      - "copilot/**"

env:
  AWS_REGION: ap-northeast-2
  APP_NAME: insight-invest
  ENV_NAME: prod

jobs:
  deploy:
    name: Deploy to AWS Copilot
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Install AWS Copilot
        run: |
          curl -Lo copilot https://github.com/aws/copilot-cli/releases/latest/download/copilot-linux
          chmod +x copilot
          sudo mv copilot /usr/local/bin/copilot
          copilot --version

      - name: Deploy API Service
        run: |
          copilot svc deploy \
            --name api \
            --env ${{ env.ENV_NAME }} \
            --app ${{ env.APP_NAME }}

      - name: Deploy Airflow Webserver
        run: |
          copilot svc deploy \
            --name airflow-web \
            --env ${{ env.ENV_NAME }} \
            --app ${{ env.APP_NAME }}

      - name: Deploy Airflow Scheduler
        run: |
          copilot svc deploy \
            --name airflow-scheduler \
            --env ${{ env.ENV_NAME }} \
            --app ${{ env.APP_NAME }}

      - name: Get Service URLs
        run: |
          echo "API URL:"
          copilot svc show --name api --env ${{ env.ENV_NAME }} --json | jq -r '.routes[0].url'

          echo "Airflow URL:"
          copilot svc show --name airflow-web --env ${{ env.ENV_NAME }} --json | jq -r '.routes[0].url'

      - name: Notify Slack (선택사항)
        if: always()
        uses: 8398a7/action-slack@v3
        with:
          status: ${{ job.status }}
          webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

**GitHub Secrets 설정:**

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- (선택) `SLACK_WEBHOOK`

---

## 📊 모니터링 (CloudWatch)

### 로그 확인

```bash
# 실시간 로그
copilot svc logs --name api --follow

# 최근 1시간 로그
copilot svc logs --name api --since 1h

# 특정 환경
copilot svc logs --name api --env prod --follow
```

### 메트릭 확인

```bash
# 서비스 상태
copilot svc status --name api --env prod

# CloudWatch Dashboard
# AWS Console → CloudWatch → Dashboards → insight-invest-prod
```

### 알람 설정 (manifest에 추가)

```yaml
# copilot/api/manifest.yml
observability:
  container_insights: true

environments:
  prod:
    observability:
      container_insights: true

    # 알람 추가
    alerts:
      cpu_percentage:
        threshold: 80
        evaluation_periods: 2
      memory_percentage:
        threshold: 80
        evaluation_periods: 2
      http_error_rate:
        threshold: 5
        evaluation_periods: 2
```

---

## 🔧 일반적인 워크플로우

### 1. 로컬 개발

```bash
# docker-compose로 개발
docker-compose up

# 코드 수정
# 테스트
```

### 2. Dev 환경 배포 (수동)

```bash
# Dev 환경에 배포
copilot svc deploy --name api --env dev

# 테스트
curl https://api-dev.insight-invest.com/health
```

### 3. Prod 배포 (자동 - GitHub Actions)

```bash
# main 브랜치에 푸시
git push origin main

# GitHub Actions가 자동으로:
# 1. 이미지 빌드
# 2. ECR에 푸시
# 3. ECS 서비스 업데이트
# 4. 헬스체크
```

### 4. 롤백

```bash
# 이전 버전으로 롤백
copilot svc deploy --name api --env prod --tag v1.2.3

# 또는 ECS Console에서 이전 Task Definition 선택
```

---

## 💡 Copilot vs 다른 옵션

### Railway

```
장점: 매우 쉬움
단점: AWS 벗어남, 기존 RDS 활용 어려움
```

### AWS ECS (직접)

```
장점: 완전한 제어
단점: 설정 복잡 (수십 개 리소스 수동 생성)
```

### **AWS Copilot** ✅

```
장점: AWS 생태계 유지 + 간편함
- 기존 RDS 스냅샷 그대로 활용
- CloudWatch, IAM 자동 통합
- GitHub Actions 쉽게 연동
- docker-compose 같은 경험
```

---

## 🗺️ 아키텍처

```
GitHub
  ↓ (push)
GitHub Actions
  ↓ (build & deploy)
ECR (Docker Registry)
  ↓
ECS Fargate
  ├─ API Service (Load Balanced)
  │   └─ Tasks: 2 (Auto Scaling)
  ├─ Airflow Web (Load Balanced)
  │   └─ Tasks: 1
  └─ Airflow Scheduler (Backend)
      └─ Tasks: 1

      ↓ (connect)

RDS PostgreSQL (기존 스냅샷 복원)
ElastiCache Redis
CloudWatch Logs & Metrics
```

---

## ✅ 체크리스트

### 준비 단계:

- [ ] AWS CLI 설정 완료
- [ ] AWS Copilot CLI 설치
- [ ] RDS 스냅샷 확인
- [ ] docker-compose.yml 작동 확인

### 배포 단계:

- [ ] Copilot App 초기화
- [ ] Dev 환경 생성
- [ ] 서비스 정의 (API, Airflow)
- [ ] Secrets 설정 (DATABASE_URL 등)
- [ ] RDS 복원 또는 연결
- [ ] ElastiCache Redis 생성
- [ ] Dev 환경 배포
- [ ] 테스트

### CI/CD 설정:

- [ ] GitHub Secrets 설정
- [ ] GitHub Actions workflow 생성
- [ ] Prod 환경 생성
- [ ] Prod 배포
- [ ] 모니터링 & 알람 설정

---

## 🎯 예상 소요 시간

```
초기 설정: 2-3시간
- Copilot 설치 & 설정: 30분
- 서비스 정의: 1시간
- RDS 복원: 30분
- Redis 설정: 30분
- 첫 배포: 30분

GitHub Actions 설정: 1시간

총: 3-4시간
```

---

## 💰 비용 최적화 팁

### 1. Dev 환경 사용 안 할 때 중지

```bash
# 서비스 스케일 0으로
copilot svc scale --name api --env dev --tasks 0

# 다시 시작
copilot svc scale --name api --env dev --tasks 1
```

### 2. Spot Instances 사용

```yaml
# copilot/api/manifest.yml
environments:
  prod:
    deployment:
      rolling: "recreate"
    platform:
      osfamily: linux
      architecture: arm64 # ARM이 더 저렴
      spot: 50 # 50% Spot Instances
```

### 3. Auto Scaling 설정

```yaml
count:
  range:
    min: 1
    max: 4
    spot_from: 2 # 2개부터는 Spot 사용
  cpu_percentage: 70
  memory_percentage: 80
```

---

## 📞 다음 단계

**지금 바로 시작:**

1. **Copilot 설치** (5분)
2. **로컬 docker-compose 테스트** (10분)
3. **Copilot 초기화** (20분)
4. **Dev 환경 배포** (30분)
5. **GitHub Actions 설정** (30분)

**총 1.5시간이면 Dev 환경 완성!**

준비되셨나요? 🚀
