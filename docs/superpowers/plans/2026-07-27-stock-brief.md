# 종목 브리프 (Bull/Bear 대립 리서치) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 매 거래일 대상 종목에 대해 서로를 보지 못하는 강세·약세 논거를 생성하고 그 둘이 갈리는 지점을 짚는 브리프를 만들어 `briefs.parquet`에 저장하고, 텔레그램·웹 4곳에 노출한다.

**Architecture:** 기존 EC2 `qdata-collector`의 평일 19:00 실행 창 안에서 `build_insights.py` 직후 `build_briefs.py`가 돈다. 사전계산 parquet에서 종목별 Evidence Pack을 조립하고 — 이때 `signal_study`(이벤트 스터디)와 `flows_signals`(현재값)을 조인해 기저율을 붙이는 것이 핵심 — Claude Opus 5로 bull ∥ bear → judge 3콜을 돌린 뒤 결과를 parquet에 쓴다. Lambda는 읽기만 한다.

**Tech Stack:** Python 3.12, pandas, pyarrow, `anthropic` SDK, FastAPI, pytest (신규), Next.js 14 + RTK Query

**설계 문서:** `docs/superpowers/specs/2026-07-27-stock-brief-design.md`

## Global Constraints

- **모델은 `claude-opus-5` 고정.** 비용 사유로 다운그레이드하지 않는다.
- **evidence pack 밖의 사실을 쓰지 않는다.** 프롬프트 규칙 + 코드 검증 이중 방어.
- **매수/매도/보유 판정을 생성하지 않는다.** 논거 정리와 판정 근거까지만.
- **기저율 조인은 `signal_study`의 조건식으로 재계산한다.** `flows_signals.divergence` 라벨(`ret_20d < 0`)을 조회 키로 쓰면 안 된다 — `signal_study.bull_divergence`는 `ret_20d < -5`다.
- **모든 실패는 비치명.** 빌더는 `try/except → None`, 섹션은 `_try()`, 파이프라인은 `|| echo "[warn]"`. 기존 파이프라인을 죽이지 않는다.
- **대상 종목 상한 15.** 절삭 발생 시 반드시 로깅한다.
- **pytest는 `requirements-dev.txt`에만.** Lambda 이미지에 들어가면 안 된다.
- **커밋 메시지는 한국어**, 기존 레포 관례(`feat(...)`, `fix(...)`, `docs(...)`)를 따른다.
- **`server/` 하위 Python은 pre-commit이 black(line-length=100) + isort(profile=black)를 강제한다.**

## File Structure

기존 `server/module/news/`(config·service·client 분리) 패턴을 따라 `server/module/brief/` 패키지를 만든다. `scripts/build_briefs.py`는 얇은 진입점으로만 둔다 — 순수 로직을 `server/module/`에 두어야 테스트에서 import할 수 있다.

```
server/module/brief/
├── __init__.py       공개 API 재수출
├── evidence.py       기저율 매칭 + Evidence Pack 조립  (순수 함수, 테스트 집중)
├── select.py         대상 종목 선정 + 절삭             (순수 함수, 테스트)
├── schema.py         JSON 스키마 + evidence_ref 검증   (순수 함수, 테스트)
└── llm.py            Claude 3콜 오케스트레이션          (모킹 테스트)

server/datastore/briefs.py    briefs.parquet 읽기/쓰기 (watchlist.py 패턴)
server/app/routers/brief.py   GET /brief/{ticker}, GET /brief/today
scripts/build_briefs.py       진입점 — 위 모듈 조립

server/tests/
├── conftest.py
├── test_brief_evidence.py
├── test_brief_select.py
├── test_brief_schema.py
└── test_brief_llm.py

client/src/app/stock/[metaId]/BriefCard.tsx
client/src/app/insight/BriefStrip.tsx
```

## 실행 순서와 위험 순서

Task 1~5는 LLM이 끼지 않는 순수 함수 계층이고, **여기가 인사이트의 정확성을 좌우한다.** 특히 Task 1(기저율 매칭)은 틀려도 에러가 나지 않고 그럴듯한 거짓 숫자가 나오므로 가장 먼저, 가장 촘촘하게 테스트한다.

Task 12~14(프론트)는 Task 11(텔레그램)로 프롬프트를 며칠 안정화한 뒤 착수한다. 프롬프트가 흔들리는 동안 UI를 만들면 UI도 같이 흔들린다.

---

## Phase 1 — 정확성 기반 (LLM 없음)

### Task 1: 테스트 인프라 + 기저율 매칭

이 플랜에서 가장 중요한 태스크다. `signal_study`의 조건식을 재계산하는 함수를 만들고, `flows_signals.divergence`와 갈리는 경계값을 테스트로 못박는다.

**Files:**
- Create: `server/requirements-dev.txt`
- Create: `server/tests/conftest.py`
- Create: `server/module/brief/__init__.py`
- Create: `server/module/brief/evidence.py`
- Test: `server/tests/test_brief_evidence.py`

**Interfaces:**
- Produces:
  - `BASE_RATE_SIGNALS: dict[str, Callable[[dict], bool]]`
  - `match_base_rate_signals(frgn_row: dict) -> list[str]`
  - `attach_base_rates(matched: list[str], study: pd.DataFrame) -> dict`

- [ ] **Step 1: 테스트 의존성 파일 생성**

`server/requirements-dev.txt`:

```
# 개발 전용 — Lambda 이미지(requirements.txt)에는 넣지 않는다.
#   pip install -r requirements.txt -r requirements-dev.txt
pytest>=8.0
```

- [ ] **Step 2: conftest 생성**

`server/tests/conftest.py`:

```python
"""테스트에서 server/ 를 import 루트로 사용 — 앱 코드의 sys.path 관례와 동일."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
```

- [ ] **Step 3: 패키지 초기화 파일 생성**

`server/module/brief/__init__.py`:

```python
"""종목 브리프 — Evidence Pack 조립, 대상 선정, 스키마 검증, LLM 오케스트레이션."""
```

- [ ] **Step 4: 실패하는 테스트 작성**

`server/tests/test_brief_evidence.py`:

```python
import pandas as pd
import pytest

from module.brief.evidence import attach_base_rates, match_base_rate_signals


def test_streak_경계_10은_발화_9는_미발화():
    assert "frgn_streak10" in match_base_rate_signals(
        {"streak": 10, "intensity_20d": 0.0, "ret_20d": 0.0}
    )
    assert "frgn_streak10" not in match_base_rate_signals(
        {"streak": 9, "intensity_20d": 0.0, "ret_20d": 0.0}
    )


def test_intensity_경계_1_0은_발화_0_99는_미발화():
    assert "high_intensity" in match_base_rate_signals(
        {"streak": 0, "intensity_20d": 1.0, "ret_20d": 0.0}
    )
    assert "high_intensity" not in match_base_rate_signals(
        {"streak": 0, "intensity_20d": 0.99, "ret_20d": 0.0}
    )


def test_bull_divergence는_ret_20d가_정확히_마이너스5면_미발화():
    # signal_study 조건은 ret_20d < -5 (이하가 아니라 미만)
    assert "bull_divergence" not in match_base_rate_signals(
        {"streak": 0, "intensity_20d": 0.31, "ret_20d": -5.0}
    )
    assert "bull_divergence" in match_base_rate_signals(
        {"streak": 0, "intensity_20d": 0.31, "ret_20d": -5.01}
    )


def test_flows_signals_divergence_라벨과_갈리는_구간():
    """★ 회귀 방지의 핵심.

    ret_20d=-3, intensity=0.5는 flows_signals에서 divergence="bull"로 라벨링되지만
    signal_study의 bull_divergence(ret_20d < -5)에는 해당하지 않는다.
    divergence 라벨을 조회 키로 쓰면 -5 기준 통계가 잘못 딸려온다.
    """
    row = {"streak": 0, "intensity_20d": 0.5, "ret_20d": -3.0}
    assert "bull_divergence" not in match_base_rate_signals(row)


def test_결측치는_예외없이_미발화():
    assert match_base_rate_signals({"streak": None, "intensity_20d": None, "ret_20d": None}) == []
    assert match_base_rate_signals({}) == []


def test_복수_신호_동시_발화():
    row = {"streak": 12, "intensity_20d": 1.5, "ret_20d": -8.0}
    matched = match_base_rate_signals(row)
    assert set(matched) == {"frgn_streak10", "high_intensity", "bull_divergence"}


def test_attach_base_rates가_지평선별로_묶는다():
    study = pd.DataFrame(
        [
            {"signal_type": "frgn_streak10", "horizon": 5, "n_events": 1800,
             "median_excess": 0.4, "hit_rate": 51.2, "mean_excess": 0.5, "avg_fwd_ret": 0.9},
            {"signal_type": "frgn_streak10", "horizon": 20, "n_events": 1847,
             "median_excess": 2.1, "hit_rate": 54.0, "mean_excess": 2.4, "avg_fwd_ret": 3.1},
            {"signal_type": "high_intensity", "horizon": 20, "n_events": 900,
             "median_excess": 1.0, "hit_rate": 52.0, "mean_excess": 1.2, "avg_fwd_ret": 2.0},
        ]
    )
    out = attach_base_rates(["frgn_streak10"], study)
    assert set(out) == {"frgn_streak10"}
    assert out["frgn_streak10"]["h20"] == {
        "n_events": 1847, "median_excess": 2.1, "hit_rate": 54.0
    }
    assert "h5" in out["frgn_streak10"]


def test_attach_base_rates는_결측_통계를_None으로():
    study = pd.DataFrame(
        [{"signal_type": "high_intensity", "horizon": 20, "n_events": 0,
          "median_excess": float("nan"), "hit_rate": float("nan"),
          "mean_excess": float("nan"), "avg_fwd_ret": float("nan")}]
    )
    out = attach_base_rates(["high_intensity"], study)
    assert out["high_intensity"]["h20"]["median_excess"] is None
    assert out["high_intensity"]["h20"]["n_events"] == 0
```

- [ ] **Step 5: 테스트가 실패하는지 확인**

Run: `cd server && python -m pytest tests/test_brief_evidence.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'module.brief.evidence'`

- [ ] **Step 6: 최소 구현 작성**

`server/module/brief/evidence.py`:

```python
"""Evidence Pack 조립 — 브리프의 유일한 사실 출처.

기저율 조인이 이 모듈의 핵심이다. build_insights의 signal_study(이벤트 스터디)와
flows_signals(종목별 현재값)이 같은 정의를 쓰므로, 조건식을 재계산해 조인하면
"신호"에 표본 수·승률·중앙값이 붙어 "확률"이 된다.
"""

import pandas as pd

# signal_study의 conds와 반드시 동일해야 한다 (scripts/build_insights.py:build_signal_study).
# flows_signals의 divergence 라벨은 ret_20d < 0 기준이라 여기 쓰면 안 된다.
BASE_RATE_SIGNALS = {
    "frgn_streak10": lambda r: r["streak"] >= 10,
    "high_intensity": lambda r: r["intensity_20d"] >= 1.0,
    "bull_divergence": lambda r: r["ret_20d"] < -5 and r["intensity_20d"] > 0.3,
}

SIGNAL_HORIZONS = (5, 20, 60)


def match_base_rate_signals(frgn_row: dict) -> list[str]:
    """flows_signals의 investor=='frgn' 행 → 현재 발화 중인 signal_study 신호명 목록.

    결측치나 키 부재는 미발화로 취급한다 (예외를 올리지 않는다).
    """
    matched = []
    for name, cond in BASE_RATE_SIGNALS.items():
        try:
            if cond(frgn_row):
                matched.append(name)
        except (KeyError, TypeError):
            continue
    return matched


def attach_base_rates(matched: list[str], study: pd.DataFrame) -> dict:
    """신호명 목록 → {signal: {"h5"|"h20"|"h60": {n_events, median_excess, hit_rate}}}."""
    out: dict = {}
    for sig in matched:
        rows = study[study["signal_type"] == sig]
        if rows.empty:
            continue
        out[sig] = {
            f"h{int(r.horizon)}": {
                "n_events": int(r.n_events),
                "median_excess": None if pd.isna(r.median_excess) else round(float(r.median_excess), 2),
                "hit_rate": None if pd.isna(r.hit_rate) else round(float(r.hit_rate), 1),
            }
            for r in rows.itertuples()
        }
    return out
```

- [ ] **Step 7: 테스트 통과 확인**

Run: `cd server && python -m pytest tests/test_brief_evidence.py -v`
Expected: PASS — 8 passed

- [ ] **Step 8: 커밋**

