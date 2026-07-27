# 신호 기준선 도입 + attention 표현 교정 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `signal_study`의 벤치마크를 시총가중 KOSPI에서 유동성 유니버스 동일가중
횡단면 평균으로 바꾸고 `baseline` 행을 추가한 뒤, 그 실측치를 attention·프론트·
텔레그램에 붙여 "급등 = 관심"이라는 거꾸로 된 표현을 사실로 교체한다.

**Architecture:** 빌더(`build_signal_study`)가 11개 신호 × 3개 지평선 = 33행을
산출한다. 새 모듈 `server/module/signal_stats.py`가 그 parquet을 읽어 "기준선 대비
몇 %p" 문장을 만드는 단일 지점이 되고, attention 라우터와 텔레그램 브리핑이 공용한다.
프론트는 `baseline` 행을 직접 읽어 경고 조건을 기준선 대비로 바꾼다.

**Tech Stack:** Python 3.12 / numpy / pandas / pyarrow / FastAPI, Next.js 14 + TypeScript

## Global Constraints

- 설계 문서: `docs/superpowers/specs/2026-07-27-signal-baseline-design.md` — 값이
  충돌하면 이 계획서가 아니라 설계 문서의 §1.1 측정표가 정답이다.
- `signal_study.parquet` **스키마 불변**: `signal_type, horizon, n_events,
  mean_excess, median_excess, hit_rate, avg_fwd_ret, as_of`. 컬럼 추가·삭제·개명 금지.
  행만 9 → 33으로 늘어난다.
- `SIGNAL_HORIZONS = (5, 20, 60)`, `SIGNAL_COOLDOWN = 20`, `MKTCAP_FLOOR = 1e10` —
  기존 상수를 그대로 쓴다. 새로 정의하지 않는다.
- **attention 라우터는 어떤 경우에도 500을 내지 않는다.** 모든 소스가 독립
  try/except로 감싸여 있다. 새로 추가하는 코드도 이 계약을 지킨다.
- 신규 런타임 의존성 추가 금지 — `server/requirements.txt`를 건드리지 않는다.
- 주석·docstring·사용자 문구는 한국어. 기존 파일의 밀도와 톤을 따른다.
- pre-commit 훅이 설치돼 있고 `files: ^server/` 범위다. `server/` 아래를 수정한
  커밋은 black(`--line-length=100`)·isort(`--profile=black`)를 통과해야 한다.
  `scripts/`·`client/`는 훅 범위 밖이므로 주변 코드 스타일에 손으로 맞춘다.
- Python 실행은 `server/.venv-test/bin/python`, 테스트는
  `server/.venv-test/bin/pytest`. 레이크는 `QDATA_LAKE=~/Quant/data-lake`.
- **매매 추천 문구를 만들지 않는다.** "사라/팔아라/피하라"가 아니라 실측치 서술까지만.

---

## File Structure

| 파일 | 책임 | 태스크 |
|---|---|---|
| `server/module/signal_stats.py` (신규) | `signal_study.parquet` 조회 + "기준선 대비" 문장 생성. attention·briefing 공용 단일 지점 | 1 |
| `server/tests/test_signal_stats.py` (신규) | 위 순수 함수의 단위 테스트 | 1 |
| `scripts/build_insights.py` | `build_signal_study()` 벤치마크 교체 + 신호 8종 추가, `_kospi_close()` 제거 | 2 |
| `server/app/routers/attention.py` | 가격 급변 항목의 라벨 제거·실측치 부착·severity 조정 | 3 |
| `client/src/state/api.ts` | `SignalStudyType` 유니온 확장, "vs KOSPI" 주석 정정 | 4 |
| `client/src/app/insight/SignalsSection.tsx` | 경고 조건을 기준선 대비로, 지평선별 기준선 델타 표시 | 4 |
| `client/src/content/indicatorHelp.ts` | `signal.study` 도움말을 새 벤치마크에 맞게 정정 | 4 |
| `scripts/send_briefing.py` | `_section_signals`에 실측치 병기 | 5 |

**태스크 순서:** 1 → 2 → 3 → 4 → 5. 태스크 3·4·5는 서로 독립이다.

---

### Task 1: `signal_stats` 모듈 — 기준선 대비 실측치 문장

**Files:**
- Create: `server/module/signal_stats.py`
- Test: `server/tests/test_signal_stats.py`

**Interfaces:**
- Consumes: `datastore.storage.read_parquet(*parts)` / `storage.exists(*parts)` —
  `server/datastore/storage.py:28,41`. 경로는 `("insight", "signal_study.parquet")`.
- Produces (Task 3·5가 이 이름으로 호출한다):
  - `load_study() -> pd.DataFrame | None`
  - `excess_vs_baseline(df: pd.DataFrame, signal_type: str, horizon: int) -> tuple[int, float, float] | None`
    — `(n_events, median_delta, hit_delta)`
  - `format_evidence(n_events: int, median_delta: float, hit_delta: float, horizon: int) -> str`
  - `evidence_phrase(signal_type: str, horizon: int = 20, df: pd.DataFrame | None = None) -> str | None`

**배경:** Task 2가 만드는 `signal_study.parquet`에는 `signal_type == "baseline"` 행이
지평선마다 하나씩 있다. 어떤 신호의 `median_excess`도 그 자체로는 의미가 없고 —
기준선이 20일 −1.80%라 전부 음수로 보인다 — 기준선과의 **차이**만 읽을 값이다.
이 모듈이 그 뺄셈을 하는 유일한 지점이다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`server/tests/test_signal_stats.py`:

