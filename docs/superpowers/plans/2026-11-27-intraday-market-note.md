# 장중 시장 노트 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 홈 장중 해설을 "시장 지도(모델 없음, 10분) + 장중 노트(AI, 정시·급변) + 노트 이후 변화 + 시장 급변 알림"으로 바꾼다.

**Architecture:** Insight 장중 폴러가 KRX 스냅샷으로 시장 지도(기여도·시장 폭·쏠림·묶음)를 계산해 앱 파일과 `market_desk/input.json`에
싣는다. ai-company 시장 데스크가 그 지도와 등록 매체 원문으로 정시·급변 노트를 쓰고 근거를 검증해 `board.json`의 `notes`·`alerts`로
게시한다. Insight API·화면이 노트·지도·노트 이후 변화를 보이고, 알림 폴러가 급변 알림을 보낸다.

**Tech Stack:** Insight — Python 3.12 FastAPI/Lambda, pandas, Next.js 16 + RTK Query. ai-company — Python 3.12, PostgreSQL, pydantic,
Codex 구독 레인(`gpt-6.1-sol`).

**Spec:** `docs/superpowers/specs/2026-11-27-intraday-market-note-design.md`

## Global Constraints

- 장중 데이터는 표시·해설 입력 전용. 레이크·신호·백테스트에 쓰지 않는다. 당일만 보존(다음 거래일 첫 폴에서 리셋). KRX 외 시세 벤더 없음.
- 종목 등락률은 KRX 제공값만 쓴다(종가로 재계산 금지). 스팩(이름에 "스팩")·거래정지는 지도에서 제외한다.
- 근거 표시는 `데이터`·`보도`·`해석` 세 가지. 노트 숫자는 packet 지도 값 또는 인용문에 있어야 한다. 매수·매도 권유와 목표가 금지.
- 정시 노트: 개장+40분, 개장+120분, 개장+270분, 마감−40분, 마감+25분. 직전 노트 30분 이내면 건너뜀.
- 급변: T1 코스피 ±2%·코스닥 ±3% 첫 돌파(방향별 1회), T2 직전 노트 대비 코스피 ±1.0%p·코스닥 ±1.5%p, T3 당일 사이드카·서킷브레이커 보도.
  급변 노트 30분 간격·하루 3회, 정시 15분 이내면 정시로 합침. 노트 전체 하루 최대 8회.
- 알림: T1·T3만, 하루 최대 3회, 같은 사건은 기기마다 1회.
- 노트 작성은 Codex(`news-market-desk-` 요청, `gpt-6.1-sol`, medium). 한도·불가 거절은 그 회차를 건너뛴다. 새 ID 재시도 없음.
- ai-company 노트 작성은 설정 `INSIGHT_NOTES_ENABLED`(기본 false)로 켠다. Insight 홈 교체 전에는 `/notes`에서만 노트를 본다.
- 운영 변경은 리뷰된 PR의 main 머지로만. 커밋·푸시는 사용자가 요청할 때만 한다.

## Review Focus

- 장 전·휴장일·KRX 지연(스냅샷이 20분 넘게 오래됨): 지도·노트 이후가 오래된 값을 최신처럼 보이지 않는다 — Task 4 테스트.
- 첫 노트 전 / 노트가 하나도 없는 날: 홈은 지도와 기존 대표 해설로 정상 표시 — Task 5 스모크.
- 같은 날 두 번째 폴부터 거래대금 기준선이 없거나 qdata가 늦음: 쏠림만 비우고 나머지 지도는 계산 — Task 2 테스트.
- 모델이 지도에 없는 숫자·종목을 쓰거나 [해석]에 근거 참조가 없음: 노트 거절, 직전 노트 유지 — Task 6 테스트.
- 사이드카 보도가 같은 날 여러 매체에서 반복: 알림·급변 노트는 한 번 — Task 7·9 테스트.

---

### Task 1: 시장 지도 계산 (Insight)

**Files:**
- Create: `server/module/market_map.py`
- Test: `server/tests/test_market_map.py` (fixture `server/tests/fixtures/intraday_20261127/latest_1105.parquet`)

**Interfaces:**
- Produces: `build_map(latest: pd.DataFrame, indices: dict[str, dict], baseline: pd.DataFrame | None, themes: list[dict], observed_at: str) -> dict`
  (`indices` = `{"KOSPI": {"level": float, "chg_pct": float|None}, ...}`; `baseline` columns `ticker, avg_value`; 결과 키:
  `version, trade_date, observed_at, indices, markets{KOSPI,KOSDAQ}{breadth, contributors{up,down}, top10_share, sectors}, value_spikes, groups`)
