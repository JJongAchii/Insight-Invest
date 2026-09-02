# Insight-Invest 📊

> 개인 시장분석·백테스팅 플랫폼 — 미국(NYSE/NASDAQ)·한국(KOSPI/KOSDAQ) 주식과 FRED 매크로 지표

포트폴리오 구성 → 백테스트 → 저장·비교, 효율적 투자선/리스크 패리티 최적화,
매크로 레짐 대시보드, 종목 검색·비교, 마켓 뉴스를 하나의 웹앱에서 제공한다.

`Action Center`는 기존 Attention·Watchlist·Holdings·Journal·Strategy·Data Trust를
공통 Event 계약으로 묶는다. 가격 기준 교차, Thesis 검토일, 리밸런싱, 데이터 이상을
한 Inbox/Calendar에 표시하고 판단 근거를 Decision Journal 초안으로 넘길 수 있다.

`Earnings Hub`는 시가총액 상위 미국 기업 50개와 내 보유·관심 종목의 일정·EPS·매출
컨센서스와 발표 결과를 누적한다. 같은 기업의 복수 클래스는 CIK로 축약하고, 미래
일정은 공급자가 회사 확정 여부를 주지 않으므로 Estimated로 표시한다. 정확한 어닝콜
시각·웹캐스트·전문은 검증된 공급원이 없을 때 추정하지 않는다.

`Research Radar`는 승인된 공개 출처의 퀀트 논문·자료를 별도 피드로 투영한다.
출처·미열람 필터와 기기간 중복 방지 Web Push를 제공하며, 원문 열람 상태만
앱에 저장하고 수집기의 canonical record는 변경하지 않는다.

## 아키텍처 (2026-07 재구조)

**"무거운 일은 배치로, 서빙은 요청 시에만"** — 상시 가동 자원이 0개다.
배치 EC2는 각 수집 회차에만 켜지고 완료 후 스스로 꺼진다.

```
[배치 — 평일 09:00·19:00 KST]              [서빙 — 요청 시에만]

EventBridge Scheduler                      S3  insight-invest-datalake/
 qdata-collector-start (Scheduler 2개)          ├─ qdata/      clean 미러 (KR·US·매크로)
   cron(0 9 ...) + cron(0 19 ...) MON-FRI      ├─ qdata-raw/  raw 증분 + 파이프라인 로그
      │ ec2:startInstances                     └─ app/        meta·인사이트·포트폴리오 parquet
      ▼                                             ▲│ 읽기/저장 (pyarrow 푸시다운)
EC2  qdata-collector (t4g.large, ARM)              ││
 systemd qdata-pipeline.service (부팅 시)     Lambda  insight-invest-api
   1. SSM SecureString → .env                        (컨테이너, 요청 시에만 실행)
   2. quant-data·Insight-Invest git pull              ▲ Function URL + X-API-Key
   3. qdata KRX·Massive US·macro/FRED 갱신             │
   4. clean 재빌드 → S3 발행 ──────────────────────────┘
   5. build_insights.py (US 앱 가격 + 파생 인사이트)
   6. send_briefing.py (텔레그램 시황 보고)     Vercel  Next.js 클라이언트
 ExecStopPost: 로그 S3 업로드 + shutdown

 qdata-collector-failsafe-stop
   10:40·20:40 KST — 파이프라인이 죽어도 인스턴스가 방치되지 않게 하는 보험
```

디버깅용으로 EC2에 `touch /data/NOAUTO` 해두면 부팅해도 파이프라인·종료를 건너뛴다.

⚠️ `run_pipeline.sh`는 quant-data 레포에 있고, 스크립트가 **자기 자신을 pull**한다.
따라서 그 스크립트의 변경은 **다음 실행부터** 적용된다 (실행 중인 bash는 이미 구 버전을 읽은 상태).
Insight-Invest 쪽 변경은 pull 이후 서브프로세스로 새로 호출되므로 같은 실행에 반영된다.