```python
"""signal_stats 순수 함수 — 기준선 대비 계산과 문장 포맷."""

import numpy as np
import pandas as pd
import pytest

from module.signal_stats import evidence_phrase, excess_vs_baseline, format_evidence


def _study() -> pd.DataFrame:
    """설계 문서 §1.1의 20일 실측치를 축약한 테스트 픽스처."""
    return pd.DataFrame(
        [
            # signal_type, horizon, n_events, median_excess, hit_rate
            ("baseline", 20, 6000695, -1.80, 41.2),
            ("spike_1d_5", 20, 276018, -4.19, 38.1),
            ("baseline", 60, 5877263, -3.83, 39.6),
            ("near_52w_high", 60, 12000, -2.89, 42.0),
            ("broken", 20, 100, np.nan, np.nan),
        ],
        columns=["signal_type", "horizon", "n_events", "median_excess", "hit_rate"],
    )


def test_excess_vs_baseline_subtracts_the_baseline_row():
    n, med, hit = excess_vs_baseline(_study(), "spike_1d_5", 20)
    assert n == 276018
    assert med == pytest.approx(-2.39)
    assert hit == pytest.approx(-3.1)


def test_excess_vs_baseline_is_horizon_scoped():
    """60일 신호는 60일 기준선과 비교해야 한다 — 지평선을 섞으면 안 된다."""
    _, med, _ = excess_vs_baseline(_study(), "near_52w_high", 60)
    assert med == pytest.approx(0.94)


def test_excess_vs_baseline_returns_none_when_baseline_missing():
    """구 parquet에는 baseline 행이 없다 — 그 경우 값을 지어내지 않는다."""
    df = _study()
    df = df[df["signal_type"] != "baseline"]
    assert excess_vs_baseline(df, "spike_1d_5", 20) is None


def test_excess_vs_baseline_returns_none_for_unknown_signal():
    assert excess_vs_baseline(_study(), "does_not_exist", 20) is None


def test_excess_vs_baseline_returns_none_when_stats_are_nan():
    """표본이 비어 통계가 NaN인 행은 문장으로 만들지 않는다."""
    assert excess_vs_baseline(_study(), "broken", 20) is None


def test_format_evidence_abbreviates_large_counts():
    s = format_evidence(276018, -2.39, -3.1, 20)
    assert s == "과거 27.6만건 · 20일 뒤 기준선 대비 -2.4%p (승률 -3.1%p)"


def test_format_evidence_keeps_small_counts_exact():
    s = format_evidence(8500, 1.2, 0.5, 60)
    assert s == "과거 8,500건 · 60일 뒤 기준선 대비 +1.2%p (승률 +0.5%p)"


def test_evidence_phrase_composes_lookup_and_format():
    assert evidence_phrase("spike_1d_5", 20, df=_study()) == (
        "과거 27.6만건 · 20일 뒤 기준선 대비 -2.4%p (승률 -3.1%p)"
    )


def test_evidence_phrase_returns_none_when_data_is_unusable():
    assert evidence_phrase("does_not_exist", 20, df=_study()) is None
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

Run: `cd server && .venv-test/bin/pytest tests/test_signal_stats.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'module.signal_stats'`

- [ ] **Step 3: 모듈을 구현한다**

`server/module/signal_stats.py`:

```python
"""signal_study 조회 — 신호 성과를 '기준선 대비 몇 %p'로 환산한다.

median_excess를 그대로 읽으면 안 된다. 벤치마크가 유동성 유니버스 동일가중
횡단면 *평균*이고 수익률 분포가 우편향이라, 조건 없는 기준선조차 20일 중앙값이
-1.80%다. 신호가 좋은지 나쁜지는 오직 baseline 행과의 차이로만 판정된다.
이 모듈이 그 뺄셈을 하는 유일한 지점이다 — attention·텔레그램 브리핑 공용.
"""

import logging

import pandas as pd

from datastore import storage

logger = logging.getLogger(__name__)

_PARTS = ("insight", "signal_study.parquet")
BASELINE = "baseline"


def load_study() -> pd.DataFrame | None:
    """signal_study.parquet 로드. 부재·손상 시 None (호출부는 실측치를 생략한다).

    33행짜리 테이블이라 캐시하지 않는다 — Lambda 컨테이너가 며칠 살아남아도
    갱신된 값을 바로 읽는 쪽이 낫다.
    """
    try:
        if not storage.exists(*_PARTS):
            return None
        return storage.read_parquet(*_PARTS)
    except Exception:
        logger.debug("signal_study 로드 실패", exc_info=True)
        return None


def _row(df: pd.DataFrame, signal_type: str, horizon: int) -> pd.Series | None:
    hit = df[(df["signal_type"] == signal_type) & (df["horizon"] == horizon)]
    return hit.iloc[0] if len(hit) else None


def excess_vs_baseline(
    df: pd.DataFrame, signal_type: str, horizon: int
) -> tuple[int, float, float] | None:
    """(n_events, 중앙값 초과수익 차이 %p, 승률 차이 %p). 비교 불가면 None.

    같은 지평선의 baseline 행하고만 뺀다 — 20일 신호를 60일 기준선에 대면
    벤치마크를 바꾼 의미가 없어진다.
    """
    sig = _row(df, signal_type, horizon)
    base = _row(df, BASELINE, horizon)
    if sig is None or base is None:
        return None
    med = float(sig["median_excess"]) - float(base["median_excess"])
    hit = float(sig["hit_rate"]) - float(base["hit_rate"])
    if pd.isna(med) or pd.isna(hit):  # 표본이 빈 신호 — 문장을 만들지 않는다
        return None
    return int(sig["n_events"]), med, hit


def format_evidence(n_events: int, median_delta: float, hit_delta: float, horizon: int) -> str:
    """'과거 27.6만건 · 20일 뒤 기준선 대비 -2.4%p (승률 -3.1%p)'."""
    n = f"{n_events / 10000:.1f}만건" if n_events >= 10000 else f"{n_events:,}건"
    return (
        f"과거 {n} · {horizon}일 뒤 기준선 대비 "
        f"{median_delta:+.1f}%p (승률 {hit_delta:+.1f}%p)"
    )


def evidence_phrase(
    signal_type: str, horizon: int = 20, df: pd.DataFrame | None = None
) -> str | None:
    """실측치 한 줄. df 미지정 시 load_study(). 데이터가 없으면 None."""
    if df is None:
        df = load_study()
    if df is None:
        return None
    stats = excess_vs_baseline(df, signal_type, horizon)
    return format_evidence(*stats, horizon) if stats else None
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

Run: `cd server && .venv-test/bin/pytest tests/test_signal_stats.py -q`
Expected: PASS — 9 passed

- [ ] **Step 5: 포매터를 확인한다**

