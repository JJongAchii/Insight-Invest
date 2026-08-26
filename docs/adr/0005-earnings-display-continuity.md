# ADR-0005: Earnings display continuity and discovery

- Status: Accepted
- Date: 2026-08-27

## Context

Finnhub의 `date`는 미국 현지 발표일이다. API가 이를 KST 달력 날짜와 직접 비교하면
장후 발표 종목은 한국에서 다음 날 00시가 되는 순간 `Upcoming`에서 빠진다. 실제치는
아직 도착하지 않았으므로 `Results`에도 들어가지 않아 같은 이벤트가 몇 시간 동안 Hub
전체에서 사라진다. 또한 기존 화면에는 Hub 유니버스 안에서 ticker·회사명으로 과거와
미래 이벤트를 함께 찾는 방법이 없었다.

## Decision

1. 원본 `lifecycle`(`scheduled`/`reported`)은 저장 계약으로 유지하고 API에 표시 전용
   `display_status`를 추가한다.
2. 발표일은 `America/New_York`에서 해석한다. Finnhub의 구간 값은 정확한 시각으로
   오해하지 않고 `bmo=09:30`, `dmh=09:30`, `amc=16:00`, `tbd=23:59` ET를 화면 상태
   전환 기준으로만 사용한다.
3. 표시 상태는 `upcoming → awaiting_results → result_unavailable` 또는 `reported`다.
   발표 구간 뒤 72시간 동안 실제치가 없으면 `awaiting_results`, 이후에도 없으면
   `result_unavailable`로 남긴다. 어느 경우에도 날짜 경계만으로 이벤트를 숨기지 않는다.
4. `GET /earnings`는 `q`를 받아 ticker·회사명을 대소문자 구분 없이 검색하고,
   `pending_results`를 별도 반환한다. 검색은 먼저 Coverage에 적용한 뒤 Calendar와 Results
   기간을 적용한다.
5. 화면은 검색어, Coverage, Calendar 기간, Results 기간, 현재 탭을 URL에 보존한다.
   요약 수치는 해당 탭으로 이동할 수 있고, 발표 후 실제치 대기 상태와 마지막 수집 시각을
   명시한다.

## Consequences

- NVDA 같은 미국 장후 발표 종목은 KST 자정 이후에도 Upcoming에 남고, 발표 구간 뒤에는
  Results의 Awaiting Results에서 계속 찾을 수 있다.
- `release_window_at`은 공식 발표·어닝콜 시각이 아니라 UI 상태 분류용 기준이다. 카드에는
  기존처럼 BMO/AMC 구간만 표시한다.
- 검색 범위는 Market Leaders 50개와 My Coverage의 합집합이다. 미국 전체 종목 검색으로
  오인하지 않도록 화면에 범위를 표시한다.
- 실제값의 도착 속도는 Finnhub와 09:00·19:00 KST 수집 배치에 의존한다. 이 ADR은 공급자
  지연을 숨기지 않고 상태를 연속적으로 보여 주는 결정이며, 별도 실시간 수집을 가장하지
  않는다.