```bash
git add server/requirements-dev.txt server/tests/ server/module/brief/
git commit -m "feat(brief): 기저율 매칭 + 테스트 인프라

signal_study 조건식을 재계산해 flows_signals 현재값과 조인한다.
flows_signals.divergence(ret_20d<0)와 signal_study.bull_divergence(ret_20d<-5)의
정의 차이를 경계값 테스트로 못박았다 — 그대로 조인하면 에러 없이 거짓 통계가 붙는다.

pytest는 requirements-dev.txt에만 넣어 Lambda 이미지에서 제외한다."
```

---

### Task 2: Evidence Pack 조립

**Files:**
- Modify: `server/module/brief/evidence.py`
- Test: `server/tests/test_brief_evidence.py`

**Interfaces:**
- Consumes: `match_base_rate_signals`, `attach_base_rates` (Task 1)
- Produces: `build_evidence_pack(ticker: str, sources: dict) -> dict`
  - `sources` 키: `flows_signals`, `signal_study`, `factor_pct`, `sector_perf`, `breadth`, `valuation`, `regime`, `holdings`, `news`, `prior_brief`, `meta`
  - 반환 dict 키: `identity`, `flows`, `base_rates`, `factors`, `sector`, `market`, `holding`, `news`, `prior_brief`

- [ ] **Step 1: 실패하는 테스트 추가**

`server/tests/test_brief_evidence.py` 끝에 추가:

```python
from module.brief.evidence import build_evidence_pack


def _sources():
    """최소 픽스처 — 모든 소스가 존재하는 정상 케이스."""
    return {
        "meta": {"name": "테스트전자", "market": "KOSPI", "sector": "반도체"},
        "flows_signals": pd.DataFrame(
            [
                {"ticker": "005930", "investor": "frgn", "streak": 12, "net_20d": 5e11,
                 "intensity_20d": 1.4, "ret_20d": -6.0, "divergence": "bull",
                 "close": 70000, "chg_pct": 1.2, "mktcap": 4e14},
                {"ticker": "005930", "investor": "inst", "streak": -3, "net_20d": -1e11,
                 "intensity_20d": -0.2, "ret_20d": -6.0, "divergence": None,
                 "close": 70000, "chg_pct": 1.2, "mktcap": 4e14},
            ]
        ),
        "signal_study": pd.DataFrame(
            [{"signal_type": "frgn_streak10", "horizon": 20, "n_events": 1847,
              "median_excess": 2.1, "hit_rate": 54.0, "mean_excess": 2.4, "avg_fwd_ret": 3.1}]
        ),
        "factor_pct": pd.DataFrame(
            [{"ticker": "005930", "momentum": 92.0, "value": 19.0, "size": 3.0, "lowvol": 61.0}]
        ),
        "sector_perf": pd.DataFrame(
            [{"market": "KOSPI", "sector": "반도체", "ret_1d": 0.8, "ret_1w": 2.1,
              "ret_1m": 5.5, "ret_3m": 12.0, "ret_ytd": 20.0, "weight": 18.4}]
        ),
        "breadth": {"advancers": 480, "decliners": 420, "above_ma20_pct": 55.2},
        "valuation": {"market": "KOSPI", "per": 11.2, "pbr": 1.05, "div_yield": 2.1},
        "regime": {"phase": "회복", "risk_gauge": 42},
        "holdings": {"005930": {"shares": 10, "avg_cost": 65000, "pnl_pct": 7.7, "weight_pct": 12.0}},
        "news": [{"title": "테스트 헤드라인", "source": "연합", "date": "2026-07-25"}],
        "prior_brief": {"as_of": "2026-07-20", "stance_note": "수급 우위", "price_change_since": 4.1},
    }


def test_evidence_pack_기본_구조():
    pack = build_evidence_pack("005930", _sources())
    assert set(pack) == {
        "identity", "flows", "base_rates", "factors",
        "sector", "market", "holding", "news", "prior_brief",
    }
    assert pack["identity"]["ticker"] == "005930"
    assert pack["identity"]["name"] == "테스트전자"


def test_evidence_pack이_frgn_기준으로_기저율을_붙인다():
    pack = build_evidence_pack("005930", _sources())
    # streak 12 → frgn_streak10 발화, intensity 1.4 → high_intensity 발화,
    # ret_20d -6.0 & intensity 1.4 → bull_divergence 발화.
    # 단 signal_study에 행이 있는 건 frgn_streak10뿐이므로 그것만 남는다.
    assert set(pack["base_rates"]) == {"frgn_streak10"}
    assert pack["base_rates"]["frgn_streak10"]["h20"]["n_events"] == 1847


def test_evidence_pack이_투자자별_수급을_분리한다():
    pack = build_evidence_pack("005930", _sources())
    assert pack["flows"]["frgn"]["streak"] == 12
    assert pack["flows"]["inst"]["streak"] == -3


def test_미보유_종목은_holding이_None():
    src = _sources()
    src["holdings"] = {}
    pack = build_evidence_pack("005930", src)
    assert pack["holding"] is None


def test_소스_결손시_해당_섹션만_None이고_예외없음():
    src = _sources()
    src["factor_pct"] = pd.DataFrame(columns=["ticker", "momentum", "value", "size", "lowvol"])
    src["news"] = []
    src["prior_brief"] = None
    pack = build_evidence_pack("005930", src)
    assert pack["factors"] is None
    assert pack["news"] == []
    assert pack["prior_brief"] is None
    assert pack["identity"]["ticker"] == "005930"  # 나머지는 정상


def test_flows_signals에_없는_종목이면_ValueError():
    with pytest.raises(ValueError, match="flows_signals"):
        build_evidence_pack("999999", _sources())
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `cd server && python -m pytest tests/test_brief_evidence.py -v -k evidence_pack`
Expected: FAIL — `ImportError: cannot import name 'build_evidence_pack'`

- [ ] **Step 3: 구현 추가**

`server/module/brief/evidence.py` 끝에 추가:

```python
def _flows_by_investor(fs: pd.DataFrame, ticker: str) -> dict:
    """flows_signals에서 종목 행을 투자자별 dict로. 없으면 빈 dict."""
    rows = fs[fs["ticker"] == ticker]
    out = {}
    for r in rows.itertuples():
        out[r.investor] = {
            "streak": int(r.streak),
            "net_20d": float(r.net_20d),
            "intensity_20d": round(float(r.intensity_20d), 3),
            "ret_20d": round(float(r.ret_20d), 2) if pd.notna(r.ret_20d) else None,
            "divergence": r.divergence,
        }
    return out


def _factors(fp: pd.DataFrame, ticker: str) -> dict | None:
    rows = fp[fp["ticker"] == ticker] if not fp.empty else fp
    if rows.empty:
        return None
    r = rows.iloc[0]
    return {
        f: (None if pd.isna(r[f]) else round(float(r[f]), 1))
        for f in ("momentum", "value", "size", "lowvol")
    }


def _sector(sp: pd.DataFrame, market: str, sector: str) -> dict | None:
    rows = sp[(sp["market"] == market) & (sp["sector"] == sector)] if not sp.empty else sp
    if rows.empty:
        return None
    r = rows.iloc[0]
    keys = ("ret_1d", "ret_1w", "ret_1m", "ret_3m", "ret_ytd", "weight")
    return {k: (None if pd.isna(r[k]) else round(float(r[k]), 2)) for k in keys}


def build_evidence_pack(ticker: str, sources: dict) -> dict:
    """종목 1개의 Evidence Pack. LLM은 이 안의 값만 쓸 수 있다.

    sources 키: meta, flows_signals, signal_study, factor_pct, sector_perf,
                breadth, valuation, regime, holdings, news, prior_brief
    개별 소스가 비어 있으면 해당 섹션만 None/빈값이 되고 예외를 올리지 않는다.
    단 flows_signals에 종목이 없으면 브리프를 만들 근거가 없으므로 ValueError.
    """
    fs = sources["flows_signals"]
    flows = _flows_by_investor(fs, ticker)
    if not flows:
        raise ValueError(f"flows_signals에 {ticker} 없음 — 브리프 생성 불가")

    meta = sources.get("meta") or {}
    snap = fs[fs["ticker"] == ticker].iloc[0]

    matched = match_base_rate_signals(flows.get("frgn", {}))
    base_rates = attach_base_rates(matched, sources["signal_study"])

    return {
        "identity": {
            "ticker": ticker,
            "name": meta.get("name", ticker),
            "market": meta.get("market"),
            "sector": meta.get("sector"),
            "mktcap": float(snap["mktcap"]),
            "close": float(snap["close"]),
            "chg_pct": round(float(snap["chg_pct"]), 2) if pd.notna(snap["chg_pct"]) else None,
        },
        "flows": flows,
        "base_rates": base_rates,
        "factors": _factors(sources["factor_pct"], ticker),
        "sector": _sector(sources["sector_perf"], meta.get("market"), meta.get("sector")),
        "market": {
            "regime": sources.get("regime"),
            "breadth": sources.get("breadth"),
            "valuation": sources.get("valuation"),
        },
        "holding": (sources.get("holdings") or {}).get(ticker),
        "news": sources.get("news") or [],
        "prior_brief": sources.get("prior_brief"),
    }
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd server && python -m pytest tests/test_brief_evidence.py -v`
Expected: PASS — 14 passed

- [ ] **Step 5: 커밋**

```bash
git add server/module/brief/evidence.py server/tests/test_brief_evidence.py
git commit -m "feat(brief): Evidence Pack 조립

종목 1개분 사실을 9개 섹션으로 모은다. 개별 소스 결손은 해당 섹션만
None이 되고 예외를 올리지 않는다 — 단 flows_signals에 종목이 없으면
브리프 근거 자체가 없으므로 ValueError."
```

---

### Task 3: 대상 종목 선정

**Files:**
- Create: `server/module/brief/select.py`
- Test: `server/tests/test_brief_select.py`

**Interfaces:**
- Produces: `select_targets(watchlist: set[str], holdings: set[str], attention_high: list[str], mktcap: dict[str, float], cap: int = 15) -> tuple[list[str], list[str]]`
  - 반환: `(선정된 티커 목록, 절삭된 티커 목록)`

- [ ] **Step 1: 실패하는 테스트 작성**

`server/tests/test_brief_select.py`:

```python
from module.brief.select import MKTCAP_FLOOR, select_targets


def _cap(tickers, value=1e12):
    return {t: value for t in tickers}


def test_세_소스의_합집합을_반환():
    picked, dropped = select_targets(
        watchlist={"A"}, holdings={"B"}, attention_high=["C"], mktcap=_cap("ABC")
    )
    assert set(picked) == {"A", "B", "C"}
    assert dropped == []


def test_중복은_한_번만():
    picked, _ = select_targets(
        watchlist={"A"}, holdings={"A"}, attention_high=["A"], mktcap=_cap("A")
    )
    assert picked == ["A"]


def test_시총_하한_미만은_제외():
    mktcap = {"A": MKTCAP_FLOOR, "B": MKTCAP_FLOOR - 1}
    picked, dropped = select_targets(
        watchlist={"A", "B"}, holdings=set(), attention_high=[], mktcap=mktcap
    )
    assert picked == ["A"]
    assert dropped == []  # 하한 미달은 절삭이 아니라 자격 미달


def test_시총_정보_없는_종목은_제외():
    picked, _ = select_targets(
        watchlist={"A", "UNKNOWN"}, holdings=set(), attention_high=[], mktcap=_cap("A")
    )
    assert picked == ["A"]


def test_상한_초과시_보유_attention_워치리스트_순으로_남긴다():
    watch = {f"W{i}" for i in range(10)}
    hold = {f"H{i}" for i in range(3)}
    att = [f"A{i}" for i in range(5)]
    all_t = watch | hold | set(att)
    picked, dropped = select_targets(
        watchlist=watch, holdings=hold, attention_high=att, mktcap=_cap(all_t), cap=6
    )
    assert len(picked) == 6
    assert set(picked[:3]) == hold          # 보유가 최우선
    assert set(picked[3:6]) == set(att[:3])  # 그다음 attention (입력 순서 유지)
    assert len(dropped) == 12
    assert set(dropped).isdisjoint(hold)


def test_attention_입력_순서가_우선순위():
    att = ["A1", "A2", "A3"]
    picked, _ = select_targets(
        watchlist=set(), holdings=set(), attention_high=att, mktcap=_cap(att), cap=2
    )
    assert picked == ["A1", "A2"]


def test_보유가_상한을_넘으면_보유만_남는다():
    hold = {f"H{i}" for i in range(20)}
    picked, dropped = select_targets(
        watchlist={"W"}, holdings=hold, attention_high=[], mktcap=_cap(hold | {"W"}), cap=15
    )
    assert len(picked) == 15
    assert set(picked).issubset(hold)
    assert "W" in dropped
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `cd server && python -m pytest tests/test_brief_select.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'module.brief.select'`

- [ ] **Step 3: 구현 작성**

`server/module/brief/select.py`:

