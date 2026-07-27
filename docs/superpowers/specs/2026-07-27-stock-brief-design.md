# 종목 브리프 (Bull/Bear 대립 리서치) 설계

- 작성일: 2026-07-27
- 상태: 설계 확정, 구현 대기
- 착안: [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)의 Researcher Team 패턴

## 1. 배경

Insight-Invest는 정량 시그널(수급·팩터·밸류에이션·시장폭·레짐)을 충실히 계산해 보여준다.
그러나 "그래서 이 종목을 어떻게 볼 것인가"로 이어지지 않는다. 숫자는 있는데 판단이 없다.

TradingAgents를 분석하며 확인한 것:

- 이 레포의 백테스트 성과(3개월, 샤프 8.21)는 신뢰할 수 없다. 표본이 60거래일이고,
  거래비용이 없고, 백본 모델이 테스트 구간을 학습 데이터로 봤다.
- 그러나 **Bull/Bear 대립 구조**는 이식할 가치가 있다. 단일 LLM 판단의 확증 편향을
  구조적으로 깨는 장치이고, 알파 주장과 무관하게 성립한다.
- Insight-Invest는 이미 애널리스트 계층(사전계산 parquet 14종)을 갖고 있어,
  TradingAgents가 종목당 20+ 툴 호출로 하는 일을 parquet 읽기로 대체할 수 있다.
  비용 구조가 근본적으로 유리하다.

## 2. 목표

정량 시그널이 이미 뽑아둔 사실 위에, **서로를 보지 못하는 강세·약세 논거**를 세우고
그 둘이 갈리는 지점을 짚는 브리프를 매 거래일 생성한다.

### 무엇을 인사이트로 보는가

숫자를 문장으로 바꾸는 것은 인사이트가 아니다. 네 가지가 있어야 한다.

| 요소 | 질문 | 재료 |
|---|---|---|
| 기저율 | 이 신호가 과거에 얼마나 나왔고 그 뒤 어떻게 됐나 | `signal_study` |
| 긴장 | 어느 지표끼리 서로 반대를 가리키는가 | flows × factors × valuation |
| 상대성 | 업종·시장 대비 어디인가 | `sector_perf`, `breadth_daily` |
| 반증 조건 | 이 논거가 틀렸다면 무엇이 먼저 보이나 | 프롬프트 설계 |

## 3. 비목표 (명시적으로 만들지 않는 것)

- **매수/매도/보유 판정** — 논거 정리까지만. 결정은 사람이 한다.
  TradingAgents의 Portfolio Manager 최종 판정에 해당하는 단계는 두지 않는다.
- **Risk 3자 토론** (Aggressive/Conservative/Neutral) — 개인 단일 계좌엔 과잉.
  리스크 관점은 judge 단계에 흡수한다.
- **LangGraph 도입** — 워크플로가 선형 배치라 이득이 없다. 조건부 분기가 실제로
  생기면 그때 재검토한다.
- **Decision Journal** — 이번 범위 밖. 단 `evidence_snapshot`·`prior_brief` 필드를
  남겨 나중에 거의 공짜로 붙을 수 있게 한다.
- **데이터 파이프라인 변경** — qdata 수집·build_insights 구조는 손대지 않는다.

## 4. 아키텍처

```
[EC2 qdata-collector — 평일 19:00 KST, EventBridge가 기동]
  qdata 수집·clean·S3 발행
  build_insights.py         기존 14개 빌더 + build_factor_pct_ticker (신규)
  build_briefs.py           ★ 신규
      대상 선정 (≤15종목)
      evidence pack 조립          ← 기저율 조인이 핵심
      bull ∥ bear → judge         Claude Opus 5, structured output
      evidence_ref 결정론적 검증
      → briefs.parquet
  send_briefing.py          + 브리프 섹션
  self-shutdown (systemd ExecStopPost)

[Lambda insight-invest-api]
  GET /brief/{ticker}, GET /brief/today   — parquet 읽기만, LLM 호출 없음

[프론트]
  텔레그램 → 종목 상세 → insight 상단 → 홈 AttentionLane
```

## 5. Evidence Pack

브리프의 유일한 사실 출처. LLM은 이 안의 값만 쓸 수 있다.

