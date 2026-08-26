# ADR-0005: KR ETF intraday snapshot

- Status: Accepted
- Date: 2026-08-26

## Context

KR 장중 폴러의 `get_market_ohlcv_by_ticker`는 KOSPI·KOSDAQ 일반 종목만 반환한다.
통합 자산 마스터와 정산 가격 경로는 ETF를 지원하지만 장중 스냅샷에는 ETF가 없어,
관심·보유 ETF가 장중 화면과 홈의 live quote에서 누락됐다.

KRX는 ETF 전종목 현재가·등락률·거래량·거래대금을 별도 응답으로 제공한다. 이 값은
일반 주식의 시총·업종 분류와 계약이 다르므로 기존 시장 집계에 그대로 합칠 수 없다.

## Decision

1. 각 10분 폴에서 KRX ETF 전종목 등락률을 한 번 추가 조회한다. 등락률은 KRX
   제공값을 그대로 쓰고 보관 종가로 다시 계산하지 않는다.
2. `app/kr_intraday_etf_latest.parquet`에 ETF 표시 전용 스냅샷을 저장한다.
3. 이 스냅샷은 `/intraday/market`의 `my.watchlist`와 `my.holdings`에만 합친다.
   breadth·섹터·거래대금 TOP·급등락 순위는 계속 일반 주식만 계산한다.
4. ETF 조회나 파일 파싱이 실패하면 기존 주식 장중 응답은 유지하고 ETF만 제외한다.
   직전 ETF 파일은 20분 stale 계약 안에서만 사용할 수 있다.
5. 홈 Watchlist는 장중 등락률뿐 아니라 장중 현재가도 함께 덮어쓴다. ETF 투자자별
   20일 수급은 원천 데이터가 없으므로 계속 `N/A`로 표시한다.
6. 파일은 앱 표시 평면에만 존재하며 정산 가격·신호·백테스트에는 연결하지 않는다.

## Consequences

KRX 호출은 폴당 4회에서 5회, 하루 160회에서 200회로 25% 증가한다. 별도 파일로
분리해 ETF 데이터 계약과 장애가 기존 주식 시장 통계에 영향을 주지 않는다.
