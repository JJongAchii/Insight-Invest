# US 가격 소스 일원화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** US 가격을 yfinance 이원 소스에서 qdata massive 미러 단일 소스로 전환 — 야간 배치가 총수익 계열을 합성해 앱 `us_prices.parquet`를 재생성하고, 서빙은 단일 경로가 된다.

**Architecture:** 스펙 `docs/superpowers/specs/2026-08-04-us-price-source-unification-design.md`. 배치(P0 신설)가 미러에서 meta US 티커(~6,700)를 추출·합성 → 앱 플레인 재생성, Lambda 는 기존 아카이브 경로 코드로 그 파일을 읽는다. 순수 계산(TR 합성·세그먼트 스티칭·연속성 가드)은 `server/module/us_prices.py` 신설 모듈에 TDD 로 만든다.

**Tech Stack:** pandas + pyarrow(필터 푸시다운), qdata api (S3 미러), 기존 배치 파이프라인(BUILDERS).

## Global Constraints

- 앱 파일 스키마 불변: `[meta_id, trade_date, ticker, adj_close, gross_return]` (+ `as_of` — 파이프라인 로그용). `gross_return` = 단순수익률(pct_change 의미), 시계열 첫 행 NaN.
- 플로어: `US_PRICE_FLOOR = "2008-01-02"` (스펙 D4 — 배당 신뢰 구간).
- TR 합성식 (스펙 D3, 그대로): `F_t = adj_close_t/close_t`, `div_adj_t = Σ cash_amount(ex_date=t) × F_t`, `r_t = (adj_close_t + div_adj_t)/adj_close_{t-1} − 1`, TR 계열은 최신 관측치 앵커로 역누적.
- 세그먼트 (스펙 D5, 그대로): `TICKER_SEGMENTS = {"QQQ": [("QQQ", None, "2004-11-30"), ("QQQQ", "2004-12-01", "2011-03-22"), ("QQQ", "2011-03-23", None)]}`.
- 연속성 가드 상수: `GAP_LIMIT_TDAYS = 10`(관측 간 영업일), `JUMP_LIMIT = 0.25`(분할 계수 변동 없는 날). 걸린 티커는 **경고 로그 + 제외** — 조용한 소실 금지.
- 미러 접근 실패 시 빌더는 `None` 반환(기존 파일 유지) + 경고 — 500 금지의 배치판.
- 테스트: `cd server && .venv-test/bin/python -m pytest tests/ -q` 전체 그린 (매 태스크).
- 커밋: conventional commits 한국어. Task 0 은 quant-data 레포에 커밋, 나머지는 Insight-Invest `feat/us-price-unification` 브랜치.

---

### Task 0: qdata `load_us_dividends` API (quant-data 레포)

**Files:**
- Modify: `~/Quant/quant-data/src/qdata/api.py` (`load_us_prices` 바로 아래)
- Test: quant-data 의 기존 API 테스트 파일 (`grep -rn "load_us_prices" tests/` 로 찾아 같은 파일·같은 픽스처 관례를 따른다)

**Interfaces:**
- Produces: `qdata.api.load_us_dividends(start: str|None=None, end: str|None=None, tickers: list[str]|None=None) -> pd.DataFrame` — clean `us_dividends` long `[ticker, ex_date, cash_amount, currency, dividend_type, frequency, pay_date, record_date, asof]`, ex_date 기준 start/end·tickers 푸시다운. Task 3 빌더가 호출.

- [ ] **Step 1: 실패하는 테스트 작성** — 기존 `load_us_prices` 테스트의 임시 레이크 픽스처 관례를 그대로 따라 작성 (아래는 로직, 픽스처 구성은 기존 테스트 파일 방식 우선):

```python
def test_load_us_dividends_filters(tmp_lake):  # tmp_lake: 기존 관례의 QDATA_LAKE 픽스처
    df = pd.DataFrame({
        "ticker": ["SPY", "SPY", "SHY"],
        "ex_date": pd.to_datetime(["2026-03-20", "2026-06-18", "2026-06-02"]),
        "cash_amount": [1.797, 1.9035, 0.31],
        "currency": "USD", "dividend_type": "CD", "frequency": 4,
        "pay_date": pd.NaT, "record_date": pd.NaT, "asof": pd.Timestamp("2026-08-04"),
    })
    df.to_parquet(tmp_lake / "clean" / "us_dividends.parquet", index=False)
    out = api.load_us_dividends(start="2026-06-01", tickers=["SPY"])
    assert out["ticker"].unique().tolist() == ["SPY"]
    assert len(out) == 1 and out.iloc[0]["cash_amount"] == 1.9035
```

- [ ] **Step 2: 실패 확인** — quant-data 의 테스트 러너로 해당 테스트만 실행. Expected: `AttributeError: load_us_dividends`
- [ ] **Step 3: 구현** (`load_us_prices` 와 동일 계약 — `_us_filters`/`_read_clean` 재사용):