```
EvidencePack(ticker, as_of):
  identity      ticker, name, market, sector, mktcap, close, chg_pct
  flows         frgn/inst × {streak, intensity_20d, net_20d, ret_20d, divergence}
  base_rates    ★ 매칭된 신호별 {n_events, median_excess, hit_rate} × h∈{5,20,60}
  factors       momentum/value/size/lowvol 백분위 (0-100, 유동성 유니버스 내)
  sector        업종 1d/1w/1m/3m/YTD + 시총 비중 + 시장 대비
  market        레짐 국면, 시장폭, 시장 PER/PBR/배당수익률
  holding       보유 시 평단·수익률·비중 / 미보유 시 None
  news          최근 5일 헤드라인 (제목·출처·날짜만, 본문 제외)
  prior_brief   직전 브리프의 판정 + 그 이후 가격 변화
```

### 5.1 기저율 조인 — 이 설계의 중심

`build_signal_study()`는 2016년 이후 전 종목에 대해 3개 신호의 이벤트 스터디를
이미 돌리고 있다. 신호 발생 후 5/20/60거래일 KOSPI 대비 초과수익, 표본 수, 승률.

`build_flows_signals()`는 **같은 정의**(streak, intensity_20d, ret_20d, 시총≥100억)로
종목별 현재값을 갖고 있다.

둘을 조인하면 "신호"가 "확률"이 된다.

> 외국인 순매수 12일째 — 2016년 이후 이 조건(10일 이상)은 1,847회 발생해
> 20일 뒤 KOSPI 대비 중앙값 +2.1%, 승률 54%. 표본은 충분하나 우위 폭은 크지 않다.

**조인 규칙** — `signal_study`의 조건식을 그대로 재계산한다.
`flows_signals` 중 `investor == "frgn"` 행에만 적용한다 (`signal_study`가 외국인 수급만 사용).

```python
frgn_streak10   := streak >= 10
high_intensity  := intensity_20d >= 1.0
bull_divergence := ret_20d < -5 and intensity_20d > 0.3
```

⚠️ **정의 불일치 주의.** `flows_signals`의 `divergence == "bull"`은 `ret_20d < 0`이고
`signal_study`의 `bull_divergence`는 `ret_20d < -5`다. `flows_signals`의 divergence
라벨을 그대로 기저율 조회 키로 쓰면 -3% 종목에 -5% 기준 통계가 딸려가 **숫자가 거짓이 된다.**
에러가 나지 않고 그럴듯한 값이 나오므로 단위 테스트로 못박는다 (§9).

### 5.2 신규 빌더: `build_factor_pct_ticker()`

종목별 팩터 백분위는 계산 로직만 있고 저장이 안 돼 있다.
`server/app/routers/insight.py`의 `_universe_factor_pct()`가 계산하지만
`POST /insight/factor-exposure` 요청 시에만 돌고, **매 콜드스타트마다 520일치
전종목 시세+펀더멘털을 Lambda에서 로드한다.**

`build_insights.py`에 빌더를 추가해 parquet으로 떨어뜨린다.

- 브리프 빌더가 읽을 재료가 생긴다
- **Lambda의 콜드스타트 부담이 사라진다** — 520일 로드가 작은 parquet 읽기로 바뀐다

계산식은 `_universe_factor_pct()`를 그대로 옮기므로 숫자는 동일하다.
`/factor-exposure`는 parquet을 읽도록 수정하고, parquet이 없으면 기존 경로로 폴백한다.

### 5.3 필드 선택 근거

- **`prior_brief`** — 브리프에 연속성이 생긴다. "지난주 수급이 가격을 먼저 꺾는지가
  분기점이라 봤는데, 이후 수급은 유지됐고 가격이 +4% 따라왔다." 토큰 ~200개.
- **`news`에 본문 제외** — 토큰 폭증 대비 이득이 작고, LLM이 뉴스 서사에 끌려가
  정량 근거를 뒷전으로 미룬다. 헤드라인은 "무슨 일이 있었나" 신호로만 쓴다.

## 6. 프롬프트와 출력 스키마

### 6.1 공통 시스템 프롬프트 (프롬프트 캐시 대상)