```python
"""브리프 대상 종목 선정.

워치리스트 ∪ 보유 ∪ attention(high)에서 시총 하한을 넘는 종목을 고르고
상한을 적용한다. 절삭된 종목은 반드시 호출자가 로깅해야 한다 —
조용한 절삭은 "전부 커버했다"는 착각을 만든다.
"""

MKTCAP_FLOOR = 1e10  # build_insights.MKTCAP_FLOOR와 동일 — signal_study 유니버스 기준
DEFAULT_CAP = 15


def select_targets(
    watchlist: set,
    holdings: set,
    attention_high: list,
    mktcap: dict,
    cap: int = DEFAULT_CAP,
) -> tuple[list, list]:
    """(선정 티커, 절삭 티커).

    우선순위: 보유 > attention high > 워치리스트.
    attention_high는 입력 순서(=attention 점수순)를 우선순위로 그대로 쓴다.
    시총 하한 미달·시총 정보 없음은 자격 미달이라 절삭 목록에 넣지 않는다.
    """

    def eligible(t):
        return mktcap.get(t) is not None and mktcap[t] >= MKTCAP_FLOOR

    ordered, seen = [], set()
    for tier in (sorted(holdings), [t for t in attention_high], sorted(watchlist)):
        for t in tier:
            if t in seen or not eligible(t):
                continue
            seen.add(t)
            ordered.append(t)

    return ordered[:cap], ordered[cap:]
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd server && python -m pytest tests/test_brief_select.py -v`
Expected: PASS — 7 passed

- [ ] **Step 5: 커밋**

```bash
git add server/module/brief/select.py server/tests/test_brief_select.py
git commit -m "feat(brief): 대상 종목 선정

보유 > attention high > 워치리스트 순, 상한 15. 시총 하한(100억)은
signal_study 유니버스와 동일 기준. 절삭 목록을 함께 반환해 호출자가
로깅하게 한다 — 조용한 절삭 금지."
```

---

### Task 4: 출력 스키마 + evidence_ref 검증

프롬프트 규칙과 무관하게 동작하는 환각 방어선이다.

**Files:**
- Create: `server/module/brief/schema.py`
- Test: `server/tests/test_brief_schema.py`

**Interfaces:**
- Produces:
  - `BULL_BEAR_SCHEMA: dict`, `JUDGE_SCHEMA: dict` (JSON Schema)
  - `flatten_keys(obj: dict, prefix: str = "") -> set[str]`
  - `validate_points(points: list[dict], pack: dict) -> tuple[list[dict], list[dict]]`
  - `enforce_lengths(judge: dict) -> tuple[dict, list[str]]`

- [ ] **Step 1: 실패하는 테스트 작성**

`server/tests/test_brief_schema.py`:

```python
from module.brief.schema import (
    BULL_BEAR_SCHEMA,
    JUDGE_SCHEMA,
    enforce_lengths,
    flatten_keys,
    validate_points,
)


def test_flatten_keys가_중첩_경로를_만든다():
    pack = {"flows": {"frgn": {"streak": 12}}, "identity": {"ticker": "005930"}}
    keys = flatten_keys(pack)
    assert "flows" in keys
    assert "flows.frgn" in keys
    assert "flows.frgn.streak" in keys
    assert "identity.ticker" in keys


def test_flatten_keys는_리스트를_리프로_취급():
    keys = flatten_keys({"news": [{"title": "x"}]})
    assert keys == {"news"}


def test_실재하는_경로만_참조한_논거는_통과():
    pack = {"flows": {"frgn": {"streak": 12}}}
    points = [{"claim": "수급 강함", "evidence": ["flows.frgn.streak"]}]
    kept, dropped = validate_points(points, pack)
    assert len(kept) == 1
    assert dropped == []


def test_없는_경로를_참조한_논거는_드롭되고_사유가_남는다():
    pack = {"flows": {"frgn": {"streak": 12}}}
    points = [{"claim": "업황 회복", "evidence": ["industry.outlook"]}]
    kept, dropped = validate_points(points, pack)
    assert kept == []
    assert len(dropped) == 1
    assert dropped[0]["bad_refs"] == ["industry.outlook"]


def test_일부만_잘못된_경로여도_논거_전체를_드롭():
    pack = {"flows": {"frgn": {"streak": 12}}}
    points = [{"claim": "혼합", "evidence": ["flows.frgn.streak", "made.up"]}]
    kept, dropped = validate_points(points, pack)
    assert kept == []
    assert dropped[0]["bad_refs"] == ["made.up"]


def test_evidence가_비어있으면_드롭():
    kept, dropped = validate_points([{"claim": "근거없음", "evidence": []}], {"a": 1})
    assert kept == []
    assert dropped[0]["bad_refs"] == []


def test_길이_초과_필드를_자르고_보고한다():
    judge = {"one_liner": "가" * 80, "summary": "나" * 250, "tension": "다"}
    out, truncated = enforce_lengths(judge)
    assert len(out["one_liner"]) == 60
    assert len(out["summary"]) == 200
    assert set(truncated) == {"one_liner", "summary"}
    assert out["tension"] == "다"


def test_길이_이내면_그대로():
    judge = {"one_liner": "짧음", "summary": "짧음"}
    out, truncated = enforce_lengths(judge)
    assert out == judge
    assert truncated == []


def test_스키마가_필수필드를_강제한다():
    assert BULL_BEAR_SCHEMA["required"] == ["points", "what_i_could_not_argue"]
    point = BULL_BEAR_SCHEMA["properties"]["points"]["items"]
    assert set(point["required"]) == {"claim", "evidence", "strength", "breaks_if"}
    assert point["additionalProperties"] is False
    assert "one_liner" in JUDGE_SCHEMA["required"]
    assert "decisive_question" in JUDGE_SCHEMA["required"]
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `cd server && python -m pytest tests/test_brief_schema.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'module.brief.schema'`

- [ ] **Step 3: 구현 작성**

`server/module/brief/schema.py`:

```python
"""브리프 출력 스키마와 결정론적 검증.

judge에게 "가짜 근거를 기각하라"고 시키는 것과 별개로, 파싱 후 코드로 검증한다.
프롬프트 규칙은 지켜지지 않을 수 있지만 이건 지켜진다.
"""

MAX_ONE_LINER = 60
MAX_SUMMARY = 200

BULL_BEAR_SCHEMA = {
    "type": "object",
    "properties": {
        "points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                    "strength": {"type": "string", "enum": ["strong", "moderate", "weak"]},
                    "breaks_if": {"type": "string"},
                },
                "required": ["claim", "evidence", "strength", "breaks_if"],
                "additionalProperties": False,
            },
        },
        "what_i_could_not_argue": {"type": "string"},
    },
    "required": ["points", "what_i_could_not_argue"],
    "additionalProperties": False,
}

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "one_liner": {"type": "string"},
        "summary": {"type": "string"},
        "tension": {"type": "string"},
        "decisive_question": {"type": "string"},
        "watch": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "metric": {"type": "string"},
                    "threshold": {"type": "string"},
                    "meaning": {"type": "string"},
                },
                "required": ["metric", "threshold", "meaning"],
                "additionalProperties": False,
            },
        },
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "confidence_reason": {"type": "string"},
        "stance_note": {"type": "string"},
    },
    "required": [
        "one_liner", "summary", "tension", "decisive_question",
        "watch", "confidence", "confidence_reason", "stance_note",
    ],
    "additionalProperties": False,
}


def flatten_keys(obj: dict, prefix: str = "") -> set:
    """중첩 dict → 점 경로 집합. 리스트는 리프로 취급한다."""
    keys = set()
    for k, v in obj.items():
        path = f"{prefix}{k}"
        keys.add(path)
        if isinstance(v, dict):
            keys |= flatten_keys(v, f"{path}.")
    return keys


def validate_points(points: list, pack: dict) -> tuple[list, list]:
    """evidence 경로가 pack에 실재하지 않는 논거를 분리. (유효, 드롭).

    evidence가 비어 있는 논거도 드롭한다 — 근거 없는 주장이기 때문.
    """
    valid = flatten_keys(pack)
    kept, dropped = [], []
    for p in points:
        refs = p.get("evidence") or []
        bad = [e for e in refs if e not in valid]
        if bad or not refs:
            dropped.append({**p, "bad_refs": bad})
        else:
            kept.append(p)
    return kept, dropped


def enforce_lengths(judge: dict) -> tuple[dict, list]:
    """JSON 스키마로 강제할 수 없는 길이 제약을 파싱 후 적용. (결과, 절단된 필드명)."""
    out = dict(judge)
    truncated = []
    for field, limit in (("one_liner", MAX_ONE_LINER), ("summary", MAX_SUMMARY)):
        val = out.get(field)
        if isinstance(val, str) and len(val) > limit:
            out[field] = val[:limit]
            truncated.append(field)
    return out, truncated
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd server && python -m pytest tests/test_brief_schema.py -v`
Expected: PASS — 9 passed

- [ ] **Step 5: 커밋**

```bash
git add server/module/brief/schema.py server/tests/test_brief_schema.py
git commit -m "feat(brief): 출력 스키마 + evidence_ref 결정론적 검증

evidence 경로가 pack에 실재하지 않으면 논거를 드롭한다. 프롬프트 규칙과
무관하게 동작하는 환각 방어선. 드롭 사유(bad_refs)를 남겨 프롬프트 품질
지표로 쓴다.

one_liner/summary 길이는 JSON 스키마로 강제할 수 없어 파싱 후 절단한다."
```

---

## Phase 2 — 팩터 백분위 영속화

### Task 5: `build_factor_pct_ticker` 빌더 + Lambda 폴백

계산 로직은 `insight.py`에 있지만 저장이 안 돼 있어 `/factor-exposure`가 매 콜드스타트마다 520일치 전종목 시세를 로드한다. parquet으로 떨어뜨려 브리프 재료를 만들면서 그 병목도 걷어낸다.

**Files:**
- Modify: `scripts/build_insights.py` (`FACTOR_NAMES` 정의부 근처 + `BUILDERS`)
- Modify: `server/app/routers/insight.py:265-297` (`_universe_factor_pct`)

**Interfaces:**
- Produces: `{APP_DATA}/insight/factor_pct_ticker.parquet` — `[ticker, momentum, value, size, lowvol, as_of]`

- [ ] **Step 1: 빌더 추가**

`scripts/build_insights.py`의 `build_factor_current()` 정의 바로 뒤에 추가:

```python
def build_factor_pct_ticker():
    """종목별 팩터 백분위 (0-100) 스냅샷 [ticker, momentum, value, size, lowvol].

    백분위 高 = 팩터 롱 방향(고모멘텀/저평가/소형/저변동). 유동성 유니버스 내 순위.
    _factor_scores와 같은 정의를 쓰되 최신 거래일 단면만 취한다.
    브리프 재료이자, Lambda /factor-exposure의 520일 로드를 대체한다.
    """
    try:
        start = (pd.Timestamp.today() - pd.Timedelta(days=520)).strftime("%Y-%m-%d")
        px = qdata_api.load_krx_prices(start=start, columns=["adj_close", "mktcap"])
        P = px.pivot(index="date", columns="ticker", values="adj_close").sort_index()
        M = px.pivot(index="date", columns="ticker", values="mktcap").sort_index()
        del px
        try:
            fund = qdata_api.load_krx_fundamental(start=start, columns=["per"])
            PER = (
                fund.pivot(index="date", columns="ticker", values="per")
                .sort_index()
                .reindex(index=P.index, columns=P.columns)
            )
        except FileNotFoundError:
            PER = pd.DataFrame(index=P.index, columns=P.columns, dtype="float64")

        last = P.index[-1]
        returns = P.pct_change(fill_method=None)
        scores = {
            "momentum": (P.shift(21) / P.shift(252) - 1).loc[last],
            "value": (1.0 / PER).where(PER > 0).loc[last],
            "size": (-M).loc[last],
            "lowvol": (-(returns.rolling(60, min_periods=40).std())).loc[last],
        }
        liquid = M.loc[last] >= MKTCAP_FLOOR
        df = pd.DataFrame(
            {f: (scores[f].where(liquid).rank(pct=True) * 100) for f in FACTOR_NAMES}
        )
        df = df.dropna(how="all").reset_index().rename(columns={"index": "ticker"})
        df.columns.name = None
        df["as_of"] = pd.Timestamp(last).strftime("%Y-%m-%d")
        print(f"[factor_pct_ticker] {len(df)} 종목, as_of={df['as_of'].iloc[0]}")
        return df
    except Exception:
        print("[warn] factor_pct_ticker 실패 (비중단):", file=sys.stderr)
        traceback.print_exc()
        return None
```

- [ ] **Step 2: BUILDERS에 등록**

`scripts/build_insights.py`의 `BUILDERS` 리스트, `factor_current` 줄 바로 뒤에 추가:

```python
    ("insight/factor_pct_ticker.parquet", build_factor_pct_ticker, {}),  # 브리프 재료 + Lambda 부담 경감