```python
def load_us_dividends(
    start: str | None = None,
    end: str | None = None,
    tickers: list[str] | None = None,
) -> pd.DataFrame:
    """US 현금분배 이력 long [ticker, ex_date, cash_amount, ...] (ex_date 기준 필터).

    원액면이다 — cash_amount 는 그날 주수 기준이라 분할 조정 계열과 합성하려면
    소비자가 그날의 수정계수를 곱해야 한다 (ADR-0007 D6: TR 구성은 소비자 몫).
    """
    filters = _us_filters(start, end, "ex_date", "ticker", tickers)
    df = _read_clean(lake_root(), "us_dividends", "qdata us actions", filters=filters or None)
    return df.reset_index(drop=True)
```

- [ ] **Step 4: 테스트 통과 확인 + quant-data 전체 테스트 그린**
- [ ] **Step 5: Commit** (quant-data 레포): `feat(api): load_us_dividends — US 분배금 조회 (ex_date 푸시다운)`

---

### Task 1: `server/module/us_prices.py` — TR 합성·세그먼트 스티칭·연속성 가드 (TDD)

**Files:**
- Create: `server/module/us_prices.py`
- Test: `server/tests/test_us_prices_module.py`

**Interfaces:**
- Produces (Task 3·4 가 사용):
  - `TICKER_SEGMENTS: dict[str, list[tuple[str, str | None, str | None]]]` (Global Constraints 값 그대로)
  - `GAP_LIMIT_TDAYS = 10`, `JUMP_LIMIT = 0.25`
  - `stitch_segments(prices: pd.DataFrame, dividends: pd.DataFrame, segments) -> tuple[pd.DataFrame, pd.DataFrame]` — prices long `[date, ticker, close, adj_close]`, dividends long `[ticker, ex_date, cash_amount]` (여분 컬럼 허용). 세그먼트 소스 행을 날짜 경계로 잘라 현행 티커로 개명·병합. 겹침이면 `ValueError`.
  - `compose_total_return(px: pd.DataFrame, div: pd.DataFrame) -> pd.DataFrame` — 단일 티커. px 는 date 인덱스 정렬·columns close/adj_close, div 는 `[ex_date, cash_amount]`(같은 날 복수 행 합산). 반환 `[adj_close, gross_return]` (date 인덱스; adj_close = 최신 관측 앵커 TR 계열).
  - `continuity_issues(px: pd.DataFrame) -> list[str]` — 단일 티커 (date 인덱스 정렬). 빈 리스트 = 통과.

- [ ] **Step 1: 실패하는 테스트 작성** (`server/tests/test_us_prices_module.py`):