Run:
```bash
cd server
.venv-test/bin/python -m black --check --line-length=100 module/signal_stats.py tests/test_signal_stats.py
.venv-test/bin/python -m isort --check-only --settings-path ../.isort.cfg module/signal_stats.py tests/test_signal_stats.py
```
Expected: 둘 다 통과. 실패하면 `--check`/`--check-only`를 빼고 다시 실행해 고친다.
(black/isort가 `.venv-test`에 없으면 `.venv-test/bin/pip install black==24.1.1 isort==5.13.2`)

- [ ] **Step 6: 커밋**

```bash
git add server/module/signal_stats.py server/tests/test_signal_stats.py
git commit -m "feat(signal): 기준선 대비 실측치 문장 생성 모듈"
```

---

### Task 2: `build_signal_study()` — 벤치마크 교체 + 신호 8종 추가

**Files:**
- Modify: `scripts/build_insights.py` — `_kospi_close()` 삭제(`:637-641`),
  `build_signal_study()` 전면 교체(`:680-750`), `_study_row()` 헬퍼 추가,
  모듈 docstring 빌더 목록에 항목 추가

**Interfaces:**
- Consumes: `_flows()`, `_signed_streak(F)`, `_event_cooldown(pos, cooldown)`,
  `_as_of()`, `MKTCAP_FLOOR`, `SIGNAL_HORIZONS`, `SIGNAL_COOLDOWN` — 모두
  `scripts/build_insights.py`에 이미 있다. 시그니처를 바꾸지 않는다.
- Produces: `insight/signal_study.parquet` 33행. `signal_type` 값 11종 —
  `baseline`, `bull_divergence`, `frgn_streak10`, `high_intensity`,
  `spike_1d_5`, `spike_1d_10`, `drop_1d_5`, `spike_5d_15`, `spike_20d_20`,
  `spike_20d_50`, `near_52w_high`. Task 1·3·4·5가 이 문자열을 그대로 쓴다.

**이 태스크의 핵심 결정 — 이벤트 처리를 신호 종류에 따라 다르게 한다:**

기존 3개 신호는 `streak >= 10`처럼 한 번 참이 되면 여러 날 유지되는 *상태*라,
`crossing`으로 첫날만 잡고 `_event_cooldown(20일)`로 재발화를 걸러야 한 사건이
20번 세어지지 않는다. 반면 `chg_pct >= 5`는 그 자체로 하루짜리 사건이다.
crossing은 거의 무의미하고(연속 급등일은 드물다) cooldown은 **서로 다른 진짜 급등을
임의로 버린다.** 그래서 1일 조건 3종에만 원본 조건을 그대로 쓴다. 5일·20일 누적
조건과 52주 신고가는 다시 상태이므로 기존 처리를 따른다.

이 선택 덕분에 1일 신호 3종의 산출값은 설계 문서 §1.1 사전 측정치와 **정확히
일치해야 한다.** Step 6의 대조가 이 태스크의 실질적 회귀 테스트다.

- [ ] **Step 1: `_kospi_close()`를 지운다**

`scripts/build_insights.py:637-641`의 함수 전체를 삭제한다:

```python
def _kospi_close(index: pd.Index) -> np.ndarray:
    """KOSPI 지수 종가를 패널 거래일 index에 정렬한 numpy 배열 (ffill 보정)."""
    idx = qdata_api.load_krx_index()
    kospi = idx[idx["index"] == "KOSPI"].set_index("date")["close"].sort_index()
    return kospi.reindex(index).ffill().to_numpy(dtype="float64")
```

확인: `grep -rn "_kospi_close" scripts/ server/` 가 아무것도 출력하지 않아야 한다.
(`load_krx_index`는 다른 빌더가 쓸 수 있으므로 임포트는 건드리지 않는다.)

- [ ] **Step 2: `_study_row()` 헬퍼를 추가한다**

`_event_cooldown()` 정의 바로 뒤(`build_signal_study` 직전)에 넣는다:

```python
def _study_row(sig: str, h: int, excess: np.ndarray, fwd_ret: np.ndarray) -> dict:
    """signal_study 한 행. 표본이 비면 통계는 NaN — 행 자체는 남긴다."""
    return {
        "signal_type": sig,
        "horizon": h,
        "n_events": int(len(excess)),
        "mean_excess": float(np.mean(excess)) if len(excess) else np.nan,
        "median_excess": float(np.median(excess)) if len(excess) else np.nan,
        "hit_rate": float((excess > 0).mean() * 100) if len(excess) else np.nan,
        "avg_fwd_ret": float(np.mean(fwd_ret)) if len(fwd_ret) else np.nan,
    }
```

- [ ] **Step 3: `warnings` 임포트를 추가한다**

`scripts/build_insights.py` 상단 표준 라이브러리 임포트 블록(`import json` /
`import os` / `import sys` / `import traceback`)에 알파벳 순으로 넣는다:

```python
import traceback
import warnings
```

`np.nanmean`은 전부 NaN인 행에서 `RuntimeWarning: Mean of empty slice`를 낸다.
상장 전·상폐 후 구간에서 필연적으로 발생하므로 Step 4에서 억제한다.

- [ ] **Step 4: `build_signal_study()`를 통째로 교체한다**

`scripts/build_insights.py:680`부터 시작하는 `def build_signal_study():` 전체
(`return None`으로 끝나는 except 블록까지)를 아래로 바꾼다:

