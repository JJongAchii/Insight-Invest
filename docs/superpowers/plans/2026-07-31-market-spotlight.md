# 오늘의 신호 종목 (마켓 스포트라이트) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 전시장 신호 스캔을 배치 parquet 하나(`insight/spotlight.parquet`)로 떨어뜨리고, 웹 홈 레인·텔레그램 브리핑이 같은 파일을 읽게 한다. 선행으로 유지형 52주 신고가 신호를 `signal_study`에 추가한다.

**Architecture:** 선정 로직은 순수 모듈 `server/module/spotlight.py`(TDD), 무거운 계산은 배치 `scripts/build_insights.py`의 신규 빌더, Lambda `GET /insight/spotlight`는 parquet 읽기 + `signal_stats` 실측치 조인만. 스펙: `docs/superpowers/specs/2026-07-31-market-spotlight-design.md`.

**Tech Stack:** Python 3.12 (pandas/numpy/pyarrow, FastAPI, pytest), Next.js 14 + RTK Query + Tailwind.

## Global Constraints

- 조건식은 `build_signal_study()`와 **문자 그대로 동일**해야 한다: 신고가 근접 `adj_close >= 252일 rolling max × 0.98` (min_periods **200**), 연속매수 `streak >= 10`, 매집형 `ret_20d < -5 and intensity_20d > 0.3`, 유동성 `mktcap >= 1e10`.
- 그룹당 상한 **5**, 텔레그램은 그중 top **3**. 잘린 종목 수는 반드시 로그.
- 실측치(기준선 대비 %p) 뺄셈은 `module/signal_stats.py`가 유일한 지점 — spotlight parquet에 통계를 복제하지 않는다.
- `GET /insight/spotlight`는 parquet 부재 시 `{"as_of": None, "groups": []}` — **500 금지**.
- 가치판단 라벨("관심"/"주의"/"추천") 금지 — 사실 + 실측치만.
- 커밋은 conventional commits + 한국어 본문 (기존 로그 관례). pre-commit(black line-length 100, isort) 통과 필수.
- 서버 테스트 실행: `cd server && .venv/bin/python -m pytest tests/ -v` (venv가 없으면 README "로컬 개발" 절차로 생성).
- 작업 브랜치: `feat/market-spotlight` (스펙이 이미 커밋돼 있음).

---

### Task 1: `near_52w_high_hold` 신호를 signal_study에 추가

측정에서 유일한 양(+)의 신호였던 "52주 신고가 근접 **유지**"(20일 기준선 대비 +0.54%p)가 빌더에 없다. entry형과 같은 조건식을 daily_conds(cooldown 없음)로 재사용해 추가한다.

**Files:**
- Modify: `scripts/build_insights.py` (모듈 docstring :22, `build_signal_study()` :689-772)
- Modify: `server/module/signal_stats.py` (:26 docstring 행 수)
- Test: `server/tests/test_signal_vocab.py` (:37-52)

**Interfaces:**
- Consumes: 기존 `state_conds`/`daily_conds` 구조, `_event_cooldown`, `_study_row`
- Produces: `signal_study.parquet`에 `signal_type == "near_52w_high_hold"` 행 (h∈{5,20,60}, 스키마 불변, 행 36→39). Task 4·5가 `signal_stats.evidence_phrase("near_52w_high_hold", 20, df=study)`로 소비.

- [ ] **Step 1: 어휘 가드 테스트를 먼저 갱신 (failing test)**

`server/tests/test_signal_vocab.py`의 `EXPECTED_SIGNAL_TYPES`에 한 줄 추가:

```python
        "near_52w_high_entry",
        "near_52w_high_hold",
```

주석도 갱신: `# 이 branch(feat/signal-baseline)가 만드는 최종 어휘 — 12종(baseline 포함).` → `# 빌더가 만드는 최종 어휘 — 13종(baseline 포함).`

- [ ] **Step 2: 실패 확인**

Run: `cd server && .venv/bin/python -m pytest tests/test_signal_vocab.py -v`
Expected: `test_builder_signal_vocabulary_matches_frozen_set` FAIL (빌더 어휘에 `near_52w_high_hold` 없음). qdata 미설치 환경이면 skip되므로, skip이면 venv에 `pip install -e "../../quant-data[s3]"` 후 재실행.

- [ ] **Step 3: 빌더에 조건 추가**

`scripts/build_insights.py`의 `build_signal_study()`에서 state_conds/daily_conds를 다음과 같이 수정 (조건식 재사용 — 메모리 증가 없음):

```python
        # 상태형 — 한 번 참이 되면 며칠 유지된다. crossing으로 첫날만 잡고
        # cooldown으로 재발화를 걸러야 한 사건이 여러 번 세어지지 않는다.
        cond_52w = (P >= hi_252 * 0.98) & liquid  # entry(진입일)·hold(유지 전 일수)가 공유
        state_conds = {
            "bull_divergence": (ret_20d < -5) & (intensity_20d > 0.3) & liquid,
            "frgn_streak10": (streak >= 10) & liquid,
            "high_intensity": (intensity_20d >= 1.0) & liquid,
            "spike_5d_15": (ret_5d >= 15) & liquid,
            "spike_20d_20": (ret_20d >= 20) & liquid,
            "spike_20d_50": (ret_20d >= 50) & liquid,
            "near_52w_high_entry": cond_52w,
        }
        # 하루짜리 사건 — crossing은 거의 무의미하고(연속 급등일은 드물다),
        # cooldown은 서로 다른 진짜 급등을 임의로 버린다. 조건 그대로 쓴다.
        # spike_1d_5(≥5%)는 spike_1d_10(≥10%)의 상위집합이라 그대로 두면
        # "5~10%" 구간을 읽으려는 소비자가 10%+ 날짜까지 섞인 통계를 인용하게
        # 된다 — spike_1d_5_10으로 배타적 구간을 별도로 둔다.
        daily_conds = {
            "spike_1d_5": (CH >= 5) & liquid,
            "spike_1d_5_10": (CH >= 5) & (CH < 10) & liquid,
            "spike_1d_10": (CH >= 10) & liquid,
            "drop_1d_5": (CH <= -5) & liquid,
            # 유지형 신고가 — "고점 근처에 머문 모든 날"의 분포라 cooldown이 없다
            # (baseline과 같은 이유). 2026-07-27 사전 측정(§1.1)과 정확히 일치해야 한다.
            "near_52w_high_hold": cond_52w,
        }
        del ret_5d, ret_20d, hi_252, intensity_20d, streak, CH, M
```

