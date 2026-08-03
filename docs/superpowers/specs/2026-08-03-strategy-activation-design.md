# 전략 운영 전환 (Active) + 리밸 전일 신호 설계

- 작성일: 2026-08-03
- 상태: 구현 완료 (2026-08-03)
- 사용자 결정: 신호는 **목표 비중만**(수량 없음), 노출은 **웹만**(텔레그램 불변),
  포트폴리오 이행 괴리 연계는 **다음 단계**.

## 1. 배경

백테스트한 전략을 "실제 운영"으로 전환하는 개념이 없다. 저장된 전략은 전부
동급이고(P7이 전 전략을 실전 추적), 리밸런싱일에 무엇을 사야 하는지는 사용자가
직접 계산해야 한다.

인프라의 절반은 이미 있다:

- `build_track_strategies`(P7)가 매일 밤 **저장 이후 실전 NAV**를 동일 엔진으로
  재계산 → 전략 상세의 라이브 오버레이·지표, attention 드로다운 경보.
- 엔진 규약이 신호 추출에 정확히 맞다: **리밸일 = 주기(M/Q/Y) 첫 거래일**,
  **비중은 리밸일 전일까지의 가격으로 산출**(`Momentum.simulate`의
  `price[:yesterday]`). 배치가 평일 19:00(장 마감 후)에 돌므로, 전일 저녁에
  오늘까지 데이터로 계산한 비중 = 백테스트가 리밸일에 쓸 비중과 **동일 계산**이다.

없는 것: (1) active 상태, (2) 리밸 전일 목표 비중 신호, (3) 신호의 웹 노출.

## 2. 목표

1. 전략 상세에서 **운영 시작/중지** — registry에 `status`(`saved`|`active`).
2. 배치가 active 전략의 **다음 거래일이 리밸일이면** 목표 비중 신호를 산출해
   `portfolio/rebal_signals.parquet`로 저장 — 직전 리밸 목표 대비
   진입/이탈/유지 표시.
3. 웹 노출: 전략 상세 "다음 리밸런싱" 카드, 목록·홈 ACTIVE 배지, attention
   "내일 리밸" 항목.
4. attention의 전략 드로다운 경보를 **active 전략 한정**으로 조정 (운영 중인
   것만 경보).

## 3. 비목표

- **주문 수량·운영금액 없음** — 목표 비중(%)과 진입/이탈까지. 수량 환산은 사용자.
- **텔레그램 불변** — 브리핑에 신호 섹션을 추가하지 않는다.
- **포트폴리오 이행 괴리 카드 없음** — 다음 단계 (보유 vs 전략 타깃 비교).
- **자동 주문·증권사 연동 없음.**
- **P7 추적 범위 불변** — live_nav는 계속 전 저장 전략을 추적한다 (active만
  추적하면 비활성 전략의 커브 이력이 끊긴다). active는 경보·신호에만 관여.

## 4. 데이터 — registry `status`

`portfolio/registry.parquet`(정확한 파일명은 datastore/portfolio.py의 registry
저장 경로를 따른다)에 `status` 컬럼 추가. 구 행은 컬럼 부재 → `saved`로 읽는다
(`config` 컬럼과 같은 후방호환 패턴). 값: `saved`(기본) | `active`.

API: `POST /backtest/strategy/{port_id}/status` body `{"status": "active"|"saved"}`
→ registry upsert, 404 if unknown port_id, 422 if invalid status.
`GET /backtest/strategy` 및 `GET /backtest/strategy/{port_id}` 응답에 `status` 포함.

## 5. 배치 — `build_rebal_signals()` (신규 빌더)

active 전략별로:

