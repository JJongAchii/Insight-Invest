# 포트폴리오 리스크 카드 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `GET /holdings/risk` + `/portfolio`의 `RiskCard` — 현재 보유 비중을 고정했을 때의 역사적 변동성·최대낙폭·상관·급락 시나리오를 사실 그대로 보여준다.

**Architecture:** 순수 계산은 `server/module/portfolio_risk.py`(TDD), 라우터는 기존 holdings 헬퍼(build_price_map·usdkrw)와 `Backtest().data()`·`fx.to_krw`로 조립만, 프론트는 RTK Query + 기존 카드 프리미티브. 스펙: `docs/superpowers/specs/2026-08-03-portfolio-risk-design.md`.

**Tech Stack:** Python 3.12 (pandas/numpy, FastAPI, pytest), Next.js 14 + RTK Query + Tailwind.

## Global Constraints

- **판단 라벨 금지** — "위험 높음/낮음" 없음. 수치 + 전제(`basis`) + 경고만.
- **500 금지** — holdings 비면 `{"empty": true}`, 공통 이력 < **60일**이면 `{"insufficient": true, "overlap_days": N}`. 부분 실패(가격 없는 종목)는 경고와 함께 진행.
- 모든 시나리오는 "현재 비중을 그 구간에 고정 적용했다면"의 반사실 — 라벨·문구에 명시.
- 고정 위기 구간: `covid_2020 = ("2020-02-14", "2020-03-23")`. **전 종목 이력이 구간 시작을 덮을 때만** 계산 (부분집합 재정규화 금지), 아니면 `ret_pct: null` + note.
- 가격은 KRW 환산(US는 `fx.to_krw`) — holdings 평가와 동일 기준. 수익률·낙폭은 adj_close 기반(`Backtest.data`가 adj_close 반환).
- 상관은 보유 ≥2종목일 때만 (`corr: null` otherwise).
- `fetchHoldingsRisk`는 `providesTags: ["Holdings"]` — 보유 추가/삭제 시 자동 재계산.
- 서버 테스트: `cd server && .venv-test/bin/python -m pytest tests/ -v`. 커밋은 conventional commits 한국어 본문, pre-commit(black 100, isort) 통과. 작업 브랜치 `feat/portfolio-risk` (스펙 커밋됨).

---

### Task 1: `server/module/portfolio_risk.py` 순수 계산 (TDD)

**Files:**
- Create: `server/module/portfolio_risk.py`
- Test: `server/tests/test_portfolio_risk.py`

**Interfaces:**
- Consumes: pandas/numpy만.
- Produces (Task 2가 사용):
  - `MIN_OVERLAP_DAYS = 60`, `SCENARIO_LABELS: dict[str, str]`
  - `clean_panel(prices: pd.DataFrame) -> pd.DataFrame` — 선두를 전 종목 공통 시점으로 절단 + ffill
  - `build_report(prices: pd.DataFrame, weights: dict[str, float]) -> dict` — 키: `insufficient?`, `overlap_days`, `ann_vol`, `max_drawdown`, `mdd_from`, `mdd_to`, `avg_pair_corr`, `corr(pd.DataFrame|None)`, `scenarios(list[dict])`, `window{start,end}` (raw float — 반올림은 라우터)

- [ ] **Step 1: 실패하는 테스트 작성**

`server/tests/test_portfolio_risk.py`:

