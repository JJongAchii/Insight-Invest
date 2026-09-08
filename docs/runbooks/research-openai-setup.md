# Research 요약 API 설정

2026-09-08: 사용자가 키 등록을 완료했고 GitHub secret 이름을 확인했다.
실제 nano/mini 비교 후 사용자가 근거·분류·한국어 보완과 mini 반영을 승인했다.
작업 브랜치 기본 모델은 GPT-5 mini다. 실제 수정 재시험과 다양한 원문 대조가 필요하며,
main/AWS/Vercel 운영 배포는 하지 않았다.

## 사용자가 한 번 설정할 것

1. [OpenAI API keys](https://platform.openai.com/api-keys)에서 이 서비스 전용 키를 만든다.
   기존 ChatGPT 로그인과 별개로 API 프로젝트에서 호출 가능한 결제/크레딧 상태를 확인한다.
   제한 키를 사용하면 Responses API 생성 권한이 필요하다. 관리자 키는 필요 없다.
2. [Insight-Invest Actions secrets](https://github.com/JJongAchii/Insight-Invest/settings/secrets/actions/new)에서
   **Name**은 `OPENAI_API_KEY`, **Secret**은 생성한 키로 저장한다.
3. 채팅에는 키 자체가 아니라 **등록 완료 여부만** 전달한다. 키를 소스 코드, `.env.example`,
   스크린샷, Vercel의 `NEXT_PUBLIC_*` 변수 또는 브라우저 코드에 넣지 않는다.

키 저장만으로 배포되거나 요약이 시작되지는 않는다. GitHub secret은 저장 후 값을 다시
읽을 수 없으므로 로컬 테스트를 위해 꺼내려고 하지 않는다. 실 API 인수는 해당 secret을
안전하게 주입받는 실행 환경에서 별도로 진행한다.

## 연결과 비용 경계

- 모델은 사용자가 승인한 `gpt-5-mini` 하나다. Qwen·Anthropic·상위 모델로 자동 전환하지 않는다.
  [공식 단가](https://developers.openai.com/api/docs/models/gpt-5-mini)는 100만 토큰당
  입력 $0.25 / 출력 $2다. 비용 예약과 사용량 정산 모두 mini 단가를 적용한다.
- `deploy.yml` → CloudFormation `OpenAIApiKey` (`NoEcho`) →
  `insight-invest-research-poller`의 `OPENAI_API_KEY`로만 전달한다.
  브라우저·API 서빙 함수·뉴스 폴러에는 이 키를 추가하지 않는다.
- 키 미등록 시 `analysis.reason=missing_api_key`. 이 경로에서는 요약 관련 저장소 조회나
  HTTP 요청을 하지 않는다. 수집/원문 읽기는 유지하되 새 핵심 연구 승격은 대기한다.
- 월 $2는 **이 Research 작업의 UTC 월별 요청 예약 상한**이다. OpenAI 계정 전체,
  다른 앱, AWS/Vercel, 세금/환율의 청구 상한을 뜻하지 않는다.
  운영 $1.90 + 인수 시험 $0.10으로 분리하여 이 둘을 합해 월 $2 안에 둔다.
  시험 예산과 캐시도 S3에 누적하며 Actions 재실행으로 초기화하지 않는다.
- 요청 입력의 UTF-8 바이트 수에 JSON Schema·인코딩·여유분을 포함해 비용을 보수적으로
  예약한다. 출력 8,192토큰 상한에는 추론 토큰도 포함된다. 응답의 전체 출력 사용량으로
  정산하며, 실패·응답 유실 시 예약액은 돌려놓지 않는다. 따라서 예약액은 실제 청구액이 아니다.
- 입력 24,000자, 정기 실행당 1편, 문서/분석 버전당 최대 3회 시도. 30분 재시도 간격과
  API 인증/HTTP 오류의 1시간 일시 중단을 둔다. 월 상한 도달 시 수집과 원문 접근은 계속된다.
- S3 `app/research_analysis/budget-YYYY-MM.json`이 비용 상태의 정본이다. 캐시는
  `app/research_analysis/cache/`. 단일 ResearchPoller만 쓴다. 같은 APP_DATA에 별도 분석
  작업을 동시에 실행하거나 한도 재설정을 위해 비용 파일을 삭제하지 않는다.
- `store=false`는 Responses 결과 저장 옵션이다. 모든 제공자 측 로그나 보존이 전혀
  없다는 뜻으로 사용하지 않는다. 전송 내용은 공개 원문 발췌와 제목이며 사용자 서재/키는
  모델 입력에 넣지 않는다.

## 배포 전 남은 인수

1. 키/프로젝트 권한·결제 가능 여부를 확인하고, 상한을 둔 실제 요청 1편으로 연결을 검증한다.
   실패하면 상태 코드와 비밀 없는 오류 유형만 기록하며 전체 키/헤더/응답을 로그로 남기지 않는다.
2. 공개 원문 20–30편의 실제 한국어 요약을 원문과 대조한다. AQR 등 주요 소스를 포함하고,
   내용 없는 티저·비퀀트 글·초록/일부 본문만 읽은 사례의 분류와 고지를 확인한다.
   근거 문자열 존재는 의미 정확성의 보증이 아니므로 오프라인 통과만으로 품질을 승인하지 않는다.
3. quant-data/앱의 관련 테스트·웹 빌드, 최초 수집 알림 억제와 읽음/저장/확인 상태 보존을 확인한다.
4. 관련 main 반영 → AWS/Vercel 배포 → 실제 핵심 카드/원문/새 알림 확인 후에만 릴리스 완료를 기록한다.

위 1의 키/연결 확인은 완료했다. 2의 실제 요약 품질 인수와 운영 main/AWS/Vercel 배포는
미완료다. Actions 34179045960과 34185928307이 `api_contract_qualified`를 기록했지만,
두 AQR 요약 모두 원문 대조에서 품질 문제가 확인되어 릴리스 근거로 사용하지 않는다.
이후 mini 3편 비교에서 개선을 확인했고, 사용자는 근거·분류 보완과 mini 반영을 승인했다.
현재 브랜치는 mini, `reasoning.effort=low`, v6 분리 인용/자료 유형 계약을 사용한다.
모델과 프롬프트·추론 설정은 캐시 식별자에 포함된다. 코드 반영과 실제 배포 완료는 별개다.

### 키를 꺼내지 않는 실제 API 시험

기존 `deploy.yml`을 `research-qualify` 모드로 실행한다. quant-data 코드는 정확한
40자리 커밋으로 고정하며, 이 모드에서는 deploy job을 건너뛴다. 처음은 AQR 한 편이다.

```bash
gh workflow run deploy.yml --repo JJongAchii/Insight-Invest \
  --ref radar-editorial-feed-v3 \
  -f mode=research-qualify -f qdata_ref=<검증한_40자리_quant_data_커밋> \
  -f research_max_items=1 -f research_sources=aqr-research
```

`research-radar/qualification/openai/` 아래에만 시험 투영·비용·캐시를 쓴다.
운영 `app/research_feed.json`·사용자 상태·Push outbox는 건드리지 않는다.
시험은 concurrency group으로 직렬화하고, 첫 오류에서 추가 문서 호출을 멈춘다.
`research-qualification-<run>-<attempt>` artifact의 원문 링크·한국어 요약·근거를 대조한다.
`api_contract_qualified`는 연결/출력 계약의 통과이며, 의미 품질이나 리서치 결과의 검증이 아니다.

### mini 비교와 수정 재시험

`research_model=gpt-5-mini`, `research_max_items=3`,
`research_sources=aqr-research,robeco-quant-insights,cfm-research`를 위 수동 시험에 넘긴다.
mini 시험은 최대 3개 출처에서 한 편씩만 허용한다. 출처별 최신 공개 본문을 먼저 선택해
ID·digest를 API 호출 전에 기록한다. 다른 모델/프롬프트의 ready 캐시는 현재 시험의
완료로 세지 않는다. 처음 v4 비교는 nano/mini가 같은 입력·프롬프트·추론을 사용했지만,
수정 재시험은 근거와 분류 계약도 바뀌므로 모델만의 비교라고 부르지 않는다.
시험 프로세스의 선택 모델·단가는 종료 시 앱 기본값으로 복원한다. 이 수동 작업은
CloudFormation 배포와 운영 피드/상태를 변경하지 않는다.

2026-09-08 결과: Actions 34187026159와 34187850601에서 AQR·CFM·Robeco의 실제
mini 요약 3편을 만들었다. 첫 실행의 Robeco AI 소개글은 사전 필터에서 제외되어 호출하지
않았으며, 다음 실행은 앞의 두 mini 캐시를 유지하고 Robeco 채권 글 한 편만 추가했다.
세 편 비용 추정 합계는 $0.008815, 기존 실패 예약을 포함한 시험 누적 예약은 $0.0245597이다.
API 출력 계약은 통과했지만 근거 문장 잘림과 자료 유형 분류 보완이 남았다. mini는
우선 후보라는 편집 판단만 기록했으며 당시 운영 모델·main·배포는 바꾸지 않았다.
그다음 사용자의 “응 진행해줘”로 수정과 앱 기본 mini 반영을 진행한다. 원문 대조의
합격 여부는 새 실제 응답으로 별도 기록하며 기존 실패/예약/캐시는 그대로 보존한다.

## 공식 문서

- [API 키 생성과 사용](https://developers.openai.com/api/docs/quickstart)
- [GPT-5 nano 기능·단가](https://developers.openai.com/api/docs/models/gpt-5-nano)
- [GPT-5 mini 기능·단가](https://developers.openai.com/api/docs/models/gpt-5-mini)
- [Structured Outputs와 미완료/거절 처리](https://developers.openai.com/api/docs/guides/structured-outputs)
- [추론 토큰과 비용 제한](https://developers.openai.com/api/docs/guides/reasoning)
