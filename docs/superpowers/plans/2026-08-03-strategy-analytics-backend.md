# 전략 분석 백엔드 (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 전략 상세 2계층 재설계의 백엔드 — 분석 순수 모듈(`strategy_analytics`), P7 `live_weights` 저장, `GET /backtest/strategy/analytics/{port_id}`. 프론트는 Phase 2 별도 플랜 (이 응답 스키마가 확정 계약).

**Architecture:** 스펙 `docs/superpowers/specs/2026-08-03-strategy-analytics-design.md`. 순수 계산 TDD → P7 확장 → 얇은 라우터. 2026-08-03 엔진 핫픽스(truncate_to_common_history) 전제.

**Tech Stack:** Python 3.12 (pandas/numpy, FastAPI, pytest).

## Global Constraints

- 판단 라벨 금지 — 수치·분포 위치·조건·경고까지만.
- 섹션 단위 degrade: 이력 부족·데이터 부재 시 해당 키 null + `note` (500 금지).
- 롤링 창 252거래일, 낙폭 에피소드 top 5, 미회복 에피소드는 `days_to_recover: null` + 진행 중.
- 위기 구간은 `module.portfolio_risk.CRISIS_WINDOWS` **재사용** (정의 중복 금지).
- 백분위 정의: `(분포 < 관측값).mean() × 100` — 낮을수록 역사적 하위.
- 반올림은 라우터(`_finite`/round 패턴), 모듈은 raw float.
- 테스트 `cd server && .venv-test/bin/python -m pytest tests/ -q` (현재 63), pre-commit(black 100·isort) 통과, conventional commits 한국어. 브랜치 `feat/strategy-analytics`(스펙 커밋됨).

---

### Task 1: `server/module/strategy_analytics.py` 순수 계산 (TDD)

**Files:**
- Create: `server/module/strategy_analytics.py`
- Test: `server/tests/test_strategy_analytics.py`

**Interfaces:**
- Consumes: pandas/numpy, `module.portfolio_risk.CRISIS_WINDOWS`
- Produces (Task 3 라우터가 사용):
  - `rolling_stats(nav: pd.Series, window: int = 252) -> pd.DataFrame` — index=date, cols `roll_ret`(창 수익률 %), `roll_sharpe`
  - `drawdown_episodes(nav: pd.Series, top_n: int = 5) -> list[dict]` — depth_pct, peak, trough, recover(None=진행 중), days_to_recover(거래일, None)
  - `monthly_returns(nav: pd.Series) -> pd.Series` — 월말 리샘플 pct
  - `monthly_stats(nav, bm_nav: pd.Series | None) -> dict` — win_rate, win_rate_vs_bm(None 허용), best/worst 각 top 5 [{month, ret_pct}]
  - `turnover_stats(rebal: pd.DataFrame) -> dict` — long [rebal_date, ticker, weight] → n_rebals, rebals_per_year, avg_turnover, cost_drag 함수형 아님: `cost_drag_pct(bps)`는 라우터에서 `rebals_per_year*avg_turnover*bps/1e4*100` 계산 (모듈은 재료만)
  - `live_percentile(bt_nav: pd.Series, live_nav: pd.Series) -> dict | None` — n_days, live_ret_pct, ret_percentile, live_dd_pct, dd_percentile (bt 이력 < n_days+window 여유 시 None)
  - `crisis_returns(nav: pd.Series, windows: dict) -> list[dict]` — key, ret_pct(None=커버 불가), note
  - `phase_monthly_means(monthly: pd.Series, phases: pd.Series) -> pd.DataFrame` — index=phase, cols mean_ret_pct, n_months (phases: PeriodIndex('M')→str)

- [ ] **Step 1: 실패하는 테스트** — `server/tests/test_strategy_analytics.py`:

