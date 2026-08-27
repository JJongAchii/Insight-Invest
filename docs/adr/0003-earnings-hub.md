# ADR-0003: Earnings Hub data contract

- Status: Accepted
- Date: 2026-08-26

## Context

기존 Action Center의 US Earnings는 보유·관심 종목만 대상으로 하고, 최근 수집 창을
통째로 교체해 과거 발표 결과가 누적되지 않았다. Finnhub의 미래 날짜는 회사 확정
여부를 구분하지 않으며, 정확한 어닝콜 시각·웹캐스트·전문도 제공하지 않는다.

## Decision

1. 앱 통합 마스터의 US `STOCK` 중 양수 시가총액 종목을 qdata의 활성 `CS`·`ADRC`
   참조축과 ticker로 정확히 조인한다.
2. 동일 CIK의 복수 주식 클래스는 시가총액이 큰 클래스 하나로 축약하고 상위 50개
   기업을 Market Leaders로 정한다. 보유·관심 종목은 순위 밖이어도 합집합에 넣는다.
3. Finnhub 전역 Earnings Calendar는 7일 창으로 조회한다. 응답이 1,500행 상한에
   닿으면 날짜 구간을 재귀 분할하며, 하루 응답도 상한에 닿으면 실패로 기록한다.
   내 종목은 심볼별 호출로 한 번 더 확인한다.
4. 이벤트 식별자는 `meta_id + fiscal year + quarter`를 우선한다. 발표일 변경은 새
   이벤트가 아니라 revision으로 남긴다. 과거 발표는 3년 동안 누적하고 새 응답의
   결측이 이미 관측한 actual을 지우지 못하게 한다.
5. Finnhub 일정은 모두 `Estimated`로 표시한다. 실제 EPS 또는 매출이 발표일 이후
   도착한 경우에만 `Reported`로 바꾼다.
6. SEC 링크는 회사의 공식 제출 목록으로만 연결한다. 이후 공식 결과 문서의 의미를
   보수적으로 식별하는 범위는 [ADR-0006](0006-official-earnings-result-signal.md)에서
   추가했으며, 일반 8-K를 실적 공시로 추정하지 않는 원칙은 유지한다.
7. 어닝콜 시각·웹캐스트·전문은 검증된 소스가 제공하지 않는 한 `Not available`로
   표시한다. 발표 전/후 구분을 어닝콜 시각으로 재해석하지 않는다.
8. 대표기업 전체는 Hub에서 조회하고, Web Push는 보유·관심 종목만 Action Center를
   통해 전달한다.

## Published tables

- `app/insight/earnings_universe.parquet`: 현재 유니버스와 조인 키
- `app/insight/earnings_universe_history.parquet`: 일별 유니버스 스냅샷
- `app/insight/earnings_events.parquet`: 누적 일정·발표 결과
- `app/insight/earnings_revisions.parquet`: 발표일 변경 이력
- `app/insight/earnings_source.parquet`: 공급원 상태와 조인·수집 커버리지

## Consequences

무료 소스만으로 일정·컨센서스·실적은 매일 갱신할 수 있지만 정확한 컨퍼런스콜
시각과 전문은 제공 범위 밖이다. 향후 Quartr 같은 라이선스 공급원을 계약하면 기존
이벤트 ID에 call enrichment를 붙이고, 소스·가용시각을 별도로 보존한다.
