# ADR-0001: Private PWA access boundary

- Status: Accepted
- Date: 2026-08-19

## Context

Insight Invest는 개인 포트폴리오 쓰기 API를 포함하지만, 기존 브라우저 번들은 Lambda
Function URL과 `NEXT_PUBLIC_API_KEY`를 직접 포함했다. CORS는 브라우저 정책일 뿐 API 인증
경계가 아니므로 공개된 키를 아는 클라이언트는 직접 호출할 수 있었다. 또한 iPhone에서는
매번 Safari URL을 열어야 했고 설치 메타데이터·아이콘·업데이트 정책이 없었다.

## Decision

1. 브라우저의 모든 API 호출은 same-origin `/api/backend/*` Route Handler를 통한다.
   Lambda URL과 API 키는 Vercel 서버 런타임에서만 읽는다.
2. 192-bit 접근 코드의 SHA-256만 저장한다. 로그인 성공 시 원문 접근 코드는 180일짜리
   `HttpOnly`, `Secure`, `SameSite=Strict` 쿠키로 보관한다.
3. Lambda는 기존 API 키와 접근 코드 두 조건을 모두 검증한다. 과거 번들에 남은 API 키만
   알아서는 읽기·쓰기 API를 호출할 수 없다.
4. PWA는 정적 셸 자산만 캐시한다. `/api/*`와 인증된 화면 HTML은 캐시하지 않으며 네트워크
   단절 시 최신 데이터처럼 보이는 숫자 대신 명시적인 오프라인 화면을 표시한다.
5. API 배포는 Vercel 프록시 readiness 확인 뒤 진행해 순차 배포 중 서비스 단절을 막는다.

## Consequences

- 홈 화면 standalone 실행, 전용 아이콘, safe-area, 업데이트 안내를 제공한다.
- 새 기기에서는 접근 코드를 한 번 입력해야 한다.
- 접근 코드를 잃으면 새 코드를 생성해 양쪽 SHA-256을 교체·배포해야 한다.
- 사용자별 계정·감사 로그가 필요해지면 단일 코드 방식을 OIDC 인증으로 교체한다.