```python
"""strategy_analytics 순수 계산 — 손계산 픽스처.

낙폭 에피소드 경계(회복일·미회복), 백분위 정의, 턴오버 합산은 틀려도
그럴듯한 숫자가 나오는 지점이다. 전부 손으로 재계산 가능한 픽스처로 못박는다.
"""

import numpy as np
import pandas as pd
import pytest

from module.strategy_analytics import (
    crisis_returns,
    drawdown_episodes,
    live_percentile,
    monthly_returns,
    monthly_stats,
    phase_monthly_means,
    rolling_stats,
    turnover_stats,
)


def _nav(vals, start="2024-01-01") -> pd.Series:
    return pd.Series(vals, index=pd.bdate_range(start, periods=len(vals)), dtype="float64")


def test_drawdown_episodes_boundaries_and_recovery():
    # 100→120(고점)→90(저점,-25%)→121(회복) 그리고 말미 진행 중 낙폭 -10%
    vals = [100, 120, 105, 90, 110, 121, 130, 117]
    eps = drawdown_episodes(_nav(vals), top_n=5)
    assert len(eps) == 2
    e1 = eps[0]  # 깊은 순 정렬 — -25%가 먼저
    assert e1["depth_pct"] == pytest.approx(-25.0)
    assert str(e1["peak"])[:10] == "2024-01-02"      # 120 고점일
    assert str(e1["trough"])[:10] == "2024-01-04"    # 90 저점일
    assert str(e1["recover"])[:10] == "2024-01-08"   # 121 ≥ 120 복귀일
    assert e1["days_to_recover"] == 4                # 고점 다음날부터 회복일까지 거래일 수
    e2 = eps[1]  # 130→117 진행 중
    assert e2["depth_pct"] == pytest.approx(-10.0)
    assert e2["recover"] is None and e2["days_to_recover"] is None


def test_rolling_stats_window_math():
    n = 300
    nav = _nav(list(100 * (1.001 ** np.arange(n))))  # 일 0.1% 복리
    rs = rolling_stats(nav, window=252)
    assert len(rs) == n - 252
    expected = (1.001 ** 252 - 1) * 100
    assert rs["roll_ret"].iloc[0] == pytest.approx(expected, rel=1e-9)
    assert rs["roll_sharpe"].iloc[-1] > 10  # 무변동 양수 드리프트 — 매우 큼 (정확값 불요)


def test_monthly_stats_win_rates():
    # 4개월: +2%, -1%, +3%, -2% → 절대 승률 50%
    idx = pd.bdate_range("2024-01-01", periods=90)
    monthly_mult = {1: 1.02, 2: 0.99, 3: 1.03, 4: 0.98}
    daily = []
    v = 100.0
    prev_month = None
    for d in idx:
        if prev_month is not None and d.month != prev_month:
            v *= monthly_mult.get(prev_month, 1.0)
        prev_month = d.month
        daily.append(v)
    # 간단화: 월내 보합, 월 경계에서 점프 — monthly_returns가 월말 값으로 재현
    nav = pd.Series(daily, index=idx)
    m = monthly_returns(nav)
    st = monthly_stats(nav, None)
    assert st["win_rate"] == pytest.approx((m > 0).mean() * 100)
    assert st["win_rate_vs_bm"] is None
    assert len(st["best"]) <= 5 and len(st["worst"]) <= 5
    st2 = monthly_stats(nav, nav)  # 자기 자신 대비 — 초과 0, 승률 0%
    assert st2["win_rate_vs_bm"] == pytest.approx(0.0)


def test_turnover_stats_hand_math():
    # 리밸 3회: 전액 A → A/B 반반 → 전액 B
    rebal = pd.DataFrame(
        {
            "rebal_date": pd.to_datetime(["2024-01-02", "2024-07-01", "2025-01-02"]),
            "ticker": ["A", "A", "B"],
            "weight": [1.0, 0.5, 1.0],
        }
    )
    rebal = pd.concat(
        [rebal, pd.DataFrame({"rebal_date": [pd.Timestamp("2024-07-01")], "ticker": ["B"], "weight": [0.5]})]
    )
    ts = turnover_stats(rebal)
    assert ts["n_rebals"] == 3
    # 턴오버: 1회차 Σ|w|=1.0(전액 매수), 2회차 |0.5-1|+|0.5-0|=1.0, 3회차 |0-0.5|+|1-0.5|=1.0
    assert ts["avg_turnover"] == pytest.approx(1.0)
    assert ts["rebals_per_year"] == pytest.approx(3 / 1.0, rel=0.1)  # 1년 구간 3회


def test_live_percentile_definition():
    # 백테스트: 일 0.1% 복리 500일. 라이브: 20일에 +5% (분포 최상단 → 백분위 ~100)
    bt = _nav(list(100 * (1.001 ** np.arange(500))))
    live = _nav(list(np.linspace(1000, 1050, 21)), start="2026-01-01")
    r = live_percentile(bt, live)
    assert r["n_days"] == 20
    assert r["live_ret_pct"] == pytest.approx(5.0)
    assert r["ret_percentile"] > 99.0
    # 라이브가 고점이면 현재 낙폭 0 → dd 백분위는 정의상 상단
    assert r["live_dd_pct"] == pytest.approx(0.0)


def test_live_percentile_insufficient_history():
    bt = _nav([100, 101, 102])
    live = _nav(list(np.linspace(1000, 1010, 30)), start="2026-01-01")
    assert live_percentile(bt, live) is None


def test_crisis_returns_coverage_rule():
    nav = _nav(list(np.linspace(100, 120, 300)), start="2021-01-01")
    out = crisis_returns(nav, {"covid_2020": ("2020-02-14", "2020-03-23")})
    assert out[0]["ret_pct"] is None and out[0]["note"]
    nav2 = _nav(list(np.linspace(100, 120, 300)), start="2020-01-02")
    out2 = crisis_returns(nav2, {"covid_2020": ("2020-02-14", "2020-03-23")})
    assert out2[0]["ret_pct"] is not None


def test_phase_monthly_means_grouping():
    monthly = pd.Series(
        [1.0, 2.0, -1.0, 3.0],
        index=pd.PeriodIndex(["2024-01", "2024-02", "2024-03", "2024-04"], freq="M"),
    )
    phases = pd.Series(
        ["Goldilocks", "Goldilocks", "Reflation", "Reflation"],
        index=monthly.index,
    )
    out = phase_monthly_means(monthly, phases)
    assert out.loc["Goldilocks", "mean_ret_pct"] == pytest.approx(1.5)
    assert int(out.loc["Reflation", "n_months"]) == 2
```

