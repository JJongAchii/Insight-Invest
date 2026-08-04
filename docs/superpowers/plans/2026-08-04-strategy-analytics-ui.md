# 전략 분석 프론트 (Phase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Phase 1 백엔드 계약 위에 전략 상세 화면을 2계층(투입 판정 분석 / 운영 추적)으로 재구성 — 분석 카드 6종 + 운영 카드 3종 + 페이지 재배치.

**Architecture:** 스펙 `docs/superpowers/specs/2026-08-03-strategy-analytics-design.md`. 서버 변경 없음(계약 고정: `GET /backtest/strategy/analytics/{port_id}`, live 응답의 weights/expectation). 기존 카드·차트 프리미티브(Card, TimeSeriesChart, PeriodBarChart, RiskCard/NextRebalCard 패턴) 재사용.

**Tech Stack:** Next.js 14 + RTK Query + Tailwind 자체 토큰 + Recharts 래퍼.

## Global Constraints

- **판단 라벨 금지** — "투입 권장" 류 문구 없음. 서버 수치·라벨·notes 사유·경고까지만.
- 카드별 독립 렌더: analytics 쿼리 하나로 받아 섹션 null이면 그 카드는 `notes`의 사유(있으면) 또는 "데이터 부족" 안내로 렌더 (카드 소실 금지 — 무엇이 왜 없는지 보이게).
- 기존 디자인 토큰만. 새 차트 라이브러리 금지 (TimeSeriesChart/PeriodBarChart 래퍼 재사용).
- 검증: `cd client && npx tsc --noEmit && npm run lint` 에러 0 (매 태스크).
- 브랜치 `feat/strategy-analytics-ui`. Pre-commit 통과, conventional commits 한국어.
- **범위 축소(스펙 대비, T4에서 스펙에 기록)**: ④ BM 라이브 연장, ⑤ 운영 구간 리밸 이력, ②의 "현 주기 목표+괴리" 열은 후속 — 서버 재료(라이브 BM·weights 전체 이력 리더)가 Phase 1 계약 밖이므로 이번엔 만들지 않는다.

---

### Task 1: api.ts — analytics 타입·쿼리 + live 타입 확장

**Files:** Modify `client/src/state/api.ts`

**Interfaces (서버 구현에서 확정된 계약 — 그대로 옮긴다):**

```ts
export interface AnalyticsPremise {
  algorithm: string | null;
  rebal_freq: string | null;
  cost_bps: number | null;
  currency: string | null;
  universe_n: number;
  saved_at: string | null;
  bt_start: string;
  bt_end: string;
  bt_days: number;
  n_rebals: number | null;
  cost_warning: boolean;
}

export interface AnalyticsRollingRow { date: string; roll_ret: number; roll_sharpe: number; }
export interface AnalyticsRolling {
  window: number;
  rows: AnalyticsRollingRow[];
  bm_rows: AnalyticsRollingRow[] | null;
}

export interface DrawdownEpisode {
  depth_pct: number; peak: string; trough: string;
  recover: string | null; days_to_recover: number | null;
}
export interface AnalyticsDrawdowns {
  underwater: { date: string; dd_pct: number }[];
  episodes: DrawdownEpisode[];
}

export interface AnalyticsPhaseRow {
  phase: string; mean_ret_pct: number; n_months: number; bm_mean_ret_pct: number | null;
}
export interface AnalyticsCrisisRow { key: string; ret_pct: number | null; note: string | null; }
export interface AnalyticsMonthly {
  win_rate: number | null; win_rate_vs_bm: number | null;
  best: { month: string; ret_pct: number }[]; worst: { month: string; ret_pct: number }[];
}
export interface AnalyticsTrading {
  n_rebals: number; rebals_per_year: number | null; avg_turnover: number | null;
  cost_drag_pct_10bps: number | null; cost_drag_pct_30bps: number | null;
}

export interface StrategyAnalyticsResponse {
  empty?: boolean;
  premise?: AnalyticsPremise;
  rolling?: AnalyticsRolling | null;
  drawdowns?: AnalyticsDrawdowns | null;
  phases?: { rows: AnalyticsPhaseRow[] } | null;
  crisis?: AnalyticsCrisisRow[];
  monthly?: AnalyticsMonthly | null;
  trading?: AnalyticsTrading | null;
  notes?: Record<string, string>;
  as_of?: string | null;
}

export interface LiveExpectation {
  n_days: number; live_ret_pct: number; ret_percentile: number;
  live_dd_pct: number; dd_percentile: number;
}
export interface LiveWeightRow { trade_date: string; ticker: string; weight: number; }
```