- Produces: `series_entry(map_: dict) -> dict` (지수 등락률, 상·하한가 티커, 기여 상위 티커, 쏠림 티커)
- Produces: `since(old: dict, new: dict) -> dict | None` (지수 변화, 새 상·하한가·기여 상위·쏠림 종목, 의미 있는 차이 없으면 None)

- [ ] **Step 1: 실패 테스트** — 11:05 고정본으로:
  - 기여 합(`approx_chg_pct`) KOSPI 1.77, KOSDAQ 5.68 (±0.01), `top10_share` KOSPI 0.54, KOSDAQ 0.29 (±0.01)
  - KOSPI 상승 기여 1·2위 삼성전자 0.36, SK하이닉스 0.20 (±0.01); KOSDAQ 1위 레인보우로보틱스
  - KOSDAQ breadth up 1461, down 219, `up10` 93, `limit_up` 이름 6개(대성하이텍·쏘닉스·에스피시스템스·제닉스로보틱스·코스모로보틱스·퀀텀레일)
  - 이름에 "스팩"이 든 종목을 넣으면 기여·상한가·쏠림 어디에도 없다
  - `since`: 지수 +0.5%p 미만 변화와 새 종목 없음 → None; 상한가 하나 추가 → 그 종목을 반환
- [ ] **Step 2: 실패 확인** `cd server && APP_DATA=<tmp> python -m pytest -q tests/test_market_map.py` → ImportError
- [ ] **Step 3: 구현** — 기여(%p) = (시총 − 시총/(1+r)) / Σ(시총/(1+r)) × 100; 상한가 = 등락률 ≥ 29.5; 묶음 = 같은 테마(`market_themes.json`) 또는
  같은 업종에서 3종목 이상 ±7%. 쏠림 = 누적 거래대금 ÷ `avg_value`, 거래대금 100억 이상·배수 3 이상 상위 8.
- [ ] **Step 4: 통과 확인** 같은 명령 → PASS

### Task 2: 거래대금 기준선 (Insight)

**Files:**
- Modify: `server/module/market_map.py` (`value_baseline`), `server/app/intraday_poller.py` (`_value_baseline`)
- Test: `server/tests/test_market_map.py`, `server/tests/test_intraday_poller.py`

**Interfaces:**
- Produces: `value_baseline(daily: pd.DataFrame, trade_date: str, sessions: int = 20) -> pd.DataFrame[ticker, avg_value]`
  (trade_date 이전 거래일만, 최근 20개)
- Produces: poller `_value_baseline(trade_date: str) -> pd.DataFrame | None` — `app/kr_value_baseline.parquet`에 `trade_date` 열과 함께 캐시,
  날짜가 다르면 qdata `load_krx_prices(start, end, columns=["date","ticker","value"])`로 다시 만든다. 실패하면 None(쏠림만 비움).

- [ ] **Step 1: 실패 테스트** — 당일 행은 평균에서 빠진다; 25거래일 입력에서 최근 20일만 평균; 캐시 날짜가 같으면 qdata를 부르지 않는다;
  qdata 예외면 None
- [ ] **Step 2~4: 실패 확인 → 구현 → 통과**

### Task 3: 폴러가 지도·신호를 발행 (Insight)

**Files:**
- Modify: `server/app/intraday_poller.py`, `server/module/market_desk.py` (`market_input`), `infra/template.yaml` (PollerRole Put 2키)
- Test: `server/tests/test_intraday_poller.py`, `server/tests/test_market_desk.py`, `server/tests/test_news_infra.py`

**Interfaces:**
- Produces: `app/kr_intraday_map.json` = `{"version":1,"trade_date","latest": <build_map 결과>,"series":[series_entry...]}` (날짜가 바뀌면 리셋)
- Produces: `index_crossings(timeline: pd.DataFrame, thresholds={"KOSPI":2.0,"KOSDAQ":3.0}) -> list[dict]`
  (`{"id": "<date>/cross/<index>/<up|down>", "index", "direction", "threshold", "observed_at", "chg_pct"}`, 방향별 첫 돌파만)
- Produces: `market_input(...)` 결과에 `"map"`(series 없는 latest)과 `"events"`(crossings) 추가. 기존 v1 키 유지.

