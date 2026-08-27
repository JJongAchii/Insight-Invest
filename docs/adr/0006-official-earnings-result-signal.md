# ADR-0006: Official Earnings result signal

- Status: Accepted
- Date: 2026-08-27

## Context

Finnhub Earnings Calendar는 일정·컨센서스·표준화된 Actual을 한 계약으로 제공하지만,
발표 직후 Actual 반영 시각에 대한 SLA는 없다. 이 지연 동안 `Awaiting Results`가 결과
발표 여부까지 알 수 없는 상태처럼 보인다. 반면 SEC Submissions API는 접수 공시를
실시간으로 갱신하며 일반적인 처리 지연이 1초 미만이라고 명시하지만, SEC의 GAAP
공시값과 Finnhub의 조정 실적 컨센서스는 그대로 비교할 수 없다.

## Decision

1. Finnhub를 일정·컨센서스·Actual·Beat/Miss의 정본으로 유지한다.
2. 최근 발표 이벤트의 CIK로 SEC Submissions API를 조회한다. 요청은 SEC 정책을
   넘지 않도록 초당 10회 미만으로 제한하고 식별 가능한 연락처를 User-Agent에 넣는다.
3. `8-K`와 `8-K/A`는 `items`에 정확히 `2.02`가 있을 때만 공식 실적 결과로 인정한다.
   `10-Q`, `10-K`, `20-F`, `40-F`와 각 amendment는 정기 실적 문서이므로 보조
   공식 결과로 인정한다. 의미를 판별할 수 없는 일반 `8-K`와 `6-K`는 자동 연결하지 않는다.
4. SEC 신호는 `official_result_*` 필드와 개별 filing index 링크만 보강한다. SEC의
   숫자를 `eps_actual`·`revenue_actual`에 복사하거나 Finnhub estimate와 비교하지 않는다.
5. 공식 공시가 먼저 확인되면 `Official Result Filed`로 표시하되 이벤트는 Finnhub
   Actual이 올 때까지 `Awaiting Results`에 둔다. Actual이 들어오면 기존 규칙대로
   `Reported`와 Beat/Miss로 자동 전환한다.
6. SEC 보강 실패는 Finnhub 갱신을 막지 않는다. 소스 상태에 실패를 기록하고 이미
   연결된 공식 filing 필드는 누적 이력 병합으로 보존한다.

## Consequences

- 사용자는 공급자 Actual을 기다리는 동안에도 회사가 공식 결과를 발표했는지 확인하고
  SEC 원문으로 바로 이동할 수 있다.
- Beat/Miss의 비교 단위가 섞이지 않는다.
- 의미 식별이 어려운 외국기업 `6-K`는 초기 범위 밖이다. 신뢰할 수 있는 문서 분류
  계약을 추가하기 전에는 파일명이나 제목만으로 실적 공시라고 추정하지 않는다.
- 데이터는 기존 09:00·19:00 KST 배치 주기로 반영된다. 이 변경은 SEC 자체의 실시간
  갱신을 앱의 실시간 폴링으로 과장하지 않는다.

## References

- [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- [SEC Form 8-K Item 2.02](https://www.sec.gov/divisions/corpfin/forms/8-k.htm)
- [Finnhub Earnings Calendar](https://finnhub.io/docs/api/earnings-calendar)