```python
"""portfolio_risk 순수 계산 — 손계산 픽스처 검증.

고정비중 포트 수익률·MDD·시나리오 윈도우는 틀려도 에러 없이 그럴듯한
숫자가 나오는 지점이다. 2종목 50:50 손계산과 대조해 못박는다.
"""

import numpy as np
import pandas as pd
import pytest

from module.portfolio_risk import (
    MIN_OVERLAP_DAYS,
    build_report,
    clean_panel,
)


def _panel(values: dict, start="2022-01-03") -> pd.DataFrame:
    n = len(next(iter(values.values())))
    return pd.DataFrame(values, index=pd.bdate_range(start, periods=n))


def test_two_asset_hand_math():
    # A: +10% 후 보합, B: 보합 후 -10% → 50:50 rp = [+5%, -5%]
    p = _panel({"A": [100.0, 110.0, 110.0], "B": [100.0, 100.0, 90.0]})
    r = build_report(p, {"A": 0.5, "B": 0.5})
    # 검증엔 MIN_OVERLAP 미달이지만 로직 검증용으로 임계 우회
    assert r.get("insufficient")  # 기본 임계에서는 생략된다

    r = build_report(p, {"A": 0.5, "B": 0.5}, min_overlap=2)
    # rp = [0.05, -0.05]; NAV = [1.05, 0.9975]; MDD = 0.9975/1.05-1 = -5%
    assert r["max_drawdown"] == pytest.approx(-5.0, rel=1e-6)
    # ann_vol = std([0.05,-0.05], ddof=1) * sqrt(252) * 100
    expected_vol = float(np.std([0.05, -0.05], ddof=1) * np.sqrt(252) * 100)
    assert r["ann_vol"] == pytest.approx(expected_vol, rel=1e-9)
    assert r["mdd_from"] < r["mdd_to"]
    # 2종목 상관: 수익률 [0.1,0]/[0,-0.1] → corr = -1
    assert r["avg_pair_corr"] == pytest.approx(-1.0, rel=1e-9)
    assert r["corr"].shape == (2, 2)


def test_single_asset_skips_corr():
    p = _panel({"A": list(np.linspace(100, 130, 80))})
    r = build_report(p, {"A": 1.0}, min_overlap=10)
    assert r["corr"] is None and r["avg_pair_corr"] is None
    assert r["ann_vol"] is not None


def test_worst_window_finds_injected_crash():
    # 250일 보합 + 중간 20일 연속 -2% 구간 주입
    rets = [0.0] * 100 + [-0.02] * 20 + [0.0] * 130
    prices = 100 * np.cumprod([1.0] + [1 + x for x in rets[1:]])
    p = _panel({"A": list(prices), "B": list(prices)})
    r = build_report(p, {"A": 0.5, "B": 0.5}, min_overlap=10)
    worst20 = next(s for s in r["scenarios"] if s["key"] == "worst_20d")
    assert worst20["ret_pct"] == pytest.approx(((0.98 ** 20) - 1) * 100, rel=1e-6)
    # 최악 구간의 끝은 주입 구간 안이다
    assert p.index[100] <= pd.Timestamp(worst20["end"]) <= p.index[125]


def test_crisis_window_requires_full_coverage():
    # 2021년 시작 이력 → covid_2020 계산 불가 (null + note)
    p = _panel(
        {"A": list(np.linspace(100, 120, 300)), "B": list(np.linspace(50, 60, 300))},
        start="2021-01-04",
    )
    r = build_report(p, {"A": 0.5, "B": 0.5}, min_overlap=10)
    covid = next(s for s in r["scenarios"] if s["key"] == "covid_2020")
    assert covid["ret_pct"] is None and covid["note"]


def test_crisis_window_computed_when_covered():
    idx = pd.bdate_range("2019-06-03", periods=400)
    a = pd.Series(100.0, index=idx)
    # covid 구간에만 매일 -1%
    win = (idx >= "2020-02-14") & (idx <= "2020-03-23")
    daily = np.where(win, 0.99, 1.0)
    a = pd.Series(100 * np.cumprod(daily), index=idx)
    p = pd.DataFrame({"A": a, "B": a})
    r = build_report(p, {"A": 0.5, "B": 0.5}, min_overlap=10)
    covid = next(s for s in r["scenarios"] if s["key"] == "covid_2020")
    n_win = int(win.sum())
    assert covid["ret_pct"] == pytest.approx(((0.99 ** n_win) - 1) * 100, rel=1e-6)


def test_clean_panel_trims_leading_and_ffills_frozen():
    # B는 늦게 상장(선두 NaN), C는 중간에 동결(후행 NaN → ffill로 0수익)
    a = list(np.linspace(100, 110, 100))
    b = [np.nan] * 30 + list(np.linspace(50, 55, 70))
    c = list(np.linspace(200, 210, 60)) + [np.nan] * 40
    p = clean_panel(_panel({"A": a, "B": b, "C": c}))
    assert p.index[0] == _panel({"A": a}).index[30]  # 공통 시작 = B 상장일
    assert not p.isna().any().any()  # 동결 구간은 ffill로 채워짐
    assert p["C"].iloc[-1] == p["C"].iloc[-41]  # 동결 가격 평탄화 (경고는 라우터 몫)
```

- [ ] **Step 2: 실패 확인**

Run: `cd server && .venv-test/bin/python -m pytest tests/test_portfolio_risk.py -q`
Expected: `ModuleNotFoundError: No module named 'module.portfolio_risk'`

- [ ] **Step 3: 구현**

`server/module/portfolio_risk.py`:

```python
"""포트폴리오 리스크 — 고정 현재비중의 역사적 위험 특성 (순수 계산).

라우터(holdings.py)가 가격(KRW 환산 완료)·비중을 조립해 넘기고, 여기는
pandas 계산만 한다. 모든 수치는 '현재 비중을 과거에 고정 적용했다면'이라는
반사실 위에 있다 — 실제 과거 실적이 아니다 (매일 리밸런싱 가정).
동결·정지 이력은 clean_panel의 ffill로 0수익 평탄화되는데, 이는 변동성을
과소평가한다 — 감지와 경고는 라우터가 한다 (조용히 계산하지 않는다).
"""

import numpy as np
import pandas as pd

MIN_OVERLAP_DAYS = 60  # 공통 이력이 이보다 짧으면 위험 수치 전체 생략
ROLL_WINDOWS = (20, 60)  # 최악 롤링 탐색 창 (거래일)
RECENT_DAYS = 20
MIN_CRISIS_DAYS = 15  # 고정 구간 내 최소 거래일 — 미달이면 계산하지 않는다
# 고정 위기 구간 — 전 종목 이력이 구간 시작을 덮을 때만 계산한다. 일부 종목만
# 덮는 경우 비중 재정규화는 조용히 다른 포트폴리오를 재는 것이라 금지.
CRISIS_WINDOWS = {"covid_2020": ("2020-02-14", "2020-03-23")}

SCENARIO_LABELS = {
    "recent_20d": "최근 20거래일 (진행 중)",
    "worst_20d": "역사적 최악 20거래일",
    "worst_60d": "역사적 최악 60거래일",
    "covid_2020": "코로나 급락 재현 (2020-02~03)",
}


def clean_panel(prices: pd.DataFrame) -> pd.DataFrame:
    """선두는 전 종목 공통 시점으로 절단, 이후 결측은 ffill.

    ffill은 상폐·동결 이력을 0수익으로 평탄화한다 — 위험 과소평가 방향이므로
    호출부가 stale 감지와 경고를 반드시 병행한다.
    """
    starts = [c.first_valid_index() for _, c in prices.items()]
    starts = [s for s in starts if s is not None]
    if not starts:
        return prices.iloc[0:0]
    return prices.loc[max(starts) :].ffill()


def portfolio_returns(prices: pd.DataFrame, weights: dict) -> pd.Series:
    """고정비중 일별 포트 수익률 — r_p(t) = Σ w_i · r_i(t)."""
    rets = prices.pct_change(fill_method=None)
    w = pd.Series(weights, dtype="float64").reindex(prices.columns).fillna(0.0)
    return rets.mul(w, axis=1).sum(axis=1).iloc[1:]


def _scenario_row(key: str, sub: pd.Series) -> dict:
    return {
        "key": key,
        "label": SCENARIO_LABELS[key],
        "ret_pct": float(((1 + sub).prod() - 1) * 100),
        "start": str(sub.index.min().date()),
        "end": str(sub.index.max().date()),
        "note": None,
    }


def _null_row(key: str, note: str) -> dict:
    return {
        "key": key,
        "label": SCENARIO_LABELS[key],
        "ret_pct": None,
        "start": None,
        "end": None,
        "note": note,
    }


def scenario_rows(rp: pd.Series) -> list:
    rows = [_scenario_row("recent_20d", rp.tail(RECENT_DAYS))]
    for k in ROLL_WINDOWS:
        key = f"worst_{k}d"
        if len(rp) < k:
            rows.append(_null_row(key, f"이력 {len(rp)}일 — {k}일 창 미달"))
            continue
        roll = (1 + rp).rolling(k).apply(np.prod, raw=True) - 1
        end = roll.idxmin()
        rows.append(_scenario_row(key, rp.loc[:end].tail(k)))
    for key, (w0, w1) in CRISIS_WINDOWS.items():
        if rp.index.min() > pd.Timestamp(w0):
            rows.append(_null_row(key, "보유 종목 이력이 구간을 덮지 못함"))
            continue
        sub = rp.loc[w0:w1]
        if len(sub) < MIN_CRISIS_DAYS:
            rows.append(_null_row(key, "구간 내 거래일 부족"))
        else:
            rows.append(_scenario_row(key, sub))
    return rows


def build_report(prices: pd.DataFrame, weights: dict, min_overlap: int = MIN_OVERLAP_DAYS) -> dict:
    prices = clean_panel(prices)
    if len(prices) < min_overlap + 1:
        return {"insufficient": True, "overlap_days": int(len(prices))}

    rp = portfolio_returns(prices, weights)
    nav = (1 + rp).cumprod()
    dd = nav / nav.cummax() - 1
    trough = dd.idxmin()
    peak = nav.loc[:trough].idxmax()

    corr, avg_corr = None, None
    if prices.shape[1] >= 2:
        corr = prices.pct_change(fill_method=None).iloc[1:].corr()
        off = corr.where(~np.eye(len(corr), dtype=bool)).stack()
        avg_corr = float(off.mean()) if not off.empty else None

    return {
        "overlap_days": int(len(prices)),
        "ann_vol": float(rp.std() * np.sqrt(252) * 100),
        "max_drawdown": float(dd.min() * 100),
        "mdd_from": str(peak.date()),
        "mdd_to": str(trough.date()),
        "avg_pair_corr": avg_corr,
        "corr": corr,
        "scenarios": scenario_rows(rp),
        "window": {"start": str(prices.index.min().date()), "end": str(prices.index.max().date())},
    }
```