그리고 `del state_conds, daily_conds` (:772) → `del state_conds, daily_conds, cond_52w`.

- [ ] **Step 4: 주석·docstring 정합 갱신 (3곳)**

1. `build_signal_study()` docstring의 "유동성 종목(시총≥100억)에 한해 12개 신호를" → "13개 신호를".
2. 같은 docstring의 sustained proximity 문단 교체:

```
    near_52w_high_entry도 상태형이라 "고점 근처에 머문 모든 날"이 아니라 "그
    구간에 처음 진입한 날"만 센다. 진입일의 성과는 우상향 꼬리를 띠어 중앙값은
    기준선보다 낮고 승률·평균은 기준선보다 높다 — 중앙값만 보고 역방향으로
    오독하지 않도록 주의. "고점 근처에 머문 모든 날"은 near_52w_high_hold
    (daily_conds, cooldown 없음)로 별도 집계한다 — 부호가 반대(중앙값 기준선
    대비 플러스)인 별개 집단이니 이름이 비슷하다고 섞어 읽지 말 것.
```

3. 모듈 docstring(:22) "signal_study: 신호 12종" → "신호 13종". `server/module/signal_stats.py` `load_study()` docstring "신호 12종 × 지평선 3개 = 36행" → "신호 13종 × 지평선 3개 = 39행".

- [ ] **Step 5: 테스트 통과 확인**

Run: `cd server && .venv/bin/python -m pytest tests/ -v`
Expected: 전부 PASS (vocab 2개 + signal_stats 기존 테스트).

- [ ] **Step 6: Commit**

```bash
git add scripts/build_insights.py server/module/signal_stats.py server/tests/test_signal_vocab.py
git commit -m "feat(signal): 유지형 52주 신고가 신호(near_52w_high_hold) 추가

측정(2026-07-27 §1.1)에서 유일하게 뚜렷한 양의 신호였던 '신고가 근접 유지'
집단이 빌더에 없었다. entry형과 같은 조건식을 daily_conds(cooldown 없음)로
재사용한다 — 행 36→39, 스키마 불변, 기존 소비자 안 깨짐."
```

수치 앵커 검증(사전 측정과 대조)은 전 기간 패널 로드가 필요해 Task 7에서 일괄 수행한다.

---

### Task 2: `server/module/spotlight.py` 선정 로직 (TDD)

전시장 스캔의 순수 로직. 틀려도 에러 없이 그럴듯한 종목이 나오는 지점이므로 픽스처로 경계값을 못박는다.

**Files:**
- Create: `server/module/spotlight.py`
- Test: `server/tests/test_spotlight.py`

**Interfaces:**
- Consumes: 없음 (순수 pandas/numpy)
- Produces (Task 3·4·5가 사용):
  - `GROUP_ORDER: tuple[str, ...] = ("near_52w_high_hold", "frgn_streak10", "bull_divergence")`
  - `GROUP_TITLES: dict[str, str]` — 한글 그룹명
  - `CAP_PER_GROUP: int = 5`
  - `near_high_state(P: pd.DataFrame) -> pd.DataFrame` — index=ticker, columns=[dist_pct, hold_days]
  - `select_spotlight(flows_frgn: pd.DataFrame, near_high: pd.DataFrame, cap: int = CAP_PER_GROUP) -> tuple[pd.DataFrame, dict[str, int]]` — (긴 형식 df, 그룹별 잘린 수). df 컬럼: `signal_type, rank, ticker, name, market, close, chg_pct, mktcap, streak, intensity_20d, ret_20d, hold_days, dist_pct, also_in(JSON 문자열)`

- [ ] **Step 1: 실패하는 테스트 작성**

`server/tests/test_spotlight.py`:

```python
"""spotlight 선정 로직 — 픽스처 패널 단위 테스트.

조건 경계(0.98·streak>=10·ret_20d<-5)가 build_signal_study와 같은지,
hold_days가 마지막 연속 구간만 세는지, 상한·also_in이 맞는지 못박는다.
틀려도 에러가 나지 않고 그럴듯한 종목이 나오는 지점이라 테스트가 필수다.
"""

import json

import numpy as np
import pandas as pd
import pytest

from module.spotlight import CAP_PER_GROUP, near_high_state, select_spotlight


def _panel(values: dict) -> pd.DataFrame:
    n = len(next(iter(values.values())))
    return pd.DataFrame(values, index=pd.bdate_range("2024-01-02", periods=n))


def test_near_high_state_boundary():
    n = 260
    steady = [100.0] * n                    # 계속 신고가 → 포함
    below = [100.0] * (n - 1) + [97.9]      # 0.98 문턱 밑 → 제외
    exact = [100.0] * (n - 1) + [98.0]      # 정확히 0.98 → 포함 (빌더의 >= 와 동일)
    df = near_high_state(_panel({"A": steady, "B": below, "C": exact}))
    assert "A" in df.index and "C" in df.index
    assert "B" not in df.index
    assert df.loc["C", "dist_pct"] == pytest.approx(-2.0)


def test_near_high_state_counts_trailing_run_only():
    n = 260
    vals = [100.0] * (n - 3) + [90.0, 100.0, 100.0]  # 중간 이탈 후 복귀 → 마지막 연속 2일
    df = near_high_state(_panel({"A": vals}))
    assert df.loc["A", "hold_days"] == 2


def test_near_high_state_requires_min_periods():
    # 유효 관측 199일 — rolling max가 NaN이라 상태가 성립하지 않는다 (min_periods=200)
    short = [np.nan] * 61 + [100.0] * 199
    df = near_high_state(_panel({"A": short}))
    assert "A" not in df.index


_FLOW_COLS = [
    "ticker", "name", "market", "close", "chg_pct", "mktcap",
    "streak", "intensity_20d", "ret_20d", "divergence",
]


def _flows_fixture() -> pd.DataFrame:
    rows = [
        ["000001", "매집A", "KOSPI", 1000.0, -1.0, 2e10, 3, 1.5, -6.0, "bull"],
        ["000002", "경계B", "KOSPI", 1000.0, 0.0, 2e10, 2, 0.5, -5.0, "bull"],  # -5.0 → 제외
        ["000003", "연속C", "KOSDAQ", 500.0, 0.5, 3e10, 12, 0.8, 2.0, None],
        ["000004", "연속D", "KOSPI", 700.0, 0.2, 4e10, 10, 0.1, 1.0, None],    # 10 → 포함
        ["000005", "짧은E", "KOSPI", 700.0, 0.2, 4e10, 9, 0.1, 1.0, None],     # 9 → 제외
        ["000006", "고점F", "KOSPI", 900.0, 0.1, 5e10, 11, 0.2, 8.0, None],    # 신고가∩연속매수
        ["000007", "고점G", "KOSDAQ", 800.0, 0.3, 1e10, 1, 0.0, 5.0, None],
    ]
    return pd.DataFrame(rows, columns=_FLOW_COLS)


def _near_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {"dist_pct": [-0.5, -1.9], "hold_days": [30, 3]}, index=["000006", "000007"]
    )


def test_select_boundaries_ordering_membership():
    df, dropped = select_spotlight(_flows_fixture(), _near_fixture())
    by = dict(tuple(df.groupby("signal_type")))

    assert list(by["bull_divergence"]["ticker"]) == ["000001"]  # ret_20d == -5.0은 제외
    # streak desc: C(12) > F(11) > D(10). E(9)는 제외
    assert list(by["frgn_streak10"]["ticker"]) == ["000003", "000006", "000004"]
    # hold_days desc: F(30) > G(3)
    assert list(by["near_52w_high_hold"]["ticker"]) == ["000006", "000007"]

    f_near = by["near_52w_high_hold"].set_index("ticker").loc["000006"]
    assert json.loads(f_near["also_in"]) == ["frgn_streak10"]
    f_streak = by["frgn_streak10"].set_index("ticker").loc["000006"]
    assert json.loads(f_streak["also_in"]) == ["near_52w_high_hold"]
    assert dropped == {}


def test_select_caps_and_reports_dropped():
    f = _flows_fixture()
    extra = pd.DataFrame(
        [[f"9{i:05d}", f"연속{i}", "KOSPI", 100.0, 0.0, 2e10, 20 + i, 0.5, 1.0, None]
         for i in range(8)],
        columns=_FLOW_COLS,
    )
    df, dropped = select_spotlight(pd.concat([f, extra], ignore_index=True), _near_fixture())
    streak = df[df["signal_type"] == "frgn_streak10"]
    assert len(streak) == CAP_PER_GROUP
    assert dropped["frgn_streak10"] == 6  # 후보 11(기존 3 + 추가 8) - 상한 5


def test_select_with_no_near_high_candidates():
    empty = pd.DataFrame(columns=["dist_pct", "hold_days"])
    df, _ = select_spotlight(_flows_fixture(), empty)
    assert "near_52w_high_hold" not in set(df["signal_type"])
    assert {"hold_days", "dist_pct", "also_in"} <= set(df.columns)
```

- [ ] **Step 2: 실패 확인**

Run: `cd server && .venv/bin/python -m pytest tests/test_spotlight.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'module.spotlight'`

- [ ] **Step 3: 구현**

`server/module/spotlight.py`:

```python
"""마켓 스포트라이트 선정 — 전시장 신호 스캔의 순수 로직.

build_insights.build_spotlight()가 이 모듈로 그룹을 선정해 parquet으로
떨어뜨리고, insight 라우터·텔레그램 브리핑이 그 parquet을 읽는다.
조건식은 반드시 build_signal_study()의 신호 정의와 같아야 한다 — 통계
(signal_study)와 선정(spotlight)이 다른 조건을 재면 실측치가 거짓말이 된다.
"""

import json

import numpy as np
import pandas as pd

# 그룹 순서 = 20일 기준선 대비 중앙값 내림차순 (2026-07-27 측정).
# 라우터는 서빙 시점의 signal_study로 다시 정렬한다 — 이 상수는 그 폴백이자
# 텔레그램의 표시 순서다.
GROUP_ORDER = ("near_52w_high_hold", "frgn_streak10", "bull_divergence")
GROUP_TITLES = {
    "near_52w_high_hold": "52주 신고가 근접 유지",
    "frgn_streak10": "외인 연속 순매수 10일+",
    "bull_divergence": "매집형 (주가↓·외인 매집)",
}
CAP_PER_GROUP = 5
NEAR_HIGH_RATIO = 0.98  # build_signal_study의 near_52w_high_* 와 동일
MIN_PERIODS_252 = 200

_OUT_COLS = [
    "signal_type", "rank", "ticker", "name", "market", "close", "chg_pct",
    "mktcap", "streak", "intensity_20d", "ret_20d", "hold_days", "dist_pct",
    "also_in",
]


def near_high_state(P: pd.DataFrame) -> pd.DataFrame:
    """마지막 거래일의 52주 신고가 근접 상태 [dist_pct, hold_days] (index=ticker).

    P: 일자×종목 adj_close 패널(index 오름차순). 상태 = adj_close >= 252일
    rolling max × 0.98 (min_periods 200 — build_signal_study와 동일).
    hold_days는 마지막 날짜에서 거슬러 올라간 연속 상태 일수로, 패널 길이에서
    포화된다 — 호출부는 충분한 창(>=520거래일)을 줘야 한다.
    """
    hi = P.rolling(252, min_periods=MIN_PERIODS_252).max()
    state = P >= hi * NEAR_HIGH_RATIO  # NaN 비교 → False
    last = state.iloc[-1]
    tickers = last[last].index
    if len(tickers) == 0:
        return pd.DataFrame(columns=["dist_pct", "hold_days"])

    sv = state[tickers].to_numpy()
    hold = np.cumprod(sv[::-1], axis=0).sum(axis=0)  # 말일부터 연속 True 길이
    dist = (P[tickers].iloc[-1] / hi[tickers].iloc[-1] - 1) * 100
    return pd.DataFrame(
        {"dist_pct": dist.to_numpy(), "hold_days": hold.astype(int)}, index=tickers
    )


def _membership(flows_frgn: pd.DataFrame, near_high: pd.DataFrame) -> dict:
    """그룹별 후보 전체 (상한 적용 전, 그룹 내 정렬 완료)."""
    f = flows_frgn
    near = f.join(near_high, on="ticker", how="inner").sort_values(
        ["hold_days", "mktcap"], ascending=False
    )
    streak = f[f["streak"] >= 10].sort_values(
        ["streak", "intensity_20d"], ascending=False
    )
    bull = f[(f["ret_20d"] < -5) & (f["intensity_20d"] > 0.3)].sort_values(
        "intensity_20d", ascending=False
    )
    return {"near_52w_high_hold": near, "frgn_streak10": streak, "bull_divergence": bull}


def select_spotlight(
    flows_frgn: pd.DataFrame, near_high: pd.DataFrame, cap: int = CAP_PER_GROUP
) -> tuple[pd.DataFrame, dict]:
    """그룹 3개 선정 → (긴 형식 DataFrame, 그룹별 잘린 종목 수).

    also_in은 상한 적용 전 조건 만족 기준이다 — 다른 그룹 상위 5에 못 들었어도
    조건에 해당하면 표시한다 (교집합은 배지일 뿐, 결합 성과는 측정된 바 없다).
    """
    members = _membership(flows_frgn, near_high)
    sets = {g: set(df["ticker"]) for g, df in members.items()}

    frames, dropped = [], {}
    for g in GROUP_ORDER:
        cand = members[g]
        if len(cand) > cap:
            dropped[g] = len(cand) - cap
        top = cand.head(cap).copy()
        top["signal_type"] = g
        top["rank"] = range(1, len(top) + 1)
        top["also_in"] = [
            json.dumps([o for o in GROUP_ORDER if o != g and t in sets[o]])
            for t in top["ticker"]
        ]
        frames.append(top)

    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return out.reindex(columns=_OUT_COLS), dropped
```