```python
"""US 가격 순수 계산 — TR 합성·세그먼트 스티칭·연속성 가드 손계산 픽스처."""
import numpy as np
import pandas as pd
import pytest

from module.us_prices import (
    GAP_LIMIT_TDAYS, compose_total_return, continuity_issues, stitch_segments,
)


def _px(dates, close, adj_close):
    idx = pd.to_datetime(dates)
    return pd.DataFrame({"close": close, "adj_close": adj_close}, index=idx)


def test_tr_dividend_day():
    """배당락일 r = (adj + div×F)/prev − 1. 무분할이라 F=1."""
    px = _px(["2026-01-05", "2026-01-06", "2026-01-07"], [100.0, 102.0, 100.0], [100.0, 102.0, 100.0])
    div = pd.DataFrame({"ex_date": pd.to_datetime(["2026-01-07"]), "cash_amount": [2.0]})
    out = compose_total_return(px, div)
    assert np.isnan(out["gross_return"].iloc[0])
    assert out["gross_return"].iloc[1] == pytest.approx(0.02)
    assert out["gross_return"].iloc[2] == pytest.approx((100.0 + 2.0) / 102.0 - 1)
    # 앵커: 최신 adj_close(TR) = 원 adj_close 최신값
    assert out["adj_close"].iloc[-1] == pytest.approx(100.0)
    # 역누적: 전일 TR = 최신 / (1+r_최신)
    assert out["adj_close"].iloc[1] == pytest.approx(100.0 / ((100.0 + 2.0) / 102.0))


def test_tr_split_day_dividend_scaled():
    """2:1 분할 이전 배당은 당시 주수 기준 → F(=0.5) 로 현재 기준 환산."""
    px = _px(
        ["2026-01-05", "2026-01-06", "2026-01-07"],
        [100.0, 102.0, 52.0],   # 1/7 에 2:1 분할 (원주가 반토막)
        [50.0, 51.0, 52.0],     # 분할 조정 계열은 연속
    )
    div = pd.DataFrame({"ex_date": pd.to_datetime(["2026-01-06"]), "cash_amount": [1.0]})
    out = compose_total_return(px, div)
    # 1/6: F=51/102=0.5 → div_adj=0.5 → r=(51+0.5)/50−1=3.0%
    assert out["gross_return"].iloc[1] == pytest.approx(0.03)
    # 1/7 분할일 자체는 가짜 점프 없음
    assert out["gross_return"].iloc[2] == pytest.approx(52.0 / 51.0 - 1)


def test_special_dividend_same_day_summed():
    px = _px(["2026-01-05", "2026-01-06"], [100.0, 100.0], [100.0, 100.0])
    div = pd.DataFrame({
        "ex_date": pd.to_datetime(["2026-01-06", "2026-01-06"]),
        "cash_amount": [1.0, 10.0],  # 정규 + 특별
    })
    out = compose_total_return(px, div)
    assert out["gross_return"].iloc[1] == pytest.approx(11.0 / 100.0)


def test_no_dividends_is_price_return():
    px = _px(["2026-01-05", "2026-01-06"], [100.0, 103.0], [100.0, 103.0])
    out = compose_total_return(px, pd.DataFrame({"ex_date": [], "cash_amount": []}))
    assert out["gross_return"].iloc[1] == pytest.approx(0.03)


def _long(ticker, dates, price):
    return pd.DataFrame({
        "date": pd.to_datetime(dates), "ticker": ticker,
        "close": price, "adj_close": price,
    })


def test_stitch_qqq_like_three_segments():
    prices = pd.concat([
        _long("QQQ", ["2004-11-29", "2004-11-30"], [36.0, 36.5]),
        _long("QQQQ", ["2004-12-01", "2011-03-22"], [36.6, 55.4]),
        _long("QQQ", ["2011-03-23", "2011-03-24"], [55.7, 56.7]),
        _long("SPY", ["2004-11-29"], [120.0]),  # 무관 티커는 그대로
    ])
    divs = pd.DataFrame({
        "ticker": ["QQQQ", "SPY"],
        "ex_date": pd.to_datetime(["2005-04-25", "2004-12-17"]),
        "cash_amount": [0.1, 0.5],
    })
    segments = {"QQQ": [("QQQ", None, "2004-11-30"), ("QQQQ", "2004-12-01", "2011-03-22"),
                        ("QQQ", "2011-03-23", None)]}
    p, d = stitch_segments(prices, divs, segments)
    qqq = p[p.ticker == "QQQ"].sort_values("date")
    assert len(qqq) == 6 and "QQQQ" not in set(p.ticker)
    assert not qqq["date"].duplicated().any()
    assert d[d.ticker == "QQQ"]["cash_amount"].tolist() == [0.1]  # QQQQ 배당이 QQQ 로
    assert d[d.ticker == "SPY"]["cash_amount"].tolist() == [0.5]


def test_stitch_overlap_raises():
    prices = pd.concat([
        _long("META", ["2022-06-08", "2022-06-09"], [1.5, 184.0]),
        _long("FB", ["2022-06-08", "2022-06-09"], [183.0, 184.0]),
    ])
    segments = {"META": [("FB", None, "2022-06-08"), ("META", "2022-06-08", None)]}  # 하루 겹침
    with pytest.raises(ValueError, match="겹침"):
        stitch_segments(prices, prices.rename(columns={"date": "ex_date"}), segments)


def test_continuity_gap_flagged():
    idx = list(pd.bdate_range("2026-01-05", periods=5)) + list(pd.bdate_range("2026-03-02", periods=5))
    px = _px(idx, [100.0] * 10, [100.0] * 10)
    issues = continuity_issues(px)
    assert len(issues) == 1 and "공백" in issues[0]


def test_continuity_jump_without_factor_change_flagged():
    px = _px(pd.bdate_range("2026-01-05", periods=3), [100.0, 140.0, 141.0], [100.0, 140.0, 141.0])
    issues = continuity_issues(px)
    assert len(issues) == 1 and "40%" in issues[0]


def test_continuity_split_day_not_flagged():
    """진짜 분할: adj_close 연속·close 점프·F 변동 → 무경고."""
    px = _px(pd.bdate_range("2026-01-05", periods=3), [100.0, 102.0, 51.5], [50.0, 51.0, 51.5])
    assert continuity_issues(px) == []


def test_continuity_clean_passes():
    px = _px(pd.bdate_range("2026-01-05", periods=30), [100.0] * 30, [100.0] * 30)
    assert continuity_issues(px) == []
```

- [ ] **Step 2: 실패 확인** — Run: `cd server && .venv-test/bin/python -m pytest tests/test_us_prices_module.py -q`. Expected: `ModuleNotFoundError: module.us_prices`
- [ ] **Step 3: 구현** (`server/module/us_prices.py`):

