# ADR-0012: Official Earnings actual fallback

- Status: Accepted
- Date: 2026-09-04
- Supersedes: ADR-0003 Decision 5, ADR-0006 Decision 4–5

## Context

DELL FY2027 Q2는 2026-09-01에 SEC 8-K Item 2.02와 EX-99.1 실적 발표문을
제출했지만, 다음 날 Finnhub Earnings Calendar의 `epsActual`과
`revenueActual`은 비어 있었다. 기존 계약은 공식 발표 여부와 링크만 표시하고
수치는 Finnhub를 기다렸기 때문에, 공식 결과가 존재해도 사용자는 핵심 숫자를 볼 수
없었다.

SEC의 GAAP EPS와 Finnhub 컨센서스 EPS는 기준이 다를 수 있으므로 값을 한 필드에
덮어쓰거나 무조건 Beat/Miss로 비교하는 것도 안전하지 않다.

## Decision

1. SEC Submissions에서 정확히 매칭된 `8-K`/`8-K/A` Item 2.02만 공식 수치 추출
   대상으로 한다. 정기보고서와 의미가 불명확한 공시는 기존처럼 결과 존재 신호만
   연결한다.
2. filing index에서 SEC가 호스팅하는 HTML `EX-99.*`만 최대 3개 확인한다. 외부 IR
   사이트, PDF, 임의 파일명 추정, LLM 추출은 사용하지 않는다.
3. 현재 분기 표와 명시적인 통화 단위가 있는 경우에만 revenue, GAAP diluted EPS,
   adjusted/non-GAAP diluted EPS를 읽는다. 동일 지표에 서로 다른 후보가 있으면 해당
   문서는 `ambiguous`로 기각한다.
4. 공식 수치는 `official_*` 필드에 원문 URL·추출 시각·상태와 함께 보존한다.
   Finnhub의 `eps_actual`·`revenue_actual` 원본 필드는 변경하지 않는다.
5. Finnhub Actual이 비어 있으면 API 표시 계층에서 공식 수치를 fallback으로 사용하고
   이벤트를 `Reported`로 보여 준다. 공식 adjusted EPS도 컨센서스 기준이 확인되기
   전에는 EPS Surprise와 종합 Beat/Miss를 계산하지 않는다. 같은 통화의 revenue만
   개별 Surprise를 계산한다.
6. Finnhub Actual이 도착하면 화면 Actual은 다시 표준값을 우선한다. 공식 adjusted
   EPS·revenue와 허용 오차 안에서 일치하는지 `matched`/`differs`로 남기며 GAAP EPS는
   adjusted 값과 비교하지 않는다.
7. SEC 문서가 5 MB를 넘거나 요청·파싱에 실패해도 Earnings 발행은 계속하고 상태와
   커버리지를 기록한다. SEC 요청은 기존처럼 초당 10회 미만으로 제한한다.

## Consequences

- DELL과 같은 공급자 지연 구간에도 공식 매출과 회계기준별 EPS를 같은 배치에서 볼 수
  있다.
- 공식값과 표준값의 출처가 분리되며, 단위가 다른 EPS를 이용한 거짓 Beat/Miss를 막는다.
- 구조가 명확하지 않은 공시는 숫자를 비워 두므로 자동 추출 커버리지는 100%가 아니다.
  이는 잘못된 수치를 채우는 것보다 의도적으로 보수적인 결과다.
- 반영 시점은 기존 09:00·19:00 KST 배치 주기를 따른다.

## References

- [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)
- [SEC DELL FY2027 Q2 8-K](https://www.sec.gov/Archives/edgar/data/1571996/000157199626000039/0001571996-26-000039-index.html)
- [SEC DELL FY2027 Q2 EX-99.1](https://www.sec.gov/Archives/edgar/data/1571996/000157199626000039/exhibit991earnings8kq2fy27.htm)