- [ ] **Step 2: RED 확인** (ModuleNotFoundError)

- [ ] **Step 3: 구현** — `server/module/strategy_analytics.py`:

```python
"""전략 분석 파생 지표 — 투입 판정(분석 계층)·운영 추적(기대 대비)의 순수 계산.

전부 저장된 NAV·리밸 이력의 파생이다. 판단하지 않는다 — 분포와 위치, 조건을
계산해 돌려줄 뿐, "좋다/나쁘다"는 라우터도 프론트도 붙이지 않는다.
백분위 정의: (분포 < 관측값).mean() × 100 — 낮을수록 역사적 하위.
"""

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def rolling_stats(nav: pd.Series, window: int = TRADING_DAYS) -> pd.DataFrame:
    """롤링 창 수익률(%)과 샤프 — 기간 의존성 진단 재료."""
    ret = nav / nav.shift(window) - 1
    daily = nav.pct_change()
    mean = daily.rolling(window).mean()
    std = daily.rolling(window).std()
    sharpe = (mean / std) * np.sqrt(TRADING_DAYS)
    out = pd.DataFrame({"roll_ret": ret * 100, "roll_sharpe": sharpe}).dropna()
    return out


def drawdown_episodes(nav: pd.Series, top_n: int = 5) -> list:
    """낙폭 에피소드 — 깊이 순 top N. 회복일수는 거래일 기준, 미회복은 None.

    에피소드 = dd<0 연속 구간. peak는 구간 직전 고점일, recover는 dd가 0으로
    복귀한 날(신고점 회복일).
    """
    dd = nav / nav.cummax() - 1
    at_high = dd >= 0
    group = at_high.cumsum()
    episodes = []
    for _, g in dd[~at_high].groupby(group[~at_high]):
        trough = g.idxmin()
        start_pos = nav.index.get_loc(g.index[0])
        peak = nav.index[start_pos - 1]
        end_pos = nav.index.get_loc(g.index[-1])
        if end_pos + 1 < len(nav.index):
            recover = nav.index[end_pos + 1]
            # 고점 다음 거래일부터 회복일까지의 거래일 수 (peak→recover 위치 차)
            days = int(nav.index.get_loc(recover) - nav.index.get_loc(peak))
        else:
            recover, days = None, None
        episodes.append(
            {
                "depth_pct": float(g.min() * 100),
                "peak": peak,
                "trough": trough,
                "recover": recover,
                "days_to_recover": days,
            }
        )
    episodes.sort(key=lambda e: e["depth_pct"])
    return episodes[:top_n]


def monthly_returns(nav: pd.Series) -> pd.Series:
    m = nav.resample("ME").last().pct_change().dropna() * 100
    m.index = m.index.to_period("M")
    return m


def monthly_stats(nav: pd.Series, bm_nav) -> dict:
    m = monthly_returns(nav)
    if m.empty:
        return {"win_rate": None, "win_rate_vs_bm": None, "best": [], "worst": []}
    win_vs_bm = None
    if bm_nav is not None and len(bm_nav):
        bm = monthly_returns(bm_nav)
        joined = pd.concat([m, bm], axis=1, keys=["s", "b"]).dropna()
        if not joined.empty:
            win_vs_bm = float((joined["s"] > joined["b"]).mean() * 100)
    def _rows(s):
        return [{"month": str(i), "ret_pct": float(v)} for i, v in s.items()]
    return {
        "win_rate": float((m > 0).mean() * 100),
        "win_rate_vs_bm": win_vs_bm,
        "best": _rows(m.nlargest(5)),
        "worst": _rows(m.nsmallest(5)),
    }


def turnover_stats(rebal: pd.DataFrame) -> dict:
    """리밸 이력(long)에서 회전율 재료. 첫 리밸은 전액 매수로 계산 — 엔진과 동일."""
    if rebal.empty:
        return {"n_rebals": 0, "rebals_per_year": None, "avg_turnover": None}
    wide = rebal.pivot_table(index="rebal_date", columns="ticker", values="weight", aggfunc="sum")
    wide = wide.sort_index().fillna(0.0)
    prev = wide.shift(1).fillna(0.0)
    turnover = (wide - prev).abs().sum(axis=1)
    years = max((wide.index[-1] - wide.index[0]).days / 365.25, 1 / 365.25)
    n = len(wide)
    return {
        "n_rebals": int(n),
        "rebals_per_year": float(n / years) if n > 1 else None,
        "avg_turnover": float(turnover.mean()),
    }


def live_percentile(bt_nav: pd.Series, live_nav: pd.Series):
    """저장 후 실전 성과의 '백테스트 동일 기간 분포 내 위치'. 표본 부족 시 None."""
    n = len(live_nav) - 1
    if n < 5 or len(bt_nav) < n + 60:  # 최소 60개 분포 표본
        return None
    live_ret = float(live_nav.iloc[-1] / live_nav.iloc[0] - 1)
    roll = (bt_nav / bt_nav.shift(n) - 1).dropna()
    if len(roll) < 60:
        return None
    live_dd = float(live_nav.iloc[-1] / live_nav.cummax().iloc[-1] - 1)
    bt_dd = (bt_nav / bt_nav.cummax() - 1).dropna()
    return {
        "n_days": int(n),
        "live_ret_pct": live_ret * 100,
        "ret_percentile": float((roll < live_ret).mean() * 100),
        "live_dd_pct": live_dd * 100,
        "dd_percentile": float((bt_dd < live_dd).mean() * 100),
    }


def crisis_returns(nav: pd.Series, windows: dict) -> list:
    """고정 위기 구간 수익 — 이력이 구간 시작을 덮을 때만 (portfolio_risk와 동일 규칙)."""
    out = []
    for key, (w0, w1) in windows.items():
        if nav.index.min() > pd.Timestamp(w0):
            out.append({"key": key, "ret_pct": None, "note": "이력이 구간을 덮지 못함"})
            continue
        sub = nav.loc[w0:w1]
        if len(sub) < 2:
            out.append({"key": key, "ret_pct": None, "note": "구간 내 데이터 부족"})
            continue
        out.append(
            {"key": key, "ret_pct": float((sub.iloc[-1] / sub.iloc[0] - 1) * 100), "note": None}
        )
    return out


def phase_monthly_means(monthly: pd.Series, phases: pd.Series) -> pd.DataFrame:
    """국면별 월수익 평균 — 인덱스 교집합만 (레짐 결측 월 제외)."""
    joined = pd.concat([monthly.rename("ret"), phases.rename("phase")], axis=1).dropna()
    g = joined.groupby("phase")["ret"]
    return pd.DataFrame({"mean_ret_pct": g.mean(), "n_months": g.size()})
```