```python
"""US 가격 순수 계산 — massive 미러 기반 총수익 합성·세그먼트 스티칭·연속성 가드.

스펙: docs/superpowers/specs/2026-08-04-us-price-source-unification-design.md D3·D5.
massive adj_close 는 분할만 조정, 배당은 us_dividends 원액면(당시 주수 기준) —
그날의 수정계수 F 를 곱해 현재 주수 기준으로 환산한 뒤 총수익을 합성한다.
"""

import numpy as np
import pandas as pd

# 같은 티커에 다른 실체가 살았던 구간을 날짜 경계로 잇는다 (QQQQ 시대 1,588거래일).
# 단순 합집합이면 META 처럼 남의 회사 구간까지 끌려온다 — 반드시 경계를 명시한다.
TICKER_SEGMENTS: dict[str, list[tuple[str, str | None, str | None]]] = {
    "QQQ": [("QQQ", None, "2004-11-30"), ("QQQQ", "2004-12-01", "2011-03-22"),
            ("QQQ", "2011-03-23", None)],
}

GAP_LIMIT_TDAYS = 10  # 관측 간 영업일 공백 상한 — 초과는 티커 재배정·수집 구멍 신호
JUMP_LIMIT = 0.25     # 분할 계수 변동 없는 날의 일수익 상한 — 초과는 계보 오염 신호


def _cut(df: pd.DataFrame, col: str, src: str, start: str | None, end: str | None) -> pd.DataFrame:
    m = df["ticker"] == src
    if start:
        m &= df[col] >= pd.Timestamp(start)
    if end:
        m &= df[col] <= pd.Timestamp(end)
    return df[m]


def stitch_segments(prices, dividends, segments):
    """세그먼트 대상 티커의 가격·배당 행을 날짜 경계로 잘라 현행 티커로 병합."""
    for final, segs in segments.items():
        p_parts = [_cut(prices, "date", s, a, b).assign(ticker=final) for s, a, b in segs]
        d_parts = [_cut(dividends, "ex_date", s, a, b).assign(ticker=final) for s, a, b in segs]
        stitched = pd.concat(p_parts, ignore_index=True)
        if stitched["date"].duplicated().any():
            raise ValueError(f"{final}: 세그먼트 겹침 — 경계 날짜 재확인 필요")
        involved = {s for s, _, _ in segs} | {final}
        prices = pd.concat(
            [prices[~prices["ticker"].isin(involved)], stitched], ignore_index=True
        )
        dividends = pd.concat(
            [dividends[~dividends["ticker"].isin(involved)],
             pd.concat(d_parts, ignore_index=True)],
            ignore_index=True,
        )
    return prices, dividends


def compose_total_return(px: pd.DataFrame, div: pd.DataFrame) -> pd.DataFrame:
    """단일 티커 TR 합성 — r_t = (adj_t + div_t×F_t)/adj_{t-1} − 1.

    adj_close(TR)는 최신 관측치를 앵커로 역누적 — 최신값이 원 adj_close 와 같아
    기존 소비자(모멘텀·NAV)와 연속적이다. 첫 행 gross_return 은 NaN (pct_change 관례).
    """
    f = px["adj_close"] / px["close"]
    cash = (
        div.groupby("ex_date")["cash_amount"].sum().reindex(px.index).fillna(0.0)
        if len(div)
        else pd.Series(0.0, index=px.index)
    )
    r = (px["adj_close"] + cash * f) / px["adj_close"].shift(1) - 1
    growth = (1 + r.fillna(0.0)).cumprod()
    tr = px["adj_close"].iloc[-1] * growth / growth.iloc[-1]
    return pd.DataFrame({"adj_close": tr, "gross_return": r})


def continuity_issues(px: pd.DataFrame) -> list[str]:
    """티커 계보 오염 감지 — 공백(영업일)·무분할 점프. 빈 리스트 = 통과."""
    issues: list[str] = []
    d = px.index.values.astype("datetime64[D]")
    if len(d) > 1:
        gaps = np.busday_count(d[:-1], d[1:])
        if gaps.max() > GAP_LIMIT_TDAYS:
            i = int(gaps.argmax())
            issues.append(
                f"공백 {int(gaps.max())}영업일 ({px.index[i].date()}→{px.index[i+1].date()})"
            )
    r = px["adj_close"].pct_change().abs()
    f_changed = (px["adj_close"] / px["close"]).pct_change().abs() > 0.005
    for dt, v in r[(r > JUMP_LIMIT) & ~f_changed].items():
        issues.append(f"{dt.date()} |일수익| {v:.0%} (분할 계수 변동 없음)")
    return issues
```

- [ ] **Step 4: 통과 확인** — Run: `cd server && .venv-test/bin/python -m pytest tests/test_us_prices_module.py -q`. Expected: 전부 PASS
- [ ] **Step 5: Commit**: `feat(us_prices): TR 합성·세그먼트 스티칭·연속성 가드 순수 모듈`

---

### Task 2: `datastore/prices.py` 단일 경로 + wide 헬퍼 + 소비자 전환

**Files:**
- Modify: `server/datastore/prices.py` (US fresh/stale 분기 제거, 헬퍼 추가)
- Modify: `server/module/regime.py:62-65` (`_hyg_ief`)
- Modify: `server/datastore/index_prices.py:31-33, 49-52` (SPY·60_40)
- Delete: `server/tests/test_prices_fresh_set.py` (fresh-set 로직 자체가 사라짐)
- Test: `server/tests/test_us_prices_path.py` (신규)

**Interfaces:**
- Consumes: 없음 (앱 `us_prices.parquet` 는 Task 3 이 재생성하지만, 스키마가 기존 아카이브와 동일해 이 태스크는 독립 배포 가능)
- Produces: `datastore.prices.us_adj_close_wide(tickers: list[str], start_date=None, end_date=None) -> pd.DataFrame` — datetime 인덱스 × 티커 컬럼의 adj_close wide. `read_price_data` 계약 불변.

- [ ] **Step 1: 실패하는 테스트 작성** (`server/tests/test_us_prices_path.py`) — 기존 테스트들의 monkeypatch 관례(`tests/` 안의 `storage.read_parquet` 패치 사례를 grep 으로 확인)를 따른다:

```python
"""US 가격 서빙 단일 경로 — 앱 us_prices.parquet 하나만 읽는다 (fresh/stale 분기 제거)."""
import pandas as pd
import pytest

from datastore import prices


@pytest.fixture
def fake_us_file(monkeypatch):
    df = pd.DataFrame({
        "meta_id": [1, 1, 55, 55],
        "trade_date": pd.to_datetime(["2026-01-05", "2026-01-06"] * 2),
        "ticker": ["SPY", "SPY", "SHY", "SHY"],
        "adj_close": [500.0, 505.0, 82.0, 82.1],
        "gross_return": [float("nan"), 0.01, float("nan"), 82.1 / 82.0 - 1],
    })
    def fake_read(name, columns=None, filters=None):
        assert name == "us_prices.parquet"
        return df[columns] if columns else df
    monkeypatch.setattr(prices.storage, "read_parquet", fake_read)
    monkeypatch.setattr(
        prices.meta, "resolve",
        lambda meta_ids=None, tickers=None: pd.DataFrame(
            {"meta_id": [1, 55], "ticker": ["SPY", "SHY"], "iso_code": "US"}
        ),
    )
    return df


def test_read_price_data_us_single_source(fake_us_file):
    out = prices.read_price_data("US", tickers=["SPY", "SHY"])
    assert list(out.columns) == ["meta_id", "trade_date", "ticker", "adj_close", "gross_return"]
    assert set(out.ticker) == {"SPY", "SHY"}
    assert out.equals(out.sort_values(["ticker", "trade_date"]).reset_index(drop=True))


def test_us_adj_close_wide(fake_us_file):
    wide = prices.us_adj_close_wide(["SPY", "SHY"])
    assert list(wide.columns) == ["SHY", "SPY"] or list(wide.columns) == ["SPY", "SHY"]
    assert wide.loc[pd.Timestamp("2026-01-06"), "SPY"] == 505.0


def test_no_yfinance_table_dependency():
    """fresh-set 경로가 완전히 사라졌는지 — 심볼 자체가 없어야 한다."""
    assert not hasattr(prices, "_qdata_us_tickers")
    assert not hasattr(prices, "_us_fresh_prices")
```

- [ ] **Step 2: 실패 확인** — Run: `cd server && .venv-test/bin/python -m pytest tests/test_us_prices_path.py -q`. Expected: FAIL (`us_adj_close_wide` 없음, fresh-set 심볼 존재)
- [ ] **Step 3: 구현** — `datastore/prices.py`:
  - `_qdata_us_tickers`·`_us_fresh_prices` 삭제, `lru_cache` import 정리
  - `_us_archive_prices` → `_us_prices` 로 개명 (본문 동일 — 컬럼·필터 계약 유지), 모듈 docstring 의 소스 설명을 "US: 배치가 massive 미러에서 재생성하는 앱 `us_prices.parquet` (총수익 계열, 매일 갱신)" 으로 교체
  - `read_price_data` US 분기를 `out = _us_prices(mapping, start_date, end_date)` 한 줄로
  - 헬퍼 추가:

```python
def us_adj_close_wide(
    tickers: list[str], start_date: date | None = None, end_date: date | None = None
) -> pd.DataFrame:
    """US adj_close(총수익 계열) wide — datetime 인덱스 × 티커 컬럼."""
    df = read_price_data("US", tickers=tickers, start_date=start_date, end_date=end_date)
    if df.empty:
        return pd.DataFrame()
    return df.pivot(index="trade_date", columns="ticker", values="adj_close").sort_index()
```

  - `module/regime.py` — `_hyg_ief` 를 앱 파일 기반으로 (lru_cache 유지):

```python
@lru_cache(maxsize=1)
def _hyg_ief() -> pd.DataFrame:
    from datastore import prices

    return prices.us_adj_close_wide(["HYG", "IEF"])
```

  - `datastore/index_prices.py` — `qdata_api.load_prices` 두 곳을 교체 (import 에 `from datastore import prices` 추가; `qdata_api` import 는 KRX 지수용으로 유지):

```python
    if name == "SPY":
        wide = prices.us_adj_close_wide(["SPY"], start_date=start, end_date=end)
        s = wide["SPY"].dropna() if not wide.empty else pd.Series(dtype=float)
        s.name = name
        return s
```

```python
        price = prices.us_adj_close_wide(["SPY", "IEF"], start_date=start, end_date=end).dropna()
```

- [ ] **Step 4: 기존 테스트 파장 수습** — `grep -rn "load_prices\|_qdata_us_tickers\|us_fresh" server/tests/` 로 monkeypatch 하던 테스트를 찾아 새 경로(`prices.us_adj_close_wide` 또는 `storage.read_parquet`)로 패치 대상을 바꾼다. `tests/test_prices_fresh_set.py` 는 삭제.
- [ ] **Step 5: 전체 통과 확인** — Run: `cd server && .venv-test/bin/python -m pytest tests/ -q`. Expected: 전부 PASS
- [ ] **Step 6: Commit**: `refactor(prices): US 서빙 단일 경로 — yfinance 테이블·fresh/stale 분기 제거`

---

### Task 3: 배치 빌더 `build_us_prices` (P0)

