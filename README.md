# Insight-Invest 📊

> 투자 분석 및 백테스팅 플랫폼

[![Deploy Status](https://github.com/your-repo/Insight-Invest/workflows/Deploy%20to%20AWS%20Copilot/badge.svg)](https://github.com/your-repo/Insight-Invest/actions)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## 🎯 개요

Insight-Invest는 미국/한국 주식 시장 데이터를 기반으로 한 투자 포트폴리오 분석 및 백테스팅 플랫폼입니다.

### 주요 기능

- 📈 **실시간 주가 데이터**: 미국(NYSE, NASDAQ), 한국(KOSPI, KOSDAQ) 시장 데이터
- 📊 **매크로 경제 지표**: FRED API를 통한 거시경제 데이터
- 🔄 **자동 백테스팅**: 포트폴리오 전략 시뮬레이션
- 📉 **리스크 분석**: 포트폴리오 리스크 메트릭 계산
- 🌐 **RESTful API**: 프론트엔드와 독립적인 API 서버

## 🏗️ 아키텍처

```
┌─────────────────┐
│   Frontend      │  (Vercel)
│   Next.js       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   API Server    │  (AWS ECS Fargate)
│   FastAPI       │
└────────┬────────┘
         │
         ├─────────────────┐
         │                 │
         ▼                 ▼
┌─────────────┐   ┌──────────────┐
│ PostgreSQL  │   │ EventBridge  │
│   (RDS)     │   │  + ECS Tasks │
└─────────────┘   └──────┬───────┘
                         │
                  ┌──────┴──────┐
                  │ Scheduled   │
                  │   Jobs      │
                  │ - US Price  │
                  │ - KR Price  │
                  │ - Macro     │
                  └─────────────┘
```

**설계 원칙**: [Architecture Document](docs/ARCHITECTURE.md)

## 🚀 빠른 시작

### 로컬 개발

```bash
# 저장소 클론
git clone https://github.com/your-username/Insight-Invest.git
cd Insight-Invest

# 환경 변수 설정
cp server/.env.example server/.env
# .env 파일 수정 (DATABASE_URL 등)

# 의존성 설치
cd server
pip install -r requirements.txt

# 개발 서버 실행
uvicorn app.main:app --reload --port 8000

# API 문서 확인
# http://localhost:8000/docs
```

### 프로덕션 배포

상세한 배포 가이드: [Deployment Guide](docs/DEPLOYMENT_GUIDE.md)

```bash
# AWS Copilot으로 배포
copilot svc deploy --name api --env dev
copilot job deploy --name us-price-updater --env dev
copilot job deploy --name kr-price-updater --env dev
copilot job deploy --name macro-updater --env dev
```

## 📂 프로젝트 구조

```
Insight-Invest/
├── server/                      # 백엔드 (FastAPI)
│   ├── app/
│   │   ├── main.py             # FastAPI 앱 (순수 API만)
│   │   └── routers/            # API 엔드포인트
│   │       ├── meta.py
│   │       ├── price.py
│   │       ├── backtest.py
│   │       └── regime.py
│   ├── module/
│   │   └── update_data/        # 데이터 업데이트 모듈
│   │       ├── price.py
│   │       └── macro.py
│   ├── db/                     # 데이터베이스 모델
│   ├── run_scheduled_job.py    # Scheduled Job 실행 스크립트
│   ├── requirements.txt
│   └── Dockerfile
│
├── client/                     # 프론트엔드 (Next.js)
│   ├── src/
│   └── package.json
│
├── copilot/                    # AWS Copilot 설정
│   ├── api/
│   │   └── manifest.yml        # API 서버 설정
│   └── jobs/
│       ├── us-price-updater/
│       ├── kr-price-updater/
│       └── macro-updater/
│
├── .github/
│   └── workflows/
│       └── deploy.yml          # CI/CD 파이프라인
│
├── docs/
│   ├── ARCHITECTURE.md         # 아키텍처 문서
│   └── DEPLOYMENT_GUIDE.md     # 배포 가이드
│
└── scripts/
    └── setup-monitoring.sh     # 모니터링 설정 스크립트
```

## 🔧 기술 스택

### Backend
- **Framework**: FastAPI 0.115+
- **Database**: PostgreSQL (RDS)
- **ORM**: SQLAlchemy 2.0
- **Data Processing**: Pandas, NumPy
- **API Clients**: yfinance, fredapi

### Infrastructure
- **Compute**: AWS ECS Fargate
- **Scheduling**: AWS EventBridge
- **Load Balancer**: Application Load Balancer
- **Monitoring**: CloudWatch
- **CI/CD**: GitHub Actions
- **IaC**: AWS Copilot

### Frontend
- **Framework**: Next.js 14
- **Deployment**: Vercel

## 📊 API 엔드포인트

### 주요 엔드포인트

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/` | 헬스 체크 |
| GET | `/health` | 헬스 체크 (ALB용) |
| GET | `/api/meta` | 종목 메타데이터 조회 |
| GET | `/api/price` | 주가 데이터 조회 |
| POST | `/api/backtest` | 백테스트 실행 |
| GET | `/api/regime` | 시장 국면 분석 |

자세한 API 문서: `http://your-api-url/docs`

## ⏰ Scheduled Jobs

### US Market Price Updater
- **실행**: 매일 18:00 KST (화~토)
- **작업**: 미국 주식 시장 가격 데이터 업데이트

### KR Market Price Updater
- **실행**: 매일 06:00 KST (화~토)
- **작업**: 한국 주식 시장 가격 데이터 업데이트

### Macro Data Updater
- **실행**: 매일 08:00 KST (월~토)
- **작업**: FRED API에서 매크로 경제 데이터 업데이트

## 📈 모니터링

### CloudWatch Dashboard

```bash
# 대시보드 URL 확인
aws cloudformation describe-stacks \
  --stack-name insight-invest-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`DashboardURL`].OutputValue' \
  --output text
```

### 로그 확인

```bash
# API 서버 로그
copilot svc logs --name api --env dev --follow

# Scheduled Job 로그
copilot job logs --name us-price-updater --env dev --follow
```

### 알림 설정

```bash
# 이메일 알림 설정
./scripts/setup-monitoring.sh --email your-email@example.com
```

## 🧪 테스트

```bash
cd server

# 단위 테스트
pytest tests/

# 커버리지 확인
pytest --cov=app tests/

# 특정 테스트 실행
pytest tests/test_backtest.py -v
```

## 📝 개발 워크플로우

### 1. 기능 개발

```bash
# 새 브랜치 생성
git checkout -b feature/new-feature

# 개발 및 테스트
# ...

# 커밋
git add .
git commit -m "Add new feature"
```

### 2. Pull Request

```bash
# PR 생성
git push origin feature/new-feature

# GitHub에서 PR 생성 및 리뷰
```

### 3. 배포

```bash
# main 브랜치에 머지하면 자동 배포
git checkout main
git merge feature/new-feature
git push origin main

# GitHub Actions가 자동으로 배포 진행
```

## 🛠️ 트러블슈팅

### Job이 실행되지 않음

```bash
# Job 상태 확인
copilot job status --name us-price-updater --env dev

# 로그 확인
copilot job logs --name us-price-updater --env dev --since 1h

# 수동 실행
copilot job run --name us-price-updater --env dev
```

### API 응답 느림

```bash
# 스케일 아웃
# copilot/api/manifest.yml에서 count 조정
count:
  range: 1-3

# 재배포
copilot svc deploy --name api --env dev
```

더 많은 트러블슈팅: [Deployment Guide](docs/DEPLOYMENT_GUIDE.md#트러블슈팅)

## 💰 비용 예상

| 항목 | 월 비용 (USD) |
|------|--------------|
| ECS Fargate (API) | ~$13 |
| ECS Fargate (Jobs) | ~$1 |
| Application Load Balancer | ~$16 |
| RDS (db.t3.micro) | ~$15 |
| CloudWatch Logs | ~$2.50 |
| 기타 | ~$1 |
| **총계** | **~$48.50** |

상세 비용 분석: [Architecture Document](docs/ARCHITECTURE.md#-비용-예상-월간)

## 🤝 기여하기

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

## 📞 연락처

Project Link: [https://github.com/your-username/Insight-Invest](https://github.com/your-username/Insight-Invest)

## 🙏 감사의 말

- [yfinance](https://github.com/ranaroussi/yfinance) - 주가 데이터 API
- [FRED API](https://fred.stlouisfed.org/docs/api/fred/) - 매크로 경제 데이터
- [AWS Copilot](https://aws.github.io/copilot-cli/) - 인프라 관리

---

**Built with ❤️ by Insight-Invest Team**