```python
def build_signal_study():
    """신호 이벤트 스터디 — 전 기간(2016~) 신호 발생 재구성 + 전방 초과성과.

    유동성 종목(시총≥100억)에 한해 11개 신호를 정의하고, 각 이벤트 이후
    h∈{5,20,60} 거래일 초과수익(adj_close 기반)을 집계한다.

    벤치마크는 **유동성 유니버스 동일가중 횡단면 평균**이다. 시총가중 KOSPI를
    쓰면 (1) KOSDAQ 종목을 KOSPI 지수에 대고 재게 되고 (2) 지수를 소수 대형주가
    끌기 때문에 중앙값 종목이 구조적으로 지수를 못 따라가, 모든 신호가 음수로
    보여 "이 신호는 나쁘다"로 오독된다. baseline 행이 그 기준을 명시한다 —
    어떤 신호든 baseline과의 차이로만 판정해야 한다.

    n_events는 신호 간 비교 불가다. 상태형 신호에만 crossing+cooldown을
    적용하기 때문이다(아래 참조). 중앙값·승률만 비교한다.

    최중량 빌더 — 실패해도 파이프라인 비중단(내부 try/except → None).
    """
    try:
        px = qdata_api.load_krx_prices(columns=["adj_close", "close", "chg_pct", "mktcap"])
        px = px[["date", "ticker", "adj_close", "chg_pct", "mktcap"]]  # close 미사용
        P = px.pivot(index="date", columns="ticker", values="adj_close").sort_index()
        M = px.pivot(index="date", columns="ticker", values="mktcap").reindex_like(P)
        CH = px.pivot(index="date", columns="ticker", values="chg_pct").reindex_like(P)
        del px

        frgn = _flows()
        frgn = frgn[frgn["investor"] == "frgn"][["date", "ticker", "net_value"]]
        F = frgn.pivot(index="date", columns="ticker", values="net_value")
        del frgn
        F = F.reindex(index=P.index, columns=P.columns)

        ret_5d = (P / P.shift(5) - 1) * 100
        ret_20d = (P / P.shift(20) - 1) * 100
        hi_252 = P.rolling(252, min_periods=200).max()
        frgn_net_20d = F.rolling(20, min_periods=20).sum()
        intensity_20d = frgn_net_20d / M * 100
        streak = _signed_streak(F)
        liquid = M >= MKTCAP_FLOOR
        del frgn_net_20d, F

        # 상태형 — 한 번 참이 되면 며칠 유지된다. crossing으로 첫날만 잡고
        # cooldown으로 재발화를 걸러야 한 사건이 여러 번 세어지지 않는다.
        state_conds = {
            "bull_divergence": (ret_20d < -5) & (intensity_20d > 0.3) & liquid,
            "frgn_streak10": (streak >= 10) & liquid,
            "high_intensity": (intensity_20d >= 1.0) & liquid,
            "spike_5d_15": (ret_5d >= 15) & liquid,
            "spike_20d_20": (ret_20d >= 20) & liquid,
            "spike_20d_50": (ret_20d >= 50) & liquid,
            "near_52w_high": (P >= hi_252 * 0.98) & liquid,
        }
        # 하루짜리 사건 — crossing은 거의 무의미하고(연속 급등일은 드물다),
        # cooldown은 서로 다른 진짜 급등을 임의로 버린다. 조건 그대로 쓴다.
        daily_conds = {
            "spike_1d_5": (CH >= 5) & liquid,
            "spike_1d_10": (CH >= 10) & liquid,
            "drop_1d_5": (CH <= -5) & liquid,
        }
        del ret_5d, ret_20d, hi_252, intensity_20d, streak, CH, M

        Pv = P.to_numpy(dtype="float64")
        Lv = liquid.to_numpy()
        n_dates = len(P.index)
        as_of = _as_of()
        del P, liquid

        events = {}  # 지평선 루프에서 재사용 — 좌표 계산은 한 번이면 된다
        for sig, cond in state_conds.items():
            crossing = cond & ~cond.shift(1, fill_value=False)  # 조건이 처음 참이 되는 날
            events[sig] = _event_cooldown(np.argwhere(crossing.to_numpy()), SIGNAL_COOLDOWN)
        for sig, cond in daily_conds.items():
            events[sig] = np.argwhere(cond.to_numpy())
        del state_conds, daily_conds

        rows = []
        for h in SIGNAL_HORIZONS:
            fwd = np.full_like(Pv, np.nan)
            fwd[: n_dates - h] = (Pv[h:] / Pv[: n_dates - h] - 1) * 100
            fwd = np.where(Lv, fwd, np.nan)  # 벤치마크·기준선 모두 유동성 유니버스
            with warnings.catch_warnings():  # 상장 전/상폐 후 전부-NaN 행 → 빈 평균
                warnings.simplefilter("ignore", RuntimeWarning)
                bench = np.nanmean(fwd, axis=1, keepdims=True)
            exc = fwd - bench

            # baseline — 이벤트가 아니라 유동성 전 종목-일. cooldown은 정의상 없다.
            ok = np.isfinite(exc)
            rows.append(_study_row("baseline", h, exc[ok], fwd[ok]))

            for sig, ev in events.items():
                dpos, tpos = ev[:, 0], ev[:, 1]
                keep = dpos + h < n_dates  # 지평선이 이력 밖이면 제외
                dpos, tpos = dpos[keep], tpos[keep]
                e, f = exc[dpos, tpos], fwd[dpos, tpos]
                m = np.isfinite(e) & np.isfinite(f)  # 상폐 등 결측 제외
                rows.append(_study_row(sig, h, e[m], f[m]))
            del fwd, bench, exc, ok

        df = pd.DataFrame(rows)
        df["as_of"] = as_of
        print("[signal_study]")
        print(df.to_string(index=False))
        return df
    except Exception:
        print("[warn] signal_study 실패 (비중단):", file=sys.stderr)
        traceback.print_exc()
        return None
```

- [ ] **Step 5: 모듈 docstring의 빌더 목록을 갱신한다**

`scripts/build_insights.py` 상단 docstring의 빌더 목록에 `valuation_daily` 항목
바로 뒤로 넣는다 (현재 `signal_study`는 목록에 없다):

```
- signal_study: 신호 11종 × 지평선 3개 전방 초과성과. 벤치마크는 유동성 유니버스
  동일가중 횡단면 평균이고, 조건 없는 baseline 행이 비교 기준으로 함께 들어간다.
```

- [ ] **Step 6: 실제 레이크로 돌려 사전 측정치와 대조한다**

이 태스크의 실질적 회귀 테스트다. 5~10분 걸린다.