- [ ] **Step 4: 통과 확인**

Run: `cd server && .venv/bin/python -m pytest tests/test_spotlight.py -v`
Expected: 6개 전부 PASS

- [ ] **Step 5: Commit**

```bash
git add server/module/spotlight.py server/tests/test_spotlight.py
git commit -m "feat(spotlight): 전시장 신호 선정 로직 순수 모듈

그룹 3종(신고가 유지·외인 연속매수·매집형)의 조건식을 signal_study와
동일하게 재고, 그룹당 상한 5·교집합 배지·잘린 수 보고를 픽스처로 못박는다."
```

---

### Task 3: `build_spotlight()` 빌더 + BUILDERS 등록

**Files:**
- Modify: `scripts/build_insights.py` (모듈 docstring, import, `build_flows_signals()` 끝, 신규 빌더, `BUILDERS`)

**Interfaces:**
- Consumes: Task 2의 `spotlight.near_high_state` / `spotlight.select_spotlight` / `spotlight.CAP_PER_GROUP`, 기존 `_cache`·`_as_of()`·`build_flows_signals()`·`qdata_api.load_krx_prices`
- Produces: `{APP_DATA}/insight/spotlight.parquet` — Task 2의 `_OUT_COLS` + `as_of`. Task 4·5가 읽는다.

- [ ] **Step 1: import 추가 및 flows_signals 캐시**

`scripts/build_insights.py` 상단 import에 (기존 `from module import regime` 옆):

```python
from module import spotlight  # noqa: E402
```

`build_flows_signals()`의 `df["as_of"] = _as_of()` 바로 뒤, `return df` 앞에:

```python
    _cache["flows_signals"] = df  # build_spotlight가 재사용 (재계산 방지)
```

- [ ] **Step 2: 빌더 함수 추가**

`build_factor_pct_ticker()` 뒤에:

```python
def build_spotlight():
    """오늘의 신호 종목 — 전시장 스캔 그룹 3종 (선정 로직: module/spotlight.py).

    수급·가격 필드는 flows_signals 스냅샷(유동성 유니버스)을 쓰고, 52주 신고가
    근접 상태만 최근 800일(달력) adj_close 패널로 별도 계산한다 — hold_days는
    창 길이에서 포화되므로 표시는 "N일+"로 읽는다. 실측치(기준선 대비)는 넣지
    않는다 — 그 뺄셈은 서빙 시점에 signal_stats가 signal_study와 조인해서 한다.
    """
    try:
        flows_sig = _cache.get("flows_signals")
        if flows_sig is None:
            flows_sig = build_flows_signals()
        frgn = flows_sig[flows_sig["investor"] == "frgn"]

        start = (pd.Timestamp.today() - pd.Timedelta(days=800)).strftime("%Y-%m-%d")
        px = qdata_api.load_krx_prices(start=start, columns=["adj_close"])
        P = px.pivot(index="date", columns="ticker", values="adj_close").sort_index()
        del px

        near = spotlight.near_high_state(P)
        del P
        df, dropped = spotlight.select_spotlight(frgn, near)
        for g, n in dropped.items():  # 조용한 절삭 금지
            print(f"[spotlight] {g}: 상한 {spotlight.CAP_PER_GROUP} 적용, {n}종목 잘림")
        if df.empty:
            print("[spotlight] 후보 0 — 저장 생략 (전일 파일 유지)", file=sys.stderr)
            return None
        df["as_of"] = _as_of()
        print(f"[spotlight] {len(df)} rows, as_of={df['as_of'].iloc[0]}")
        return df
    except Exception:
        print("[warn] spotlight 실패 (비중단):", file=sys.stderr)
        traceback.print_exc()
        return None
```

- [ ] **Step 3: BUILDERS 등록 + 모듈 docstring**

`BUILDERS` 리스트에서 `("insight/factor_pct_ticker.parquet", ...)` 다음 줄에:

```python
    ("insight/spotlight.parquet", build_spotlight, {}),  # 오늘의 신호 종목 (전시장 스캔)
```

모듈 docstring(:8~ 빌더 목록)에 한 줄 추가:

```
- spotlight: 오늘의 신호 종목 — 전시장 스캔 그룹 3종(신고가 유지·외인 연속매수
  10일+·매집형) × 상한 5. 웹 홈 레인·텔레그램 신호 섹션 공용.
```

- [ ] **Step 4: 로컬 실행 검증 (레이크 필요, flows 374MB 로드 — 수 분)**

```bash
cd /Users/achii/Quant/Insight-Invest && APP_DATA=$(mktemp -d) server/.venv/bin/python - <<'EOF'
import sys
sys.path.insert(0, "scripts")
import build_insights as bi
df = bi.build_spotlight()
print(df.to_string(index=False))
assert df is not None and not df.empty
assert set(df["signal_type"]) <= {"near_52w_high_hold", "frgn_streak10", "bull_divergence"}
assert df.groupby("signal_type").size().max() <= 5
EOF
```