1. **evidence pack 안의 사실만 사용한다.** 종목·산업에 대한 사전 지식 인용 금지.
2. **숫자를 다시 말하지 않는다.** 숫자는 함의를 말할 때 근거로만 인용한다.
3. **기저율이 있으면 반드시 인용한다** — 표본 수, 승률, 중앙값. 없으면 "표본 없음"을 명시.
4. **모든 주장에 `evidence` 경로를 단다.** 근거 없는 주장은 출력하지 않는다.
5. **모든 논거에 `breaks_if`를 단다** — 무엇이 관찰되면 이 논거가 무효인가.
6. **없으면 없다고 한다.** 억지 논거 대신 `what_i_could_not_argue`에 적는다.

1번이 가장 중요하다. 모델은 학습 데이터로 개별 종목을 많이 알고 있고, 그것은 전부
과거 시점의·검증 불가능한·아마도 낡은 정보다. "메모리 업황 회복 국면에서" 같은 문장이
나오는 순간 브리프의 신뢰성이 무너진다. TradingAgents에서 지적한 모델 가중치 레벨
룩어헤드와 같은 문제이며, 여기서는 프롬프트와 코드로 이중 방어한다 (§6.4).

6번은 채워넣기 방지 장치다. "약세 논거 3개를 대라"고 하면 3개를 만들어낸다.
"댈 수 있는 만큼만 대고 못 댄 건 적어라"고 하면 2개를 대고 하나를 비운다.
그 빈칸 자체가 정보다.

### 6.2 Bull / Bear 콜 (병렬, 서로의 출력을 보지 못함)

> **Bull:** 이 종목을 매수·유지해야 할 이유만 찾아라. 균형 잡기는 네 일이 아니다.
> 반대편은 다른 분석가가 독립적으로 맡는다. 네 임무는 강세 논거의 최선 버전을 만드는 것이다.

> **Bear:** 이 종목을 매도·회피해야 할 이유만 찾아라. (이하 대칭)

서로의 출력을 보지 못하는 것이 이 설계의 전부다. 한 컨텍스트에서 양쪽을 쓰게 하면
모델이 자동으로 균형을 맞춰 "강세 3개, 약세 3개, 결론은 중립" 같은 무해하고
쓸모없는 출력이 나온다.

```json
{
  "points": [
    {
      "claim":     "한 문장. 숫자가 아니라 함의를 말한다",
      "evidence":  ["flows.frgn.streak", "base_rates.frgn_streak10.h20"],
      "strength":  "strong | moderate | weak",
      "breaks_if": "이 논거가 무효화되는 관찰 가능한 조건"
    }
  ],
  "strongest_point_index": 0,
  "what_i_could_not_argue": "이 방향으로 주장하려 했으나 근거가 없었던 것"
}
```

### 6.3 Judge 콜 (bull + bear + evidence pack 전부 열람)

> 점수를 매기지 마라. 매수/매도 판정을 내리지 마라. 두 논거가 **어디서 갈리는지** 짚어라.
> 같은 사실을 양쪽이 다르게 읽고 있다면 그게 핵심이다. 그리고 **무엇이 관찰되면
> 결판나는지**를 다음 며칠 안에 확인 가능한 형태로 적어라.
>
> `evidence` 경로가 evidence pack에 실제로 없는 논거는 기각하고 근거에서 제외하라.
> 기저율 표본이 30 미만이면 그 논거의 신뢰도를 낮춰 다뤄라.

```json
{
  "one_liner":         "≤60자   → 홈 AttentionLane",
  "summary":           "≤200자  → 텔레그램, insight 상단",
  "tension":           "두 논거가 같은 사실을 다르게 읽는 지점",
  "decisive_question": "무엇이 확인되면 결판나는가",
  "watch": [{"metric": "...", "threshold": "...", "meaning": "..."}],
  "confidence":        "high | medium | low",
  "confidence_reason": "왜 그 수준인가",
  "stance_note":       "논거 무게중심 (매수/매도 신호 아님)"
}
```

네 곳에 노출되므로 judge 한 번의 호출에서 4단계 분량을 동시에 생성한다.
분량별로 LLM을 다시 부르지 않는다.

### 6.4 코드 레벨 환각 방어

judge에게 "가짜 근거를 기각하라"고 시키는 것과 **별개로** 파싱 후 결정론적으로 검증한다.

```
evidence 경로가 evidence pack의 실제 키가 아니면 → 해당 논거 드롭 + dropped_refs에 기록
```

프롬프트 규칙은 지켜지지 않을 수 있지만 이건 지켜진다.
드롭 건수는 프롬프트 품질 지표로도 쓴다 — 드롭률 상승은 프롬프트가 무너지고 있다는 신호다.

