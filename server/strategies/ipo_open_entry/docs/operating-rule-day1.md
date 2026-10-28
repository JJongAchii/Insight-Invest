---
spec: op-day1-v2
mode: record-only
candidate_trial: ipo-listing-day-day1-v1/t01
candidate_commit: ca78281025556973acafeb433f86dc433262eeb7
strategy: ipo_open_entry.models.regression:SignedRegression
strategy_args:
  decision: top
  blocks:
  - H1
  - H1p
  - H4
  - H5
  - H6
  - H7
  - H8
  - H9
  percentile: train
  shrinkage: 300
  missing_indicators: true
  label: rank
  top_grid:
  - 0.1
  - 0.2
  - 0.3
  - 0.4
  - 0.5
  entry_cap: 1.5
dataset: data/dev-20260909-v4
dataset_manifest_sha256: c79e8fba0aab5975ad04eea45a6cd5e89223293c9390474e1fbeca6961e5906e
frozen_code_sha256: ea7665e583ef5c2750a8517aedbc2ef91bf13d422391dba11e38191781e8a0ef
evaluation_summary_sha256: 1e75ef914082a263097c62a4b84b263952b56e56dbe971a43f2a64ceba5f48a1
record_horizons:
- 1
- 2
- 3
horizon_evidence_trial: av-v1-20261026/t01
horizon_evidence_sha256: a98952c042177930da35183c523625d7967e4a2d001cbeec1ab4fb6b0f628954
---

# 공모주 상장일 기록 규칙 (op-day1-v2, 기록 전용)

> 계약 ipo-listing-day INTENT-v1 DAY1_DECISION. day1-v1 개발 구간 탐색(과학 실행 16회, 누수 감사 pass)의 최선 t01이다. t01은 1차 탐색 35회에서 고른 t32를 그대로 다시 돌린 것이라 표본 밖 성과가 아니다. **실제 주문 규칙이 아니라 순방향 기록 규칙이다**(2026-10-26 사용자 결정, 과거 봉인 없음).
> op-day1-v1과 매수 결정이 같고, 같은 매수에 2일째·3일째 종가 매도 기록을 더했다(계약 ipo-analyst-view AV_DECISION, 2026-10-26 사용자 결정).
> 이 문서는 `scripts/write_operating_rule_day1.py`가 `docs/evidence/search/day1-v1/SUMMARY.json`와 `docs/evidence/search/av-v1/GATES.json`에서 만든다.

## 규칙

1. 점수: 부호 제약 회귀(SignedRegression, 순위 라벨, R1→R2 수축 k=300, 학습창 백분위, 결측 지시 켬). 블록 H1·H1′·H4·H5·H6·H7·H8·H9(docs/brief.md §11). 분기 시작 전에 세 청산이 끝난 사건으로 학습한다
2. 매수: 학습창에서 고른 상위 q 안이면 상장일 동시호가 전에 공모가 × 1.5 당일 유효 지정가(상장일 시가는 결정에 쓰지 않는다)
3. 매도 기록: 같은 매수에 상장일·2일째·3일째 종가를 함께 기록한다. 그날 종가가 하한가면 다음 거래일 종가. 셋은 한 결정의 청산 기록이지 별개 주문이 아니다
4. 배분: 거래마다 전일 평가금액의 1/7(백테스트 가정)

## 개발 구간 근거 (평가 묶음에서 읽음)

- stress 대표 지표(연 분수) +0.0355, base +0.0382
- 총수익 상위 3건 제외 +0.0095, R2(2023-06-26~) +0.0653
- 문턱 +0.0000(B1o -0.4675가 음이라 B0 = 0)
- 리포트: https://claude.ai/artifact/EP41NKocZ9PmXRXjm8t5n6 (개발 전용, 확증 아님)

### 청산 시점별 (av-v1 t01, 같은 매수 결정)

- 상장일 종가: stress +0.0355, base +0.0382, 상위 3건 제외 +0.0095
- 2일째 종가: stress +0.0648, base +0.0676, 상위 3건 제외 +0.0245
- 3일째 종가: stress +0.0533, base +0.0561, 상위 3건 제외 +0.0078
- 세 청산 중 가장 좋은 값을 고르면 낙관 편향이 있다 — 어느 청산이 나은지는 순방향 기록으로 본다
- 리포트: https://claude.ai/artifact/4T7zyuy9N4zc4zygJ8k6i5 (개발 전용, 확증 아님)

## 실행

- op-v2(패턴 점수)와 같은 밤, 같은 스냅샷으로 돌린다: `scripts/decide.py`에 `--spec strategies/ipo-open-entry/docs/operating-rule-day1.md`를 더한다
- 결정은 `decisions/op-day1-v2/<상장일>/<event_id>.json`에 한 번만 쓰이고 `RECORDS.jsonl` 사슬에 이어진다. 결정 문서의 `spec.record_horizons`가 남길 매도 기록 시점이다
- 기록 전용이라 주문을 내지 않는다. 각 매도 기록 시점의 결과는 나중에 같은 레이크에서 읽어 순방향 기록에 붙인다

## 지키는 것

- 공시는 접수일이 상장일 전인 판본만, 시장 정보는 상장 전 거래일 종가까지 쓴다
- 결정 코드(`operate/spec.py` FROZEN_CODE)와 학습 데이터셋이 머리말 digest와 다르면 결정 도구가 멈춘다
- 2026-09-14~10-12 KRX 가격(시간외 오염 구간)에 닿는 사건은 입력과 학습에서 뺀다