```

- [ ] **Step 3: 로컬에서 빌더만 실행해 스키마 확인**

Run:
```bash
cd /Users/achii/Quant/Insight-Invest
QDATA_LAKE=~/Quant/data-lake python -c "
import sys; sys.path.insert(0, 'server')
sys.argv = ['x']
exec(open('scripts/build_insights.py').read().split('def main()')[0])
df = build_factor_pct_ticker()
print(df.head())
print(df.columns.tolist())
assert list(df.columns) == ['ticker', 'momentum', 'value', 'size', 'lowvol', 'as_of'], df.columns.tolist()
print('OK')
"
```
Expected: 종목 수천 건 출력 후 `OK`. 로컬 레이크가 없으면 이 단계는 EC2에서 확인한다 (Task 10에서 전체 파이프라인 실행).

- [ ] **Step 4: Lambda가 parquet을 우선 사용하도록 수정**

`server/app/routers/insight.py`의 `_universe_factor_pct()` 본문 맨 앞(`from qdata import api as qdata_api` 줄 앞)에 삽입:

```python
    # 빌더가 떨어뜨린 스냅샷이 있으면 그걸 쓴다 — 520일 전종목 로드 회피.
    if storage.exists("insight/factor_pct_ticker.parquet"):
        df = storage.read_parquet("insight/factor_pct_ticker.parquet")
        pct = {f: df.set_index("ticker")[f].dropna() for f in FACTOR_NAMES}
        return pct, str(df["as_of"].iloc[0])

```

`insight.py` 상단에 `storage` import가 있는지 확인하고 없으면 추가한다 (`from datastore import storage`).

- [ ] **Step 5: 폴백이 유지되는지 확인**

Run:
```bash
cd server && python -c "
import ast, sys
src = open('app/routers/insight.py').read()
assert 'factor_pct_ticker.parquet' in src, 'parquet 우선 경로 없음'
assert 'load_krx_prices' in src, '폴백 경로가 사라짐'
ast.parse(src)
print('OK — parquet 우선 + 폴백 유지, 문법 정상')
"
```
Expected: `OK — parquet 우선 + 폴백 유지, 문법 정상`

- [ ] **Step 6: 커밋**

```bash
git add scripts/build_insights.py server/app/routers/insight.py
git commit -m "feat(insight): 종목별 팩터 백분위 parquet 영속화

_universe_factor_pct의 계산식을 그대로 빌더로 옮겨 factor_pct_ticker.parquet에
저장한다. 브리프 재료가 생기고, /factor-exposure가 매 콜드스타트마다 520일치
전종목 시세+펀더멘털을 로드하던 부담이 사라진다. parquet이 없으면 기존
계산 경로로 폴백한다."
```

---

## Phase 3 — LLM과 파이프라인

### Task 6: Claude 3콜 오케스트레이션

**Files:**
- Create: `server/module/brief/llm.py`
- Modify: `server/requirements.txt`
- Test: `server/tests/test_brief_llm.py`

**Interfaces:**
- Consumes: `BULL_BEAR_SCHEMA`, `JUDGE_SCHEMA`, `validate_points`, `enforce_lengths` (Task 4)
- Produces:
  - `generate_brief(pack: dict, client, market_context: str) -> dict | None`
  - 반환 키: `bull_points`, `bear_points`, `bull_could_not_argue`, `bear_could_not_argue`, `dropped_refs`, `judge`(dict), `usage`(dict: input_tokens/output_tokens/cache_read/cache_write/cost_usd)

- [ ] **Step 1: 의존성 추가**

`server/requirements.txt`의 `httpx` 줄 뒤에 추가:

```
anthropic>=0.70          # 종목 브리프 (build_briefs.py) — Lambda는 호출하지 않음
```

- [ ] **Step 2: 실패하는 테스트 작성**

`server/tests/test_brief_llm.py`:

```python
import json
from types import SimpleNamespace

from module.brief.llm import PRICE_PER_TOKEN, generate_brief


class _FakeResponse:
    def __init__(self, payload, stop_reason="end_turn"):
        self.content = [SimpleNamespace(type="text", text=json.dumps(payload))]
        self.stop_reason = stop_reason
        self.usage = SimpleNamespace(
            input_tokens=1000,
            output_tokens=200,
            cache_read_input_tokens=500,
            cache_creation_input_tokens=100,
        )


class _FakeClient:
    """호출 순서대로 준비된 응답을 돌려준다 (bull, bear, judge)."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


PACK = {"flows": {"frgn": {"streak": 12}}, "identity": {"ticker": "005930"}}

BULL = {
    "points": [
        {"claim": "수급이 붙었다", "evidence": ["flows.frgn.streak"],
         "strength": "moderate", "breaks_if": "streak 단절"}
    ],
    "what_i_could_not_argue": "밸류에이션 측면 근거 없음",
}
BEAR = {
    "points": [
        {"claim": "업황이 나쁘다", "evidence": ["industry.outlook"],
         "strength": "strong", "breaks_if": "업황 반등"}
    ],
    "what_i_could_not_argue": "",
}
JUDGE = {
    "one_liner": "수급 우위, 근거는 얇음",
    "summary": "외국인 수급이 유일한 강세 근거다.",
    "tension": "수급과 밸류에이션이 갈린다",
    "decisive_question": "수급이 유지되는데 가격이 안 따라오는 날이 나오는가",
    "watch": [{"metric": "intensity_20d", "threshold": "< 0.3", "meaning": "수급 소진"}],
    "confidence": "medium",
    "confidence_reason": "표본은 충분하나 우위 폭이 작다",
    "stance_note": "강세 쪽으로 약간 기울었다",
}


def test_세_콜을_순서대로_호출한다():
    client = _FakeClient([_FakeResponse(BULL), _FakeResponse(BEAR), _FakeResponse(JUDGE)])
    out = generate_brief(PACK, client, "시장 맥락")
    assert len(client.calls) == 3
    assert out["judge"]["one_liner"] == "수급 우위, 근거는 얇음"


def test_bear의_가짜_근거가_드롭된다():
    client = _FakeClient([_FakeResponse(BULL), _FakeResponse(BEAR), _FakeResponse(JUDGE)])
    out = generate_brief(PACK, client, "시장 맥락")
    assert len(out["bull_points"]) == 1
    assert out["bear_points"] == []
    assert out["dropped_refs"][0]["bad_refs"] == ["industry.outlook"]


def test_시스템_프롬프트에_캐시_제어가_걸린다():
    client = _FakeClient([_FakeResponse(BULL), _FakeResponse(BEAR), _FakeResponse(JUDGE)])
    generate_brief(PACK, client, "시장 맥락")
    system = client.calls[0]["system"]
    assert system[-1]["cache_control"] == {"type": "ephemeral"}


def test_bull과_bear는_서로의_출력을_받지_않는다():
    client = _FakeClient([_FakeResponse(BULL), _FakeResponse(BEAR), _FakeResponse(JUDGE)])
    generate_brief(PACK, client, "시장 맥락")
    bull_prompt = json.dumps(client.calls[0]["messages"], ensure_ascii=False)
    bear_prompt = json.dumps(client.calls[1]["messages"], ensure_ascii=False)
    assert "업황이 나쁘다" not in bull_prompt
    assert "수급이 붙었다" not in bear_prompt
    # judge는 둘 다 본다
    judge_prompt = json.dumps(client.calls[2]["messages"], ensure_ascii=False)
    assert "수급이 붙었다" in judge_prompt
    assert "업황이 나쁘다" in judge_prompt


def test_refusal이면_None을_반환하고_예외를_올리지_않는다():
    refused = _FakeResponse(BULL, stop_reason="refusal")
    refused.content = []  # refusal은 content가 비어 있을 수 있다
    client = _FakeClient([refused, _FakeResponse(BEAR), _FakeResponse(JUDGE)])
    assert generate_brief(PACK, client, "시장 맥락") is None


def test_bull만_실패해도_bear로_judge를_진행한다():
    boom = _FakeResponse(BULL)
    boom.content = [SimpleNamespace(type="text", text="not json{{{")]
    client = _FakeClient([boom, _FakeResponse(BEAR), _FakeResponse(JUDGE)])
    out = generate_brief(PACK, client, "시장 맥락")
    assert out is not None
    assert out["bull_points"] == []
    assert out["judge"]["one_liner"] == "수급 우위, 근거는 얇음"


def test_usage와_비용이_집계된다():
    client = _FakeClient([_FakeResponse(BULL), _FakeResponse(BEAR), _FakeResponse(JUDGE)])
    out = generate_brief(PACK, client, "시장 맥락")
    u = out["usage"]
    assert u["input_tokens"] == 3000       # 1000 × 3콜
    assert u["output_tokens"] == 600       # 200 × 3콜
    assert u["cache_read_input_tokens"] == 1500
    expected = (
        3000 * PRICE_PER_TOKEN["input"]
        + 600 * PRICE_PER_TOKEN["output"]
        + 1500 * PRICE_PER_TOKEN["cache_read"]
        + 300 * PRICE_PER_TOKEN["cache_write"]
    )
    assert abs(u["cost_usd"] - expected) < 1e-9
```

- [ ] **Step 3: 테스트가 실패하는지 확인**

Run: `cd server && python -m pytest tests/test_brief_llm.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'module.brief.llm'`

- [ ] **Step 4: 구현 작성**

`server/module/brief/llm.py`:

```python
"""Claude Opus 5 3콜 오케스트레이션 — bull ∥ bear → judge.

bull과 bear는 서로의 출력을 보지 못한다. 한 컨텍스트에서 양쪽을 쓰게 하면
모델이 균형을 맞춰버려 "강세 3개, 약세 3개, 결론은 중립" 같은 무해하고
쓸모없는 출력이 나온다. 대립은 구조로 만들어야 한다.
"""

import json
import logging

from module.brief.schema import (
    BULL_BEAR_SCHEMA,
    JUDGE_SCHEMA,
    enforce_lengths,
    validate_points,
)

logger = logging.getLogger(__name__)

MODEL = "claude-opus-5"
MAX_TOKENS = 8000

# Claude Opus 5: $5 in / $25 out per MTok. 캐시 쓰기 1.25×, 캐시 읽기 0.1×.
PRICE_PER_TOKEN = {
    "input": 5.0 / 1_000_000,
    "output": 25.0 / 1_000_000,
    "cache_write": 6.25 / 1_000_000,
    "cache_read": 0.5 / 1_000_000,
}

SYSTEM_RULES = """너는 한국 주식 시장의 리서치 애널리스트다.

절대 규칙:
1. 주어진 evidence pack 안의 사실만 사용한다. 종목·산업에 대해 네가 따로 알고 있는
   지식은 인용하지 않는다. 학습 시점의 정보는 낡았고 사용자가 검증할 수 없다.
2. 숫자를 다시 말하지 않는다. 사용자는 대시보드에서 숫자를 이미 봤다.
   숫자는 그것이 무엇을 함의하는지 말할 때 근거로만 인용한다.
3. base_rates가 있으면 반드시 인용한다 — 표본 수, 승률, 중앙값을 함께.
   표본이 없으면 "표본 없음"이라고 명시한다.
4. 모든 주장에 evidence 경로를 단다. evidence pack의 실제 키 경로여야 한다
   (예: "flows.frgn.streak", "base_rates.frgn_streak10.h20").
   근거를 댈 수 없는 주장은 출력하지 않는다.
5. 모든 논거에 breaks_if를 단다 — 무엇이 관찰되면 이 논거가 무효가 되는가.
   관찰 가능한 조건이어야 한다.
6. 없으면 없다고 한다. 억지 논거를 만들지 말고 what_i_could_not_argue에 적는다.
   빈칸도 정보다."""

BULL_ROLE = """이 종목을 매수하거나 계속 보유해야 할 이유만 찾아라.
균형을 잡는 것은 네 일이 아니다 — 반대편은 다른 분석가가 독립적으로 맡는다.
네 임무는 강세 논거의 최선 버전을 만드는 것이다."""

BEAR_ROLE = """이 종목을 매도하거나 회피해야 할 이유만 찾아라.
균형을 잡는 것은 네 일이 아니다 — 반대편은 다른 분석가가 독립적으로 맡는다.
네 임무는 약세 논거의 최선 버전을 만드는 것이다."""

JUDGE_ROLE = """강세·약세 분석가의 논거를 모두 받았다.

점수를 매기지 마라. 매수/매도 판정을 내리지 마라.
두 논거가 어디서 갈리는지 짚어라. 같은 사실을 양쪽이 다르게 읽고 있다면 그게 핵심이다.
그리고 무엇이 관찰되면 결판나는지를, 다음 며칠 안에 확인 가능한 형태로 적어라.