- [ ] **Step 4: 통과 확인**

Run: `cd server && .venv-test/bin/python -m pytest tests/test_portfolio_risk.py -q`
Expected: 6개 전부 PASS. 이후 전체 스위트 1회.

- [ ] **Step 5: Commit**

```bash
git add server/module/portfolio_risk.py server/tests/test_portfolio_risk.py
git commit -m "feat(risk): 고정비중 포트폴리오 위험 계산 순수 모듈

변동성·MDD·상관·시나리오(최근/최악 롤링/코로나 재현)를 손계산 픽스처로
못박는다. 고정 위기 구간은 전 종목 이력이 덮을 때만 계산 — 부분집합
재정규화는 조용히 다른 포트폴리오가 된다."
```

---

### Task 2: `GET /holdings/risk` 라우터 조립 + 계약 테스트

**Files:**
- Modify: `server/app/routers/holdings.py`
- Test: `server/tests/test_holdings_risk_api.py`

**Interfaces:**
- Consumes: Task 1의 `build_report`/`MIN_OVERLAP_DAYS`, 기존 `holdings_store.list_items`·`meta.meta_df`·`build_price_map`·`_usdkrw_latest`·`_r`, `module.backtest.Backtest`, `datastore.fx.to_krw`, `qdata_api.load_krx_prices`
- Produces: `GET /holdings/risk` 응답 (Task 3 프론트가 소비):
  `{empty?} | {insufficient, overlap_days, warnings} | {ann_vol, max_drawdown, mdd_from, mdd_to, avg_pair_corr, corr:{tickers,names,values}|null, scenarios:[{key,label,ret_pct,start,end,note}], warnings:[{kind,ticker,detail}], basis:{n_assets,weights_as_of,window}}`

- [ ] **Step 1: 실패하는 계약 테스트 작성**

`server/tests/test_holdings_risk_api.py`:

```python
"""GET /holdings/risk 계약 — 빈 보유 시 empty, 정상 경로의 응답 형태.

무거운 실데이터 경로는 Task 4 통합 검증이 맡고, 여기는 조립 계약만 픽스처로
고정한다 (spotlight API 테스트와 같은 monkeypatch 패턴).
"""

import numpy as np
import pandas as pd
import pytest

import app.routers.holdings as h


def test_risk_empty_holdings(monkeypatch):
    monkeypatch.setattr(
        h.holdings_store, "list_items", lambda: pd.DataFrame(columns=h.holdings_store._EMPTY)
    )
    assert h.get_holdings_risk() == {"empty": True}


@pytest.fixture()
def two_holdings(monkeypatch):
    items = pd.DataFrame(
        {
            "meta_id": [1, 2],
            "shares": [10.0, 20.0],
            "avg_cost": [90.0, 40.0],
            "currency": ["KRW", "KRW"],
        }
    )
    md = pd.DataFrame(
        {
            "meta_id": [1, 2],
            "ticker": ["000001", "000002"],
            "name": ["가나", "다라"],
            "iso_code": ["KR", "KR"],
            "security_type": ["stock", "stock"],
            "sector": ["기타", "기타"],
        }
    )
    monkeypatch.setattr(h.holdings_store, "list_items", lambda: items)
    monkeypatch.setattr(h.meta, "meta_df", lambda: md)
    # 최신가: A 100원 × 10주 = 1000, B 50원 × 20주 = 1000 → 50:50
    monkeypatch.setattr(
        h, "build_price_map", lambda df: {1: (100.0, 0.0), 2: (50.0, 0.0)}
    )
    monkeypatch.setattr(h, "_usdkrw_latest", lambda: 1400.0)

    idx = pd.bdate_range("2023-01-02", periods=300)
    prices = pd.DataFrame(
        {
            "000001": np.linspace(80, 100, 300),
            "000002": np.linspace(60, 50, 300),
        },
        index=idx,
    )

    class FakeBT:
        def data(self, meta_id=None, start_date=None, **kw):
            return prices

    monkeypatch.setattr(h, "Backtest", FakeBT)
    monkeypatch.setattr(h.fx, "to_krw", lambda df, iso: df)  # KR만 — 환산 무변화
    monkeypatch.setattr(h, "_recent_kr_volume", lambda tickers: pd.DataFrame())
    return items


def test_risk_shape_and_weights(two_holdings):
    r = h.get_holdings_risk()
    assert "empty" not in r and "insufficient" not in r
    assert r["basis"]["n_assets"] == 2
    assert set(s["key"] for s in r["scenarios"]) == {
        "recent_20d", "worst_20d", "worst_60d", "covid_2020",
    }
    covid = next(s for s in r["scenarios"] if s["key"] == "covid_2020")
    assert covid["ret_pct"] is None  # 2023년 시작 이력 — 커버 불가
    assert r["corr"]["tickers"] == ["000001", "000002"]
    assert r["corr"]["names"] == ["가나", "다라"]
    assert isinstance(r["ann_vol"], float)
    # 가격 조회 실패 종목 경고 경로
    assert isinstance(r["warnings"], list)


def test_risk_excludes_priceless_position(two_holdings, monkeypatch):
    monkeypatch.setattr(h, "build_price_map", lambda df: {1: (100.0, 0.0), 2: (None, None)})
    r = h.get_holdings_risk()
    assert r["basis"]["n_assets"] == 1
    assert r["corr"] is None  # 단일 종목 — 상관 생략
    assert any(w["kind"] == "no_price" for w in r["warnings"])
```