Expected: 그룹별 최대 5행, 종목명·지표가 상식적인 값(신고가 그룹 dist_pct ≥ −2.0, streak 그룹 streak ≥ 10). 출력을 눈으로 확인한다.

- [ ] **Step 5: 기존 테스트 회귀 확인 + Commit**

Run: `cd server && .venv/bin/python -m pytest tests/ -v` — 전부 PASS 확인.

```bash
git add scripts/build_insights.py
git commit -m "feat(spotlight): build_spotlight 빌더 — 전시장 스캔 parquet

flows_signals 스냅샷 + 800일 가격 패널로 그룹 3종을 선정해
insight/spotlight.parquet으로 저장. 실측치는 넣지 않는다(서빙 시 조인)."
```

---

### Task 4: `GET /insight/spotlight` API + 계약 테스트

**Files:**
- Modify: `server/app/routers/insight.py`
- Test: `server/tests/test_spotlight_api.py`

**Interfaces:**
- Consumes: `spotlight.parquet`(Task 3), `signal_stats.load_study`/`excess_vs_baseline`/`evidence_phrase`, `spotlight.GROUP_TITLES`, `meta_store.meta_df()`, `holdings_store.list_items()`, `watchlist_store.list_items()`
- Produces: `GET /insight/spotlight` → `{as_of, groups: [{signal_type, title, evidence, items: [{ticker, name, market, close, chg_pct, streak, intensity_20d, ret_20d, hold_days, dist_pct, also_in, meta_id, link, mine}]}]}` — Task 6 프론트가 소비.

- [ ] **Step 1: 실패하는 계약 테스트 작성**

`server/tests/test_spotlight_api.py`:

```python
"""GET /insight/spotlight 계약 — parquet 부재 시 빈 응답(500 금지), 존재 시
그룹이 서빙 시점 signal_study의 20일 기준선 대비 중앙값 내림차순으로 정렬된다."""

import asyncio

import pandas as pd


def _write(tmp_path, name, df):
    d = tmp_path / "insight"
    d.mkdir(exist_ok=True)
    df.to_parquet(d / name, index=False)


def test_spotlight_absent_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    import app.routers.insight as insight

    assert asyncio.run(insight.get_spotlight()) == {"as_of": None, "groups": []}


_SPOT_COLS = [
    "signal_type", "rank", "ticker", "name", "market", "close", "chg_pct",
    "mktcap", "streak", "intensity_20d", "ret_20d", "hold_days", "dist_pct",
    "also_in", "as_of",
]
_STUDY_COLS = [
    "signal_type", "horizon", "n_events", "mean_excess", "median_excess",
    "hit_rate", "avg_fwd_ret", "as_of",
]


def test_spotlight_groups_ordered_and_marked(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    import app.routers.insight as insight

    # parquet에는 streak 그룹을 먼저 넣는다 — 정렬이 study 기반임을 증명하기 위해
    spot = pd.DataFrame(
        [
            ["frgn_streak10", 1, "000003", "연속C", "KOSDAQ", 500.0, 0.5, 3e10,
             12, 0.8, 2.0, None, None, "[]", "2026-07-31"],
            ["near_52w_high_hold", 1, "000006", "고점F", "KOSPI", 900.0, 0.1, 5e10,
             11, 0.2, 8.0, 30.0, -0.5, '["frgn_streak10"]', "2026-07-31"],
        ],
        columns=_SPOT_COLS,
    )
    study = pd.DataFrame(
        [
            ["baseline", 20, 6_000_000, -0.5, -1.80, 41.2, 3.0, "2026-07-31"],
            ["near_52w_high_hold", 20, 282_143, 0.5, -1.26, 44.2, 4.0, "2026-07-31"],
            ["frgn_streak10", 20, 1_847, 0.2, -1.29, 43.0, 3.5, "2026-07-31"],
        ],
        columns=_STUDY_COLS,
    )
    _write(tmp_path, "spotlight.parquet", spot)
    _write(tmp_path, "signal_study.parquet", study)

    monkeypatch.setattr(
        insight.meta_store,
        "meta_df",
        lambda: pd.DataFrame(
            {"meta_id": [1], "ticker": ["000006"], "iso_code": ["KR"],
             "name": ["고점F"], "security_type": ["stock"], "sector": ["기타"]}
        ),
    )
    monkeypatch.setattr(
        insight.holdings_store, "list_items", lambda: pd.DataFrame(columns=["meta_id"])
    )
    monkeypatch.setattr(
        insight.watchlist_store, "list_items", lambda: pd.DataFrame({"meta_id": [1]})
    )

    res = asyncio.run(insight.get_spotlight())
    # +0.54%p(near) > +0.51%p(streak) — parquet 순서가 아니라 study로 정렬됐다
    assert [g["signal_type"] for g in res["groups"]] == [
        "near_52w_high_hold", "frgn_streak10"
    ]
    near = res["groups"][0]
    assert near["evidence"] is not None and "기준선 대비" in near["evidence"]
    item = near["items"][0]
    assert item["meta_id"] == 1
    assert item["link"] == "/stock/1"
    assert item["mine"] == "watchlist"
    assert item["also_in"] == ["frgn_streak10"]
    assert item["hold_days"] == 30
    # meta에 없는 종목은 링크 없이 내려간다 (500 금지)
    streak_item = res["groups"][1]["items"][0]
    assert streak_item["meta_id"] is None and streak_item["mine"] is None
```

- [ ] **Step 2: 실패 확인**

Run: `cd server && .venv/bin/python -m pytest tests/test_spotlight_api.py -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'get_spotlight'`

- [ ] **Step 3: 엔드포인트 구현**

`server/app/routers/insight.py` — import 블록에 추가:

```python
import json
```

```python
from datastore import holdings as holdings_store
from datastore import meta as meta_store
from datastore import storage
from datastore import watchlist as watchlist_store
from module import signal_stats
from module import spotlight as spotlight_mod
```

(기존 `from datastore import meta as meta_store` / `from datastore import storage` 두 줄을 위처럼 확장. isort가 정렬한다.)

`get_signals_study` 아래에 엔드포인트 추가:

```python
@router.get("/spotlight")
async def get_spotlight():
    """오늘의 신호 종목 — 전시장 스캔 (spotlight.parquet의 얇은 리더).

    그룹 순서는 서빙 시점 signal_study의 20일 기준선 대비 중앙값 내림차순 —
    우위가 있는 신호가 먼저 보인다. parquet 부재 시 빈 그룹 (500 금지,
    attention과 같은 계약). 보유·관심 마킹 실패는 마킹 없이 진행한다.
    """
    df = _read("spotlight.parquet")
    if df is None or df.empty:
        return {"as_of": None, "groups": []}

    study = signal_stats.load_study()

    holding_ids, watch_ids = set(), set()
    try:
        hd = holdings_store.list_items()
        holding_ids = {int(x) for x in hd["meta_id"]} if not hd.empty else set()
        wl = watchlist_store.list_items()
        watch_ids = {int(x) for x in wl["meta_id"]} if not wl.empty else set()
    except Exception:
        pass

    md = meta_store.meta_df()
    kr = md[md["iso_code"] == "KR"]
    tk2meta = {r.ticker: int(r.meta_id) for r in kr.itertuples()}

    def _delta20(sig: str):
        if study is None:
            return None
        stats = signal_stats.excess_vs_baseline(study, sig, 20)
        return stats[1] if stats else None

    groups = []
    for sig in df["signal_type"].unique():
        sub = df[df["signal_type"] == sig].sort_values("rank")
        items = []
        for r in sub.itertuples():
            mid = tk2meta.get(r.ticker)
            mine = (
                "holding"
                if mid in holding_ids
                else "watchlist" if mid in watch_ids else None
            )
            items.append(
                {
                    "ticker": r.ticker,
                    "name": r.name,
                    "market": r.market,
                    "close": r.close,
                    "chg_pct": r.chg_pct,
                    "streak": int(r.streak) if pd.notna(r.streak) else None,
                    "intensity_20d": r.intensity_20d,
                    "ret_20d": r.ret_20d,
                    "hold_days": int(r.hold_days) if pd.notna(r.hold_days) else None,
                    "dist_pct": r.dist_pct,
                    "also_in": json.loads(r.also_in) if isinstance(r.also_in, str) else [],
                    "meta_id": mid,
                    "link": f"/stock/{mid}" if mid is not None else None,
                    "mine": mine,
                }
            )
        groups.append(
            {
                "signal_type": sig,
                "title": spotlight_mod.GROUP_TITLES.get(sig, sig),
                "evidence": signal_stats.evidence_phrase(sig, 20, df=study),
                "_delta": _delta20(sig),
                "items": items,
            }
        )
    groups.sort(key=lambda g: (g["_delta"] is None, -(g["_delta"] or 0)))
    for g in groups:
        g.pop("_delta")
    return _round2({"as_of": _as_of(df), "groups": groups})
```

- [ ] **Step 4: 통과 확인**

Run: `cd server && .venv/bin/python -m pytest tests/ -v`
Expected: 전부 PASS

- [ ] **Step 5: Commit**

```bash
git add server/app/routers/insight.py server/tests/test_spotlight_api.py
git commit -m "feat(api): GET /insight/spotlight — 전시장 신호 종목 리더

spotlight.parquet + signal_study 조인으로 그룹을 우위 내림차순 정렬,
실측치 문구·보유/관심 마킹 부착. parquet 부재 시 빈 그룹 (500 금지)."
```

---

### Task 5: 텔레그램 `_section_signals`를 spotlight 기반으로 대체

**Files:**
- Modify: `scripts/send_briefing.py` (import :31, `_section_signals` :274-309)

**Interfaces:**
- Consumes: `spotlight.parquet`, `spotlight.GROUP_ORDER`/`GROUP_TITLES`, `signal_stats.load_study`/`evidence_phrase`
- Produces: 텔레그램 "신호" 섹션 — 그룹별 top 3 + 실측치 줄. 섹션 등록명(`("signals", _section_signals)`)은 불변.

- [ ] **Step 1: import 갱신**

`from module import signal_stats  # noqa: E402` → `from module import signal_stats, spotlight  # noqa: E402`

- [ ] **Step 2: `_section_signals` 전체 교체**

```python
def _section_signals() -> str | None:
    """오늘의 신호 종목 — spotlight.parquet (전시장 스캔, 그룹 상한 5 중 top 3).

    선정·정렬·조건식은 전부 빌더(module/spotlight.py) 몫이다 — 여기서는 읽고
    포맷만 한다. 웹 홈 레인과 같은 파일을 읽으므로 둘이 어긋나지 않는다.
    """
    df = storage.read_parquet("insight", "spotlight.parquet")
    if df.empty:
        return None
    study = signal_stats.load_study()

    def _metric(sig: str, r) -> str:
        if sig == "near_52w_high_hold":
            return f"{int(r['hold_days'])}일째"
        if sig == "frgn_streak10":
            return f"{int(r['streak'])}일"
        return f"강도 {r['intensity_20d']:.1f}%"

    lines = []
    for sig in spotlight.GROUP_ORDER:
        sub = df[df["signal_type"] == sig].sort_values("rank").head(3)
        if sub.empty:
            continue
        items = " · ".join(f"{_esc(r['name'])}({_metric(sig, r)})" for _, r in sub.iterrows())
        lines.append(f"{_esc(spotlight.GROUP_TITLES[sig])}: {items}")
        # 신호마다 "과거에 통했는가"를 한 줄로 붙인다 — 이름만 나열하면 우위가
        # 없는 신호와 있는 신호가 같은 무게로 읽힌다.
        ev = signal_stats.evidence_phrase(sig, 20, df=study)
        if ev:
            lines.append(f"  └ {_esc(ev)}")

    if not lines:
        return None
    return "<b>신호</b>\n" + "\n".join(lines)
```

기존 함수의 bull 재필터(`ret_20d < -5` 재적용) 주석 블록은 함수와 함께 삭제된다 — 그 로직은 빌더 조건식으로 이동했다.

- [ ] **Step 3: 픽스처 parquet으로 수동 검증**