Run:
```bash
cd /Users/achii/Quant/Insight-Invest/server
QDATA_LAKE=~/Quant/data-lake .venv-test/bin/python - <<'PY'
import sys
sys.path.insert(0, "../scripts")
import pandas as pd
from build_insights import build_signal_study

df = build_signal_study()
assert df is not None, "빌더가 None을 반환했다 — 위 traceback 확인"
assert len(df) == 33, f"행 수 {len(df)} != 33"
assert list(df.columns) == [
    "signal_type", "horizon", "n_events", "mean_excess",
    "median_excess", "hit_rate", "avg_fwd_ret", "as_of",
], f"스키마 변경됨: {list(df.columns)}"

base = df[df.signal_type == "baseline"].set_index("horizon")
print("\n--- baseline (기대: -0.67/-1.80/-3.83, 승률 42.9/41.2/39.6) ---")
print(base[["median_excess", "hit_rate", "n_events"]])

print("\n--- 기준선 대비 (%p) ---")
out = []
for h in (5, 20, 60):
    d = df[df.horizon == h].copy()
    d["vs_med"] = d.median_excess - base.loc[h, "median_excess"]
    d["vs_hit"] = d.hit_rate - base.loc[h, "hit_rate"]
    out.append(d.sort_values("vs_med", ascending=False)[
        ["signal_type", "horizon", "n_events", "vs_med", "vs_hit"]])
print(pd.concat(out).to_string(index=False))
PY
```

**합격 기준 — 1일 신호 3종은 정확히 맞아야 한다** (설계 문서 §1.1):

| signal_type | 5일 vs기준 | 20일 vs기준 | 60일 vs기준 | 20일 N |
|---|---|---|---|---|
| `spike_1d_5` | −1.16 | −2.39 | −4.60 | ≈ 276,018 |
| `spike_1d_10` | −2.54 | −5.41 | −9.16 | ≈ 73,207 |
| `drop_1d_5` | −0.20 | −1.22 | −2.95 | ≈ 223,663 |

`baseline` 중앙값 −0.67 / −1.80 / −3.83, 승률 42.9 / 41.2 / 39.6 도 일치해야 한다.
소수 둘째 자리의 미세 차이는 무방하나, 첫째 자리가 어긋나면 구현이 틀린 것이다.

**상태형 5종은 값이 달라지는 게 정상이다** — crossing+cooldown 때문에 N이 크게
작아진다. 부호만 확인한다: `spike_5d_15`·`spike_20d_20`·`spike_20d_50`은 20·60일이
음수, `near_52w_high`는 20·60일이 양수여야 한다. 부호가 뒤집히면 멈추고 보고한다.

- [ ] **Step 7: 커밋**

```bash
cd /Users/achii/Quant/Insight-Invest
git add scripts/build_insights.py
git commit -m "feat(signal): 벤치마크를 동일가중 횡단면으로 교체 + baseline·급등 신호 8종 추가"
```

---

### Task 3: `attention.py` — 가치판단 라벨 제거, 실측치 부착

**Files:**
- Modify: `server/app/routers/attention.py` — 임포트 블록(`:18-22`),
  가격 급변 블록(`:135-153`)

**Interfaces:**
- Consumes (Task 1): `module.signal_stats.load_study()`,
  `module.signal_stats.evidence_phrase(signal_type, horizon=20, df=None)`.
  signal_type 문자열은 Task 2가 만드는 `"spike_1d_10"` / `"spike_1d_5"` / `"drop_1d_5"`.
- Produces: 없음 (엔드포인트 응답 스키마 불변 — `severity`/`title`/`detail` 값만 바뀐다)

**배경 — 지금 라벨이 거꾸로다.** 현재 코드는 1일 +5%에 "관심", −5%에 "주의"를 붙인다.
600만 종목-일 측정 결과는 반대다: 급등 뒤 20일이 기준선 대비 −2.39%p, 급락 뒤는
−1.22%p로 **급등이 급락보다 2배 나빴다.** 가치판단 라벨을 걷어내고 실측치를 놓는다.
판단은 사용자가 한다.

- [ ] **Step 1: 임포트를 추가한다**

`server/app/routers/attention.py:21` — `from module import regime as regime_mod`
바로 뒤에 넣는다 (isort가 알파벳 순을 요구한다: `regime` < `signal_stats`):

```python
from module import regime as regime_mod
from module import signal_stats
```

- [ ] **Step 2: 가격 급변 블록을 교체한다**

`server/app/routers/attention.py:135-153`의 아래 블록을

```python
    # ── 가격 급변 (|오늘 등락| ≥ 5%) ─────────────────────────────────
    try:
        for mid, (price, chg) in price_map.items():
            if chg is None or abs(chg) < 5:
                continue
            up = chg > 0
            items.append(
                {
                    "severity": "medium",
                    "category": "price",
                    "ticker": tk_by_id.get(mid),
                    "name": name_by_id.get(mid),
                    "meta_id": mid,
                    "title": f"오늘 {chg:+.1f}% ({'관심' if up else '주의'})",
                    "detail": f"{'급등' if up else '급락'} {chg:+.1f}% — {'관심' if up else '주의'} 종목",
                    "link": f"/stock/{mid}",
                }
            )
    except Exception:
        logger.debug("attention price moves 실패", exc_info=True)
```

이걸로 바꾼다:

```python
    # ── 가격 급변 (|오늘 등락| ≥ 5%) ─────────────────────────────────
    # "관심/주의" 같은 가치판단 라벨을 붙이지 않는다. 2016~ 전 종목 측정에서
    # 급등(+5%) 뒤 20일은 기준선 대비 -2.4%p, 급락(-5%) 뒤는 -1.2%p로 급등이
    # 오히려 2배 나빴다. 사실과 실측치만 두고 판단은 사용자에게 맡긴다.
    try:
        study = signal_stats.load_study()  # 루프 밖에서 한 번만 (부재 시 None)
        for mid, (price, chg) in price_map.items():
            if chg is None or abs(chg) < 5:
                continue
            if chg >= 10:
                sig, sev, word = "spike_1d_10", "high", "급등"  # 60일 -9.2%p — 볼 만한 수준
            elif chg > 0:
                sig, sev, word = "spike_1d_5", "medium", "급등"
            else:
                sig, sev, word = "drop_1d_5", "medium", "급락"
            evidence = signal_stats.evidence_phrase(sig, 20, df=study)
            items.append(
                {
                    "severity": sev,
                    "category": "price",
                    "ticker": tk_by_id.get(mid),
                    "name": name_by_id.get(mid),
                    "meta_id": mid,
                    "title": f"오늘 {chg:+.1f}% {word}",
                    "detail": evidence or "과거 성과 통계 없음",
                    "link": f"/stock/{mid}",
                }
            )
    except Exception:
        logger.debug("attention price moves 실패", exc_info=True)
```