- [ ] **Step 2: 실패 확인**

Run: `cd server && .venv-test/bin/python -m pytest tests/test_holdings_risk_api.py -q`
Expected: `AttributeError` (`get_holdings_risk` / `_recent_kr_volume` 없음)

- [ ] **Step 3: 라우터 구현**

`server/app/routers/holdings.py` — import 블록에 추가 (isort가 정렬):

```python
from datastore import fx
from module import portfolio_risk
from module.backtest import Backtest
from qdata import api as qdata_api
```

(기존 `from datastore import fx, meta`가 이미 fx를 들여오면 그대로 두고 나머지만 추가.)

파일 하단에 추가:

```python
# ---------- 위험 요약 ----------

RISK_HISTORY_START = "2019-06-03"  # covid_2020 창 + 워밍업 여유
STALE_CAL_DAYS = 7  # 패널 마지막 날짜보다 이보다 오래 뒤처지면 동결 의심
HALT_ROWS = 5  # 최근 N행 거래량 합 0 → 거래정지 의심 (spotlight와 같은 기준)


def _recent_kr_volume(tickers: list) -> pd.DataFrame:
    """최근 ~3주 KR 거래량 패널 (일자×티커). 실패 시 빈 프레임 — 경고만 포기."""
    try:
        start = (pd.Timestamp.today() - pd.Timedelta(days=21)).strftime("%Y-%m-%d")
        px = qdata_api.load_krx_prices(start=start, columns=["volume"])
        px = px[px["ticker"].isin(tickers)]
        return px.pivot(index="date", columns="ticker", values="volume")
    except Exception:
        logger.debug("risk 거래량 조회 실패 — 정지 경고 생략", exc_info=True)
        return pd.DataFrame()


@router.get("/risk")
def get_holdings_risk():
    """보유 조합의 역사적 위험 요약 — 현재 비중 고정 가정 (module/portfolio_risk).

    판단 라벨 없음 — 수치·전제·데이터 경고만. holdings 비면 empty, 공통 이력
    부족이면 insufficient. 어느 경로든 500을 내지 않는다.
    """
    items = holdings_store.list_items()
    if items.empty:
        return {"empty": True}

    md = meta.meta_df()[_META_COLS]
    df = items.merge(md, on="meta_id", how="left")
    price_map = build_price_map(df[["meta_id", "ticker", "iso_code"]])
    usdkrw = _usdkrw_latest()

    warnings: list = []
    mv: dict = {}
    tickers_iso: dict = {}
    names: dict = {}
    for r in df.itertuples():
        ticker = _none_if_na(r.ticker)
        price, _chg = price_map.get(int(r.meta_id), (None, None))
        fxrate = usdkrw if r.iso_code == "US" else 1.0
        if ticker is None or price is None or fxrate is None:
            warnings.append(
                {"kind": "no_price", "ticker": ticker, "detail": "가격 조회 실패 — 위험 계산에서 제외"}
            )
            continue
        mv[ticker] = mv.get(ticker, 0.0) + float(r.shares) * price * fxrate
        tickers_iso[ticker] = r.iso_code
        names[ticker] = _none_if_na(r.name) or ticker

    total = sum(mv.values())
    if not mv or total <= 0:
        return {"empty": True, "reason": "평가 가능한 포지션 없음"}
    weights = {t: v / total for t, v in mv.items()}

    prices = Backtest().data(
        meta_id=[int(x) for x in df["meta_id"]], start_date=RISK_HISTORY_START
    )
    prices = prices[[c for c in prices.columns if c in weights]]
    missing = sorted(set(weights) - set(prices.columns))
    for t in missing:
        warnings.append({"kind": "no_history", "ticker": t, "detail": "가격 이력 없음 — 제외"})
        weights.pop(t)
    if not weights:
        return {"empty": True, "reason": "가격 이력 있는 포지션 없음"}
    total_w = sum(weights.values())
    weights = {t: w / total_w for t, w in weights.items()}
    prices = fx.to_krw(prices, tickers_iso)

    # 데이터 품질 경고 — 조용히 계산하지 않는다 (동결·정지는 위험 과소평가 방향)
    panel_end = prices.index.max()
    for t in prices.columns:
        last = prices[t].last_valid_index()
        if last is not None and (panel_end - last).days > STALE_CAL_DAYS:
            warnings.append(
                {"kind": "stale", "ticker": t,
                 "detail": f"가격 이력이 {last.date()}에서 멈춤 — 이후 변동 미반영"}
            )
    kr = [t for t, iso in tickers_iso.items() if iso == "KR" and t in prices.columns]
    vol = _recent_kr_volume(kr)
    for t in kr:
        if t in vol.columns and len(vol) >= HALT_ROWS and float(vol[t].tail(HALT_ROWS).sum()) == 0:
            warnings.append(
                {"kind": "halted", "ticker": t,
                 "detail": "최근 5일 거래량 0 — 동결 가격이 변동성·상관을 과소평가"}
            )

    report = portfolio_risk.build_report(prices, weights)
    if report.get("insufficient"):
        return {
            "insufficient": True,
            "overlap_days": report["overlap_days"],
            "warnings": warnings,
        }
    if report["overlap_days"] < 250:
        warnings.append(
            {"kind": "short_history", "ticker": None,
             "detail": f"공통 가격 이력 {report['overlap_days']}일 — 최근 상장 종목이 분석 구간을 절단"}
        )

    corr = report["corr"]
    corr_payload = None
    if corr is not None:
        order = list(corr.columns)
        corr_payload = {
            "tickers": order,
            "names": [names.get(t, t) for t in order],
            "values": [[_r(corr.loc[a, b], 2) for b in order] for a in order],
        }

    return {
        "ann_vol": _r(report["ann_vol"], 1),
        "max_drawdown": _r(report["max_drawdown"], 1),
        "mdd_from": report["mdd_from"],
        "mdd_to": report["mdd_to"],
        "avg_pair_corr": _r(report["avg_pair_corr"], 2),
        "corr": corr_payload,
        "scenarios": [
            {**s, "ret_pct": _r(s["ret_pct"], 1)} for s in report["scenarios"]
        ],
        "warnings": warnings,
        "basis": {
            "n_assets": len(weights),
            "weights_as_of": date.today().isoformat(),
            "overlap_days": report["overlap_days"],
            "window": report["window"],
        },
    }
```

