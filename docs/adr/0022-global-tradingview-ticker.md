# ADR 0022 — 모든 앱 화면의 TradingView 시세 띠

- 상태: 채택
- 일자: 2026-09-11

사용자는 어느 화면에서도 TradingView 배너를 항상 확인할 수 있게 최상단 또는
최하단에 배치해 달라고 요청했다. 기존 위젯은 홈의 접힌 섹션을 열어야 표시됐다.

## 배치와 시각 방향

공통 DashboardLayout의 **하단 고정 시세 띠**를 선택한다. 기존 상단의 검색·탐색과
본문의 읽기 시작점을 유지하고, 시장·경제·리서치와 개인 도구를 이동해도 시세가 이어진다.
모바일에서는 63px 하단 탐색 메뉴와 기기 safe area 바로 위에 둔다. 로그인·오프라인은
기존 독립 화면을 유지한다.

상단 고정 후보는 상단 탐색과 함께 읽기 시작점을 밀고 기존 섹션 이동의 scroll offset을
바꿔야 한다. 하단 후보는 공통 본문 하단 여백으로 가림을 해결하며 기존 상단 동선을 유지한다.

- 색상: 기존 canvas #0a0f1a, surface #101726, lavender #9b7eff,
  sky #38bdf8, gains #34d399, losses #fb7185와 light 모드 토큰을 유지한다.
- 글꼴: Inter/시스템 한국어 sans의 작은 설명, 기존 SF Mono 숫자 스타일 및 공식 위젯 서체.
- 배치: `본문 / 시세 한 줄 + 공식 출처 / 모바일 탐색 + safe area`.
- 특징: 반복되는 별도 카드 대신 화면 하단의 얇은 시장 시세 띠 하나만 강조한다.
  앱 자체의 추가 애니메이션은 두지 않는다.

## 임베드 수명과 공간

공식 ticker tape iframe의 regular 모드를 사용한다. compact는 오히려 72px의 두 줄이며
regular는 44px 한 줄이다. regular 44px와 위젯 경계 2px, 공식 출처 32px, 상단 경계 1px를 합쳐
79px 공간을 예약한다. 투명 iframe의 흰 기본 배경이 어두운 앱에서 드러나지 않도록
위젯의 불투명 테마 배경을 사용한다. 출처를 잘라내거나 덮어 쓰지 않는다. 기존 지수·원자재·환율·Bitcoin
범위는 보존하고 외부 지연 가능성을 출처 옆에 표시한다. 실제 iframe에서 NASDAQ:NDX는
“이 심볼은 트레이딩뷰에서만 볼 수 있습니다”라는 표시 제한을 확인했다. 이를 표시 가능한
[VANTAGE:NAS100](https://www.tradingview.com/symbols/VANTAGE-NAS100/)으로 연결하고,
기존 VANTAGE:SP500과 함께 명칭에 CFD를 명시한다.

공통 레이아웃에 한 번 마운트해 Next 내부 페이지 이동 시 iframe과 연결을 유지한다.
테마 변경과 명시적 실패 재시도에서만 새 임베드를 만든다. 공식 스크립트는 자신의 부모
요소에서 설정과 컨테이너를 찾으므로 React 관리 DOM 내부에 별도 소유 컨테이너를 만들고,
해제할 때 컨테이너·관찰자·타이머·등록한 이벤트를 제거한다. `next/script`의 URL 단위
중복 제거는 테마별 임베드 재생성과 맞지 않아 공식 DOM 삽입 방식으로 통합한다.

본문 하단 여백과 PWA 설치 안내 위치는 공통 `--app-bottom-inset`을 사용한다.
사이드바가 접히면 띠의 왼쪽 경계도 함께 맞춘다. 상태는 연결 중·표시·실패로 구분하며
실패 시 다시 시도와 TradingView 원문 링크를 제공한다. iframe load는 차단된 문서에서도
발생할 수 있으므로 공식 스크립트가 사용하는 resize 초기화 메시지를 source window와
origin으로 검증한 뒤 표시 상태로 전환한다.

## 검증 근거

- [공식 Ticker Tape](https://www.tradingview.com/widget-docs/widgets/tickers/ticker-tape/)
- [공식 임베드 스크립트](https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js): displayMode별 높이·출처 영역 및 부모 컨테이너 계약 확인.
- 설치된 Next 16.3.3 문서의 Client Components·Scripts 가이드 확인.
- 실제 위젯 표시와 별도 합성 실패/로딩, 내부 페이지 이동, 스크롤, 모바일 탐색·메뉴,
  테마 변경, 320/390/768/1440px 및 본문 마지막 요소 접근을 검증했다.
- 회귀: `client`에서 운영 빌드를 3141 포트로 실행한 뒤
  `node tests/marketTicker.smoke.mjs`. 앱 API와 실패 상황은 합성 fixture이며,
  마지막 시나리오는 실제 공식 TradingView 위젯·시세를 사용한다.