**Files:**
- Modify: `scripts/build_insights.py` (빌더 함수 + BUILDERS 첫 항목 등록 + `US_PRICE_FLOOR` 상수)
- Test: `server/tests/test_us_prices_builder.py` (신규 — `tests/test_live_weights_builder.py` 의 build_insights 임포트·픽스처 관례를 그대로 따른다)

**Interfaces:**
- Consumes: `qdata_api.load_us_prices` / `load_us_dividends` (Task 0), `module.us_prices` 의 `TICKER_SEGMENTS`·`stitch_segments`·`compose_total_return`·`continuity_issues` (Task 1), `meta.meta_df()`, 기존 `_as_of()`.
- Produces: 앱 `us_prices.parquet` `[meta_id, trade_date, ticker, adj_close, gross_return, as_of]` — Task 2 의 서빙 경로가 읽는 파일.

- [ ] **Step 1: 실패하는 테스트 작성** (`server/tests/test_us_prices_builder.py`) — build_insights 모듈을 `test_live_weights_builder.py` 와 같은 방식으로 로드한 뒤:

```python
def _fake_mirror(monkeypatch, bi, px_long, div_long, meta_df):
    monkeypatch.setattr(bi.qdata_api, "load_us_prices",
                        lambda start=None, end=None, tickers=None, columns=None:
                        px_long[(px_long.date >= start) & (px_long.date <= end)].copy())
    monkeypatch.setattr(bi.qdata_api, "load_us_dividends",
                        lambda start=None, end=None, tickers=None: div_long.copy())
    monkeypatch.setattr(bi.meta, "meta_df", lambda: meta_df)


def test_builder_schema_and_meta_join(monkeypatch, bi, capsys):
    dates = pd.bdate_range("2026-01-05", periods=3)
    px = pd.DataFrame({"date": list(dates) * 1, "ticker": "SPY",
                       "close": [500.0, 505.0, 500.0], "adj_close": [500.0, 505.0, 500.0]})
    div = pd.DataFrame({"ticker": ["SPY"], "ex_date": [dates[2]], "cash_amount": [2.0]})
    meta_df = pd.DataFrame({"meta_id": [1], "ticker": ["SPY"], "iso_code": ["US"]})
    _fake_mirror(monkeypatch, bi, px, div, meta_df)
    out = bi.build_us_prices()
    assert list(out.columns) == ["meta_id", "trade_date", "ticker", "adj_close", "gross_return", "as_of"]
    assert out["gross_return"].iloc[2] == pytest.approx((500.0 + 2.0) / 505.0 - 1)
    # 픽스처가 과거 날짜이므로 신선도 경고(§5)가 함께 발화해야 한다
    assert "미러 최종일" in capsys.readouterr().err


def test_builder_guard_excludes_with_warning(monkeypatch, bi, capsys):
    """40% 점프 티커는 제외 + 경고, 나머지는 살아남는다 — 조용한 소실 금지."""
    dates = pd.bdate_range("2026-01-05", periods=3)
    px = pd.concat([
        pd.DataFrame({"date": dates, "ticker": "GOOD", "close": [100.0, 101.0, 102.0],
                      "adj_close": [100.0, 101.0, 102.0]}),
        pd.DataFrame({"date": dates, "ticker": "BAD", "close": [1.0, 1.0, 100.0],
                      "adj_close": [1.0, 1.0, 100.0]}),
    ])
    meta_df = pd.DataFrame({"meta_id": [1, 2], "ticker": ["GOOD", "BAD"], "iso_code": ["US", "US"]})
    _fake_mirror(monkeypatch, bi, px, pd.DataFrame({"ticker": [], "ex_date": [], "cash_amount": []}), meta_df)
    out = bi.build_us_prices()
    assert set(out.ticker) == {"GOOD"}
    assert "연속성 가드" in capsys.readouterr().err


def test_builder_returns_none_on_mirror_failure(monkeypatch, bi, capsys):
    """미러 읽기 실패 → None (기존 파일 유지) + 경고. 예외가 새어 나가면 안 된다."""
    meta_df = pd.DataFrame({"meta_id": [1], "ticker": ["SPY"], "iso_code": ["US"]})
    monkeypatch.setattr(bi.meta, "meta_df", lambda: meta_df)  # 실 S3 접근 차단

    def boom(**kwargs):
        raise OSError("s3 down")

    monkeypatch.setattr(bi.qdata_api, "load_us_prices", boom)
    assert bi.build_us_prices() is None
    assert "기존 파일 유지" in capsys.readouterr().err
```

- [ ] **Step 2: 실패 확인** — Run: `cd server && .venv-test/bin/python -m pytest tests/test_us_prices_builder.py -q`. Expected: `AttributeError: build_us_prices`
- [ ] **Step 3: 구현** — `scripts/build_insights.py` 에 추가 (기존 import 블록에 `from qdata import api as qdata_api` 가 이미 있는지 확인, 없으면 추가):