```
cfg 로드 (build_track_strategies와 동일 파싱 — algorithm/freq/params/currency)
as_of = 전략 가격 패널의 마지막 거래일 (오늘)
next_bday = as_of 다음 영업일 (월~금 달력 기준)
if next_bday가 as_of와 다른 주기(freq 기준 월/분기/연)에 속하면:
    엔진 그대로: price(워밍업 포함, 오늘까지) → bt.rebalance(...)의 마지막 행
      + 마지막 행이 이번 주기 것이면 다음 주기 비중을 직접 산출
      (Momentum.simulate와 동일하게 price[:as_of]로 absolute_momentum → top_n)
    prev = portfolio.rebalance(port_id) 마지막 리밸일의 목표 비중
    action = enter(신규) / exit(prev에만 있음, weight 0으로 행 유지) / keep
    행 저장
else: 신호 없음 (해당 전략 행 미생성)
```

- **산출 로직은 엔진 재사용이 원칙**이다. `bt.rebalance`는 가격 인덱스에 있는
  리밸일에만 행을 만들므로 "다음 주기" 행은 나오지 않는다 — 다음 주기 비중은
  전략 클래스의 산출식(`absolute_momentum` → `nlargest(top_n)` → 정규화,
  eq는 1/N, custom은 고정 비중)을 **같은 함수를 호출해서** 얻는다. 조건식을
  베끼지 않는다 (스포트라이트에서 배운 규칙: 산출과 표시가 다른 코드를 재면
  숫자가 거짓이 된다).
- **휴장 처리**: next_bday는 월~금 달력 근사다. 주기 말일이 휴장이면 신호가
  실제 리밸일보다 1~2 저녁 일찍 뜨고, 다음 배치가 최신 데이터로 재산출한다
  (신호는 밤마다 멱등 갱신). UI 문구가 "최종 비중은 리밸 전일 저녁 확정"을
  명시한다. KRX 휴일 캘린더 의존성을 만들지 않는다.
- 리밸일 당일 저녁 배치는 신호를 재생성하지 않는다(next_bday가 같은 주기) —
  파일에는 마지막 신호가 남고, 웹은 `next_rebal <= as_of`면 "지난 신호"로
  표시한다.

### 스키마 — `portfolio/rebal_signals.parquet`

```
port_id, port_name, freq, as_of(산출 기준일), next_rebal(예상 리밸일 = next_bday),
ticker, name, target_weight, prev_weight, action(enter|exit|keep), rank
```

전체 active 전략의 최신 신호만 유지 (밤마다 전체 재작성 — 이력은 rebalance
parquet이 이미 보존). 신호 산출 실패는 전략 단위 경고 후 스킵 (P7과 동일).

## 6. API — `GET /backtest/rebal-signals`

parquet 리더 (인자 없음): `{as_of, signals: [{port_id, port_name, freq,
next_rebal, is_stale(next_rebal <= 최신 거래일), items: [{ticker, name,
target_weight, prev_weight, action, rank}]}]}`. 부재 시 빈 배열, 500 금지.

## 7. 웹

| 위치 | 변경 |
|---|---|
| 전략 상세 (`[port_id]/page.tsx`) | ACTIVE 배지 + "운영 시작/중지" 버튼(확인 다이얼로그 없음 — 가역 토글). **"다음 리밸런싱" 카드**: 신호 있으면 목표 비중 테이블(enter 초록·exit 빨강 배지, prev→target 비중), "as_of 기준 · 최종 비중은 리밸 전일 저녁 확정" 문구. 신호 없으면 "다음 리밸: {다음 주기 첫 거래일 예상} — 신호는 전일 저녁 생성" |
| 전략 목록 카드 | ACTIVE 배지 (뱃지 스타일은 badge-neutral 변형, 새 토큰 없음) |
| 홈 StrategiesCard | ACTIVE 배지만 (신호 상세는 전략 상세로) |
| attention | 신호가 있고 stale 아니면: `{"category": "strategy", "severity": "high", "title": "내일 리밸: {port_name}", "detail": "진입 N · 이탈 M · 유지 K", "link": "/backtest/strategy_list/{id}"}`. 기존 드로다운 경보는 status=active인 전략만 |

RTK Query: `fetchRebalSignals`(providesTags 없음 — 배치 산출물),
`useSetStrategyStatusMutation`(invalidates `Strategies` 계열 태그 — api.ts의
기존 전략 태그 이름을 따른다).

## 8. 에러 처리

