# ADR-0019: 원문 피드와 자동 요약 릴리스를 분리

날짜: 2026-09-09 · 상태: 원문 우선 배포 승인, 운영 반영 준비

## 배경

실제 GPT-5 mini 검수 v2/medium 시험(Action 34313772847)은 3개 문서를 처리했다.
2개 보류/1개 시장 배경 요약 통과였으나, AQR의 기존 금융 용어 오역은 검수 모델이 다시
놓쳤다. AQR 게시를 막은 것은 별도 연도-근거 코드 검사였다. API 계약 통과는 한국어
의미 정확성의 인수가 아니다. 같은 모델의 검수 단계를 추가한 것만으로 해결되지 않았다.

따라서 등록된 API 키와 main 배포가 검증되지 않은 요약 기능을 자동으로 켜서는 안 된다.
원문 수집/읽기/서재 상태와 자동 요약의 운영 권한은 분리한다. 이는 완전한 Research
릴리스의 인수 기준을 낮춘 것이 아니다. 사용자는 원문 우선 배포 제안에
“그래 진행해줘봐”로 승인했다 (`user-20260909-original-feed-first-release`).

## 결정

- CloudFormation `ResearchAnalysisEnabled` 기본값은 문자열 `false`이다.
  API 서빙 함수와 ResearchPoller 모두 동일한 `RADAR_ANALYSIS_ENABLED`를 읽는다.
  정확한 `true`만 허용한다. 키·예산·ready 캐시는 릴리스 승인을 대신하지 않는다.
- 비활성 상태에서는 요약/검수 저장소 및 외부 요청 전에 반환한다. `analysis.reason`은
  `editorial_release_pending`이다. 누적 예산/캐시/실패 기록을 지우지 않는다.
- 읽기 API도 비활성 상태에서 캐시된 ready 요약을 노출/핵심 승격하지 않는다. 원문/초록은
  발견함 또는 기존 배경 유형에 남기고 새로운 핵심 배지/Push는 막는다. 기존 요약 데이터와
  source-bound receipt 자체는 삭제하지 않는다. 대기 알림은 보존한다.
- 기본 핵심 탭을 전체 자료로 몰래 바꾸지 않는다. 원문 우선 단계에서는 발견함/전체 기록에서
  자료를 읽는다. 요약 보류를 연구 논문 자체의 부적합/성과 실패로 표시하지 않는다.
- API는 현재 `editorial_enabled`를 읽기 전용으로 알려준다. 웹은 비활성 상태를 명시하고
  핵심 탭에서 ‘발견한 원문 보기’를 제공한다. 배포된 실제 플래그와 다른 알림 안내를 하지 않는다.
- 격리된 수동 `research-qualify` Actions만 명시적으로 이 플래그를 켠다. 기존 S3
  qualification prefix, 정확한 producer commit, 월 $0.50 상한, 단일 실행 규칙은 유지한다.
  운영 예산은 월 $1.50이며 둘의 예약 합계 상한 $2를 유지한다. 추가 유료 호출은 중단했다.
- 카드에서 `publisher_description`은 ‘발행처 소개문’으로 표시한다. 잠정 요약을 원문처럼
  보여주지 않는다. 비활성 이유는 ‘한국어 요약 기능 검증 중 · 원문은 읽을 수 있습니다’다.

## 검사

기본 비활성에서 I/O 0회, 캐시 ready 상태에서도 핵심/미확인 0건, 대기 Push 보존,
읽음/보관 상태 바이트 보존을 회귀 검사한다. qual workflow만 opt-in 하는지도 검사한다.
`scripts/qualify_research_originals.py`는 실제 공개 source probe와 과거 Verdad record를
기존 메모리 S3 대역·임시 합성 서재에 재생한다. 3회 반복 후 추가/수정/삭제/알림 0건을
확인하고 브라우저용 원문 표본을 만든다. 운영 상태 보존의 배포 후 검사를 대체하지 않는다.

main/AWS/Vercel은 아직 바꾸지 않았다. 요약 기능을 켜려면 별도 의미 정확성 인수를
완료해야 한다. API 호출 성공이나 모든 회귀/빌드의 통과만으로 활성화하지 않는다.

## 함께 적용하는 보안 패치

배포 대상의 알려진 취약점을 제거하기 위해 Next / eslint-config-next 16.3.3,
sharp 0.35.4, js-yaml 4.3.2, postcss-selector-parser 6.1.4를 lockfile에 반영했다.
주요 버전 변경이나 기능 확장이 아니며 `npm ci` 감사는 취약점 0건이다.
근거: [Next 공식 권고](https://github.com/vercel/next.js/security/advisories/GHSA-2xp9-vwfh-vxw4),
[sharp 공식 권고](https://github.com/lovell/sharp/security/advisories/GHSA-rgj7-g3m4-5g8c),
[js-yaml 공식 권고](https://github.com/nodeca/js-yaml/security/advisories/GHSA-2883-xcg3-v3hh).