### 6.5 모델 설정

```python
model="claude-opus-5"
thinking={"type": "adaptive"}
output_config={
    "effort": "high",
    "format": {"type": "json_schema", "schema": SCHEMA},
}
max_tokens=8000    # thinking + 응답 합산 상한이므로 여유 있게
```

**캐싱** — 시스템 프롬프트 + 시장 공통 맥락(레짐·시장폭·밸류에이션, 종목 무관)까지
접두부로 묶어 `cache_control`을 건다. 약 1,700토큰으로 Opus 5 최소치(512)를 넘는다.

⚠️ 캐시는 첫 응답이 시작된 뒤에야 읽을 수 있다. 30콜을 한꺼번에 병렬로 쏘면 전부 미스다.
**첫 종목의 bull 콜 하나를 완주시켜 캐시를 만든 뒤 나머지를 팬아웃**해야 절감이 실제로 발생한다.

## 7. 실행 파이프라인

### 7.1 삽입 지점

`quant-data/scripts/server/run_pipeline.sh` 6단계:

```bash
  IIPY=$BASE/ii-venv/bin/python
  QDATA_LAKE=/data/lake $IIPY $BASE/Insight-Invest/scripts/build_insights.py || echo "[warn] build_insights 실패"
+ QDATA_LAKE=/data/lake BRIEFING_ENV_FILE=$ENVF $IIPY $BASE/Insight-Invest/scripts/build_briefs.py || echo "[warn] build_briefs 실패"
  QDATA_LAKE=/data/lake BRIEFING_ENV_FILE=$ENVF $IIPY $BASE/Insight-Invest/scripts/send_briefing.py || echo "[warn] briefing 실패"
```

기존 구조가 이걸 거의 무료로 만든다.

- `run_pipeline.sh`가 매 실행마다 Insight-Invest를 `git pull` — **배포 절차 없음.**
  main에 푸시하면 다음 실행부터 반영된다.
- `ii-venv`에 `server/requirements.txt`가 이미 설치돼 있다 — `anthropic` 한 줄 추가.
- systemd `TimeoutStartSec=7200`(2시간)에 현재 약 40분 사용. 5분 추가는 여유 안쪽.
- `ExecStopPost`가 성공·실패·타임아웃 무엇이든 로그 업로드 + `shutdown -h now`.
  브리프 생성이 무한 대기해도 인스턴스가 방치되지 않는다.
- `/data/NOAUTO` 플래그로 수동 실행 테스트 가능.

⚠️ **`run_pipeline.sh`는 quant-data 레포에 있다.** 레포 두 개를 건드려야 한다.
순서는 Insight-Invest(`build_briefs.py` 추가) 먼저, quant-data(호출 한 줄) 나중.
반대로 해도 `|| echo "[warn]"` 때문에 파이프라인이 죽지는 않는다.

### 7.2 시크릿

`run_pipeline.sh` 1단계의 SSM SecureString 루프에 키를 추가한다.

```bash
aws ssm put-parameter --name /qdata/ANTHROPIC_API_KEY --type SecureString --value sk-ant-...
```

```diff
- for KEY in FRED_API_KEY KRX_ID KRX_PW ECOS_API_KEY TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID; do
+ for KEY in FRED_API_KEY KRX_ID KRX_PW ECOS_API_KEY TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID ANTHROPIC_API_KEY; do
```

키는 EC2 인스턴스 프로파일로만 복호화되고 레포·로그에 남지 않는다.

### 7.3 대상 종목 선정

```
워치리스트 ∪ 보유종목 ∪ attention(severity=high)
  → 시총 100억 이상 (signal_study 유니버스와 동일 기준)
  → 상한 15종목
```

상한 초과 시 **보유 > attention high > 워치리스트** 순, 동순위는 attention 점수순.
**잘린 종목은 반드시 로깅한다** — 조용한 절삭은 "전부 커버했다"는 착각을 만든다.

상한 15는 비용 상한이자 폭주 안전장치다.

### 7.4 저장 — `{APP_DATA}/briefs.parquet`

