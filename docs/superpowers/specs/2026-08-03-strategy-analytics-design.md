# 전략 상세 — 투입 판정·운영 추적 2계층 재설계

- 작성일: 2026-08-03
- 상태: 백엔드 구현 완료 (Phase 1, 2026-08-04) — 프론트 Phase 2 대기
- 사용자 방향: 이 화면의 첫 직무는 **투입 전 성과 분석**(투입 판정·전략 개선
  인사이트)이고, 둘째가 투입 후 추적이다. 화면을 두 계층의 의사결정 표면으로
  재구성한다.
- 데이터 전제: 2026-08-03 엔진 핫픽스(시세 단절 시 NAV 거짓 급락 제거,
  `truncate_to_common_history`) 위에서만 유효 — 라이브 NAV는 다음 배치부터
  정직한 커브다.

## 1. 두 계층

**분석 계층 (모든 전략)** — "이 백테스트를 믿고 투입해도 되는가, 어디가 약한가":

| # | 섹션 | 답하는 질문 | 재료 |
|---|---|---|---|
| A | 전제 카드 | 이 숫자의 조건은? | config(알고리즘·주기·cost_bps·유니버스), nav 구간·거래일수, 리밸 횟수. **cost_bps=0이면 명시 경고** |
| B | 롤링 성과 | 꾸준한가, 한 방인가? | 롤링 1년 수익·샤프 (전략 vs BM) — nav·bm_nav 파생 |
| C | 낙폭 해부 | 최악을 견딜 수 있나? | 수중곡선 + 에피소드 Top5 (깊이·저점일·**회복일수**) |
| D | 국면·위기 성과 | 지금 같은 장에서 어땠나? | 레짐 4국면 × 월수익 (전략 vs BM, regime.phase_history 조인) + CRISIS_WINDOWS(portfolio_risk와 공유) 구간수익 |
| E | 월 수익 통계 | 분포가 어떤가? | 월 승률(절대·BM 대비), 최고/최악 월 Top5 |
| F | 거래 현실성 | 실전 비용이 얼마나 갉아먹나? | 연평균 리밸 횟수, 평균 턴오버(Σ\|Δw\| — 편도 합산, 전량 교체=2.0; 엔진 cost 규약과 동일), 비용 드래그 근사(턴오버×bps — "근사" 명기) |

**운영 계층 (active 전략)** — "약속대로 굴러가는가" (기승인 설계 유지):

| # | 섹션 | 내용 |
|---|---|---|
| ① | 실전 헤드라인 타일 | 저장 후 연환산·현재 낙폭·라이브 vs BM(동기간)·다음 리밸 D-day. 부제에 백테스트 기대치, as_of 명시 |
| ② | 실보유 vs 목표 배분 | live_weights(어제, 드리프트) + 현 주기 목표 + 괴리. 백테스트 최종 배분은 명시적 라벨로 강등 |
| ③ | 기대 대비 실전 | 저장 후 N거래일 수익의 **백테스트 N일 롤링 분포 내 백분위** + 현재 낙폭의 DD 분포 내 위치. 판단 라벨 없이 위치만 |
| ④ | NAV 차트 | 유지 + **벤치마크 라이브 연장** |
| ⑤ | 리밸 이력 | 운영 구간(live_weights에서 추출) + 백테스트 구간 타임라인: 진입/이탈/구간수익 |
| ⑥ | 연/월 수익률 | 저장 후 구간 라이브 실측 병기 |

**정보구조**: saved → A·타일·B~F 순. active → ①②③·다음리밸·④⑤⑥ 위, 분석
계층은 아래 유지(비교 기준이므로 숨기지 않음).

## 2. 비목표

- 백테스트 재실행·파라미터 튜닝 UI 없음 (개선 인사이트는 재료 제시까지 —
  실제 개선은 simulation 페이지에서).
- 백테스트+라이브 합산 단일 지표 없음 (모집단 다름 — 나란히만).
- 벤치마크 다중 선택 없음 (후속).
- 판단 라벨 없음 — "투입 권장/비권장" 문구 금지. 분포 위 위치·조건·경고까지.

## 3. 데이터·계산

**신규 배치 산출물 1개** — `portfolio/live_weights.parquet`
[port_id, trade_date, ticker, weight, as_of]: P7이 이미 계산하고 버리는
드리프트 보유 비중(book)을 전 이력 저장. 운영 구간 리밸 이력(⑤)·실보유(②)의
단일 소스. 규모: 전략 15개 × ~450일 × ~6종목 ≈ 4만 행/년 — 작음.

**신규 순수 모듈** — `server/module/strategy_analytics.py` (TDD):
- `rolling_stats(nav, bm_nav, window=252)` → 롤링 수익·샤프
- `drawdown_episodes(nav, top_n=5)` → [{depth, peak, trough, recover, days_to_recover|None(미회복)}]
- `monthly_stats(nav, bm_nav)` → 승률·최고/최악 월
- `turnover_stats(rebal_long)` → 연평균 리밸·평균 턴오버(Σ|Δw| — 편도 합산, 전량
  교체=2.0; 엔진 cost 규약과 동일)·비용 드래그 근사
- `phase_returns(nav, bm_nav, phases)` → 국면별 월평균 (레짐 조인은 라우터)
- `live_percentile(bt_nav, live_nav)` → N일 수익의 롤링 분포 백분위 + DD 위치
- `crisis_returns(nav, windows)` → portfolio_risk.CRISIS_WINDOWS 재사용

**API** — `GET /backtest/strategy/analytics/{port_id}` 하나로 분석 계층 전부
(nav 3,365행 파생 — 서빙 계산 가벼움, optimization 전례). 운영 계층은 기존
live 응답 확장(weights, percentile). 부재·짧은 이력은 섹션 단위 null+사유,
500 금지.

## 4. 에러 처리·엣지

- nav < 252일: B·③ 생략+사유. bm 없음: BM 비교 열만 생략. 레짐 결측 월: 제외.
- 미회복 낙폭(진행 중): days_to_recover null + "진행 중" 표기.
- cost_bps=0 백테스트: A 카드에 경고 + F의 드래그 근사가 유일한 비용 정보임을 명시.

## 5. 테스트

analytics 순수 함수 전부 손계산 픽스처 TDD (에피소드 경계·미회복·백분위·턴오버).
API 계약(존재/부재/짧은 이력). live_weights는 P7 확장이라 강제 경계 검증 방식.

## 6. 변경 파일

신규: `server/module/strategy_analytics.py`, `server/tests/test_strategy_analytics.py`,
프론트 섹션 컴포넌트(PremiseCard·RollingChart·DrawdownCard·PhaseCard·
MonthlyStatsCard·TradingRealityCard·ExpectationCard·AllocationCompare·RebalHistory).
수정: `scripts/build_insights.py`(P7 live_weights), `server/app/routers/backtest.py`
(analytics GET + live 확장), `client/src/state/api.ts`, `[port_id]/page.tsx`
(2계층 재배치), `LineChart`(BM 라이브 연장), `MetricSummary`(모드 적응).

## 7. 후속

- 벤치마크 선택, 파라미터 민감도(재실행 필요), Decision Journal 연계.