- [ ] **Step 1: 실패 테스트** — 11/27 타임라인(`timeline_through_1105.parquet`)에서 KOSDAQ +3% 첫 돌파가 `2026-11-27 09:45` 한 번만;
  지도 파일 series가 폴마다 하나씩 늘고 날짜가 바뀌면 1개로 리셋; `input.json`에 `map`·`events`가 있고 개인 보유·관심 정보가 없다;
  템플릿 PollerRole이 `app/kr_intraday_map.json`·`app/kr_value_baseline.parquet`에 Put 가능
- [ ] **Step 2~4: 실패 확인 → 구현 → 통과** (지도 실패는 격리: 스냅샷·타임라인 발행은 계속, `map_status: degraded`)

### Task 4: API — 지도·노트·노트 이후 (Insight)

**Files:**
- Modify: `server/app/routers/market_desk.py`
- Test: `server/tests/test_market_desk.py`

**Interfaces:**
- Consumes: Task 3 지도 파일; ai-company 보드 `notes`(Task 7 계약)
- Produces: `GET /market-desk` 응답에 `map`(오늘·20분 이내일 때, 아니면 `{"state":"stale"|"awaiting"}`), `my`(보유·관심 종목 등락: 지도 시각 기준),
  `notes`(당일, 시간순), `since_note`(최근 노트 기준 `since()` 결과 또는 null)
- Produces: pydantic `Note`·`Claim`·`NoteStock`·`Alert` 모델 (Task 7 출력과 같은 키)

- [ ] **Step 1: 실패 테스트** — 지도가 어제 것이면 `map.state == "stale"`; 노트 2개면 최신이 마지막; `since_note`가 노트 시각 series와 최신의 차이;
  `notes` 형식 오류 한 건은 빼고 나머지 응답 정상
- [ ] **Step 2~4: 실패 확인 → 구현 → 통과**

### Task 5: 화면 — 시장 지도, 노트 미리보기 (Insight)

**Files:**
- Create: `client/src/app/home/MarketMap.tsx`, `client/src/app/home/NoteCard.tsx`, `client/src/app/notes/page.tsx`
- Modify: `client/src/app/home/MarketDesk.tsx`, `client/src/app/home/marketDesk.module.css`, `client/src/state/api.ts`
- Test: `client/tests/marketExperience.smoke.mjs`, `client/tests/marketExperience.fixtures.mjs`

**Interfaces:**
- Consumes: Task 4 응답
- Produces: 홈 — 대표 해설(있으면) → 시장 지도(지수 기여 상위·상승/하락·쏠림·묶음·내 종목) → 아침·마감 브리핑 → 주요 뉴스.
  규칙 문장, "원인 미확인" 변동 목록, 시간대별 변동 기록 제거. `/notes` — 당일 노트(근거 표시 칩, 근거 열기)와 노트 이후.
  홈 교체는 `NOTES_ON_HOME` 상수(기본 false).

- [ ] **Step 1: 스모크 기대값** — 홈에 "지수를 움직인 종목"(삼성전자 +0.36%p), "상승 1,461 · 하락 219", 쏠림 "평소 하루치의 N배", 규칙 문장
  "다음 수집에서도 이어지는지"가 없다; `/notes`에 노트 제목·[보도] 칩·근거 링크; 지도 stale이면 "시세 수집 지연"
- [ ] **Step 2~4: 실패 확인 → 구현 → 통과** (`npm run lint`, `npx tsc --noEmit`, 격리 빌드, 스모크)

### Task 6: 노트 작성기 (ai-company)

**Files:**
- Create: `src/quant_company/market_desk/note.py`
- Test: `tests/test_market_desk_note.py`

**Interfaces:**
- Produces: `session_bounds(day, changes) -> (open_at, close_at) | None` (override close 이동분만큼 개장도 이동)
- Produces: `due_slot(at, bounds, written: list[dict]) -> str | None` (`open|morning|afternoon|preclose|close`)
- Produces: `urgent_trigger(at, market, last_note, headlines, written) -> dict | None` (T1·T2·T3, 간격·상한 적용)
- Produces: `packet_for(slot_or_trigger, market, docs, previous, at) -> dict` (`kind: "note"`, `map`, `facts`(지도를 숫자 문장으로), `docs`)
- Produces: `request_for(revision, packet) -> ProviderRequest`, `edited(response, row, at) -> dict`
  (출력: `headline, drivers[{text,label,refs,quotes}], stocks[{name,reason,label,refs,quotes}], since_last, watch[]`)