주의: `holdings.py`에 이미 `from datetime import date`가 있는지 확인하고 없으면 추가. `pd`는 이미 임포트돼 있다.

- [ ] **Step 4: 통과 확인 + 전체 스위트**

Run: `cd server && .venv-test/bin/python -m pytest tests/ -q`
Expected: 전부 PASS (기존 + 신규 9개).

- [ ] **Step 5: Commit**

```bash
git add server/app/routers/holdings.py server/tests/test_holdings_risk_api.py
git commit -m "feat(api): GET /holdings/risk — 보유 조합 위험 요약

기존 부품(build_price_map·usdkrw·Backtest.data·fx.to_krw) 조립 + 데이터
품질 경고(동결·정지·이력 부족). 빈 보유 empty, 이력 부족 insufficient —
500 금지."
```

---

### Task 3: 프론트 — api.ts + `RiskCard` + 페이지 배치

**Files:**
- Modify: `client/src/state/api.ts` (Holdings 타입들 옆, holdings 엔드포인트들 옆, export 블록)
- Create: `client/src/app/portfolio/RiskCard.tsx`
- Modify: `client/src/app/portfolio/page.tsx`

**Interfaces:**
- Consumes: Task 2 응답 스키마
- Produces: `useFetchHoldingsRiskQuery` 훅, `HoldingsRiskResponse` 타입, 카드 컴포넌트

- [ ] **Step 1: api.ts 타입** (`HoldingMutationResponse` 인터페이스 근처에 추가)