`spike_1d_5`는 빌더에서 `chg_pct >= 5`(10% 이상 포함)로 정의된다. +7%인 종목에
붙는 문장은 "5% 이상" 모집단의 통계이며, 그것이 문장이 주장하는 바와 정확히 같다.

- [ ] **Step 3: 라우터가 정상 응답하는지 확인한다**

Run:
```bash
cd /Users/achii/Quant/Insight-Invest/server
QDATA_LAKE=~/Quant/data-lake API_TOKEN= .venv-test/bin/python - <<'PY'
import sys; sys.path.insert(0, ".")
from fastapi.testclient import TestClient
from app.main import app

r = TestClient(app).get("/attention")
print("status:", r.status_code)
assert r.status_code == 200, r.text
price = [i for i in r.json()["items"] if i["category"] == "price"]
print(f"가격 급변 항목 {len(price)}건")
for i in price[:5]:
    print(f"  [{i['severity']:6}] {i['title']}  |  {i['detail']}")
assert not any("관심" in i["title"] or "주의" in i["title"] for i in price), "라벨이 남아 있다"
PY
```
Expected: `status: 200`. 가격 급변 항목이 0건이면 오늘 워치리스트·보유 종목에
5% 이상 움직인 게 없다는 뜻이므로 실패가 아니다 — 그 경우 다음 단계로 간다.

`fastapi.testclient`에 `httpx`가 필요하다. 없으면
`.venv-test/bin/pip install httpx` 후 다시 실행한다.

- [ ] **Step 4: `signal_study` 부재 시에도 200을 내는지 확인한다**

attention은 어떤 경우에도 500을 내지 않는다는 계약이 있다. `load_study()`가
None을 반환하는 경로를 강제로 태운다:

Run:
```bash
cd /Users/achii/Quant/Insight-Invest/server
QDATA_LAKE=~/Quant/data-lake API_TOKEN= .venv-test/bin/python - <<'PY'
import sys; sys.path.insert(0, ".")
from module import signal_stats
signal_stats.load_study = lambda: None  # parquet 부재 상황 재현
from fastapi.testclient import TestClient
from app.main import app

r = TestClient(app).get("/attention")
print("status:", r.status_code)
assert r.status_code == 200, r.text
price = [i for i in r.json()["items"] if i["category"] == "price"]
assert all(i["detail"] == "과거 성과 통계 없음" for i in price), [i["detail"] for i in price]
print(f"가격 급변 {len(price)}건 — 전부 폴백 문구, 200 유지")
PY
```
Expected: `status: 200`

- [ ] **Step 5: 포매터를 확인한다**

Run:
```bash
cd /Users/achii/Quant/Insight-Invest/server
.venv-test/bin/python -m black --check --line-length=100 app/routers/attention.py
.venv-test/bin/python -m isort --check-only --settings-path ../.isort.cfg app/routers/attention.py
```
Expected: 둘 다 통과.

- [ ] **Step 6: 커밋**

```bash
cd /Users/achii/Quant/Insight-Invest
git add server/app/routers/attention.py
git commit -m "fix(attention): 급등 '관심'/급락 '주의' 라벨 제거 — 실측치로 교체"
```

---

### Task 4: 프론트 — 경고 조건을 기준선 대비로

**Files:**
- Modify: `client/src/state/api.ts:680-697` — `SignalStudyType` 유니온, 주석
- Modify: `client/src/app/insight/SignalsSection.tsx:64-120,146-154,205` —
  `TrackRecordStrip`
- Modify: `client/src/content/indicatorHelp.ts:163-170` — `signal.study` 도움말

**Interfaces:**
- Consumes (Task 2): `signal_study.parquet`의 `signal_type == "baseline"` 행.
  `/insight/signals/study` 응답에 그대로 실려 온다 (라우터 변경 불필요).
- Produces: 없음

**배경 — 경고가 항상 켜져 있다.** `SignalsSection.tsx:72`가
`h20.median_excess < 0`을 경고 조건으로 쓰는데, 새 벤치마크에서도 기준선 자체가
20일 −1.80%다. 즉 세 신호 전부 항상 경고가 뜬다. 항상 켜지는 경고는 정보가 없고,
셋 중 유일하게 우위가 있는 `frgn_streak10`까지 깎아내린다. 기준선 대비로 바꾼다.

- [ ] **Step 1: `api.ts`의 타입과 주석을 고친다**

`client/src/state/api.ts:680-697`을 아래로 바꾼다:

```typescript
export type SignalStudyType =
  /** 조건 없는 유동성 전 종목-일 — 다른 모든 행의 비교 기준. */
  | "baseline"
  | "bull_divergence"
  | "frgn_streak10"
  | "high_intensity"
  | "spike_1d_5"
  | "spike_1d_10"
  | "drop_1d_5"
  | "spike_5d_15"
  | "spike_20d_20"
  | "spike_20d_50"
  | "near_52w_high";

export interface SignalStudyRow {
  signal_type: SignalStudyType;
  horizon: 5 | 20 | 60;
  /**
   * 이벤트 수. 신호 간 비교 불가 — 상태형 신호에만 20일 쿨다운이 걸리고
   * 1일 급등/급락과 baseline에는 걸리지 않는다.
   */
  n_events: number;
  /** Mean forward excess return vs equal-weight cross-sectional mean, %. */
  mean_excess: number;
  /**
   * Median forward excess return vs equal-weight cross-sectional mean, %.
   * 벤치마크가 평균이고 수익률 분포가 우편향이라 baseline조차 음수다 —
   * 절대값이 아니라 baseline 행과의 차이로만 판정할 것.
   */
  median_excess: number;
  /** Share of events with positive excess return, %. */
  hit_rate: number;
  /** Mean absolute forward return, %. */
  avg_fwd_ret: number;
}
```

- [ ] **Step 2: `TrackRecordStrip`을 기준선 대비로 바꾼다**

`client/src/app/insight/SignalsSection.tsx:64-120`의 `TrackRecordStrip` 정의
전체(주석 블록 포함)를 아래로 바꾼다:

