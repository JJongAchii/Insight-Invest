# ADR-0023: 자료 형식과 투자 주제를 별도 필드로 판정

- 날짜: 2026-09-11
- 승인 범위: radar-editorial-feed-v3 / intent `2d79bae58179`.
- 재개 승인: 자동분류 실패를 수정·재검증하자는 요청에 대한 사용자의 `ㅇㅇ`.
- 선행: ADR-0022, PR #48. v3/v4 실제 실패 영수증은 그대로 보존한다.

## 원인과 변경

v3/v4는 프롬프트에서 주제를 먼저 확인하라고 했지만 응답에는 독립적인 주제 필드가
없었다. `research/practitioner` 형식과 `investment_focus` 진리값이 겹쳐, 퇴직연금
제도 개편 연구가 투자 방법 연구처럼 core가 됐다. 정책 문서를 research가 아니라고
강제하는 것도 형식과 주제의 잘못된 결합이다.

v5는 한 번의 기존 선별 호출에서 `primary_subject`와 `content_kind`를 별도로
받는다. 주제는 투자 방법, 시장 실증, 제도 정책, 연구 업무, 시장 전망, 산업/상품,
기술 업데이트, 기타로 나눈다. 기존 인용·형식·원문 길이 조건과 함께 투자 방법/시장
실증일 때만 core가 가능하다. 정책/연구 업무이면 형식이 research이고 다른 진리값이
true라도 코드에서 context로 남긴다. 상충하는 모델 값은 진단을 위해 영수증에 보존한다.
누락·알 수 없는 주제는 pending이며 과거 캐시를 새 계약의 성공으로 재사용하지 않는다.

Structured Outputs는 schema 순서대로 키를 내보내지만 내용 오류를 없애지는 않는다.
`primary_subject`를 형식보다 앞에 두며, 이것이 오분류를 해결하는지는 실제 API 회귀로
검사한다. 모델/추론/토큰 상한/API 호출 단계 수는 바꾸지 않는다.
[공식 응답 형식 문서](https://developers.openai.com/api/docs/guides/structured-outputs).

## 인수 기준 — 호출 전에 고정

- `reading-subject-v1`: 이전 실패와 **같은 URL·본문·제목·기대 lane**의 KCMI 정책,
  Robeco AI 업무, AQR 스타일 프리미아 원문을 사용한다. 정책 연구를 research 형식으로
  인정할 수 있게 형식 기대만 별도 기록하며, context/core 기대와 주제 기대는 모두 검사한다.
  기존 `reading-scope-v1`의 형식 기대를 덮어쓰지 않는다.
- `reading-subject-positive-v1`: D. E. Shaw 옵티마이저 해설, CFM dip-trade의 beta 분석,
  Robeco 체계적 채권 연구를 core로 보존하는지 별도 검사한다. 원문 hash 변경 시 다른
  자료로 바꾸거나 검사 조건을 완화하지 않는다.
- 동결된 Codex 편집 override가 아닌 `model_state`만 인수 판정에 사용한다.
- 주제·형식·lane 모두 일치하고 요청한 전체 표본이 완료되어야 통과다. 이 표본에 맞춘
  개발 회귀이며, 전체 모집단 정확도나 외부 holdout 평가로 표현하지 않는다.
- 단위 테스트는 형식×주제 조합과 상충하는 진리값, 캐시·출판 경로의 주제 보존을 검사한다.
- 원문 편집 32개와 기존 검수 요약은 보존한다. writer/reviewer 버전은 바꾸지 않는다.

## 비용·배포 경계

기존 GPT-5 mini, production 월 $1.50 + qualification $0.50 원장을 유지한다.
이번 시작 시험 예약액은 $0.46797995이며 잔여 예산 안에서만 실행한다. 예산 파일·실패
영수증을 초기화하지 않는다. 필요하면 새 호출을 멈추며 상한 증액은 사용자 승인이 필요하다.

실제 인수가 통과한 뒤 최신 main을 통합하고 전체 관련 테스트·웹 빌드·배포 스모크와
사용자 상태 보존을 확인한다. 실패한 선별을 배포하거나 문서별 제목 차단 목록으로
회귀를 통과시키지 않는다. 수집 소스 확장·전략 구현·백테스트는 이번 범위 밖이다.

## 실제 재검증 — 2026-09-11

동일 v5 구현 `0d47e25`, 최신 main 통합 커밋 `00e7487`에서 다음 고정 표본 6개가
모두 주제·형식·자동 lane 기대와 일치했다. 동결된 편집 결정은 인수에 사용하지 않았다.

| 원문 | 주제 / 형식 | 자동 lane | Actions run |
| --- | --- | --- | --- |
| KCMI 퇴직연금제도 개편 | institutional_policy / research | context | 34570139448 |
| Robeco AI research workflow | research_operations / practitioner | context | 34570139448 |
| AQR Academic Alpha | investment_methodology / practitioner | core | 34570139448 |
| D. E. Shaw Machine Teaching | investment_methodology / practitioner | core | 34570443364 |
| CFM Hidden Beta in Dip Trade | investment_methodology / research | core | 34570762398 |
| Robeco Systematic fixed income | investment_methodology / practitioner | core | 34570950713 |

CFM 첫 실행 `34570712687`은 작업자의 잘못된 source ID 입력으로 환경 검사에서
중단됐다. sources/items/analysis_runs가 모두 비어 있고 모델 호출은 0회다. 등록된
`cfm-research`로 바로잡아 실행했으며 입력 검사를 완화하지 않았다.

실제 선별 6회, 생성·검수 0회. 토큰 영수증 기준 추가 비용 추정은 $0.021585이며
시험 원장 예약액은 $0.46797995 → $0.48956495 / $0.50이다. 한도·출력 토큰·모델을
바꾸거나 실패 예약을 삭제하지 않았다. 이 숫자는 제공자 청구서가 아니다.

최신 main의 전역 시세 표시를 보존한 상태에서 관련 테스트 234개, Ruff, Next production
build, 실제 출력 1440px/390px 읽기 UI 검사가 통과했다. 현재 운영 스냅샷 654개를
오프라인 적용하면 core 25개(전체 표시 14, 부분 표시 11)이며 ID·기존 영수증·최초
노출 시각·알림 출처를 보존한다. 이는 배포 전 투영 결과다.

이 결과로 ADR-0022의 v4 자동분류 실패에 따른 보류를 해제하고 PR #48의 배포 검증으로
진행한다. 실제 운영 배포·상태 보존 결과는 qws `subject-release-20260911` 증거로
별도 기록한다. 여섯 표본은 개발 회귀이지 미래 전체 문서의 정확도 보증이 아니다.