- [ ] **Step 1: 실패 테스트** — 평일 슬롯 09:40/11:00/13:30/14:50/15:55, 수능형 예외(마감 16:30)면 10:40/…/16:55; 30분 규칙;
  11/27 입력으로 T1(09:45)·T3(사이드카 제목)·T2; 검증기: 지도에 없는 숫자 거절, [해석] 참조 없음 거절, 인용 불일치 거절, "매수하세요" 거절,
  지도에 없는 종목 거절, 정상 초안 통과
- [ ] **Step 2~4: 실패 확인 → 구현 → 통과** (`uv run pytest tests/test_market_desk_note.py`, 실 PostgreSQL 불필요)

### Task 7: 노트 등록·작성·게시 (ai-company)

**Files:**
- Modify: `src/quant_company/market_desk/store.py`, `src/quant_company/market_desk/runner.py`, `src/quant_company/config.py`,
  `deploy/compose.yaml`, `deploy/market-desk.compose.yaml`
- Test: `tests/test_market_desk_note.py` (PostgreSQL), `deploy/test_deployment_contract.py`

**Interfaces:**
- Consumes: Task 6
- Produces: `DeskStore.register_note(conn, at, market)` — `market_desk_revisions`에 `issue_id = note/<day>/<slot|urgent-HHMM>`로 동결
- Produces: 보드 `notes`(당일 written, 시간순: `{id, kind:"scheduled"|"urgent", slot, trigger, observed_at, published_at, headline, drivers, stocks,
  since_last, watch, sources[]}`), `alerts`(T3: `{id, kind:"market_action", title, published_at, source}`)
- Produces: 설정 `insight_notes_enabled`(기본 false), 운영 overlay에서 true

- [ ] **Step 1: 실패 테스트** — 설정 false면 노트 0; 같은 슬롯 재등록 없음; 하루 8회·급변 3회 상한; 작성 성공 시 보드 `notes`; Codex `quota` 거절은
  그 회차 실패로 끝나고 재요청 없음; 사이드카 기사 두 매체 → `alerts` 1건
- [ ] **Step 2~4: 실패 확인 → 구현 → 통과** (`TEST_DATABASE_URL=… uv run pytest tests/test_market_desk*.py deploy/test_deployment_contract.py`)

### Task 8: 시황·특징주 매체 등록 (ai-company)

**Files:**
- Modify: `src/quant_company/news/sources.json`, `docs/news.md`
- Test: `uv run quant-company news probe` (실제 RSS), `tests/test_news.py` 소스 로드

- [ ] **Step 1:** 조사 결과에서 RSS·이용 조건·본문 수집이 확인된 매체만 `enabled`, 요약 허용 매체만 `use_for_summary`
- [ ] **Step 2:** `news probe`로 항목 수·최신 시각 확인, 원문 1건 `fetch_original` 확인

### Task 9: 시장 급변 알림 (Insight)

**Files:**
- Modify: `server/app/news_poller.py`, `infra/template.yaml`(뉴스 폴러 Get 지도 파일), `client/src/app/actions/NotificationSettings.tsx`
- Test: `server/tests/test_news_poller.py`, `server/tests/test_news_infra.py`

**Interfaces:**
- Consumes: 보드 `alerts`(T3), 지도 파일 `latest`/series의 crossings(T1)
- Produces: 알림 `{"title":"시장 급변", body, url:"/home"}`, 이벤트 id `market:<id>`, 하루 3회(오늘 보낸 `market:` 영수증 수로 판단)

- [ ] **Step 1: 실패 테스트** — T1 한 번·T3 한 번 → 2건; 네 번째 사건은 보내지 않음; 같은 사건 재실행 0건; 어제 사건 0건
- [ ] **Step 2~4: 실패 확인 → 구현 → 통과**

### Task 10: 뉴스 연결과 문서

**Files:**
- Modify: ai-company `market_desk/store.py`(노트 인용 원문 → 데스크 뉴스 `category: "시장"`), Insight `client/src/app/news/NewsFeed.tsx`(분야 `시장`),
  Insight `server/app/routers/market_desk.py`(지도 종목별 당일 뉴스 수), README, ai-company runbook, Insight ADR-0037
- Test: 각 저장소 해당 테스트, 스모크

- [ ] **Step 1~4:** 노트가 인용한 원문이 주요 뉴스 `시장`으로 보이고, 지도 종목 옆에 당일 기사 수가 보인다
- [ ] **Step 5:** 전체 회귀 — Insight `pytest`, 클라이언트 lint·tsc·빌드·스모크, ai-company CI와 같은 명령