- `StrategyLiveResponse`에 `weights?: LiveWeightRow[] | null; expectation?: LiveExpectation | null;` 추가 (기존 필드 불변 — 실제 인터페이스를 열어 확인).
- 엔드포인트: `fetchStrategyAnalytics: builder.query<StrategyAnalyticsResponse, number>({ query: (portId) => \`/backtest/strategy/analytics/${portId}\` })` + 훅 export.
- 검증 tsc/lint. Commit: `feat(client): 전략 분석 응답 타입·쿼리 (Phase 1 계약)`

---

### Task 2: 분석 카드 6종

**Files:** Create `client/src/app/backtest/strategy_list/[port_id]/analysis/` 아래 6개 컴포넌트 (디렉터리로 분석 계층 구분).

공통 규약 — 각 카드는 `Card`(title) + 해당 섹션 데이터 props. 섹션이 null이면 카드 내부에 `notes` 사유 또는 "이력 부족으로 계산되지 않았습니다" 문구 (카드 자체는 렌더). 스타일은 RiskCard의 타일·행 패턴, 수치 색은 `signColor` 관례(var(--gains)/var(--losses)).

| 컴포넌트 | 내용 (데이터 → 표시) |
|---|---|
| `PremiseCard` | premise → 2열 정의 리스트: 알고리즘·리밸 주기·거래비용(bps)·통화·유니버스 N종목·구간(bt_start~bt_end, bt_days일)·리밸 n_rebals회·저장일. **cost_warning이면 상단에 amber 경고줄**: "⚠ 거래비용 0으로 백테스트됨 — 수익률이 실전 대비 부풀려져 있습니다" (사실 서술). null 필드는 "—" |
| `RollingCard` | rolling → TimeSeriesChart 2개 탭 또는 상하: 롤링 1년 수익률(%)·롤링 샤프, 전략 vs BM(bm_rows 있으면) 2시리즈. 창 표기 "252거래일" |
| `DrawdownCard` | drawdowns → 상단 수중곡선(TimeSeriesChart, area 느낌은 기존 옵션 범위 내), 하단 에피소드 테이블: 깊이·고점→저점→회복·회복일수(null → "진행 중" 배지) |
| `PhaseCrisisCard` | phases.rows + crisis → 좌: 국면별 월평균 수익 막대/행 (전략 vs BM, n_months 병기), 우: 위기 구간 행(covid_2020 → "코로나 급락 (2020-02~03)" 라벨 맵, ret_pct null → note). 현재 국면 강조는 하지 않는다 (regime 쿼리 추가 없이 — 후속) |
| `MonthlyStatsCard` | monthly → 승률 타일 2개(절대·BM 대비) + 최고/최악 월 각 5행 (월, 수익률 색상) |
| `TradingRealityCard` | trading → 타일: 리밸 n회·연평균 rebals_per_year회·평균 턴오버(avg_turnover, "편도 합산 — 전량 교체=2.0" InfoTip)·비용 드래그 근사 "10bps: 연 −x.xx%p / 30bps: 연 −x.xx%p" ("근사" 명기) |

- props는 Task 1 타입 사용. 각 카드 독립 파일, 페이지 결선은 Task 4.
- 검증 tsc/lint (미사용 경고 방지를 위해 임시 index.ts export 또는 lint 설정 확인 — 기존 관례 따름). Commit: `feat(client): 분석 계층 카드 6종 — 투입 판정 재료`

---

### Task 3: 운영 카드 3종 + 연/월 라이브 병기

**Files:** Create `LiveHeadline.tsx`, `HoldingsNowCard.tsx`, `ExpectationCard.tsx` (같은 `[port_id]` 디렉터리). Modify `page.tsx`의 `buildReturnData` 유틸(라이브 시리즈 추가).