```
ticker, name, as_of, generated_at
one_liner, summary, tension, decisive_question, watch(json)
confidence, confidence_reason, stance_note
bull_points(json), bear_points(json)
bull_could_not_argue, bear_could_not_argue
evidence_snapshot(json)      생성 시점 evidence pack 통째로 박제
dropped_refs(json)           환각 방어 로깅
model, input_tokens, output_tokens, cost_usd
```

기존 `datastore/portfolio.py`·`holdings.py`의 단일 parquet read-modify-write 패턴을 따른다.
15종목 × 250거래일 = 연 3,750행이라 파티셔닝은 불필요하다.

- **`evidence_snapshot`** — "왜 이렇게 판단했나"를 재현할 수 있고, 프론트가 근거 링크
  값을 재조회할 필요가 없고, Decision Journal을 붙일 때 그대로 뼈대가 된다.
  종목당 ~3KB, 연 11MB.
- **`cost_usd`** — 응답의 실제 `usage` 기반. 추정치 검증용이기도 하다.

### 7.5 API — Lambda는 읽기만

```
GET /brief/{ticker}          단일 종목 전체
GET /brief/today?limit=3     오늘자 상위 N
```

`attention.py`는 기존 응답에 `one_liner` 필드만 조인한다.
**Lambda에 LLM 호출은 없다** — 콜드스타트·타임아웃·비용 변동과 무관하다.

### 7.6 노출 순서

| 순서 | 지점 | 파일 | 작업량 |
|---|---|---|---|
| 1 | 텔레그램 | `send_briefing.py` — `_section_briefs()` | 함수 1개, 프론트 0 |
| 2 | 종목 상세 | `stock/[metaId]/page.tsx` + `BriefCard.tsx` | 컴포넌트 1개 |
| 3 | insight 상단 | `insight/page.tsx` + `BriefStrip.tsx` | 컴포넌트 1개 |
| 4 | 홈 | `home/AttentionLane.tsx` | 필드 추가 |

텔레그램이 1번인 이유: 프론트 작업 0으로 다음 날 아침부터 실물을 읽을 수 있다.
**프롬프트는 실제 출력을 며칠 읽어봐야 튜닝된다.** 프롬프트가 안정되기 전에 UI를
만들면 프롬프트가 바뀔 때마다 UI도 흔들린다.

## 8. 에러 처리

코드베이스 전반의 관례를 따른다 — 빌더는 `try/except → None`, `send_briefing`은
섹션별 `_try()`, `attention.py`는 소스별 격리, `run_pipeline.sh`는 전 단계
`|| echo "[warn]"`. 한 군데 실패가 전체를 죽이지 않는다.

| 계층 | 처리 |
|---|---|
| 종목 단위 | 한 종목 실패해도 나머지 진행. 실패 종목은 전날 브리프 유지 + `as_of`로 stale 표시 |
| 콜 단위 | bull만 실패하면 bear + evidence pack으로 judge 진행 (판정에 "강세 논거 확보 실패" 명시). 둘 다 실패면 스킵 |
| API 오류 | SDK 기본 재시도(429/5xx, `max_retries=2`)에 위임 |
| `stop_reason: "refusal"` | **`content`를 읽기 전에 반드시 확인.** Opus 5는 안전 분류기가 HTTP 200 + refusal로 응답할 수 있다. 확인하지 않으면 `content[0]`에서 터진다 |
| `stop_reason: "max_tokens"` | structured output이 잘려 파싱 실패. `max_tokens` 2배로 1회 재시도 |
| 길이 제약 | `one_liner ≤60자`는 JSON 스키마로 강제 불가. 파싱 후 검증, 초과 시 절단 + 로깅 |
| 비용 상한 | 하루 누적 토큰이 임계 초과 시 즉시 중단 + 텔레그램 알림 |

전체 실패 시 `send_briefing.py`는 브리프 섹션만 빠진 채 기존 8개 섹션으로 정상 발송된다.
프론트는 브리프가 없으면 카드를 렌더하지 않는다.

## 9. 테스트

**이 레포에는 현재 테스트가 없다.** pytest도, conftest.py도, 테스트 파일도 없고
pre-commit은 black·isort·hadolint만 돌린다(ruff는 주석 처리됨).
따라서 "기존 관례를 따른다"고 쓸 수 없고, 테스트 도입 여부 자체가 결정 사항이다.

**결정: 선별 도입.** 전면 도입이 아니라, 틀렸을 때 조용히 거짓말하는 지점만 덮는다.