```python
US_PRICE_FLOOR = "2008-01-02"  # 스펙 D4 — 배당 축 신뢰 구간 (ETF 분배금 2007 중반부터)


def build_us_prices():
    """US 가격 앱 추출 (P0) — massive 미러에서 meta US 티커의 총수익 계열 재생성.

    스펙 docs/superpowers/specs/2026-08-04-us-price-source-unification-design.md §3.
    미러 읽기 실패 시 None 반환 → 기존 us_prices.parquet 유지 (경고만 — 하류 빌더는
    어제 데이터로 진행). 연속성 가드 제외·배당락 소실은 반드시 경고 로그로 남긴다.
    """
    from module import us_prices as uspx

    try:
        m = meta.meta_df()
        us = m[m["iso_code"] == "US"][["meta_id", "ticker"]].drop_duplicates("ticker")
        seg_src = {s for segs in uspx.TICKER_SEGMENTS.values() for s, _, _ in segs}
        want = sorted(set(us["ticker"]) | seg_src)

        frames = []
        for y in range(int(US_PRICE_FLOOR[:4]), pd.Timestamp.today().year + 1):
            chunk = qdata_api.load_us_prices(
                start=max(f"{y}-01-01", US_PRICE_FLOOR), end=f"{y}-12-31",
                tickers=want, columns=["close", "adj_close"],
            )
            if not chunk.empty:
                frames.append(chunk)
        px = pd.concat(frames, ignore_index=True)
        px["date"] = pd.to_datetime(px["date"])
        div = qdata_api.load_us_dividends(tickers=want)
        div["ex_date"] = pd.to_datetime(div["ex_date"])
        px, div = uspx.stitch_segments(px, div, uspx.TICKER_SEGMENTS)
    except Exception:
        print("[warn] us_prices: 미러 읽기 실패 — 기존 파일 유지", file=sys.stderr)
        traceback.print_exc()
        return None

    stale_days = (pd.Timestamp.today().normalize() - px["date"].max()).days
    if stale_days > 4:
        print(f"[warn] us_prices: 미러 최종일 {px['date'].max().date()} ({stale_days}일 경과) — "
              "리밸 신호는 is_new_period 가 자연 스킵", file=sys.stderr)

    out, skipped, lost_div = [], [], 0.0
    for tk, g in px.groupby("ticker", sort=False):
        g = g.sort_values("date").set_index("date")
        issues = uspx.continuity_issues(g)
        if issues:
            skipped.append(f"{tk}({'; '.join(issues[:2])})")
            continue
        dv = div[div["ticker"] == tk]
        lost_div += float(dv.loc[~dv["ex_date"].isin(g.index), "cash_amount"].sum())
        res = uspx.compose_total_return(g, dv)
        res = res.reset_index().rename(columns={"date": "trade_date"})
        res["ticker"] = tk
        out.append(res)

    if skipped:
        print(f"[warn] us_prices: 연속성 가드 제외 {len(skipped)}종목 — {skipped[:20]}",
              file=sys.stderr)
    if lost_div:
        print(f"[warn] us_prices: 비거래일 배당락 소실 합계 ${lost_div:.2f}", file=sys.stderr)

    df = pd.concat(out, ignore_index=True).merge(us, on="ticker", how="inner")
    missing = sorted(set(us["ticker"]) - set(df["ticker"]))
    if missing:
        print(f"[warn] us_prices: meta 등록 but 미수록 {len(missing)}종목 "
              "(플로어 이전 상폐·미러 부재·가드 제외)", file=sys.stderr)
    df = df[["meta_id", "trade_date", "ticker", "adj_close", "gross_return"]]
    df = df.sort_values(["ticker", "trade_date"]).reset_index(drop=True)
    df["as_of"] = _as_of()
    return df
```

  - BUILDERS **맨 앞**에 등록 (P0 — 다른 빌더가 이 파일을 읽는다):

```python
BUILDERS = [
    ("us_prices.parquet", build_us_prices, {"row_group_size": 100_000}),  # P0: US 가격 앱 추출
    ("insight/regime_asset_perf.parquet", build_regime_asset_perf, {}),
    ...
```

- [ ] **Step 4: 통과 확인** — Run: `cd server && .venv-test/bin/python -m pytest tests/test_us_prices_builder.py tests/ -q`. Expected: 전부 PASS
- [ ] **Step 5: Commit**: `feat(batch): build_us_prices P0 — massive 미러에서 US 총수익 계열 재생성`

---

### Task 4: 검증 도구 확장 — 전수 연속성 스캔 + 앱 파일 대조 모드

**Files:**
- Modify: `scripts/validate_us_adj.py`

**Interfaces:**
- Consumes: `module.us_prices.continuity_issues`·`TICKER_SEGMENTS` (Task 1). 서버 venv 로 실행: `server/.venv-test/bin/python scripts/validate_us_adj.py --scan`.
- Produces: 사람이 읽는 리포트 (stdout) — 구현 후 전환 게이트에서 사용.

동작 (인자 없으면 기존 24종 yfinance 대조 그대로 유지):
- `--scan`: 미러에서 meta US 전 종목을 연 청크로 읽어 티커별 `continuity_issues` + **리포트 전용 완화 티어**(분할 계수 변동 없는 날 |일수익| 15~25% — T 2022 WBD 스핀오프류가 여기 걸린다)를 집계, 티커·사유·해당일 목록을 출력. 자동 제외(>25%·공백)와 사람 검토(15~25%)를 구분해 표기.
- `--app-file`: yfinance 대조의 massive 쪽 입력을 미러 원본+합성 대신 **빌드된 앱 `us_prices.parquet`** (APP_DATA 경로, adj_close·gross_return 그대로)로 바꿔 24종을 재대조 — 빌더까지 통과한 최종 산출물의 회귀 확인.