```tsx
/**
 * Honest historical track record: forward excess return vs the equal-weight
 * cross-sectional mean at 5/20/60d. The absolute medians are negative even for
 * the unconditional baseline (the benchmark is a mean, returns are right-skewed),
 * so the only readable number is the delta vs baseline — that's what's emphasized.
 */
const TrackRecordStrip: React.FC<{
  rows: SignalStudyRow[];
  baseline: SignalStudyRow[];
}> = ({ rows, baseline }) => {
  const byHorizon = new Map(rows.map((r) => [r.horizon, r]));
  const baseByHorizon = new Map(baseline.map((r) => [r.horizon, r]));
  const h20 = byHorizon.get(20);
  const b20 = baseByHorizon.get(20);
  // baseline 행이 없는 구 parquet에서는 경고를 띄우지 않는다 — 비교 근거가 없다.
  const showWarning =
    h20 !== undefined &&
    b20 !== undefined &&
    h20.median_excess < b20.median_excess;

  return (
    <div className="rounded-xl border border-edge bg-raised p-3 flex flex-col gap-2.5">
      <div className="flex items-center gap-1.5">
        <span className="text-xs font-semibold text-ink-secondary">
          역사적 성과 · 동일가중 평균 대비 (2016~)
        </span>
        <InfoTip helpKey="signal.study" />
      </div>
      <div className="grid grid-cols-3 gap-2">
        {STUDY_HORIZONS.map((h) => {
          const r = byHorizon.get(h);
          const b = baseByHorizon.get(h);
          const delta =
            r !== undefined && b !== undefined
              ? r.median_excess - b.median_excess
              : null;
          return (
            <div
              key={h}
              className="rounded-lg border border-edge bg-surface px-3 py-2"
            >
              <p className="text-[11px] text-ink-muted">{h}일 후 초과수익</p>
              {r ? (
                <>
                  {delta !== null && (
                    <p className="mt-0.5">
                      <span className="text-[11px] text-ink-muted">
                        기준선 대비{" "}
                      </span>
                      <span className={`${signClass(delta)} font-semibold num`}>
                        {delta >= 0 ? "+" : ""}
                        {delta.toFixed(2)}%p
                      </span>
                    </p>
                  )}
                  <p className="text-[11px] text-ink-muted num mt-0.5">
                    중앙값 {fmtPct(r.median_excess)} · 히트율{" "}
                    {r.hit_rate.toFixed(0)}%
                  </p>
                  <p className="text-[11px] text-ink-muted num mt-0.5">
                    N={r.n_events.toLocaleString()}건
                  </p>
                </>
              ) : (
                <p className="mt-0.5 num text-ink-muted">—</p>
              )}
            </div>
          );
        })}
      </div>
      {showWarning && h20 && b20 && (
        <p className="text-[11px] text-losses">
          ⚠ 이 신호는 아무 종목이나 골랐을 때보다 20일 성과가 낮았습니다 — 승률{" "}
          {h20.hit_rate.toFixed(1)}% vs 기준선 {b20.hit_rate.toFixed(1)}%.
        </p>
      )}
    </div>
  );
};
```

- [ ] **Step 3: baseline 행을 뽑아 넘긴다**

`client/src/app/insight/SignalsSection.tsx:148-154`의 `studyRows` useMemo 바로
뒤에 추가한다:

```tsx
  const studyRows = useMemo(
    () =>
      (studyData?.rows ?? []).filter(
        (r) => r.signal_type === STUDY_TYPE[type]
      ),
    [studyData, type]
  );
  // 비교 기준 — 조건 없는 유동성 전 종목-일. 구 parquet에는 없을 수 있다.
  const baselineRows = useMemo(
    () => (studyData?.rows ?? []).filter((r) => r.signal_type === "baseline"),
    [studyData]
  );
```

그리고 `:205`의 렌더 호출을 바꾼다:

```tsx
          {studyRows.length > 0 && (
            <TrackRecordStrip rows={studyRows} baseline={baselineRows} />
          )}
```

- [ ] **Step 4: 도움말 문구를 고친다**

`client/src/content/indicatorHelp.ts:163-172`의 아래 블록을

```typescript
  "signal.study": {
    title: "신호 이벤트 스터디",
    what: "2016년 이후 이 신호가 발생한 뒤 5·20·60일 KOSPI 대비 초과수익과 히트율을 집계.",
    how: [
      "히트율 50% 미만·중앙값 음수면 예측력이 없거나 오히려 역행",
      "서사가 아닌 증거로 신호를 판단하는 도구",
      "한국 수급 추종은 평균회귀 경향이 강해 단기 신호가 약함",
    ],
  },
```

이걸로 통째로 바꾼다:

```typescript
  "signal.study": {
    title: "신호 이벤트 스터디",
    what: "2016년 이후 이 신호가 발생한 뒤 5·20·60일 초과수익과 히트율을 집계. 비교 대상은 KOSPI 지수가 아니라 같은 날 유동성 종목 전체의 동일가중 평균.",
    how: [
      "중앙값·히트율의 절대치는 읽지 말 것 — 벤치마크가 평균이라 조건 없는 기준선조차 20일 중앙값 -1.8%·히트율 41%다",
      "기준선 대비 %p가 유일하게 읽을 값. 0 근처면 이 신호에 우위가 없다는 뜻",
      "N은 신호 간 비교 불가 — 신호 종류에 따라 중복 제거 방식이 다르다",
      "한국 수급 추종은 평균회귀 경향이 강해 단기 신호가 약함",
    ],
  },
```

첫 번째 `how` 항목이 특히 중요하다. **"히트율 50% 미만이면 예측력 없음"은 틀렸다** —
기준선 히트율이 41.2%라 50%는 도달 불가능한 기준이고, 그 문장대로 읽으면 모든
신호가 무가치해 보인다.

- [ ] **Step 5: 남은 KOSPI 기준 표현이 없는지 확인한다**

Run:
```bash
cd /Users/achii/Quant/Insight-Invest
grep -rn "KOSPI 대비" client/src/ | grep -v node_modules
```
Expected: 출력 없음. (`client/src/app/regime/PhasePerformance.tsx`와
`client/src/state/api.ts:449`의 `hit_rate`는 매크로 레짐 기능의 별개 필드다 —
건드리지 않는다.)

- [ ] **Step 6: 타입 체크와 빌드를 돌린다**

Run:
```bash
cd /Users/achii/Quant/Insight-Invest/client
npx tsc --noEmit
npm run build
```
Expected: 둘 다 에러 없이 완료.