```bash
cd /Users/achii/Quant/Insight-Invest && APP_DATA=$(mktemp -d) server/.venv/bin/python - <<'EOF'
import os, sys
import pandas as pd
sys.path.insert(0, "server")
sys.path.insert(0, "scripts")
root = os.environ["APP_DATA"]
os.makedirs(f"{root}/insight", exist_ok=True)
pd.DataFrame({
    "signal_type": ["near_52w_high_hold", "frgn_streak10", "bull_divergence"],
    "rank": [1, 1, 1], "ticker": ["000006", "000003", "000001"],
    "name": ["고점F", "연속C", "매집A"], "market": ["KOSPI", "KOSDAQ", "KOSPI"],
    "close": [900.0, 500.0, 1000.0], "chg_pct": [0.1, 0.5, -1.0],
    "mktcap": [5e10, 3e10, 2e10], "streak": [11, 12, 3],
    "intensity_20d": [0.2, 0.8, 1.5], "ret_20d": [8.0, 2.0, -6.0],
    "hold_days": [30.0, None, None], "dist_pct": [-0.5, None, None],
    "also_in": ['["frgn_streak10"]', "[]", "[]"], "as_of": ["2026-07-31"] * 3,
}).to_parquet(f"{root}/insight/spotlight.parquet", index=False)
import send_briefing as sb
out = sb._section_signals()
print(out)
assert "52주 신고가 근접 유지" in out and "고점F(30일째)" in out
assert "외인 연속 순매수 10일+" in out and "연속C(12일)" in out
assert "매집형" in out and "매집A(강도 1.5%)" in out
EOF
```

Expected: 세 그룹 줄이 출력되고 assert 통과. (signal_study가 없으므로 `└` 실측치 줄은 생략 — 정상.)

- [ ] **Step 4: Commit**

```bash
git add scripts/send_briefing.py
git commit -m "feat(briefing): 신호 섹션을 spotlight parquet 기반으로 대체

매집형·연속매수에 신고가 유지 그룹이 추가되고, 웹 홈 레인과 같은 파일을
읽어 노출이 어긋나지 않는다. 서빙 시점 bull 재필터는 빌더 조건식으로
이동해 소멸."
```

---

### Task 6: 프론트 — api.ts 타입/엔드포인트 + `SpotlightLane` + 홈 배치

**Files:**
- Modify: `client/src/state/api.ts` (AttentionResponse 타입 옆 :241, fetchAttention 엔드포인트 옆 :915-919, export 블록 :1090)
- Create: `client/src/app/home/SpotlightLane.tsx`
- Modify: `client/src/app/home/page.tsx` (import + `<AttentionLane />` 아래)

**Interfaces:**
- Consumes: Task 4의 응답 스키마
- Produces: `useFetchSpotlightQuery` 훅, `SpotlightItem`/`SpotlightGroup`/`SpotlightResponse` 타입, 홈 레인 컴포넌트

- [ ] **Step 1: api.ts 타입 추가** (`AttentionResponse` 인터페이스 바로 아래)

```ts
// Types for the "오늘의 신호 종목" market spotlight lane
export interface SpotlightItem {
  ticker: string;
  name: string;
  market: string;
  close: number | null;
  chg_pct: number | null;
  streak: number | null;
  intensity_20d: number | null;
  ret_20d: number | null;
  hold_days: number | null;
  dist_pct: number | null;
  also_in: string[];
  meta_id: number | null;
  link: string | null;
  mine: "holding" | "watchlist" | null;
}

export interface SpotlightGroup {
  signal_type: string;
  title: string;
  evidence: string | null;
  items: SpotlightItem[];
}

export interface SpotlightResponse {
  as_of: string | null;
  groups: SpotlightGroup[];
}
```

- [ ] **Step 2: api.ts 엔드포인트 + 훅 export**

`fetchAttention` 정의 바로 아래:

```ts
    // Market spotlight ("오늘의 신호 종목") endpoint
    fetchSpotlight: builder.query<SpotlightResponse, void>({
      query: () => "/insight/spotlight",
    }),
```

export 블록의 `useFetchAttentionQuery,` 다음 줄에:

```ts
  useFetchSpotlightQuery,
```

- [ ] **Step 3: SpotlightLane 컴포넌트 작성**

`client/src/app/home/SpotlightLane.tsx`:

```tsx
"use client";

import React from "react";
import Link from "next/link";

import {
  SpotlightGroup,
  SpotlightItem,
  useFetchSpotlightQuery,
} from "@/state/api";

const MINE_LABEL: Record<string, string> = {
  holding: "보유",
  watchlist: "관심",
};

// 그룹별 대표 지표 한 줄 — 그 그룹에 의미 있는 컬럼만 고른다
const metricLine = (signalType: string, item: SpotlightItem): string => {
  if (signalType === "near_52w_high_hold") {
    return [
      item.hold_days != null ? `${item.hold_days}일째 유지` : "",
      item.dist_pct != null ? `고점 대비 ${item.dist_pct.toFixed(1)}%` : "",
    ]
      .filter(Boolean)
      .join(" · ");
  }
  if (signalType === "frgn_streak10") {
    return [
      item.streak != null ? `${item.streak}일 연속 순매수` : "",
      item.intensity_20d != null ? `강도 ${item.intensity_20d.toFixed(1)}%` : "",
    ]
      .filter(Boolean)
      .join(" · ");
  }
  return [
    item.intensity_20d != null ? `강도 ${item.intensity_20d.toFixed(1)}%` : "",
    item.ret_20d != null ? `20일 ${item.ret_20d.toFixed(1)}%` : "",
  ]
    .filter(Boolean)
    .join(" · ");
};

const SpotlightCard: React.FC<{ group: SpotlightGroup; item: SpotlightItem }> = ({
  group,
  item,
}) => {
  const body = (
    <>
      <div className="flex items-center gap-2 mb-1">
        <span className="text-sm font-semibold text-ink truncate">{item.name}</span>
        {item.mine && <span className="badge-neutral">{MINE_LABEL[item.mine]}</span>}
        {item.also_in.length > 0 && <span className="badge-neutral">복합</span>}
        <span
          className="ml-auto text-xs num shrink-0"
          style={{
            color: (item.chg_pct ?? 0) >= 0 ? "var(--gains)" : "var(--losses)",
          }}
        >
          {item.chg_pct != null
            ? `${item.chg_pct > 0 ? "+" : ""}${item.chg_pct.toFixed(1)}%`
            : ""}
        </span>
      </div>
      <p className="text-xs text-ink-secondary">{metricLine(group.signal_type, item)}</p>
    </>
  );
  const cls =
    "group shrink-0 w-[240px] p-4 rounded-2xl border border-edge bg-surface " +
    "hover:border-edge-strong hover:bg-raised transition-all duration-200";
  return item.link ? (
    <Link href={item.link} className={cls}>
      {body}
    </Link>
  ) : (
    <div className={cls}>{body}</div>
  );
};

/** "오늘의 신호 종목" — 전시장 신호 스캔 (attention의 내 종목 트리아지와 별개).
 *  그룹 순서는 서버가 기준선 대비 우위 내림차순으로 준다. 에러·빈 데이터면
 *  레인 자체를 렌더하지 않는다 (AttentionLane 관례). */
const SpotlightLane: React.FC = () => {
  const { data, isLoading, error } = useFetchSpotlightQuery();
  if (error || isLoading) return null;
  const groups = (data?.groups ?? []).filter((g) => g.items.length > 0);
  if (groups.length === 0) return null;

  return (
    <div>
      <h2 className="text-sm font-semibold text-ink-secondary mb-3">
        오늘의 신호 종목
      </h2>
      <div className="flex flex-col gap-4">
        {groups.map((g) => (
          <div key={g.signal_type}>
            <div className="flex flex-wrap items-baseline gap-x-2 mb-2">
              <span className="text-sm font-medium text-ink">{g.title}</span>
              {g.evidence && (
                <span className="text-xs text-ink-muted">{g.evidence}</span>
              )}
            </div>
            <div className="flex gap-3 overflow-x-auto pb-2 -mx-1 px-1">
              {g.items.map((item) => (
                <SpotlightCard
                  key={`${g.signal_type}-${item.ticker}`}
                  group={g}
                  item={item}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default SpotlightLane;
```