| 컴포넌트 | 내용 |
|---|---|
| `LiveHeadline` | liveData(기존 fetchStrategyLiveById) + analytics.premise → 타일 4: 저장 후 실전 수익률(nav 마지막/1000−1, 연환산은 metrics_live.ann_ret 있으면 그것), 현재 낙폭(nav 고점 대비), 라이브 vs BM은 **생략(④ 후속과 함께)** — 대신 저장 후 경과 n일. 각 타일 부제에 백테스트 대응치(metrics_backtest). as_of 명시 |
| `HoldingsNowCard` | live.weights → "현재 보유 비중 (어제 종가 기준, 드리프트 반영)" — WeightBar 또는 RiskCard식 행. weights null이면 "다음 배치부터 집계됩니다" 안내. **"백테스트 최종 배분과 다름"을 명시하지 않아도 됨 — MetricSummary 쪽 라벨이 담당(Task 4)** |
| `ExpectationCard` | live.expectation → "저장 후 {n_days}거래일 수익 {live_ret_pct}%는 백테스트의 모든 {n_days}일 구간 중 **하위/상위 {percentile}%**" + 현재 낙폭 {live_dd_pct}%의 DD 분포 백분위. 백분위를 0~100 가로 스트립 위 마커로 시각화(단순 div bar — 새 차트 불필요). null이면 "표본 부족(최소 5일·분포 60개)" 안내. 문구는 위치 서술만 — 판단 없음 |

- ⑥: `buildReturnData`에 liveNav 인자 추가 — 저장 후 구간의 월/연 바에 `live` 시리즈 병기 (라이브는 있는 기간만; 시리즈 이름 "실전(저장 후)", 색 var(--chart-3)). PeriodBarChart 시리즈 배열 확장.
- 검증 tsc/lint. Commit: `feat(client): 운영 계층 카드 — 실전 헤드라인·보유·기대 대비`

---

### Task 4: 페이지 2계층 재배치 + MetricSummary 정리 + 스펙 기록

**Files:** Modify `page.tsx`, `MetricSummary.tsx`, spec.

- `page.tsx`: `useFetchStrategyAnalyticsQuery(port_id)` 추가. 배치 —
  - 공통 상단: PageHeader(기존 토글·배지).
  - **active**: LiveHeadline → HoldingsNowCard·ExpectationCard(2열) → NextRebalCard → LineChart → LiveMetricsTable → 연/월(라이브 병기) → 구분 헤더 "백테스트 분석" → PremiseCard → RollingCard → DrawdownCard → PhaseCrisisCard → MonthlyStatsCard·TradingRealityCard(2열) → MetricSummary(배분 포함).
  - **saved**: PremiseCard → MetricSummary(기존 타일+배분) → RollingCard → DrawdownCard → PhaseCrisisCard → MonthlyStatsCard·TradingRealityCard(2열) → LineChart → 연/월.
  - analytics 로딩 중엔 분석 카드 영역만 LoadingState (기존 게이트는 불변 — bm 등 기존 쿼리 의존 유지).
- `MetricSummary`: Current Allocation 헤더를 **"백테스트 최종 배분"** 으로 바꾸고 부제 `as of {lastDate} — 백테스트 종료 시점의 목표 배분입니다` (사용자 최초 지적의 명시적 해소 — 현재 보유는 HoldingsNowCard가 담당).
- 스펙: 상태 줄 → `- 상태: 구현 완료 (Phase 2, 2026-08-04)`, `## 8. 구현 중 확인 (Phase 2)` 절 추가 — 범위 축소 3건(④ BM 라이브 연장·⑤ 운영 구간 리밸 이력·② 목표-괴리 열 → 후속, 사유: Phase 1 계약 밖 서버 재료) 기록.
- 검증: tsc/lint + (가능하면) 로컬 dev로 saved·active 각 1개 페이지 수동 렌더 확인 캡처.
- Commit: `feat(client): 전략 상세 2계층 재배치 — 투입 판정이 기본, 운영은 active 상단`
