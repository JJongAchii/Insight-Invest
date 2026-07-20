# Insight-Invest 📊

> 개인 시장분석·백테스팅 플랫폼 — 미국(NYSE/NASDAQ)·한국(KOSPI/KOSDAQ) 주식과 FRED 매크로 지표

포트폴리오 구성 → 백테스트 → 저장·비교, 효율적 투자선/리스크 패리티 최적화,
매크로 레짐 대시보드, 종목 검색·비교, 마켓 뉴스를 하나의 웹앱에서 제공한다.

## 아키텍처 (2026-07 재구조)

**"무거운 일은 로컬에서, 클라우드는 서빙만"** — 상시 가동 자원과 클라우드 스케줄 잡이 0개다.

```
[로컬 (맥)]                            [AWS — 서빙 전용]
qdata 레이크 (데이터의 진실)
 └─ launchd (평일 19시, 자가치유)        S3  insight-invest-datalake/
     qdata krx/yf/FRED 갱신    ──sync──▶    ├─ qdata/   qdata clean 미러 (KR 전종목·US ETF·FRED)
                                            └─ app/     meta·US 아카이브·포트폴리오 parquet
                                                 ▲│ 읽기/저장 (pyarrow 푸시다운)
                                        Lambda  insight-invest-api (컨테이너, 요청 시에만 실행)
                                                 ▲ Function URL + X-API-Key
                                        Vercel  Next.js 클라이언트
```

| 계층 | 구성 | 비고 |
|------|------|------|
| API | FastAPI + Mangum → **Lambda 컨테이너** (x86_64, 2GB, 120s) + Function URL | 유휴 비용 $0, 콜드스타트 2~4초 |
| 데이터 | **[quant-data](https://github.com/JJongAchii/quant-data)** S3 미러 + `app/` parquet | DB 없음 — RDS·Iceberg·Glue·Athena 제거됨 |
| 저장 | 포트폴리오 기록 = `app/portfolio/*.parquet` read-modify-write | 단일 사용자 전제 |
| 인증 | 앱 레벨 `X-API-Key` 미들웨어 (`API_TOKEN` 환경변수) | `/`·`/health`만 공개 |
| 배포 | GitHub Actions → ECR → CloudFormation (`infra/template.yaml`) | 스택 1개가 인프라 전부 |
| 프론트 | Next.js 14 (Vercel) | |

### 데이터 소스

| 데이터 | 소스 | 갱신 |
|--------|------|------|
| KR 전 종목 (KOSPI+KOSDAQ, 상폐 포함, 2016~) | qdata KRX 패널 | 매일 (로컬 launchd → sync) |
| US ETF (SPY·TLT 등 레이크 등록 종목) | qdata yfinance | 매일 |
| US 개별주 6,677종목 (1993~2025-12) | `app/us_prices.parquet` 아카이브 | 정지 (구 ETL 이력 보존분) |
| FRED 매크로 (레짐 대시보드) | qdata FRED + RDS 시절 아카이브 병합 | 매일 |
| 종목 메타 9,325건 / 포트폴리오 | `app/meta.parquet` / `app/portfolio/` | 앱에서 저장 시 |
| 뉴스 | Google News RSS 실시간 | 요청 시 |

## 로컬 개발

```bash
# 서버 — python 3.12
cd server
uv venv --python 3.12 .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e "../../quant-data[s3]"
cp .env.example .env        # QDATA_LAKE/APP_DATA: s3:// 또는 로컬 경로 (오프라인 개발 가능)
uvicorn app.main:app --reload   # http://localhost:8000/docs

# 클라이언트
cd client
npm install
cp .env.example .env.local  # NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
npm run dev                 # http://localhost:3000
```

`API_TOKEN`을 비우면 인증이 꺼진다(로컬 개발용). 데이터 위치는 환경변수가 전부라,
같은 코드가 로컬 레이크로도 S3 미러로도 돈다 — 개발 환경 = 운영 환경 − 환경변수.

## 배포

`main`에 `server/**`·`infra/**` 변경이 푸시되면 GitHub Actions(`deploy-api`)가
이미지 빌드 → ECR 푸시 → CloudFormation 배포 → 스모크 테스트까지 수행한다.

필요한 repo secrets:

| Secret | 용도 |
|--------|------|
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | ECR push + CFN deploy |
| `GH_PAT` | quant-data(private) 설치용 — Contents read-only면 충분 |
| `API_TOKEN` | X-API-Key 값 (Vercel `NEXT_PUBLIC_API_KEY`와 동일) |

수동 배포는 `infra/template.yaml` 헤더의 명령 참조. 참고: 2025-10부터 신규 Lambda
Function URL은 `lambda:InvokeFunctionUrl` + `lambda:InvokeFunction`(`InvokedViaFunctionUrl`
조건) 두 권한이 모두 필요하다 — 템플릿에 반영돼 있다.

## 저장소 구조

```
server/
├── app/
│   ├── main.py            # FastAPI + 인증 미들웨어 + Mangum 핸들러
│   ├── schemas.py
│   └── routers/           # meta / price / backtest / regime / optimization / news
├── datastore/             # 데이터 계층 (구 RDS·Iceberg 대체)
│   ├── storage.py         #   APP_DATA(s3://|로컬) parquet 읽기/쓰기
│   ├── meta.py            #   종목 메타·전략·매크로 정의 (캐시)
│   ├── prices.py          #   가격 조회 — qdata(KR/ETF) + US 아카이브 라우팅
│   └── portfolio.py       #   포트폴리오 CRUD (parquet upsert)
├── module/                # 백테스트·최적화·지표·뉴스 엔진
├── Dockerfile             # Lambda 베이스 이미지 (BuildKit secret으로 qdata 설치)
└── requirements.txt
infra/template.yaml        # Lambda + Function URL + IAM (CloudFormation 전부)
client/                    # Next.js 14 + RTK Query
docs/archive/              # 구 ECS/Copilot 시절 문서 (참고용)
```

## 이력

- **v3 (2026-07)**: qdata 소비자로 재구조. RDS·Iceberg·Athena·ECS/Copilot·자체 ETL 제거,
  Lambda+S3 parquet 전환. KR 데이터를 Yahoo `.KS`(KOSDAQ 미지원)에서 KRX 전 종목 패널로 교체.
  월 비용 ~$54 → $0.1 미만. 배경과 결정 기록: quant-data `docs/adr/0002-s3-mirror.md`
- v2 (2025): AWS Copilot 기반 ECS Fargate + RDS PostgreSQL + Iceberg 데이터 레이크 (`docs/archive/`)
- v1 (2025): 단일 서버 + MySQL