| 대상 | 방식 | 왜 |
|---|---|---|
| 기저율 매칭 | 단위 테스트, 경계값 명시 | §5.1의 `-5` vs `0` 불일치. 틀려도 에러가 안 나고 그럴듯한 숫자가 나온다 |
| evidence pack 조립 | 골든 픽스처 | 가짜 parquet → 기대 pack 비교. LLM 없는 순수 함수 |
| evidence_ref 검증 | 단위 테스트 | 없는 경로가 실제로 드롭되는지 |
| LLM 콜 | 모킹 스모크 | 고정 응답으로 파이프라인 관통 |
| 출력 품질 | 자동화 불가 — 수동 리뷰 | 프롬프트 변경 시마다 종목 3개를 사람이 읽고 판단 |

앞의 세 개는 순수 함수이므로 TDD로 작성한다. 여기가 인사이트의 정확성을 좌우한다.

`pytest`는 `server/requirements.txt`가 아니라 `server/requirements-dev.txt`에 넣어
Lambda 이미지가 무거워지지 않게 한다.

## 10. 비용

| 항목 | 값 |
|---|---|
| AWS 인프라 순증 | **$0** — 이미 평일 19시에 기동하는 EC2 창 안에서 실행 |
| LLM (10종목/일, 프롬프트 캐싱 적용) | **월 ~$18** |
| LLM (상한 15종목/일) | 월 ~$27 |

산출 근거 (10종목 기준, 월 22거래일):

- 종목당 3콜 — input ~10,400 tok, output ~1,900 tok
- 브리핑 요약 1콜 — input ~4,000 tok, output ~600 tok
- 일 합계 input ~108,000 / output ~19,600
- 캐싱으로 input 실효 ~69,000
- Claude Opus 5 $5/$25 per MTok → 일 ~$0.84 → 월 ~$18

토큰 추정치는 구현 후 `count_tokens`로 재측정하고, 실제 `usage`를 `cost_usd`에
기록해 검증한다.

## 11. 변경 파일

### 신규 (Insight-Invest)

- `scripts/build_briefs.py` — 대상 선정, evidence pack 조립, 3콜 오케스트레이션, 검증, 저장
- `server/app/routers/brief.py` — `GET /brief/{ticker}`, `GET /brief/today`
- `server/requirements-dev.txt` — pytest
- `client/src/app/stock/[metaId]/BriefCard.tsx`
- `client/src/app/insight/BriefStrip.tsx`
- 테스트 파일 (기저율 매칭 / evidence pack / evidence_ref 검증)

### 수정 (Insight-Invest)

- `scripts/build_insights.py` — `build_factor_pct_ticker()` 추가
- `scripts/send_briefing.py` — `_section_briefs()` 추가
- `server/app/main.py` — brief 라우터 등록
- `server/app/routers/insight.py` — `/factor-exposure`가 parquet 우선 사용 (없으면 폴백)
- `server/app/routers/attention.py` — 응답에 `one_liner` 조인
- `server/requirements.txt` — `anthropic` 추가
- `client/src/state/api.ts` — brief 엔드포인트
- `client/src/app/home/AttentionLane.tsx` — `one_liner` 표시

### 수정 (quant-data 레포)

- `scripts/server/run_pipeline.sh` — `build_briefs.py` 호출 한 줄, SSM 키 루프에 `ANTHROPIC_API_KEY` 추가

### 인프라

- SSM Parameter `/qdata/ANTHROPIC_API_KEY` (SecureString) 생성
- CloudFormation 변경 없음, EventBridge 변경 없음, Lambda 설정 변경 없음

## 12. 후속 (이번 범위 밖)

- **Decision Journal** — 결정 로그 + 실현 수익률 자동 해소 + 반성문.
  `evidence_snapshot`·`prior_brief`가 이미 뼈대를 제공한다.
- **README 정정** — 아키텍처 다이어그램이 `[로컬 (맥)] launchd (평일 19시)`로
  적혀 있으나 실제로는 EC2 `qdata-collector` + EventBridge Scheduler다.
- **v2 잔재 정리** — Lambda `data-update-with-eventbridge`, `insight-invest`
  (둘 다 python3.9, 2025-03 이후 미변경)와 이를 가리키는 DISABLED 스케줄 3개
  (`kr_price_update`, `macro_data_update`, `us_price_update`).