- [ ] **Step 4: GREEN + 전체 스위트** — 신규 9개 + 기존 63 유지.

- [ ] **Step 5: Commit** — `feat(analytics): 전략 분석 순수 지표 — 낙폭 해부·롤링·백분위·턴오버`

---

### Task 2: P7 `live_weights` 저장

**Files:**
- Modify: `scripts/build_insights.py` (`build_track_strategies`), `server/datastore/portfolio.py` (`_EMPTY` + 리더)

**Interfaces:**
- Consumes: P7이 이미 계산하는 `book` (backtest_result 반환 — 현재 버려짐)
- Produces: `portfolio/live_weights.parquet` [port_id, trade_date, ticker, weight, as_of] 전 이력 + `portfolio.live_weights(port_id) -> pd.DataFrame` 리더. Phase 2 ②⑤의 소스.

- [ ] **Step 1**: `portfolio.py` — `_EMPTY["live_weights.parquet"] = ["port_id", "trade_date", "ticker", "weight", "as_of"]`, 리더:

```python
def live_weights(port_id: int) -> pd.DataFrame:
    """실전 추적 드리프트 보유 비중 (P7 생성) — [trade_date, ticker, weight]."""
    df = _read("live_weights.parquet", filters=[("port_id", "==", port_id)])
    return df[["trade_date", "ticker", "weight"]].sort_values(["trade_date", "ticker"]).reset_index(drop=True)
```

