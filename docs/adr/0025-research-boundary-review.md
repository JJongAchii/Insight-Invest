# ADR-0025: 애매한 핵심 후보의 별도 원문 검수

- 날짜: 2026-09-14.
- 승인: 별도 원문 검수·불일치 승격 보류·월 $2 유지 제안에 대한 `응 지냉해`,
  이후 `이어서 해봐`. qws intent `2d79bae58179`는 변경하지 않는다.
- 상태: 구현 완료, 실제 원문 경계 인수 실패로 운영 배포 보류.

## 결정

ADR-0024의 v6/v7는 같은 경계에서 서로 다른 오분류를 냈다. v7 첫 선별의
프롬프트·캐시·실패 결과를 유지하고, 애매한 core 후보에 별도 source-only 요청을
추가한다. 두 번째 요청은 제목과 원문 passage만 읽으며 첫 분류·선별 근거·한국어
요약을 보지 않는다. 같은 GPT-5 mini이므로 오류의 통계적 독립을 주장하지 않는다.

자동 첫 판단이 core이고 `research + empirical_market_research + empirical_finding`
세 조건이 모두 맞는 경우만 추가 호출을 생략한다. 그 밖의 설명·방법론·실무 core
후보를 검수한다. 첫 판단 context에는 비용을 쓰지 않는다. 이 라우터는 첫 모델의
분류에 의존하며 모든 오분류를 막는다는 보장은 없다. 기관·제목 차단 목록은 없다.

2차 `substantive`면 core, `context/uncertain`이면 held(발견함)다. 검수 누락·만료·
예산 부족·API 실패는 pending(발견함)이며 core로 폴백하지 않는다. 의미 불일치는
같은 원문으로 재호출해 뒤집지 않는다. 읽음·저장·원문·ID·기존 알림 이력은 유지한다.
이 판단은 읽을 가치의 편집 분류이지 논문/투자 주장 검증이나 백테스트가 아니다.

선별 → 필요한 원문 검수 → 한국어 요약 → 요약 원문 대조. 기존 poller·단일 writer·
durable cache/retry·호출 전 예약을 재사용한다. 추가 서비스나 에이전트는 만들지 않는다.
유료 단계 수 상한도 그대로이며 일부 글의 요약 대기 시간/처리량이 줄 수 있다.

## 비용·인수

운영 $1.40 + 격리 검증 $0.60 = UTC 월 $2 요청 예약 한도 유지. 이번 시작 검증
원장은 $0.53899345이며 이전 사용·실패 예약을 지우지 않는다. GPT-5 mini의 입력
$0.25/출력 $2 per 1M, Responses strict Structured Outputs 계약을 유지한다.
[모델](https://developers.openai.com/api/docs/models/gpt-5-mini),
[출력 형식](https://developers.openai.com/api/docs/guides/structured-outputs).

기존 13편의 URL·본문 hash·첫 선별 core/context 기대값을 바꾸지 않는다. 별도
`reading-gate-*` 묶음은 같은 고정 원문을 참조한다. 최종 읽기 경로의 기대값은
양성 7편 core, 음성 6편 context 또는 held다. raw selector의 오분류는 그대로
실패로 기록하고 hold 성공과 혼동하지 않는다. 이전 6개 v7 캐시부터 재사용하며,
실제 호출 수와 캐시 회복 수를 따로 보고한다. 미실행은 성공으로 세지 않는다.

13편 자동 경계 인수·단위 테스트·웹 빌드 후에만 운영 반영한다. 원문 변화, 의미
오분류 또는 예산 부족이면 증거를 보존하고 배포를 보류한다. 캐시 운영 이관은
원문 재조회·digest·근거 문장·기대 경로를 검사한 뒤 immutable 객체만 추가한다.
피드·서재·pending·예산을 이관 스크립트가 쓰지 않는다. 과거 source-bound 수동
편집 결정은 운영 마이그레이션 때 보존하되 자동 인수에서는 사용하지 않는다.

## 2026-09-14 실제 인수 결과 — 배포 보류

- 5138502: 원문 2차 검수·동일 예산·durable retry/cache·발견함 보류 구현.
- d7d657b: 격리 보고서/UI에서도 수동 편집 결과를 빌리지 않도록 투영 분리.
  선별/검수 프롬프트·source fingerprint는 바뀌지 않았다.
- [34789288442](https://github.com/JJongAchii/Insight-Invest/actions/runs/34789288442):
  AQR Academic Alpha·CFM Hidden Beta core 유지, ETF 소개는 첫 core/두 번째
  context 불일치로 held. 첫 선별의 오분류를 수정됐다고 기록하지 않는다.
- [34789435872](https://github.com/JJongAchii/Insight-Invest/actions/runs/34789435872):
  D. E. Shaw Machine Teaching core, 생물다양성 상품화·KCMI 퇴직연금 정책 context.
- [34792518009](https://github.com/JJongAchii/Insight-Invest/actions/runs/34792518009):
  AQR Warming World core, KCMI 토큰증권 인프라 context. **Syzygy SaaS 산업
  전망이 두 번 모두 core/substantive로 잘못 통과**했다.

고정 13편 중 9편 실행, 최종 경로 기대값 일치 8편/불일치 1편. 나머지 4편은
미실행이며 13편 통과나 일반화 정확도를 주장하지 않는다. 신규 API 요청은 9회
(선별 3회 + 원문 검수 6회), $0.03314975. 검증 원장은
$0.53899345 → $0.57214320, 원장 증가와 응답 usage 합계가 일치한다.
예산 소진이 아니라 의미 경계 실패로 추가 유료 호출·캐시 운영 이관·merge를 보류했다.

원문을 다시 읽은 결과 SaaS 글은 사업/산업 분석으로서 설명이 있다. 그러나 고정된
퀀트 핵심 분류의 대상인 투자 규칙·측정·실증을 제시하는 것과는 다르다. 두 번째
판단은 'AI 생산성 → 고용/좌석 라이선스 감소 → 매출·가치평가 영향'을 asset-pricing
mechanism으로 넓게 받아들였다. **설명의 유무와 설명의 분석 대상을 분리하지 않은
검수 설계 결함**이다. 원문이 비어 있거나 API가 실패한 것이 아니다. PDF의 과도한
단어 분절도 관찰되지만, 그것이 이 오분류를 야기했다고 단정하지 않는다.

후속 수정은 호출·심판 수를 늘리는 것이 아니라 같은 2차 요청에서 분석 대상을
투자 규칙/측정/시장 실증과 기업 매출/제품 경쟁/산업 전망으로 명시적으로 구분하는
방향이어야 한다. 아직 그 수정의 성공을 검증하지 않았다. 이 글의 기대값을 바꾸거나
기관별 예외를 추가하지 않았으며 새 유료 버전도 실행하지 않았다.

회귀 277개·Ruff·웹 빌드·1440/390px 원문/보류/검색/저장/모두 읽음 smoke 통과는
상태 전이·UI의 증거이며 위 의미 인수 실패를 덮지 않는다. PR #51은 draft다.
운영 main은 797ba778, Lambda 예산은 $1.40, 운영에는 boundary receipt가 없다.
