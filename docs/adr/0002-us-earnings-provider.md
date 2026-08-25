# ADR 0002: US Earnings 공급자와 시점 계약

- 상태: Accepted
- 날짜: 2026-08-25

## Context

Action Center에는 미국 보유·관심 종목의 실적 예정일과 발표 후 EPS·매출 실제값이
필요하다. 기존 Massive Benzinga Earnings API는 현재 키에서 HTTP 403이며 별도 유료
권한이 필요하다. 화면 크롤링은 구현 가능성만으로 선택하지 않고 이용약관, 응답 계약,
장애 탐지 가능성을 함께 평가해야 한다.

## Decision

1. [Finnhub 공식 Earnings Calendar API](https://finnhub.io/docs/api/earnings-calendar)를
   우선 공급자로 사용한다. 한 응답에 예정일, 장전/장후, EPS·매출 예상값과 발표 후
   실제값이 있어 일정과 발표 내용을 같은 키로 갱신할 수 있다.
2. `FINNHUB_API_KEY`가 없을 때만 기존 Massive Benzinga 경로를 확인한다. 둘 다 사용할
   수 없으면 `configuration_required`를 발행하고 과거 패턴으로 미래 일정을 만들지 않는다.
3. Finnhub는 일정의 확정 여부를 별도 필드로 제공하지 않는다. 실제값이 들어온 과거
   이벤트만 `observed`, 나머지는 모두 `projected`다.
4. `available_at`은 배치가 응답을 수집한 시각, `data_as_of`는 수집일,
   `scheduled_for`는 공급자가 준 발표일이다. 이 세 필드를 서로 대체하지 않는다.
5. 최근 7일과 향후 180일을 읽되 앱의 통합 종목 마스터에 연결된 US 보유·관심 종목만
   남긴다. 조인에서 사라진 종목은 허용하지 않는다.

## Rejected alternatives

- Nasdaq Earnings 화면/API 자동 수집: [Nasdaq 이용약관](https://www.nasdaq.com/legal)이
  자동 데이터 캡처와 스크래핑을 제한하고, 표시된 실적일도 역사적 보고일 기반 알고리즘
  추정치라고 명시하므로 운영 소스로 사용하지 않는다.
- Alpha Vantage Earnings Calendar: 공식 API이고 좋은 예비 후보지만 일정 중심이다.
  발표 후 actual EPS·매출까지 한 계약으로 연결하는 현재 요구에는 Finnhub가 더 직접적이다.
- SEC EDGAR: 인증 없이 실제 접수 공시를 빠르게 확인하는 공식 소스이므로 현재처럼
  `observed` 공시에 계속 사용한다. 다만 기업의 미래 실적 발표 일정을 제공하지 않는다.
- 과거 10-Q/10-K 주기로 다음 발표일 추정: 실제 발표 전 알 수 없었던 정보를 일정처럼
  보이게 하므로 금지한다.

## Operations

배치 EC2의 SSM SecureString `/qdata/FINNHUB_API_KEY`에 토큰을 등록하면 다음 09:00 또는
19:00 KST 실행부터 적용된다. 공급자 장애 시 이전 정상 이벤트는 유효 기간 안에서
보존되고 `External Sources`에는 `Last good`가 표시된다.