```ts
// Types for the portfolio risk card (GET /holdings/risk)
export interface RiskScenario {
  key: string;
  label: string;
  ret_pct: number | null;
  start: string | null;
  end: string | null;
  note: string | null;
}

export interface RiskWarning {
  kind: string;
  ticker: string | null;
  detail: string;
}

export interface RiskCorr {
  tickers: string[];
  names: string[];
  values: (number | null)[][];
}

export interface HoldingsRiskResponse {
  empty?: boolean;
  reason?: string;
  insufficient?: boolean;
  overlap_days?: number;
  ann_vol?: number | null;
  max_drawdown?: number | null;
  mdd_from?: string;
  mdd_to?: string;
  avg_pair_corr?: number | null;
  corr?: RiskCorr | null;
  scenarios?: RiskScenario[];
  warnings?: RiskWarning[];
  basis?: {
    n_assets: number;
    weights_as_of: string;
    overlap_days: number;
    window: { start: string; end: string };
  };
}
```

- [ ] **Step 2: api.ts 엔드포인트 + 훅** (`fetchHoldings` 정의 근처)

```ts
    fetchHoldingsRisk: builder.query<HoldingsRiskResponse, void>({
      query: () => "/holdings/risk",
      providesTags: ["Holdings"],  // 보유 추가/삭제 시 자동 재계산
    }),
```

export 블록의 `useFetchHoldingsQuery,` 다음 줄에 `useFetchHoldingsRiskQuery,` 추가.

- [ ] **Step 3: RiskCard 컴포넌트**

`client/src/app/portfolio/RiskCard.tsx`:

```tsx
"use client";

import React from "react";

import {
  RiskCorr,
  useFetchHoldingsRiskQuery,
} from "@/state/api";
import Card from "@/components/ui/Card";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";
import InfoTip from "@/components/ui/InfoTip";

const fmtPct = (v: number | null | undefined, digits = 1): string =>
  v == null ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(digits)}%`;

const signColor = (v: number | null | undefined) =>
  v == null ? undefined : v >= 0 ? "var(--gains)" : "var(--losses)";

const Tile: React.FC<{ label: React.ReactNode; value: string; sub?: string }> = ({
  label,
  value,
  sub,
}) => (
  <div className="flex-1 min-w-[140px] p-3 rounded-xl border border-edge bg-surface">
    <div className="text-xs text-ink-muted mb-1">{label}</div>
    <div className="text-lg font-semibold text-ink num">{value}</div>
    {sub && <div className="text-xs text-ink-muted mt-0.5">{sub}</div>}
  </div>
);