| 계층 | 구성 | 비고 |
|------|------|------|
| API | FastAPI + Mangum → **Lambda 컨테이너** (x86_64, 2GB, 120s) + Function URL | 유휴 비용 $0, 콜드스타트 2~4초 |
| 데이터 | **[quant-data](https://github.com/JJongAchii/quant-data)** S3 미러 + `app/` parquet | DB 없음 — RDS·Iceberg·Glue·Athena 제거됨 |
| 저장 | 포트폴리오 기록 = `app/portfolio/*.parquet` read-modify-write | 단일 사용자 전제 |
| 인증 | 앱 레벨 `X-API-Key` 미들웨어 (`API_TOKEN` 환경변수) | `/`·`/health`만 공개 |
| 배포 | GitHub Actions → ECR → CloudFormation (`infra/template.yaml`) | 서빙 스택. 배치 EC2는 CFN 밖 (콘솔 생성) |
| 배치 | EC2 `qdata-collector` + EventBridge Scheduler 2개 | 코드 갱신은 `git pull` — 배포 절차 없음 |
| 프론트 | Next.js 16 (Vercel) | PWA·iOS Home Screen·Web Push |
| 리서치 피드 | Research Radar canonical S3 → 10분 투영 Lambda → `app/research_feed.json` | 원문은 공개 URL, 읽음 상태만 별도 저장 |

### Web Push

iOS/iPadOS 16.4+의 홈 화면 PWA와 데스크톱 브라우저에 표준 Web Push를 보낸다.
`WEB_PUSH_PUBLIC_KEY`와 `WEB_PUSH_PRIVATE_KEY`는 P-256 raw key의 base64url(no padding),
`WEB_PUSH_SUBJECT`는 Apple도 검증할 수 있는 공개 HTTPS URL 또는 실제 `mailto:` 연락처다
(`.local` 주소 금지). 키가 없으면 API·화면은 정상 동작하고 Push만
fail-closed로 비활성화된다. GitHub Actions 배포에는 같은 이름의 repository secret을 둔다.

EventBridge의 `insight-invest-action-poller`가 데이터 배치 뒤 09:45·20:30 KST에 실행된다.
동일 event/subscription 조합은 delivery receipt로 한 번만 보내며, 여러 건은 한 알림으로
묶어 과도한 알림을 방지한다.

`insight-invest-research-poller`는 UTC `:02/:12/...`에 Research 피드를 갱신하고
durable pending을 같은 delivery receipt로 발행한다. 일시 실패는 pending을 남겨 해당
기기만 재시도하고, 404/410 구독은 비활성화한다. 활성 구독이 없을 때는 피드만
갱신하며 나중에 과거 알림을 몰아 보내지 않는다.

### 데이터 소스

| 데이터 | 소스 | 갱신 |
|--------|------|------|
| KR 전 종목 (KOSPI+KOSDAQ, 상폐 포함, 2016~) | qdata KRX 패널 | 매일 (배치 EC2 → S3 sync) |
| US 종목·ETF (앱 meta 등록분, 2008~) | qdata Massive 전종목 가격 + 분할·배당 | 매일 09:00·19:00 KST 배치 → `app/us_prices.parquet` |
| FRED 매크로 (레짐 대시보드) | qdata FRED 단일 원천(필요 시계열 1980~ 직접 수집) | 매일 |
| 통합 종목 마스터 | qdata KRX 주식·ETF + Massive 티커 참조 → `app/asset_master.parquet` | 매일 |
| US 실적 일정·발표 | Finnhub Earnings Calendar + qdata 활성 US 종목 참조 + SEC 공식 제출 페이지 | 평일 09:00·19:00 KST 우선 배치 · 주요 기업 50개 + 내 종목, 과거 결과 누적 |
| 앱 자산 ID / 포트폴리오 | `app/asset_id_registry.parquet` / `app/portfolio/` | 신규 상장·앱 저장 시 |
| 뉴스 | Google News RSS 실시간 | 요청 시 |
| 퀀트 문헌 피드 | qdata Research Radar 공개 출처 watchlist | 수집 10분, 앱 투영 최대 약 5분 후 |

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
이미지 빌드 → ECR 푸시 → CloudFormation 배포 → Research 투영·Push 준비·API 스모크
테스트까지 수행한다.

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
│   └── routers/           # meta / price / backtest / regime / insight / news
│                          # optimization / watchlist / holdings / attention
├── datastore/             # 데이터 계층 (구 RDS·Iceberg 대체)
│   ├── storage.py         #   APP_DATA(s3://|로컬) parquet 읽기/쓰기
│   ├── meta.py            #   종목 메타·전략·매크로 정의 (캐시)
│   ├── prices.py          #   가격 조회 — qdata(KR/ETF) + Massive 기반 US 앱 패널
│   ├── portfolio.py       #   포트폴리오 CRUD (parquet upsert)
│   ├── watchlist.py       #   관심종목 / holdings.py 보유종목
│   └── fx.py              #   환율
├── module/                # 백테스트·최적화·지표·레짐·뉴스 엔진
│   └── research_feed.py  # Radar canonical → 앱 투영
├── tests/                 # pytest (conftest가 server/를 import 루트로 설정)
├── Dockerfile             # Lambda 베이스 이미지 (BuildKit secret으로 qdata 설치)
├── requirements.txt       # 런타임 / requirements-dev.txt 개발 전용(pytest)
scripts/
├── build_insights.py      # 파생 인사이트·Earnings Hub 빌더 (배치 EC2에서 실행)
└── send_briefing.py       # 텔레그램 시황 보고 (배치 EC2에서 실행)
infra/template.yaml        # Lambda + Function URL + IAM (서빙 스택 전부)
.isort.cfg                 # known_first_party 고정 — isort 결과의 cwd 의존성 제거
client/                    # Next.js 16 + RTK Query
docs/archive/              # 구 ECS/Copilot 시절 문서 (참고용)
docs/superpowers/          # 설계·구현계획 기록 (폐기된 것 포함)
```

## 이력

- **v3.3 (2026-09-02)**: Research Radar 전용 PWA 피드·읽음 상태·iPhone Web Push와
  10분 투영 Lambda 추가. Telegram 대신 durable S3 handoff를 소비하도록 이관.
- **v3.1 (2026-07-27)**: 배치를 맥 launchd에서 EC2 `qdata-collector` + EventBridge로 이관
  (README가 이관 전 구조를 그대로 담고 있던 것을 이때 정정). 종목별 팩터 백분위
  parquet 영속화 — `/factor-exposure`가 콜드스타트마다 520일치 전종목을 로드하던 것을 대체.
- **v3.2 (2026-08)**: RDS 덤프 기반 종목·매크로·전략 정의 의존 제거. qdata 단일 종목
  마스터와 append-only 앱 ID 레지스트리로 전환하고 신규 상장을 일일 자동 편입.
- **v3 (2026-07)**: qdata 소비자로 재구조. RDS·Iceberg·Athena·ECS/Copilot·자체 ETL 제거,
  Lambda+S3 parquet 전환. KR 데이터를 Yahoo `.KS`(KOSDAQ 미지원)에서 KRX 전 종목 패널로 교체.
  월 비용 ~$54 → $0.1 미만. 배경과 결정 기록: quant-data `docs/adr/0002-s3-mirror.md`
- v2 (2025): AWS Copilot 기반 ECS Fargate + RDS PostgreSQL + Iceberg 데이터 레이크 (`docs/archive/`)
- v1 (2025): 단일 서버 + MySQL