- [ ] **Step 2**: `build_track_strategies` — 엔진 결과에서 book을 받아 프레임 누적, 함수 끝에서 **직접 기록** (한 빌더가 두 산출물 — nav는 main() 경유, weights는 직접; rebal_signals의 빈-케이스 직접 기록 전례). book의 반환 형태(backtest_result의 book: Date 인덱스 long [ticker, weights])를 열어 확인하고 [port_id, trade_date, ticker, weight] long으로 정규화 + `as_of`. 전략 루프 실패 시 해당 전략 weights도 스킵 (nav와 동일 스킵 단위). 저장 직전 `print(f"[live_weights] {len(df)}행")`.

- [ ] **Step 3**: 검증 — 실데이터로 `build_track_strategies()` 호출(반환만으로는 weights가 직접 기록되므로 **tmp APP_DATA 불가** — S3 쓰기 금지 원칙과 충돌): 기록 경로를 함수 인자 `write_weights=True` 기본으로 두되 검증 스니펫에서는 monkeypatch로 `storage.write_parquet`를 가로채 프레임만 검사한다 (S3 무변경). port 1 weights 마지막 날짜 == live_nav 마지막 날짜, 일별 비중 합 ≈ 1(현금 제외 시 ≤1) 확인, 출력 리포트 첨부.