const CorrHeatmap: React.FC<{ corr: RiskCorr }> = ({ corr }) => (
  <div className="overflow-x-auto">
    <table className="text-xs num">
      <thead>
        <tr>
          <th />
          {corr.names.map((n) => (
            <th key={n} className="px-1.5 py-1 font-normal text-ink-muted max-w-[72px] truncate">
              {n}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {corr.names.map((rowName, i) => (
          <tr key={rowName}>
            <td className="pr-2 py-1 text-ink-muted max-w-[96px] truncate">{rowName}</td>
            {corr.values[i].map((v, j) => (
              <td
                key={j}
                className="px-1.5 py-1 text-center text-ink"
                style={{
                  backgroundColor:
                    v == null || i === j
                      ? "transparent"
                      : `color-mix(in srgb, var(--chart-1) ${Math.round(
                          Math.abs(v) * 55
                        )}%, transparent)`,
                }}
              >
                {i === j ? "·" : v == null ? "—" : v.toFixed(2)}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

/** 위험 요약 — 현재 비중을 과거에 고정 적용했다면의 반사실 수치.
 *  판단 라벨 없음: 수치·전제·데이터 경고만 (스펙 §3). */
const RiskCard: React.FC = () => {
  const { data, isLoading, error, refetch } = useFetchHoldingsRiskQuery();

  if (error)
    return (
      <Card title="위험 요약">
        <ErrorState message="위험 정보를 불러오지 못했습니다" onRetry={refetch} />
      </Card>
    );
  if (isLoading || !data)
    return (
      <Card title="위험 요약">
        <LoadingState label="위험 지표 계산 중..." />
      </Card>
    );
  if (data.empty) return null;
  if (data.insufficient)
    return (
      <Card title="위험 요약">
        <p className="text-sm text-ink-muted">
          공통 가격 이력이 {data.overlap_days}일뿐이라 위험 지표를 계산하지 않습니다 (최소 60일).
        </p>
      </Card>
    );

  return (
    <Card
      title="위험 요약"
      subtitle={`현재 비중 고정 가정 · ${data.basis?.window.start} ~ ${data.basis?.window.end}`}
    >
      <div className="flex flex-wrap gap-3">
        <Tile label="연환산 변동성" value={fmtPct(data.ann_vol)} />
        <Tile
          label="최대 낙폭"
          value={fmtPct(data.max_drawdown)}
          sub={`${data.mdd_from} ~ ${data.mdd_to}`}
        />
        <Tile
          label={
            <span className="inline-flex items-center gap-1">
              평균 상관
              <InfoTip text="보유 종목 일수익률 상관의 평균 — 1에 가까울수록 같이 움직여 분산 효과가 없다" />
            </span>
          }
          value={data.avg_pair_corr == null ? "—" : data.avg_pair_corr.toFixed(2)}
        />
      </div>

      <div className="mt-4">
        <h4 className="text-sm font-medium text-ink mb-2">
          시나리오 <span className="text-xs text-ink-muted">(현재 비중을 각 구간에 적용했다면)</span>
        </h4>
        <div className="flex flex-col gap-1.5">
          {(data.scenarios ?? []).map((s) => (
            <div key={s.key} className="flex items-baseline gap-2 text-sm">
              <span className="text-ink-secondary w-56 shrink-0">{s.label}</span>
              <span className="num font-medium" style={{ color: signColor(s.ret_pct) }}>
                {fmtPct(s.ret_pct)}
              </span>
              <span className="text-xs text-ink-muted truncate">
                {s.note ?? (s.start && s.end ? `${s.start} ~ ${s.end}` : "")}
              </span>
            </div>
          ))}
        </div>
      </div>

      {data.corr && (
        <div className="mt-4">
          <h4 className="text-sm font-medium text-ink mb-2">상관 히트맵</h4>
          <CorrHeatmap corr={data.corr} />
        </div>
      )}

      {(data.warnings ?? []).length > 0 && (
        <div className="mt-4 flex flex-col gap-1">
          {(data.warnings ?? []).map((w, i) => (
            <p key={i} className="text-xs" style={{ color: "var(--chart-4)" }}>
              ⚠ {w.ticker ? `${w.ticker} — ` : ""}{w.detail}
            </p>
          ))}
        </div>
      )}
    </Card>
  );
};

export default RiskCard;
```

주의: `Card` 컴포넌트의 props(title/subtitle/children)를 먼저 확인하고, 다르면 페이지의 기존 카드 사용 방식(AllocationCard가 Card를 어떻게 쓰는지)에 맞춘다 — 마크업 구조는 유지.

- [ ] **Step 4: 페이지 배치**

`client/src/app/portfolio/page.tsx` — `import RiskCard from "./RiskCard";` 추가, 본문에서 `<AllocationCard` 블록 바로 다음(FactorExposureCard 앞)에 `<RiskCard />` 배치. 기존 그리드/스택 구조를 따른다.

- [ ] **Step 5: 검증 + Commit**

Run: `cd client && npx tsc --noEmit && npm run lint`
Expected: 에러 0.

```bash
git add client/src/state/api.ts client/src/app/portfolio/RiskCard.tsx client/src/app/portfolio/page.tsx
git commit -m "feat(client): 포트폴리오 위험 요약 카드

변동성·MDD·평균상관 타일 + 반사실 시나리오 + 상관 히트맵 + 데이터 경고.
Holdings 태그 구독으로 보유 변경 시 자동 재계산."
```

---

### Task 4: 통합 검증 + 문서 갱신

**Files:**
- Modify: `docs/superpowers/specs/2026-08-03-portfolio-risk-design.md` (상태 줄)

**Interfaces:** Task 1~3 전부.

- [ ] **Step 1: 실데이터 통합 검증**

로컬 uvicorn을 S3 데이터로 띄우고 실제 보유로 응답을 확인한다:

```bash
cd /Users/achii/Quant/Insight-Invest/server && \
QDATA_LAKE=s3://insight-invest-datalake/qdata APP_DATA=s3://insight-invest-datalake/app \
.venv-test/bin/python -c "
from app.routers import holdings
import json
r = holdings.get_holdings_risk()
print(json.dumps(r, ensure_ascii=False, indent=1, default=str)[:3000])
"
```

Expected: 실제 보유 기준 JSON. 확인 항목 — (1) 500/예외 없음, (2) `recent_20d`가 진행 중 급락을 반영해 큰 음수인지, (3) US 개별주 보유 시 `stale` 경고가 실제로 붙는지, (4) `basis.window`가 상식적인지. 출력을 리포트에 붙인다.

- [ ] **Step 2: 전체 테스트 + 프론트 최종 확인**

`cd server && .venv-test/bin/python -m pytest tests/ -q` 전부 PASS, `cd client && npx tsc --noEmit` 에러 0.

- [ ] **Step 3: 스펙 상태 갱신 + Commit**

스펙 상태 줄 → `- 상태: 구현 완료 (2026-08-03)`.

```bash
git add docs/superpowers/specs/2026-08-03-portfolio-risk-design.md
git commit -m "docs: 포트폴리오 리스크 카드 스펙 상태 갱신"
```

- [ ] **Step 4: 머지·배포는 컨트롤러가 사용자 확인 후 진행** (finishing-a-development-branch)