evidence 경로가 evidence pack에 실제로 없는 논거는 기각하고 근거에서 제외하라.
base_rates의 표본이 30 미만이면 그 논거의 신뢰도를 낮춰 다뤄라.

one_liner는 60자 이내, summary는 200자 이내로 쓴다."""


def _system_blocks(market_context: str) -> list:
    """규칙 + 시장 공통 맥락을 캐시 접두부로 묶는다. 종목별 내용은 여기 넣지 않는다."""
    return [
        {"type": "text", "text": SYSTEM_RULES},
        {
            "type": "text",
            "text": f"오늘의 시장 맥락:\n{market_context}",
            "cache_control": {"type": "ephemeral"},
        },
    ]


def _call(client, system, user_text, schema):
    """단일 호출. 실패·거부·파싱 불가 시 (None, usage)."""
    resp = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        thinking={"type": "adaptive"},
        output_config={
            "effort": "high",
            "format": {"type": "json_schema", "schema": schema},
        },
        system=system,
        messages=[{"role": "user", "content": user_text}],
    )
    usage = _usage_of(resp)

    if resp.stop_reason == "refusal":
        logger.warning("브리프 콜 거부됨 (stop_reason=refusal)")
        return None, usage
    if resp.stop_reason == "max_tokens":
        logger.warning("브리프 콜이 max_tokens에 도달 — 출력이 잘렸을 수 있음")

    text = next((b.text for b in resp.content if getattr(b, "type", None) == "text"), None)
    if not text:
        return None, usage
    try:
        return json.loads(text), usage
    except json.JSONDecodeError:
        logger.warning("브리프 콜 응답 JSON 파싱 실패")
        return None, usage


def _usage_of(resp) -> dict:
    u = resp.usage
    return {
        "input_tokens": getattr(u, "input_tokens", 0) or 0,
        "output_tokens": getattr(u, "output_tokens", 0) or 0,
        "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
        "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
    }


def _accumulate(total: dict, one: dict) -> dict:
    for k, v in one.items():
        total[k] = total.get(k, 0) + v
    return total


def _cost(usage: dict) -> float:
    return (
        usage["input_tokens"] * PRICE_PER_TOKEN["input"]
        + usage["output_tokens"] * PRICE_PER_TOKEN["output"]
        + usage["cache_read_input_tokens"] * PRICE_PER_TOKEN["cache_read"]
        + usage["cache_creation_input_tokens"] * PRICE_PER_TOKEN["cache_write"]
    )


def generate_brief(pack: dict, client, market_context: str) -> dict | None:
    """3콜을 돌려 브리프 한 건을 만든다. judge가 실패하면 None."""
    system = _system_blocks(market_context)
    pack_json = json.dumps(pack, ensure_ascii=False, indent=1, default=str)
    usage: dict = {}

    bull, u = _call(client, system, f"{BULL_ROLE}\n\nevidence pack:\n{pack_json}", BULL_BEAR_SCHEMA)
    _accumulate(usage, u)
    bear, u = _call(client, system, f"{BEAR_ROLE}\n\nevidence pack:\n{pack_json}", BULL_BEAR_SCHEMA)
    _accumulate(usage, u)

    if bull is None and bear is None:
        logger.warning("bull·bear 모두 실패 — 브리프 생성 포기")
        return None

    bull_kept, bull_dropped = validate_points((bull or {}).get("points", []), pack)
    bear_kept, bear_dropped = validate_points((bear or {}).get("points", []), pack)

    judge_input = (
        f"{JUDGE_ROLE}\n\n"
        f"evidence pack:\n{pack_json}\n\n"
        f"강세 논거:\n{json.dumps({'points': bull_kept}, ensure_ascii=False, indent=1)}\n"
        f"강세가 주장하지 못한 것: {(bull or {}).get('what_i_could_not_argue', '(강세 논거 확보 실패)')}\n\n"
        f"약세 논거:\n{json.dumps({'points': bear_kept}, ensure_ascii=False, indent=1)}\n"
        f"약세가 주장하지 못한 것: {(bear or {}).get('what_i_could_not_argue', '(약세 논거 확보 실패)')}"
    )
    judge, u = _call(client, system, judge_input, JUDGE_SCHEMA)
    _accumulate(usage, u)

    if judge is None:
        logger.warning("judge 실패 — 브리프 생성 포기")
        return None

    judge, truncated = enforce_lengths(judge)
    if truncated:
        logger.warning("길이 초과로 절단된 필드: %s", truncated)

    usage["cost_usd"] = _cost(usage)
    return {
        "bull_points": bull_kept,
        "bear_points": bear_kept,
        "bull_could_not_argue": (bull or {}).get("what_i_could_not_argue", ""),
        "bear_could_not_argue": (bear or {}).get("what_i_could_not_argue", ""),
        "dropped_refs": bull_dropped + bear_dropped,
        "judge": judge,
        "usage": usage,
    }
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd server && python -m pytest tests/test_brief_llm.py -v`
Expected: PASS — 7 passed

- [ ] **Step 6: 전체 테스트 통과 확인**

Run: `cd server && python -m pytest tests/ -v`
Expected: PASS — 37 passed

- [ ] **Step 7: 커밋**

```bash
git add server/module/brief/llm.py server/tests/test_brief_llm.py server/requirements.txt
git commit -m "feat(brief): Claude Opus 5 3콜 오케스트레이션

bull과 bear가 서로의 출력을 받지 않는 것을 테스트로 못박았다 — 이게
대립 구조의 전부다. judge만 둘 다 본다.

거부(stop_reason=refusal)를 content 읽기 전에 확인한다. bull만 실패하면
bear로 judge를 진행하고 '강세 논거 확보 실패'를 명시한다.
usage는 실제 응답값 기반으로 집계해 cost_usd까지 계산한다."
```

---

### Task 7: briefs 저장소 + 진입점

**Files:**
- Create: `server/datastore/briefs.py`
- Create: `scripts/build_briefs.py`

**Interfaces:**
- Consumes: 모든 `module.brief.*` (Task 1~4, 6)
- Produces:
  - `briefs.list_items() -> pd.DataFrame`
  - `briefs.latest(ticker: str) -> dict | None`
  - `briefs.upsert_many(rows: list[dict]) -> None`

- [ ] **Step 1: 저장소 작성**

`server/datastore/briefs.py`:

```python
"""종목 브리프 저장소 — {APP_DATA}/briefs.parquet.

watchlist.py·holdings.py와 같은 read-modify-write(파일 통째 교체) 패턴.
15종목 × 250거래일 = 연 3,750행이라 파티셔닝은 불필요하다.
"""

import logging

import pandas as pd

from datastore import storage

logger = logging.getLogger(__name__)

FILE = "briefs.parquet"
COLUMNS = [
    "ticker", "meta_id", "name", "as_of", "generated_at",
    "one_liner", "summary", "tension", "decisive_question", "watch",
    "confidence", "confidence_reason", "stance_note",
    "bull_points", "bear_points",
    "bull_could_not_argue", "bear_could_not_argue",
    "evidence_snapshot", "dropped_refs",
    "model", "input_tokens", "output_tokens", "cost_usd",
]


def list_items() -> pd.DataFrame:
    if not storage.exists(FILE):
        return pd.DataFrame(columns=COLUMNS)
    return storage.read_parquet(FILE)


def latest(ticker: str) -> dict | None:
    """해당 종목의 가장 최근 브리프 1건. 없으면 None."""
    df = list_items()
    rows = df[df["ticker"] == ticker]
    if rows.empty:
        return None
    return rows.sort_values("as_of").iloc[-1].to_dict()


def by_date(as_of: str) -> pd.DataFrame:
    df = list_items()
    return df[df["as_of"] == as_of] if not df.empty else df


def upsert_many(rows: list) -> None:
    """(ticker, as_of) 기준 교체 후 통째로 쓴다."""
    if not rows:
        return
    new = pd.DataFrame(rows).reindex(columns=COLUMNS)
    old = list_items()
    if not old.empty:
        keys = set(zip(new["ticker"], new["as_of"]))
        mask = [(t, a) not in keys for t, a in zip(old["ticker"], old["as_of"])]
        old = old[mask]
        out = pd.concat([old, new], ignore_index=True)
    else:
        out = new
    storage.write_parquet(out, FILE)
    logger.info("briefs %d건 저장 (총 %d행)", len(new), len(out))
```

- [ ] **Step 2: 진입점 작성**

`scripts/build_briefs.py`:

```python
#!/usr/bin/env python
"""종목 브리프 생성 — Bull/Bear 대립 리서치 (설계: docs/superpowers/specs/2026-07-27-stock-brief-design.md).