- [ ] **Step 4: 홈에 배치**

`client/src/app/home/page.tsx` — import 블록에 `import SpotlightLane from "./SpotlightLane";` 추가, 본문의 `<AttentionLane />` 아래에:

```tsx
      {/* Row 0: 오늘 주목 attention lane (top) */}
      <AttentionLane />

      {/* Row 0.5: 오늘의 신호 종목 — 전시장 스캔 (내 종목 밖 발굴) */}
      <SpotlightLane />
```

- [ ] **Step 5: 타입·린트 확인**

Run: `cd client && npx tsc --noEmit && npm run lint`
Expected: 에러 0. (로컬 API를 띄워둔 상태라면 `npm run dev`로 홈에서 레인이 숨김 처리되는 것(스포트라이트 parquet 부재)도 확인 가능 — 선택.)

- [ ] **Step 6: Commit**

```bash
git add client/src/state/api.ts client/src/app/home/SpotlightLane.tsx client/src/app/home/page.tsx
git commit -m "feat(client): 홈 '오늘의 신호 종목' 레인

전시장 스캔 그룹을 실측치 헤더와 함께 노출. 보유/관심/복합 배지,
에러·빈 데이터 시 레인 미렌더 (AttentionLane 관례)."
```

---

### Task 7: 통합 검증 + 문서 갱신

**Files:**
- Modify: `README.md` (:28 "파생 인사이트 14종" → "15종", :120 동일)
- Modify: `docs/superpowers/specs/2026-07-31-market-spotlight-design.md` (상태 줄)

**Interfaces:**
- Consumes: Task 1~6 전부
- Produces: 머지 준비 완료된 브랜치

- [ ] **Step 1: 신호 통계 앵커 검증 (전 기간 패널 — RSS ~3GB, 수 분 소요)**

```bash
cd /Users/achii/Quant/Insight-Invest && server/.venv/bin/python - <<'EOF'
import sys
sys.path.insert(0, "scripts")
import build_insights as bi
df = bi.build_signal_study()
sub = df[df["signal_type"].isin(["baseline", "near_52w_high_hold"])]
print(sub.to_string(index=False))
b20 = sub[(sub.signal_type == "baseline") & (sub.horizon == 20)].iloc[0]
h20 = sub[(sub.signal_type == "near_52w_high_hold") & (sub.horizon == 20)].iloc[0]
print(f"delta20 median={h20.median_excess - b20.median_excess:+.2f}%p "
      f"hit={h20.hit_rate - b20.hit_rate:+.1f}%p n={h20.n_events:,}")
EOF
```

Expected: 20일 중앙값 델타 ≈ **+0.54%p**, 승률 델타 ≈ **+3.0%p**, 60일 델타 ≈ **+0.94%p**, N ≈ 282,143+. 측정 스냅샷(2026-07-20) 이후 거래일이 추가됐으므로 소수점 둘째 자리까지 같을 필요는 없다 — **부호가 다르거나 0.2%p 이상 이탈하면 구현 오류를 의심**하고 조건식을 §1.1과 재대조한다.

- [ ] **Step 2: 전체 테스트 + 프론트 빌드 최종 확인**

Run: `cd server && .venv/bin/python -m pytest tests/ -v` — 전부 PASS
Run: `cd client && npx tsc --noEmit` — 에러 0

- [ ] **Step 3: README·스펙 상태 갱신**

- `README.md`의 두 곳 `파생 인사이트 14종` → `파생 인사이트 15종` (아키텍처 다이어그램 5행, 저장소 구조의 build_insights 주석).
- 스펙 문서 상태 줄: `- 상태: 설계, 사용자 리뷰 대기` → `- 상태: 구현 완료 (2026-07-31)`

- [ ] **Step 4: Commit**

```bash
git add README.md docs/superpowers/specs/2026-07-31-market-spotlight-design.md
git commit -m "docs: 스포트라이트 반영 — 빌더 수 15종, 스펙 상태 갱신"
```

- [ ] **Step 5: 머지·배포 절차 안내 (실행은 사용자 확인 후)**

- 머지는 superpowers:finishing-a-development-branch 스킬로 진행 (`feat/market-spotlight` → `main`).
- 머지 푸시 시: GitHub Actions가 Lambda 배포(`server/**` 변경), Vercel이 클라이언트 배포.
- **첫 spotlight.parquet은 다음 평일 19:00 KST 배치가 만든다** (EC2가 `git pull` 후 실행 — 별도 배포 절차 없음). 그 전까지 `GET /insight/spotlight`는 빈 그룹을 반환하고 홈 레인은 숨겨진다 — 의도된 동작.
- 다음 날 아침 텔레그램 신호 섹션과 홈 레인에서 같은 종목이 보이는지 확인한다.