- [ ] **Step 7: 커밋**

```bash
cd /Users/achii/Quant/Insight-Invest
git add client/src/state/api.ts client/src/app/insight/SignalsSection.tsx client/src/content/indicatorHelp.ts
git commit -m "fix(insight): 신호 경고를 기준선 대비로 — 항상 켜지던 경고 해소"
```

---

### Task 5: 텔레그램 브리핑에 실측치 병기

**Files:**
- Modify: `scripts/send_briefing.py:273-293` — `_section_signals()`

**Interfaces:**
- Consumes (Task 1): `module.signal_stats.load_study()`,
  `module.signal_stats.evidence_phrase(signal_type, horizon=20, df=None)`.
  signal_type은 `"bull_divergence"` / `"frgn_streak10"`.
- Produces: 없음

**배경:** 브리핑의 신호 섹션은 종목 이름만 나열한다. 그 신호가 과거에 통했는지는
말하지 않는다. 20일 기준선 대비 실측치를 한 줄씩 붙인다. `bull_divergence`는
−0.29%p로 우위가 없고 `frgn_streak10`은 +0.51%p로 약하게 플러스인데, 지금은 둘이
같은 무게로 나열된다.

- [ ] **Step 1: `_section_signals()`를 교체한다**

`scripts/send_briefing.py:273-293`을 아래로 바꾼다:

```python
def _section_signals() -> str | None:
    df = storage.read_parquet("insight", "flows_signals.parquet")
    frgn = df[df["investor"] == "frgn"]
    lines = []
    # 신호마다 "과거에 통했는가"를 한 줄로 붙인다 — 이름만 나열하면 우위가 없는
    # 신호와 있는 신호가 같은 무게로 읽힌다.
    study = signal_stats.load_study()

    def _append(text: str, signal_type: str) -> None:
        lines.append(text)
        ev = signal_stats.evidence_phrase(signal_type, 20, df=study)
        if ev:
            lines.append(f"  └ {_esc(ev)}")

    bull = frgn[frgn["divergence"] == "bull"].copy()
    if not bull.empty:
        bull = bull.reindex(bull["intensity_20d"].abs().sort_values(ascending=False).index)
        names = " · ".join(_esc(n) for n in bull["name"].head(3))
        _append(f"매집형(주가↓·외인 매집): {names}", "bull_divergence")

    streak = frgn[frgn["streak"] >= 7].sort_values("streak", ascending=False).head(3)
    if not streak.empty:
        items = " · ".join(
            f"{_esc(r['name'])}({int(r['streak'])}일)" for _, r in streak.iterrows()
        )
        _append(f"외인 연속매수 7일+: {items}", "frgn_streak10")

    if not lines:
        return None
    return "<b>신호</b>\n" + "\n".join(lines)
```

브리핑은 텔레그램 HTML 파스모드라 `_esc()`로 이스케이프해야 한다. 실측치 문장에
`<`·`&`가 들어갈 일은 없지만 다른 사용자 노출 문자열과 규칙을 맞춘다.

- [ ] **Step 2: 임포트를 추가한다**

`scripts/send_briefing.py:34-35`의

```python
from datastore import meta, portfolio, storage, watchlist  # noqa: E402
from qdata import api as qdata_api  # noqa: E402
```

를 이걸로 바꾼다 (알파벳 순: `datastore` < `module` < `qdata`):

```python
from datastore import meta, portfolio, storage, watchlist  # noqa: E402
from module import signal_stats  # noqa: E402
from qdata import api as qdata_api  # noqa: E402
```

`# noqa: E402`는 이 파일이 `sys.path.insert` 뒤에 임포트하기 때문에 필요하다 —
주변 두 줄과 동일하게 붙인다.

- [ ] **Step 3: 신호 섹션만 렌더해서 확인한다**

Run:
```bash
cd /Users/achii/Quant/Insight-Invest/server
QDATA_LAKE=~/Quant/data-lake .venv-test/bin/python - <<'PY'
import sys
sys.path.insert(0, "../scripts")
from send_briefing import _section_signals

s = _section_signals()
print(s if s else "(신호 없음 — 오늘 조건 충족 종목 0건)")
PY
```
Expected: `<b>신호</b>` 아래 각 신호 줄 뒤에 `└ 과거 N건 · 20일 뒤 기준선 대비
±X.X%p (승률 ±Y.Y%p)` 가 붙어 출력된다. Task 2가 아직 S3에 발행되지 않았다면
실측치 줄이 없을 수 있다 — 그건 폴백이 동작한 것이므로 실패가 아니다.

- [ ] **Step 4: 커밋**

```bash
cd /Users/achii/Quant/Insight-Invest
git add scripts/send_briefing.py
git commit -m "feat(briefing): 신호 섹션에 기준선 대비 실측치 병기"
```

---

## 배포 (전 태스크 완료 후)

1. `main`에 푸시한다. `server/**` 변경이 있으므로 GitHub Actions `deploy-api`가
   Lambda를 재배포한다 (Task 1·3).
2. `client/**`는 Vercel이 자동 배포한다 (Task 4).
3. `scripts/**`는 배포 절차가 없다 — 배치 EC2가 매 실행 `git pull` 한다.
   따라서 **다음 평일 19:00 KST 실행에서** 새 `signal_study.parquet`이 발행된다.
4. 그 전까지 프론트·attention은 구 parquet(baseline 행 없음)을 읽는다. 폴백이
   설계돼 있으므로 화면은 깨지지 않는다 — 경고와 기준선 델타가 안 보일 뿐이다.

## 알려진 한계 (설계 문서 §9와 동일)

- 거래비용·슬리피지 미반영
- `n_events`는 독립 표본 수가 아니다 (이벤트가 겹친다)
- 레짐 조건부 분석 없음 — 2016~2026 전 기간 단일 통계
- 생존 편향 미검증

## 후속 (이번 범위 밖)

- 양의 신호(저변동·소형·저평가·외인연속매도) 교차분석 — 독립적인 신호가 몇 개인지
- 레짐별 조건부 성과
- 거래비용 반영 후 실행 가능성 판단
- "오늘의 중요 종목" 기능 — 위 검증을 통과한 신호가 재료가 된다