- [ ] **Step 1: `--scan` 구현** — argparse 로 모드 분기. 스캔 본체:

```python
def scan_continuity():
    import sys
    sys.path.insert(0, "server")
    from datastore import meta
    from module.us_prices import JUMP_LIMIT, TICKER_SEGMENTS, continuity_issues, stitch_segments

    us = meta.meta_df().query("iso_code == 'US'")[["ticker"]].drop_duplicates()
    want = sorted(set(us["ticker"]) | {s for v in TICKER_SEGMENTS.values() for s, _, _ in v})
    frames = []
    for y in range(2008, pd.Timestamp.today().year + 1):
        c = pd.read_parquet(
            f"{MIRROR}/us_prices.parquet", columns=["date", "ticker", "close", "adj_close"],
            filters=[("ticker", "in", want), ("date", ">=", pd.Timestamp(f"{y}-01-01")),
                     ("date", "<=", pd.Timestamp(f"{y}-12-31"))],
        )
        if len(c):
            frames.append(c)
    px = pd.concat(frames, ignore_index=True)
    px["date"] = pd.to_datetime(px["date"])
    empty_div = pd.DataFrame({"ticker": [], "ex_date": [], "cash_amount": []})
    px, _ = stitch_segments(px, empty_div, TICKER_SEGMENTS)

    hard, soft = [], []
    for tk, g in px.groupby("ticker", sort=False):
        g = g.sort_values("date").set_index("date")
        issues = continuity_issues(g)
        if issues:
            hard.append((tk, issues[:3]))
        r = g["adj_close"].pct_change().abs()
        f_chg = (g["adj_close"] / g["close"]).pct_change().abs() > 0.005
        watch = r[(r > 0.15) & (r <= JUMP_LIMIT) & ~f_chg]
        if len(watch):
            soft.append((tk, [f"{d.date()} {v:.0%}" for d, v in watch.tail(3).items()]))
    print(f"자동 제외(가드) {len(hard)}종목:")
    for tk, iss in hard:
        print(f"  {tk}: {'; '.join(iss)}")
    print(f"\n사람 검토(15~25% 점프) {len(soft)}종목:")
    for tk, days in soft:
        print(f"  {tk}: {'; '.join(days)}")
```

- [ ] **Step 2: `--app-file` 구현** — 기존 대조 루프에서 massive 쪽 시계열 구성을 분기: 앱 파일에서 `pd.read_parquet(f"{app}/us_prices.parquet", filters=[("ticker","==",tk)])` 로 읽어 `adj_close` 의 pct_change 를 `r_tr` 로 쓴다 (합성 재계산 없음 — 빌더 산출을 그대로 검증). ETF 10종 + 개별주 14종 목록 재사용.
- [ ] **Step 3: 스모크 실행** — `--scan` 을 실제 미러로 1회 실행해 완주 확인 (수 분 소요 허용). 리포트는 커밋하지 않고 stdout — 전환 게이트에서 다시 돌린다.
- [ ] **Step 4: Commit**: `feat(validate): 전수 연속성 스캔·앱 파일 대조 모드 — 전환 게이트 도구`

---

### Task 5: 스펙 상태 갱신 + 최종 정리

**Files:**
- Modify: `docs/superpowers/specs/2026-08-04-us-price-source-unification-design.md`

- [ ] **Step 1**: 스펙 상태 줄을 `- 상태: 구현 완료 (2026-08-XX)` 로, `## 8. 구현 중 확인` 절 신설 — 구현에서 스펙과 달라진 점·실측치(빌더 소요 시간·메모리, 스캔 결과 요약)를 기록
- [ ] **Step 2**: 전체 테스트 최종 확인 — Run: `cd server && .venv-test/bin/python -m pytest tests/ -q`
- [ ] **Step 3: Commit**: `docs(spec): US 소스 일원화 구현 기록`

---

## 전환 게이트 (머지·배포 시 사람 확인 — 태스크 아님)

1. **타이밍 계약 실측**: 오후 수집 사이클 후 미러 `us_prices` 최종일이 직전 마감 US 세션인지 (`aws s3 ls s3://insight-invest-datalake/qdata-raw/raw/massive/ohlcv/ | tail`). 미충족이면 quant-data cron 시각 보정이 선행.
2. **qdata 배포 반영**: Task 0 의 `load_us_dividends` 가 EC2 배치·Lambda 의 qdata 설치본에 포함되는지 — server 의 qdata 의존 방식(requirements 의 git ref/버전)을 확인하고 필요 시 ref 갱신.
3. `--scan` 리포트 검토: 자동 제외 목록 승인, 15~25% 점프 종목(T·MO 류 스핀오프) 처리 결정 (세그먼트 추가 또는 수용).
4. 머지·푸시 후 첫 배치: `build_us_prices` 소요 시간·메모리 로그 확인, `--app-file` 재대조 실행, 전략 상세 페이지에서 XLE/TMF 부활·리밸 소급 반영(라이브 NAV 재작성) 확인.