| 계층 | 처리 |
|---|---|
| 빌더 | 전략 단위 try/except → 경고 후 스킵, 파이프라인 비중단 |
| status API | 404/422 외 500 금지 — registry 읽기 실패는 503이 아니라 기존 라우터 관례를 따른다 |
| 신호 API | parquet 부재 → 빈 배열 |
| 프론트 | 신호 없음 → 안내 문구, 에러 → 카드 내 ErrorState |

## 9. 테스트

| 대상 | 방식 |
|---|---|
| 다음 주기 판정 (`_is_next_bday_new_period`) | 순수 함수 TDD — 월말 금요일→월요일, 분기 경계, 연 경계, 주중 월중(신호 없음), freq별 |
| 다음 주기 비중 산출 | 픽스처 가격 패널 — Momentum top_n 선정·정규화가 `strategy.Momentum.simulate`의 같은 날짜 행과 일치(엔진 동일성 앵커), eq 1/N |
| action 분류 | prev/target 픽스처 — enter/exit/keep + exit의 weight 0 행 |
| status API | 계약 — 저장→active 토글, 404, 422, 구 행(컬럼 부재) 읽기 `saved` |
| 신호 API | 부재 시 빈 배열 |

## 10. 비용

- 배치: active 전략 수 × 엔진 1회 (P7이 이미 전략마다 엔진을 돌리므로 동급).
  active 0개면 스킵.
- Lambda: parquet 리더 1개 + registry upsert 1개. 인프라 변경 없음.

## 11. 변경 파일

**신규**
- `server/module/rebal_signal.py` — 주기 판정·비중 산출·action 분류 (순수)
- `server/tests/test_rebal_signal.py`, `server/tests/test_strategy_status_api.py`
- `client/src/app/backtest/strategy_list/[port_id]/NextRebalCard.tsx`

**수정**
- `server/datastore/portfolio.py` — registry `status` 후방호환 읽기 + upsert
- `scripts/build_insights.py` — `build_rebal_signals` + BUILDERS 등록
- `server/app/routers/backtest.py` — status POST + rebal-signals GET + 응답에 status
- `server/app/routers/attention.py` — 내일 리밸 항목 + 드로다운 active 한정
- `client/src/state/api.ts`, 전략 상세/목록/홈 카드

## 12. 한계 (문서·UI에 명시)

- next_bday는 월~금 근사 — 휴장 시 신호가 일찍 뜨고 밤마다 갱신된다.
- 신호는 "엔진이 리밸일에 쓸 계산"의 전일 저녁 스냅샷이다 — 당일 시가 갭은
  반영되지 않는다 (백테스트 규약과 동일).
- 목표 비중만 제공 — 수량·주문은 범위 밖.

## 13. 후속 (범위 밖)

- 포트폴리오 이행 괴리 카드 (active 타깃 vs 실보유) — 사용자 결정으로 다음 단계
- 신호 이력 보존·집행 기록 (Decision Journal과 접점)
- 전략 추가 (현재 eq/momentum/dual_mmt/custom)

## 14. 구현 중 확인 (2026-08-03)

- **prev(직전 목표) 출처 정정**: §5는 `portfolio.rebalance()` 저장본의 마지막
  행을 쓰기로 했으나, 저장 parquet은 백테스트 시점 이후 갱신되지 않아 오래
  운영된 전략에서 낡는다. 구현은 엔진 재계산(`bt.rebalance` 마지막 행)을 쓴다
  — 신호 산출과 같은 dropna된 가격 패널을 보므로 자기일관적이다.
- **엔진 동일성 보강**: `Backtest.rebalance`가 내부에서 `dropna()`를 적용하므로
  빌더도 로드 직후 같은 전처리를 한다 — 혼합 캘린더(KR+US) NaN으로 신호와
  prev 계산이 갈리는 것을 막는다.
- **검증**: 엔진 동일성 앵커(1e-12), 강제 경계 실물 검증(dual_mmt 4 ETF, 비중
  합 1) 통과. enter/exit 행 형태는 API 계약 테스트가 커버.