로컬 파이프라인(EC2 qdata-collector)에서 build_insights 다음, send_briefing 앞에 실행한다.
- 인사이트 parquet: APP_DATA (기본 s3://insight-invest-datalake/app)
- Claude 키: 환경변수 ANTHROPIC_API_KEY 또는 BRIEFING_ENV_FILE 의 .env

ANTHROPIC_API_KEY가 없으면 조용히 스킵(exit 0) — 파이프라인은 warn-only로 감싼다.

사용:
    APP_DATA=... QDATA_LAKE=... BRIEFING_ENV_FILE=... python scripts/build_briefs.py
"""

import json
import logging
import os
import sys
import traceback
from datetime import datetime, timezone

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server"))

from datastore import briefs as briefs_store  # noqa: E402
from datastore import holdings as holdings_store  # noqa: E402
from datastore import meta as meta_store  # noqa: E402
from datastore import storage  # noqa: E402
from datastore import watchlist as watchlist_store  # noqa: E402
from module.brief.evidence import build_evidence_pack  # noqa: E402
from module.brief.llm import MODEL, generate_brief  # noqa: E402
from module.brief.select import select_targets  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("build_briefs")

MAX_COST_USD = 5.0  # 하루 누적 상한 — 초과 시 중단 (폭주 방지)

# 뉴스 헤드라인은 Task 14에서 연결한다 (NewsService.fetch_news가 async라 배관이 별건).
# 그때까지 evidence pack의 news는 빈 목록이고, 프롬프트는 정량 근거만 쓴다.


def _load_key() -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    env_file = os.environ.get("BRIEFING_ENV_FILE")
    if env_file and os.path.exists(env_file):
        for line in open(env_file, encoding="utf-8"):
            k, _, v = line.partition("=")
            if k.strip() == "ANTHROPIC_API_KEY":
                return v.strip()
    return None


def _read(name: str, default=None):
    """insight parquet 안전 읽기 — 없거나 실패하면 default."""
    try:
        if not storage.exists(f"insight/{name}"):
            return default
        return storage.read_parquet(f"insight/{name}")
    except Exception:
        logger.warning("insight/%s 읽기 실패", name)
        return default


def _market_context(breadth, valuation, regime) -> str:
    """캐시 접두부에 들어갈 종목 무관 시장 맥락 (한 번만 만든다)."""
    return json.dumps(
        {"breadth": breadth, "valuation": valuation, "regime": regime},
        ensure_ascii=False,
        default=str,
    )


def _latest_row(df, **filters) -> dict | None:
    if df is None or df.empty:
        return None
    sub = df
    for k, v in filters.items():
        sub = sub[sub[k] == v]
    return sub.iloc[-1].to_dict() if not sub.empty else None


def main() -> int:
    key = _load_key()
    if not key:
        print("[skip] build_briefs (ANTHROPIC_API_KEY 없음)")
        return 0

    import anthropic

    client = anthropic.Anthropic(api_key=key)

    flows_signals = _read("flows_signals.parquet")
    if flows_signals is None or flows_signals.empty:
        logger.error("flows_signals 없음 — 브리프 생성 불가")
        return 1
    as_of = str(flows_signals["as_of"].iloc[0])

    signal_study = _read("signal_study.parquet", pd.DataFrame(columns=["signal_type", "horizon"]))
    factor_pct = _read(
        "factor_pct_ticker.parquet",
        pd.DataFrame(columns=["ticker", "momentum", "value", "size", "lowvol"]),
    )
    sector_perf = _read("sector_perf.parquet", pd.DataFrame(columns=["market", "sector"]))
    breadth = _latest_row(_read("breadth_daily.parquet"))
    valuation = _latest_row(_read("valuation_daily.parquet"))

    # ---- 대상 선정
    meta_df = meta_store.meta_df()
    id_to_ticker = meta_df.set_index("meta_id")["ticker"].to_dict()
    watch = {id_to_ticker.get(i) for i in watchlist_store.list_items()["meta_id"]} - {None}
    hold_ids = holdings_store.list_items()["meta_id"].tolist()
    hold = {id_to_ticker.get(i) for i in hold_ids} - {None}
    mktcap = flows_signals.drop_duplicates("ticker").set_index("ticker")["mktcap"].to_dict()

    # attention(severity=high) — get_attention()은 동기 함수이고 items가 이미
    # 우선순위순으로 정렬돼 있다. 그 순서를 그대로 우선순위로 쓴다.
    try:
        from app.routers.attention import get_attention

        att_items = get_attention()["items"]
        attention_high = [
            i["ticker"]
            for i in att_items
            if i.get("severity") == "high" and i.get("ticker")
        ]
    except Exception:
        logger.warning("attention 조회 실패 — 워치리스트·보유만 사용", exc_info=True)
        attention_high = []

    picked, dropped = select_targets(watch, hold, attention_high, mktcap)
    if dropped:
        logger.warning("상한 초과로 제외된 종목 %d개: %s", len(dropped), dropped)
    if not picked:
        logger.info("대상 종목 없음 — 종료")
        return 0
    logger.info("대상 %d종목: %s", len(picked), picked)

    # ---- 공통 재료
    meta_by_ticker = meta_df.set_index("ticker")[["name", "sector"]].to_dict("index")
    market_by_ticker = flows_signals.drop_duplicates("ticker").set_index("ticker")["market"].to_dict()
    holdings_map = {}
    for r in holdings_store.list_items().itertuples():
        t = id_to_ticker.get(r.meta_id)
        if t:
            holdings_map[t] = {"shares": float(r.shares), "avg_cost": float(r.avg_cost)}
    ticker_to_id = {v: k for k, v in id_to_ticker.items()}

    try:
        from module import regime as regime_mod

        regime = {"phase": regime_mod.current_phase(), "risk_gauge": regime_mod.risk_gauge()}
    except Exception:
        logger.warning("레짐 조회 실패 — 시장 맥락에서 생략", exc_info=True)
        regime = None

    ctx = _market_context(breadth, valuation, regime)

    # ---- 종목별 생성
    rows, total_cost = [], 0.0
    for ticker in picked:
        if total_cost >= MAX_COST_USD:
            logger.error("비용 상한 $%.2f 도달 — 남은 종목 중단", MAX_COST_USD)
            break
        try:
            m = meta_by_ticker.get(ticker, {})
            pack = build_evidence_pack(
                ticker,
                {
                    "meta": {
                        "name": m.get("name", ticker),
                        "sector": m.get("sector"),
                        "market": market_by_ticker.get(ticker),
                    },
                    "flows_signals": flows_signals,
                    "signal_study": signal_study,
                    "factor_pct": factor_pct,
                    "sector_perf": sector_perf,
                    "breadth": breadth,
                    "valuation": valuation,
                    "regime": regime,
                    "holdings": holdings_map,
                    "news": [],  # Task 14에서 연결
                    "prior_brief": briefs_store.latest(ticker),
                },
            )
            out = generate_brief(pack, client, ctx)
            if out is None:
                logger.warning("%s 브리프 생성 실패 — 건너뜀", ticker)
                continue
            j = out["judge"]
            total_cost += out["usage"]["cost_usd"]
            rows.append(
                {
                    "ticker": ticker,
                    "meta_id": ticker_to_id.get(ticker),
                    "name": pack["identity"]["name"],
                    "as_of": as_of,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "one_liner": j["one_liner"],
                    "summary": j["summary"],
                    "tension": j["tension"],
                    "decisive_question": j["decisive_question"],
                    "watch": json.dumps(j["watch"], ensure_ascii=False),
                    "confidence": j["confidence"],
                    "confidence_reason": j["confidence_reason"],
                    "stance_note": j["stance_note"],
                    "bull_points": json.dumps(out["bull_points"], ensure_ascii=False),
                    "bear_points": json.dumps(out["bear_points"], ensure_ascii=False),
                    "bull_could_not_argue": out["bull_could_not_argue"],
                    "bear_could_not_argue": out["bear_could_not_argue"],
                    "evidence_snapshot": json.dumps(pack, ensure_ascii=False, default=str),
                    "dropped_refs": json.dumps(out["dropped_refs"], ensure_ascii=False),
                    "model": MODEL,
                    "input_tokens": out["usage"]["input_tokens"],
                    "output_tokens": out["usage"]["output_tokens"],
                    "cost_usd": round(out["usage"]["cost_usd"], 5),
                }
            )
            logger.info("%s ✓ (%s) $%.4f", ticker, j["one_liner"], out["usage"]["cost_usd"])
        except Exception:
            logger.warning("%s 처리 중 예외 — 건너뜀", ticker)
            traceback.print_exc()

    briefs_store.upsert_many(rows)
    n_dropped = sum(len(json.loads(r["dropped_refs"])) for r in rows)
    print(f"브리프 {len(rows)}건 생성, 총 ${total_cost:.4f}, 근거 드롭 {n_dropped}건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: 진입점이 키 없이도 안전하게 종료하는지 확인**

Run:
```bash
cd /Users/achii/Quant/Insight-Invest
env -u ANTHROPIC_API_KEY BRIEFING_ENV_FILE=/nonexistent python scripts/build_briefs.py; echo "exit=$?"
```
Expected: `[skip] build_briefs (ANTHROPIC_API_KEY 없음)` 후 `exit=0`

- [ ] **Step 4: 문법·import 검증**

Run:
```bash
cd server && python -c "
import sys; sys.path.insert(0, '.')
from datastore import briefs
assert briefs.FILE == 'briefs.parquet'
assert 'evidence_snapshot' in briefs.COLUMNS
assert 'cost_usd' in briefs.COLUMNS
print('OK')
"
```
Expected: `OK`

- [ ] **Step 5: 커밋**

```bash
git add server/datastore/briefs.py scripts/build_briefs.py
git commit -m "feat(brief): briefs 저장소 + build_briefs 진입점

evidence_snapshot을 통째로 박제한다 — 판단 근거 재현, 프론트의 근거 재조회
회피, 그리고 나중에 Decision Journal을 붙일 때의 뼈대.

ANTHROPIC_API_KEY가 없으면 exit 0으로 조용히 스킵한다. 종목 단위 예외 격리와
하루 비용 상한 \$5로 폭주를 막는다."
```

---

### Task 8: 파이프라인 연결 (quant-data 레포 + SSM)

**Files:**
- Modify: `~/Quant/quant-data/scripts/server/run_pipeline.sh` (별도 레포)
- 인프라: SSM Parameter `/qdata/ANTHROPIC_API_KEY`

**Interfaces:**
- Consumes: `scripts/build_briefs.py` (Task 7)

- [ ] **Step 1: Insight-Invest 변경을 main에 먼저 반영**

`run_pipeline.sh`는 매 실행마다 Insight-Invest를 `git pull`한다. 스크립트가 없는 파일을 부르면 `|| echo "[warn]"`로 넘어가지만, 순서를 지키는 편이 로그가 깨끗하다.

```bash
cd /Users/achii/Quant/Insight-Invest
git push -u origin feat/stock-brief
# PR 생성 후 main 머지 (또는 로컬에서 main에 머지 후 push)
```

- [ ] **Step 2: SSM에 API 키 저장**

```bash
aws ssm put-parameter \
  --name /qdata/ANTHROPIC_API_KEY \
  --type SecureString \
  --value "sk-ant-…" \
  --region ap-northeast-2
```

확인:
```bash
aws ssm get-parameter --name /qdata/ANTHROPIC_API_KEY --with-decryption \
  --region ap-northeast-2 --query 'Parameter.Value' --output text | head -c 12
```
Expected: `sk-ant-api03` 등 키 접두부

- [ ] **Step 3: `run_pipeline.sh` 시크릿 루프에 키 추가**

`~/Quant/quant-data/scripts/server/run_pipeline.sh`:

```diff
-  for KEY in FRED_API_KEY KRX_ID KRX_PW ECOS_API_KEY TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID; do
+  for KEY in FRED_API_KEY KRX_ID KRX_PW ECOS_API_KEY TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID ANTHROPIC_API_KEY; do
```

- [ ] **Step 4: `run_pipeline.sh` 6단계에 호출 추가**

```diff
   IIPY=$BASE/ii-venv/bin/python
   QDATA_LAKE=/data/lake $IIPY $BASE/Insight-Invest/scripts/build_insights.py || echo "[warn] build_insights 실패"
+  QDATA_LAKE=/data/lake BRIEFING_ENV_FILE=$ENVF $IIPY $BASE/Insight-Invest/scripts/build_briefs.py || echo "[warn] build_briefs 실패"
   QDATA_LAKE=/data/lake BRIEFING_ENV_FILE=$ENVF $IIPY $BASE/Insight-Invest/scripts/send_briefing.py || echo "[warn] briefing 실패"
```

- [ ] **Step 5: `ii-venv`에 anthropic 설치가 필요한지 확인**

`setup.sh`는 1회만 실행되므로 이미 만들어진 `ii-venv`에는 `anthropic`이 없다. `run_pipeline.sh`의 레포 갱신 단계(2번) 뒤에 의존성 동기화를 추가한다:

```diff
   cd $BASE/quant-data && uv sync --extra s3 --quiet || echo "[warn] uv sync 실패"
+  # Insight-Invest 의존성 갱신 (requirements.txt 변경 반영 — anthropic 등)
+  uv pip install --quiet --python $BASE/ii-venv/bin/python \
+    -r $BASE/Insight-Invest/server/requirements.txt || echo "[warn] ii-venv 동기화 실패"
```

- [ ] **Step 6: quant-data 커밋**

```bash
cd ~/Quant/quant-data
git add scripts/server/run_pipeline.sh
git commit -m "feat(pipeline): 종목 브리프 생성 단계 추가

build_insights와 send_briefing 사이에 Insight-Invest/scripts/build_briefs.py를
끼운다. ANTHROPIC_API_KEY를 SSM 시크릿 루프에 추가하고, ii-venv가 이미
생성된 인스턴스에서도 requirements.txt 변경이 반영되도록 매 실행 동기화한다.

설계: Insight-Invest docs/superpowers/specs/2026-07-27-stock-brief-design.md"
git push
```

- [ ] **Step 7: EC2에서 수동 실행 검증**

```bash
aws ec2 start-instances --instance-ids i-09340ef564f41eb42 --region ap-northeast-2
# 부팅 후 systemd가 파이프라인을 자동 실행한다. 완료 후 자체 종료되므로 로그로 확인:
sleep 2700
aws s3 ls s3://insight-invest-datalake/qdata-raw/logs/ --region ap-northeast-2 | tail -3
aws s3 cp s3://insight-invest-datalake/qdata-raw/logs/<최신로그> - | grep -A5 -E 'build_briefs|브리프'
```
Expected: `대상 N종목: [...]` 및 `브리프 N건 생성, 총 $0.xxxx, 근거 드롭 N건`

`briefs.parquet` 생성 확인:
```bash
aws s3 ls s3://insight-invest-datalake/app/briefs.parquet --region ap-northeast-2
```
Expected: 파일 존재

---

## Phase 4 — 노출

### Task 9: 텔레그램 브리프 섹션

프론트 작업 없이 다음 날 아침부터 실물을 읽을 수 있게 하는 단계다. 여기서 며칠 프롬프트를 튜닝한 뒤 Task 11~13으로 넘어간다.

**Files:**
- Modify: `scripts/send_briefing.py`

**Interfaces:**
- Consumes: `datastore.briefs.by_date` (Task 7)

- [ ] **Step 1: 섹션 빌더 추가**

`scripts/send_briefing.py`의 `_section_strategies()` 정의 뒤, `_section_summary()` 앞에 삽입:

```python
BRIEF_CAP = 3


def _section_briefs() -> str | None:
    """종목 브리프 — 오늘자 상위 N건의 한 줄 요약."""
    from datastore import briefs as briefs_store

    df = briefs_store.list_items()
    if df.empty:
        return None
    as_of = df["as_of"].max()
    today = df[df["as_of"] == as_of]
    if today.empty:
        return None

    # 신뢰도 높은 것부터, 동률이면 종목명 순
    rank = {"high": 0, "medium": 1, "low": 2}
    today = today.assign(_r=today["confidence"].map(rank).fillna(9)).sort_values(["_r", "name"])

    lines = [f"<b>🧭 오늘 주목 종목</b> <i>({_esc(as_of)})</i>"]
    for r in today.head(BRIEF_CAP).itertuples():
        lines.append(f"• <b>{_esc(r.name)}</b> — {_esc(r.one_liner)}")
        lines.append(f"  {_esc(r.summary)}")
    rest = len(today) - BRIEF_CAP
    if rest > 0:
        lines.append(f"<i>외 {rest}종목</i>")
    _ctx["brief_count"] = len(today)
    return "\n".join(lines)
```

- [ ] **Step 2: `compose_message()` 섹션 목록에 등록**

`scripts/send_briefing.py`의 `compose_message()` 안 `("strategies", _section_strategies),` 줄 뒤에 삽입:

```python
        ("briefs", _section_briefs),
```

`("summary", _section_summary)` 앞에 와야 한다 — summary가 `_ctx`를 읽기 때문이다.

- [ ] **Step 3: 브리프 없이도 정상 동작하는지 확인**

Run:
```bash
cd /Users/achii/Quant/Insight-Invest
env -u TELEGRAM_BOT_TOKEN python scripts/send_briefing.py; echo "exit=$?"
```
Expected: `[skip] briefing (토큰 없음)` 후 `exit=0` — 섹션 추가가 기존 흐름을 깨지 않음

- [ ] **Step 4: 섹션 함수가 결손에 안전한지 확인**

Run:
```bash
cd server && python -c "
import sys, os
sys.path.insert(0, '.')
os.environ['APP_DATA'] = '/tmp/empty-app-data'
sys.path.insert(0, '../scripts')
from datastore import briefs
assert briefs.list_items().empty
print('OK — 파일 없어도 빈 프레임')
"
```
Expected: `OK — 파일 없어도 빈 프레임`

- [ ] **Step 5: 커밋**

```bash
git add scripts/send_briefing.py
git commit -m "feat(briefing): 텔레그램에 종목 브리프 섹션 추가

오늘자 브리프를 신뢰도순 상위 3건까지 한 줄 요약으로 싣는다.
브리프가 없으면 섹션을 생략하고 기존 8개 섹션으로 정상 발송한다."
```

---

### Task 10: 브리프 API 라우터

**Files:**
- Create: `server/app/routers/brief.py`
- Modify: `server/app/main.py`
- Modify: `server/app/routers/attention.py`

**Interfaces:**
- Consumes: `datastore.briefs` (Task 7)
- Produces:
  - `GET /brief/{ticker}` → 브리프 전체 (JSON 필드는 파싱 후 반환)
  - `GET /brief/today?limit=3` → 오늘자 목록 (요약 필드만)
  - `attention` 응답 항목에 `one_liner` 추가

- [ ] **Step 1: 라우터 작성**

`server/app/routers/brief.py`:

```python
"""종목 브리프 API — briefs.parquet 읽기 전용.

LLM 호출은 전부 로컬 파이프라인(build_briefs.py)에서 끝난다. Lambda는 읽기만 한다.
"""

import json
import logging
import os
import sys

from fastapi import APIRouter, HTTPException

sys.path.insert(0, os.path.abspath(os.path.join(os.path.abspath(__file__), "../../../")))

from datastore import briefs as briefs_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/brief", tags=["Brief"])

_JSON_FIELDS = ("watch", "bull_points", "bear_points", "evidence_snapshot", "dropped_refs")
_SUMMARY_FIELDS = (
    "ticker", "meta_id", "name", "as_of", "one_liner", "summary", "confidence", "stance_note",
)


def _parse(row: dict) -> dict:
    out = dict(row)
    for f in _JSON_FIELDS:
        raw = out.get(f)
        try:
            out[f] = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            out[f] = None
    return out


@router.get("/today")
async def get_today(limit: int = 3):
    """가장 최근 as_of의 브리프 요약 목록 — 신뢰도 높은 순."""
    df = briefs_store.list_items()
    if df.empty:
        return {"as_of": None, "items": []}
    as_of = df["as_of"].max()
    today = df[df["as_of"] == as_of]
    rank = {"high": 0, "medium": 1, "low": 2}
    today = today.assign(_r=today["confidence"].map(rank).fillna(9)).sort_values(["_r", "name"])
    items = today.head(max(limit, 0))[list(_SUMMARY_FIELDS)].to_dict(orient="records")
    return {"as_of": as_of, "items": items}


@router.get("/{ticker}")
async def get_brief(ticker: str):
    """해당 종목의 가장 최근 브리프 전체."""
    row = briefs_store.latest(ticker)
    if row is None:
        raise HTTPException(status_code=404, detail=f"{ticker} 브리프 없음")
    return _parse(row)
```

- [ ] **Step 2: 라우터 등록**

`server/app/main.py`:

```diff
 from .routers import (
     attention,
     backtest,
+    brief,
     holdings,
     insight,
```

```diff
 app.include_router(attention.router)
+app.include_router(brief.router)
 app.include_router(price.stock_router)
```

- [ ] **Step 3: attention 응답에 one_liner 조인**

`server/app/routers/attention.py`의 import 블록에 추가:

```python
from datastore import briefs as briefs_store
```

그리고 `get_attention()` 끝의 `items.sort(key=_sort_key)` **바로 앞**에 다음을 삽입한다. 항목 리스트 변수명은 `items`이고, signal·price·holding 카테고리 항목만 `ticker` 키를 갖는다 (macro·strategy 항목은 `.get()`이 None을 돌려주므로 안전하다):

```python
    # 브리프 한 줄 요약 조인 — 없으면 조용히 생략 (attention은 절대 500 없음)
    try:
        bdf = briefs_store.list_items()
        if not bdf.empty:
            latest_as_of = bdf["as_of"].max()
            one_liners = (
                bdf[bdf["as_of"] == latest_as_of].set_index("ticker")["one_liner"].to_dict()
            )
            for it in items:
                if it.get("ticker") in one_liners:
                    it["one_liner"] = one_liners[it["ticker"]]
    except Exception:
        logger.warning("브리프 one_liner 조인 실패 — 생략", exc_info=True)
```

- [ ] **Step 4: 로컬에서 라우트 등록 확인**

Run:
```bash
cd server && python -c "
import sys; sys.path.insert(0, '.')
from app.main import app
paths = sorted(r.path for r in app.routes)
assert '/brief/{ticker}' in paths, paths
assert '/brief/today' in paths, paths
print('OK —', [p for p in paths if p.startswith('/brief')])
"
```
Expected: `OK — ['/brief/today', '/brief/{ticker}']`

- [ ] **Step 5: 브리프 없을 때 404/빈 목록 확인**

Run:
```bash
cd server && APP_DATA=/tmp/empty-app-data python -c "
import sys; sys.path.insert(0, '.')
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)
assert c.get('/brief/today').json() == {'as_of': None, 'items': []}
assert c.get('/brief/000000').status_code == 404
print('OK')
"
```
Expected: `OK`
(`fastapi.testclient`가 없으면 `pip install httpx` 후 재시도 — 이미 requirements에 있다.)

- [ ] **Step 6: 커밋**

```bash
git add server/app/routers/brief.py server/app/main.py server/app/routers/attention.py
git commit -m "feat(api): 브리프 조회 엔드포인트 + attention one_liner 조인

GET /brief/{ticker}, GET /brief/today. Lambda는 parquet 읽기만 하고
LLM을 호출하지 않는다 — 콜드스타트·타임아웃·비용 변동과 무관하다.
attention 조인은 실패해도 생략되며 500을 내지 않는다."
```

---

### ⏸ 체크포인트: 프롬프트 안정화

Task 11~13(프론트)에 착수하기 전에 **최소 3거래일간 텔레그램 브리프를 읽고 프롬프트를 튜닝한다.**

확인할 것:
- 숫자 재서술이 아니라 함의가 나오는가
- `base_rates`가 실제로 인용되는가
- `breaks_if`가 관찰 가능한 조건으로 쓰이는가
- `dropped_refs` 건수 (0에 가까워야 정상. 계속 나오면 프롬프트가 무너지고 있다)
- `cost_usd` 합계가 예상 범위(일 $0.8~1.0)인가

프롬프트 수정은 `server/module/brief/llm.py`의 `SYSTEM_RULES`·`*_ROLE` 상수만 고치면 되고, `run_pipeline.sh`가 매 실행 `git pull`하므로 main 푸시로 즉시 반영된다.

---

### Task 11: 종목 상세 BriefCard

**Files:**
- Create: `client/src/app/stock/[metaId]/BriefCard.tsx`
- Modify: `client/src/state/api.ts`
- Modify: `client/src/app/stock/[metaId]/page.tsx`

**Interfaces:**
- Consumes: `GET /brief/{ticker}` (Task 10)

- [ ] **Step 1: API 훅 추가**

`client/src/state/api.ts`의 `endpoints` 객체에 추가 (기존 엔드포인트 정의 스타일을 그대로 따른다):

```ts
    getBrief: build.query<Brief, string>({
      query: (ticker) => `/brief/${ticker}`,
    }),
    getBriefsToday: build.query<BriefTodayResponse, number | void>({
      query: (limit = 3) => `/brief/today?limit=${limit}`,
    }),
```

같은 파일 상단 타입 정의부에 추가:

```ts
export interface BriefPoint {
  claim: string;
  evidence: string[];
  strength: "strong" | "moderate" | "weak";
  breaks_if: string;
}

export interface BriefWatch {
  metric: string;
  threshold: string;
  meaning: string;
}

export interface Brief {
  ticker: string;
  meta_id: number | null;
  name: string;
  as_of: string;
  one_liner: string;
  summary: string;
  tension: string;
  decisive_question: string;
  watch: BriefWatch[];
  confidence: "high" | "medium" | "low";
  confidence_reason: string;
  stance_note: string;
  bull_points: BriefPoint[];
  bear_points: BriefPoint[];
  bull_could_not_argue: string;
  bear_could_not_argue: string;
}

export interface BriefTodayResponse {
  as_of: string | null;
  items: Pick<
    Brief,
    | "ticker"
    | "meta_id"
    | "name"
    | "as_of"
    | "one_liner"
    | "summary"
    | "confidence"
    | "stance_note"
  >[];
}
```

export 목록(`export const { ... } = api;`)에 `useGetBriefQuery`, `useGetBriefsTodayQuery`를 추가한다.

- [ ] **Step 2: 컴포넌트 작성**

`client/src/app/stock/[metaId]/BriefCard.tsx`:

```tsx
"use client";

import { useGetBriefQuery, type BriefPoint } from "@/state/api";

const CONFIDENCE_LABEL: Record<string, string> = {
  high: "신뢰도 높음",
  medium: "신뢰도 보통",
  low: "신뢰도 낮음",
};

function PointList({ points, tone }: { points: BriefPoint[]; tone: "bull" | "bear" }) {
  const color = tone === "bull" ? "text-emerald-600" : "text-rose-600";
  if (points.length === 0) {
    return <p className="text-sm text-gray-400">근거 있는 논거 없음</p>;
  }
  return (
    <ul className="space-y-3">
      {points.map((p, i) => (
        <li key={i} className="text-sm">
          <span className={`font-medium ${color}`}>▸</span> {p.claim}
          <div className="mt-1 text-xs text-gray-500">
            깨지는 조건: {p.breaks_if}
          </div>
          <div className="mt-0.5 flex flex-wrap gap-1">
            {p.evidence.map((e) => (
              <code key={e} className="rounded bg-gray-100 px-1 py-0.5 text-[11px] text-gray-600">
                {e}
              </code>
            ))}
          </div>
        </li>
      ))}
    </ul>
  );
}

export default function BriefCard({ ticker }: { ticker: string }) {
  const { data, isLoading, isError } = useGetBriefQuery(ticker, { skip: !ticker });

  if (isLoading) return null;
  if (isError || !data) return null;

  return (
    <section className="rounded-lg border border-gray-200 bg-white p-5">
      <header className="mb-4 flex items-baseline justify-between gap-2">
        <h2 className="text-base font-semibold">{data.one_liner}</h2>
        <span className="shrink-0 text-xs text-gray-400">
          {CONFIDENCE_LABEL[data.confidence] ?? data.confidence} · {data.as_of}
        </span>
      </header>

      <p className="mb-5 text-sm text-gray-700">{data.summary}</p>

      <div className="grid gap-6 md:grid-cols-2">
        <div>
          <h3 className="mb-2 text-sm font-semibold text-emerald-700">강세 논거</h3>
          <PointList points={data.bull_points} tone="bull" />
          {data.bull_could_not_argue && (
            <p className="mt-2 text-xs text-gray-400">
              주장하지 못한 것: {data.bull_could_not_argue}
            </p>
          )}
        </div>
        <div>
          <h3 className="mb-2 text-sm font-semibold text-rose-700">약세 논거</h3>
          <PointList points={data.bear_points} tone="bear" />
          {data.bear_could_not_argue && (
            <p className="mt-2 text-xs text-gray-400">
              주장하지 못한 것: {data.bear_could_not_argue}
            </p>
          )}
        </div>
      </div>

      <dl className="mt-5 space-y-2 border-t border-gray-100 pt-4 text-sm">
        <div>
          <dt className="text-xs font-medium text-gray-500">긴장</dt>
          <dd>{data.tension}</dd>
        </div>
        <div>
          <dt className="text-xs font-medium text-gray-500">결판 지점</dt>
          <dd>{data.decisive_question}</dd>
        </div>
        {data.watch.length > 0 && (
          <div>
            <dt className="text-xs font-medium text-gray-500">확인할 것</dt>
            <dd>
              <ul className="mt-1 space-y-1">
                {data.watch.map((w, i) => (
                  <li key={i} className="text-xs text-gray-600">
                    <code className="rounded bg-gray-100 px-1">{w.metric}</code> {w.threshold} —{" "}
                    {w.meaning}
                  </li>
                ))}
              </ul>
            </dd>
          </div>
        )}
      </dl>

      <p className="mt-4 text-[11px] text-gray-400">
        논거 정리이며 매매 신호가 아닙니다. {data.confidence_reason}
      </p>
    </section>
  );
}
```

- [ ] **Step 3: 종목 상세 페이지에 배치**

`client/src/app/stock/[metaId]/page.tsx`에서 종목 티커를 이미 알고 있는 위치(차트 섹션 위)에 삽입한다:

```tsx
import BriefCard from "./BriefCard";
```

```tsx
{ticker && <BriefCard ticker={ticker} />}
```

- [ ] **Step 4: 타입·빌드 검증**

Run: `cd client && npx tsc --noEmit`
Expected: 에러 없음

Run: `cd client && npm run build`
Expected: 빌드 성공

- [ ] **Step 5: 커밋**

```bash
git add client/src/app/stock/ client/src/state/api.ts
git commit -m "feat(client): 종목 상세에 Bull/Bear 브리프 카드

강세·약세 논거를 좌우로 나란히 놓고 각 논거에 깨지는 조건과 근거 경로를 단다.
브리프가 없으면 카드를 렌더하지 않는다.
매매 신호가 아니라는 문구를 하단에 고정한다."
```

---

### Task 12: insight 페이지 BriefStrip

**Files:**
- Create: `client/src/app/insight/BriefStrip.tsx`
- Modify: `client/src/app/insight/page.tsx`

**Interfaces:**
- Consumes: `GET /brief/today` + `useGetBriefsTodayQuery` (Task 10, 11)

- [ ] **Step 1: 컴포넌트 작성**

`client/src/app/insight/BriefStrip.tsx`:

```tsx
"use client";

import Link from "next/link";
import { useGetBriefsTodayQuery } from "@/state/api";

export default function BriefStrip() {
  const { data, isLoading } = useGetBriefsTodayQuery(3);

  if (isLoading || !data || data.items.length === 0) return null;

  return (
    <section className="mb-6">
      <header className="mb-2 flex items-baseline justify-between">
        <h2 className="text-sm font-semibold text-gray-700">오늘 주목 종목</h2>
        <span className="text-xs text-gray-400">{data.as_of}</span>
      </header>
      <div className="grid gap-3 md:grid-cols-3">
        {data.items.map((b) => (
          <Link
            key={b.ticker}
            // 종목 상세 라우트는 client/src/app/stock/[metaId] — ticker가 아니라 meta_id다.
            href={`/stock/${b.meta_id}`}
            className="rounded-lg border border-gray-200 bg-white p-4 transition hover:border-gray-300"
          >
            <div className="mb-1 text-xs text-gray-400">{b.name}</div>
            <div className="mb-2 text-sm font-medium">{b.one_liner}</div>
            <p className="line-clamp-3 text-xs text-gray-600">{b.summary}</p>
          </Link>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 2: insight 페이지 최상단에 배치**

`client/src/app/insight/page.tsx`:

```tsx
import BriefStrip from "./BriefStrip";
```

기존 첫 섹션(`IndexBreadthStrip` 등) 바로 앞에 `<BriefStrip />`을 넣는다.

- [ ] **Step 3: meta_id가 응답에 실려 오는지 확인**

종목 상세 라우트는 `/stock/[metaId]`이므로 링크는 `meta_id`로 건다. `meta_id`는 Task 7(`build_briefs.py` 행 구성 + `briefs.COLUMNS`)과 Task 10(`_SUMMARY_FIELDS`)에서 이미 실려 있어야 한다.

Run:
```bash
cd server && python -c "
import sys; sys.path.insert(0, '.')
from datastore import briefs
from app.routers.brief import _SUMMARY_FIELDS
assert 'meta_id' in briefs.COLUMNS, briefs.COLUMNS
assert 'meta_id' in _SUMMARY_FIELDS, _SUMMARY_FIELDS
print('OK — meta_id 경로 확보')
"
```
Expected: `OK — meta_id 경로 확보`

- [ ] **Step 4: 빌드 검증**

Run: `cd client && npx tsc --noEmit && npm run build`
Expected: 성공

- [ ] **Step 5: 커밋**

```bash
git add client/src/app/insight/
git commit -m "feat(client): insight 상단에 오늘 주목 종목 스트립

브리프 상위 3건을 한 줄 요약 카드로 노출하고 종목 상세로 링크한다.
브리프가 없으면 렌더하지 않는다."
```

---

### Task 13: 홈 AttentionLane 연계

**Files:**
- Modify: `client/src/app/home/AttentionLane.tsx`
- Modify: `client/src/state/api.ts` (attention 응답 타입)

**Interfaces:**
- Consumes: attention 응답의 `one_liner` (Task 10)

- [ ] **Step 1: attention 항목 타입에 필드 추가**

`client/src/state/api.ts`의 attention 항목 인터페이스에 추가:

```ts
  one_liner?: string;
```

- [ ] **Step 2: 렌더에 반영**

`client/src/app/home/AttentionLane.tsx`에서 각 항목의 기존 설명 텍스트 아래에 삽입:

```tsx
{item.one_liner && (
  <div className="mt-1 text-xs text-gray-500">{item.one_liner}</div>
)}
```

- [ ] **Step 3: 빌드 검증**

Run: `cd client && npx tsc --noEmit && npm run build`
Expected: 성공

- [ ] **Step 4: 커밋**

```bash
git add client/src/app/home/AttentionLane.tsx client/src/state/api.ts
git commit -m "feat(client): 홈 attention에 브리프 한 줄 요약 표시

severity 라벨만 있던 자리에 '왜 주목해야 하는가'가 문장으로 붙는다.
브리프가 없는 항목은 기존과 동일하게 표시된다."
```

---

### Task 14: 뉴스 헤드라인 연결

스펙 §5.3의 `news` 필드를 채운다. `NewsService.fetch_news`가 async라 배관이 별건이고, 종목당 RSS 호출이라 실패 모드가 늘어난다 — 그래서 정량 근거로 프롬프트를 먼저 안정화한 뒤 마지막에 붙인다.

**Files:**
- Modify: `scripts/build_briefs.py`

**Interfaces:**
- Consumes: `module.news.service.NewsService.fetch_news(search_query=..., limit=...)` — async, `List[NewsArticle]` 반환. 각 항목은 `.title`, `.source`, `.published_at`(datetime|None), `.url`.
- Produces: evidence pack의 `news` = `[{"title": str, "source": str, "date": str}]`

- [ ] **Step 1: 뉴스 수집 헬퍼 추가**

`scripts/build_briefs.py`의 `_market_context()` 정의 뒤에 삽입:

```python
NEWS_DAYS = 5
NEWS_PER_TICKER = 5


async def _fetch_all_news(names: dict) -> dict:
    """{ticker: 종목명} → {ticker: [{title, source, date}]}.

    종목별 RSS를 동시에 던지고, 개별 실패는 빈 목록으로 흡수한다.
    최근 NEWS_DAYS일 이내 기사만 남긴다 (본문은 싣지 않는다 — 스펙 §5.3).
    """
    from module.news.service import NewsService

    svc = NewsService()
    cutoff = datetime.now(timezone.utc) - timedelta(days=NEWS_DAYS)

    async def one(ticker: str, name: str):
        try:
            arts = await svc.fetch_news(search_query=name, limit=NEWS_PER_TICKER)
        except Exception:
            logger.warning("%s 뉴스 조회 실패 — 생략", ticker)
            return ticker, []
        out = []
        for a in arts:
            pub = getattr(a, "published_at", None)
            if pub is not None:
                if pub.tzinfo is None:
                    pub = pub.replace(tzinfo=timezone.utc)
                if pub < cutoff:
                    continue
            out.append(
                {
                    "title": a.title,
                    "source": a.source,
                    "date": pub.strftime("%Y-%m-%d") if pub else None,
                }
            )
        return ticker, out

    pairs = await asyncio.gather(*(one(t, n) for t, n in names.items()))
    return dict(pairs)
```

같은 파일 상단 import 블록을 수정한다:

```diff
+import asyncio
 import json
 import logging
 import os
 import sys
 import traceback
-from datetime import datetime, timezone
+from datetime import datetime, timedelta, timezone
```

그리고 `MAX_COST_USD` 아래의 안내 주석을 지운다:

```diff
 MAX_COST_USD = 5.0  # 하루 누적 상한 — 초과 시 중단 (폭주 방지)
-
-# 뉴스 헤드라인은 Task 14에서 연결한다 (NewsService.fetch_news가 async라 배관이 별건).
-# 그때까지 evidence pack의 news는 빈 목록이고, 프롬프트는 정량 근거만 쓴다.
```

- [ ] **Step 2: 대상 확정 직후 뉴스를 일괄 수집**

`main()`의 `ctx = _market_context(...)` 줄 바로 뒤에 삽입:

```python
    try:
        news_map = asyncio.run(
            _fetch_all_news({t: meta_by_ticker.get(t, {}).get("name", t) for t in picked})
        )
    except Exception:
        logger.warning("뉴스 일괄 조회 실패 — 뉴스 없이 진행", exc_info=True)
        news_map = {}
```

- [ ] **Step 3: pack 구성에 반영**

```diff
-                    "news": [],  # Task 14에서 연결
+                    "news": news_map.get(ticker, []),
```

- [ ] **Step 4: 뉴스 실패가 브리프를 막지 않는지 확인**

Run:
```bash
cd /Users/achii/Quant/Insight-Invest
python -c "
import ast, sys
src = open('scripts/build_briefs.py').read()
ast.parse(src)
assert 'news_map.get(ticker, [])' in src
assert 'import asyncio' in src
assert 'Task 14에서 연결' not in src, '안내 주석이 남아 있음'
print('OK')
"
```
Expected: `OK`

- [ ] **Step 5: 네트워크 없이도 종료되는지 확인**

Run:
```bash
cd /Users/achii/Quant/Insight-Invest
env -u ANTHROPIC_API_KEY BRIEFING_ENV_FILE=/nonexistent python scripts/build_briefs.py; echo "exit=$?"
```
Expected: `[skip] build_briefs (ANTHROPIC_API_KEY 없음)` 후 `exit=0` — 키 확인이 뉴스 조회보다 먼저다

- [ ] **Step 6: 커밋**

```bash
git add scripts/build_briefs.py
git commit -m "feat(brief): evidence pack에 뉴스 헤드라인 연결

대상 종목의 최근 5일 헤드라인을 종목명 검색으로 동시 수집한다.
제목·출처·날짜만 싣고 본문은 넣지 않는다 — 토큰 대비 이득이 작고
LLM이 뉴스 서사에 끌려가 정량 근거를 뒷전으로 미룬다.

개별 종목 조회 실패는 빈 목록으로 흡수하고, 일괄 실패해도 뉴스 없이 진행한다."
```

---

## 완료 검증

전체 구현 후 확인한다.

- [ ] **테스트 전량 통과**

Run: `cd server && python -m pytest tests/ -v`
Expected: 37 passed

- [ ] **Lambda 이미지에 pytest가 들어가지 않았는지 확인**

Run: `grep -c pytest server/requirements.txt`
Expected: `0`

- [ ] **EC2 파이프라인 1회 완주 후 산출물 확인**

```bash
aws s3 ls s3://insight-invest-datalake/app/briefs.parquet --region ap-northeast-2
aws s3 ls s3://insight-invest-datalake/app/insight/factor_pct_ticker.parquet --region ap-northeast-2
```
Expected: 두 파일 모두 존재

- [ ] **비용이 예상 범위인지 확인**

```bash
cd server && python -c "
import sys; sys.path.insert(0, '.')
from datastore import briefs
df = briefs.list_items()
d = df[df['as_of'] == df['as_of'].max()]
print(f\"{len(d)}종목, 합계 \${d['cost_usd'].sum():.4f}\")
"
```
Expected: 10종목 기준 $0.8~1.0. 크게 벗어나면 `docs/superpowers/specs/2026-07-27-stock-brief-design.md` §10의 토큰 추정치를 실측으로 갱신한다.

- [ ] **근거 드롭률 확인**

```bash
cd server && python -c "
import json, sys; sys.path.insert(0, '.')
from datastore import briefs
df = briefs.list_items()
d = df[df['as_of'] == df['as_of'].max()]
n = sum(len(json.loads(x)) for x in d['dropped_refs'])
print(f'드롭 {n}건 / {len(d)}종목')
"
```
Expected: 0에 가까움. 지속적으로 발생하면 `SYSTEM_RULES`의 4번 규칙에 evidence pack 키 목록을 명시적으로 넣는 것을 검토한다.