- [ ] **Step 4**: 전체 스위트 + Commit — `feat(batch): P7 드리프트 보유 비중(live_weights) 저장`

---

### Task 3: `GET /backtest/strategy/analytics/{port_id}` + live 확장 + 계약 테스트

**Files:**
- Modify: `server/app/routers/backtest.py`
- Test: `server/tests/test_strategy_analytics_api.py`

**Interfaces:**
- Consumes: Task 1 모듈 전부, `portfolio.nav/benchmark_nav/rebalance/records/live_nav/live_weights`, `regime.phase_history()`, `portfolio_risk.CRISIS_WINDOWS`
- Produces (Phase 2 프론트 계약):

```
GET /backtest/strategy/analytics/{port_id} →
{
  premise: {algorithm, rebal_freq, cost_bps, currency, universe_n, saved_at,
            bt_start, bt_end, bt_days, n_rebals, cost_warning: bool(cost_bps==0)},
  rolling: {window, rows: [{date, roll_ret, roll_sharpe}], bm_rows: [...] | null} | null(+note),
  drawdowns: {underwater: [{date, dd_pct}](주간 다운샘플), episodes: [...]} ,
  phases: {rows: [{phase, mean_ret_pct, n_months, bm_mean_ret_pct|null}]} | null,
  crisis: [{key, ret_pct, note}],
  monthly: {win_rate, win_rate_vs_bm, best, worst},
  trading: {n_rebals, rebals_per_year, avg_turnover, cost_drag_pct_10bps, cost_drag_pct_30bps},
  as_of: bt_end
}

GET /backtest/strategy/live/{port_id} 기존 응답에 추가:
  weights: [{trade_date, ticker, weight}] (최근일만) | null,
  expectation: live_percentile 결과 | null
```

- [ ] **Step 1: 계약 테스트 먼저** — 픽스처 parquet(tmp APP_DATA) + `regime.phase_history` monkeypatch로: 정상 경로 키 전부 존재·cost_warning 로직·rolling null(이력<252) 계약·crisis 규칙, live 확장은 live_nav/weights 픽스처로 expectation 키·weights 최근일 필터 검증. 404(모르는 포트) 아닌 `{empty: true}` 반환 (이 페이지 소비 전용 — 500 금지 계약).

- [ ] **Step 2: 구현** — 라우터는 로드·조인·반올림만. phases: `regime.phase_history()["phase"]`의 인덱스(Period M)와 `monthly_returns` 조인 → `phase_monthly_means` (전략·BM 각각). underwater는 주간 다운샘플(`resample("W-FRI").last()` 패턴 — insight 라우터 관례). rolling에 BM 동일 창 병기(bm_nav 있으면). try/except 섹션 단위 — 한 섹션 실패는 그 키만 null.

- [ ] **Step 3**: 전체 스위트 + 실데이터 검증 (port 1 analytics 호출 — 출력 리포트 첨부, 낙폭 에피소드가 상식적인지·국면 행이 4개 이하인지 확인) + Commit — `feat(api): 전략 분석 엔드포인트 — 투입 판정 재료`

---

### Task 4: 통합 검증

- [ ] 전체 스위트 + 실데이터 analytics/live 응답 확인 (port 1·port 3), 스펙 상태 줄에 `백엔드 구현 완료 (Phase 1)` 추가. Commit — `docs: 분석 백엔드 Phase 1 완료 기록`. 머지·배포·Phase 2(프론트) 플랜은 컨트롤러가 사용자 게이트에서.
