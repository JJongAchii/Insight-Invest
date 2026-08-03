# 전략 운영 전환(active) + 리밸 전일 신호 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 저장 전략에 `status`(saved|active)를 도입하고, 배치가 active 전략의 다음 거래일이 리밸일이면 엔진과 동일 계산으로 목표 비중 신호를 산출해 웹(전략 상세·목록·홈·attention)에 노출한다.

**Architecture:** 순수 신호 로직 `server/module/rebal_signal.py`(TDD, 엔진 동일성 앵커), datastore 후방호환 status, 배치 빌더 `build_rebal_signals`, 얇은 리더/토글 API, RTK Query + 기존 카드 프리미티브. 스펙: `docs/superpowers/specs/2026-08-03-strategy-activation-design.md`.

**Tech Stack:** Python 3.12 (pandas, FastAPI, pytest), Next.js 14 + RTK Query.

## Global Constraints

- **엔진 동일성** — 다음 주기 비중은 `module/strategy.py`의 같은 함수(`absolute_momentum` 등)로 산출한다. 조건식 복제 금지. `dual_mmt`는 `Backtest.rebalance`와 동일하게 **params 무시, top_n=4·lookback 12 고정**.
- 리밸일 = 주기(M/Q/Y) **첫 거래일**. next_business_day는 월~금 달력 근사(휴일 캘린더 의존성 금지) — 신호는 밤마다 멱등 재산출.
- status 값: `saved`|`active`. 구 행(컬럼 부재)은 **saved로 읽는다** (config 컬럼과 같은 후방호환 패턴).
- 500 금지: 신호 API 부재→빈 배열, status API는 404/422만. 빌더는 전략 단위 try/except.
- exit 종목은 target_weight 0 행으로 유지 (조용한 소실 금지). 판단 라벨 금지.
- 텔레그램·live_nav(P7) 추적 범위 불변. attention 드로다운 경보만 active 한정으로.
- 서버 테스트 `cd server && .venv-test/bin/python -m pytest tests/ -q`(현재 39개), 클라 `cd client && npx tsc --noEmit && npm run lint`. pre-commit(black 100, isort) 통과, conventional commits 한국어. 브랜치 `feat/strategy-activation`(스펙 커밋됨).

---

### Task 1: `server/module/rebal_signal.py` 순수 신호 로직 (TDD)

**Files:**
- Create: `server/module/rebal_signal.py`
- Test: `server/tests/test_rebal_signal.py`

**Interfaces:**
- Consumes: `module.strategy.absolute_momentum`, `module.strategy.Momentum`(앵커 테스트용)
- Produces (Task 3·4가 사용):
  - `next_business_day(d: pd.Timestamp) -> pd.Timestamp`
  - `is_new_period(as_of, nxt, freq: str) -> bool` — freq ∈ M/Q/Y
  - `next_period_weights(price: pd.DataFrame, algorithm: str, params: dict|None) -> dict[str, float]`
  - `classify_actions(prev: dict, target: dict) -> list[dict]` — keys: ticker, target_weight, prev_weight, action(enter|exit|keep), rank(exit은 None)

- [ ] **Step 1: 실패하는 테스트 작성** — `server/tests/test_rebal_signal.py`:

```python
"""리밸 전일 신호 순수 로직 — 엔진 동일성 앵커가 핵심.

next_period_weights가 Momentum.simulate의 같은 날짜 행과 정확히 일치해야
신호가 백테스트와 같은 숫자다. 어긋나면 '내일 살 종목'이 거짓이 된다.
"""

import numpy as np
import pandas as pd
import pytest

from module.rebal_signal import (
    classify_actions,
    is_new_period,
    next_business_day,
    next_period_weights,
)
from module.strategy import Momentum


def test_next_business_day_skips_weekend():
    assert next_business_day(pd.Timestamp("2026-02-27")) == pd.Timestamp("2026-03-02")  # 금→월
    assert next_business_day(pd.Timestamp("2026-03-03")) == pd.Timestamp("2026-03-04")  # 화→수


@pytest.mark.parametrize(
    "as_of,nxt,freq,expected",
    [
        ("2026-02-27", "2026-03-02", "M", True),   # 월말 금 → 새 달 월요일
        ("2026-03-10", "2026-03-11", "M", False),  # 월중
        ("2026-02-27", "2026-03-02", "Q", False),  # 2월→3월은 같은 1분기
        ("2026-03-31", "2026-04-01", "Q", True),   # 분기 경계
        ("2026-12-31", "2027-01-01", "Y", True),   # 연 경계
        ("2026-06-30", "2026-07-01", "Y", False),
    ],
)
def test_is_new_period(as_of, nxt, freq, expected):
    assert is_new_period(pd.Timestamp(as_of), pd.Timestamp(nxt), freq) is expected


def _drift_panel(n=420, cols=4) -> pd.DataFrame:
    # 결정적 패널 — 열마다 다른 드리프트로 모멘텀 순위가 뚜렷함 (난수 금지)
    idx = pd.bdate_range("2023-01-02", periods=n)
    data = {
        f"T{i}": 100.0 * np.power(1.0 + 0.0004 * (i + 1), np.arange(n))
        for i in range(cols)
    }
    return pd.DataFrame(data, index=idx)


def test_momentum_engine_identity_anchor():
    """simulate가 마지막 리밸일에 만든 행 == 그 전일까지 가격으로 산출한 신호."""
    price = _drift_panel()
    sim = Momentum(top_n=2, lookback_months=6).simulate(price=price, freq="M")
    last_date = sim.index[-1]
    trunc = price.loc[: last_date - pd.Timedelta(days=1)]
    mine = next_period_weights(trunc, "momentum", {"top_n": 2, "lookback_months": 6})
    row = sim.loc[last_date].dropna()
    assert set(mine) == set(row.index)
    for t, w in mine.items():
        assert w == pytest.approx(float(row[t]), rel=1e-12)


def test_dual_mmt_ignores_params_like_engine():
    """Backtest.rebalance는 dual_mmt에서 params를 무시하고 4/12 고정 — 동일해야 한다."""
    price = _drift_panel(cols=6)
    a = next_period_weights(price, "dual_mmt", {"top_n": 2, "lookback_months": 3})
    b = next_period_weights(price, "momentum", {"top_n": 4, "lookback_months": 12})
    assert a == b


def test_eq_and_custom_weights():
    price = _drift_panel(cols=3)
    eq = next_period_weights(price, "eq", None)
    assert eq == {t: pytest.approx(1 / 3) for t in price.columns}
    cw = next_period_weights(price, "custom", {"weights": {"SPY": 0.6, "IEF": 0.4}})
    assert cw == {"SPY": 0.6, "IEF": 0.4}


def test_classify_actions_enter_exit_keep():
    prev = {"A": 0.5, "B": 0.5}
    target = {"A": 0.7, "C": 0.3}
    rows = classify_actions(prev, target)
    by = {r["ticker"]: r for r in rows}
    assert by["A"]["action"] == "keep" and by["A"]["prev_weight"] == 0.5
    assert by["C"]["action"] == "enter" and by["C"]["prev_weight"] == 0.0
    assert by["B"]["action"] == "exit" and by["B"]["target_weight"] == 0.0 and by["B"]["rank"] is None
    # rank는 target 비중 내림차순 1..N
    assert by["A"]["rank"] == 1 and by["C"]["rank"] == 2
```

- [ ] **Step 2: RED 확인** — `cd server && .venv-test/bin/python -m pytest tests/test_rebal_signal.py -q` → ModuleNotFoundError

- [ ] **Step 3: 구현** — `server/module/rebal_signal.py`:

```python
"""리밸 전일 신호 — active 전략의 다음 리밸일 목표 비중 (순수 로직).

엔진 동일성이 생명이다: 리밸일 = 주기 첫 거래일, 비중은 전일까지 가격으로
산출 (Momentum.simulate의 price[:rebal_date-1일]과 동치). 같은 함수를 호출해
같은 식으로 계산한다 — 산출과 백테스트가 다른 코드를 재면 신호가 거짓이 된다.
"""

import pandas as pd

from module.strategy import absolute_momentum

_FREQ_PERIOD = {"M": "M", "Q": "Q", "Y": "Y"}


def next_business_day(d: pd.Timestamp) -> pd.Timestamp:
    """월~금 달력 근사 — KRX 휴일은 모른다. 주기 말 휴장이면 신호가 1~2 저녁
    일찍 뜨고 다음 배치가 최신 데이터로 재산출한다 (멱등)."""
    nxt = d + pd.Timedelta(days=1)
    while nxt.weekday() >= 5:
        nxt += pd.Timedelta(days=1)
    return nxt


def is_new_period(as_of: pd.Timestamp, nxt: pd.Timestamp, freq: str) -> bool:
    p = _FREQ_PERIOD[freq]
    return bool(pd.Period(nxt, p) != pd.Period(as_of, p))


def next_period_weights(price: pd.DataFrame, algorithm: str, params: dict | None = None) -> dict:
    """다음 리밸일에 엔진이 쓸 목표 비중 — strategy.simulate와 동일 산출식.

    price는 신호 산출 기준일(as_of)까지의 일별 가격 — simulate가 리밸일 r에서
    쓰는 price[:r-1일]과 동치다. dual_mmt는 Backtest.rebalance와 동일하게
    params를 무시하고 top_n=4·lookback 12를 쓴다.
    """
    params = params or {}
    if algorithm == "eq":
        w = 1.0 / len(price.columns)
        return {str(t): w for t in price.columns}
    if algorithm in ("momentum", "dual_mmt"):
        if algorithm == "dual_mmt":
            top_n, lookback = 4, 12
        else:
            top_n = int(params.get("top_n", 4))
            lookback = int(params.get("lookback_months", 12))
        score = absolute_momentum(price=price, lookback_months=lookback)
        if score is None:
            return {}
        top = score.nlargest(top_n)
        s = float(top.sum())
        return {str(t): (float(v) / s if s > 0 else 0.0) for t, v in top.items()}
    if algorithm == "custom":
        return {str(k): float(v) for k, v in (params.get("weights") or {}).items()}
    raise ValueError(f"unknown algorithm: {algorithm}")


def classify_actions(prev: dict, target: dict) -> list:
    """진입/이탈/유지 분류 — exit은 target 0 행으로 유지한다 (조용한 소실 금지)."""
    rows = []
    ordered = sorted(target.items(), key=lambda kv: -kv[1])
    for rank, (t, w) in enumerate(ordered, start=1):
        rows.append(
            {
                "ticker": t,
                "target_weight": float(w),
                "prev_weight": float(prev.get(t, 0.0)),
                "action": "keep" if t in prev else "enter",
                "rank": rank,
            }
        )
    for t, w in sorted(prev.items(), key=lambda kv: -kv[1]):
        if t not in target:
            rows.append(
                {
                    "ticker": t,
                    "target_weight": 0.0,
                    "prev_weight": float(w),
                    "action": "exit",
                    "rank": None,
                }
            )
    return rows
```

- [ ] **Step 4: GREEN + 전체 스위트** — 신규 파일 테스트 전부 PASS, 기존 39개 유지.

- [ ] **Step 5: Commit**

```bash
git add server/module/rebal_signal.py server/tests/test_rebal_signal.py
git commit -m "feat(signal): 리밸 전일 신호 순수 로직 — 엔진 동일성 앵커

next_period_weights가 Momentum.simulate의 같은 날짜 행과 1e-12 안에서
일치함을 못박는다. dual_mmt의 params 무시(4/12 고정)도 엔진과 동일."
```

---

### Task 2: datastore `status` + 라우터 (토글·신호 리더) + 계약 테스트

**Files:**
- Modify: `server/datastore/portfolio.py`, `server/app/routers/backtest.py`, `server/app/schemas.py`
- Test: `server/tests/test_strategy_status_api.py`

**Interfaces:**
- Consumes: 기존 `_read`/`_upsert`/`_EMPTY` 패턴, `schemas.Portfolio`(응답 모델 — 필드 추가 필요)
- Produces:
  - `portfolio.set_status(port_id: int, status: str) -> None` (KeyError if unknown port)
  - `portfolio.records()`/`registry()`가 `status` 포함 (구 행 → "saved")
  - `portfolio.rebal_signals() -> pd.DataFrame` (`portfolio/rebal_signals.parquet` 리더, 부재 시 빈 프레임)
  - `POST /backtest/strategy/{port_id}/status` `{"status": ...}` / `GET /backtest/rebal-signals`
  - `GET /backtest/strategy`·`/strategy/{port_id}` 응답에 `status`

- [ ] **Step 1: 실패하는 계약 테스트** — `server/tests/test_strategy_status_api.py`:

```python
"""status 토글·신호 리더 계약 — 구 행 후방호환(saved)과 404/422를 못박는다."""

import asyncio

import pandas as pd
import pytest
from fastapi import HTTPException


def _seed_ports(tmp_path, monkeypatch, with_status=False):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    d = tmp_path / "portfolio"
    d.mkdir(exist_ok=True)
    cols = {
        "port_id": [1],
        "port_name": ["막포"],
        "strategy_id": [1],
        "created_at": [pd.Timestamp("2026-07-01")],
        "config": [None],
    }
    if with_status:
        cols["status"] = ["active"]
    pd.DataFrame(cols).to_parquet(d / "portfolio.parquet", index=False)


def test_records_backfills_saved(tmp_path, monkeypatch):
    _seed_ports(tmp_path, monkeypatch)
    from datastore import portfolio

    df = portfolio.records()
    assert list(df["status"]) == ["saved"]


def test_set_status_and_read_back(tmp_path, monkeypatch):
    _seed_ports(tmp_path, monkeypatch)
    from datastore import portfolio

    portfolio.set_status(1, "active")
    assert list(portfolio.records()["status"]) == ["active"]
    with pytest.raises(KeyError):
        portfolio.set_status(999, "active")


def test_status_endpoint_contract(tmp_path, monkeypatch):
    _seed_ports(tmp_path, monkeypatch)
    import app.routers.backtest as bt
    from app import schemas

    r = asyncio.run(bt.post_strategy_status(1, schemas.StrategyStatusRequest(status="active")))
    assert r == {"port_id": 1, "status": "active"}
    with pytest.raises(HTTPException) as e404:
        asyncio.run(bt.post_strategy_status(999, schemas.StrategyStatusRequest(status="active")))
    assert e404.value.status_code == 404
    with pytest.raises(HTTPException) as e422:
        asyncio.run(bt.post_strategy_status(1, schemas.StrategyStatusRequest(status="hot")))
    assert e422.value.status_code == 422


def test_rebal_signals_absent_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    import app.routers.backtest as bt

    assert asyncio.run(bt.get_rebal_signals()) == {"as_of": None, "signals": []}
```

- [ ] **Step 2: RED 확인** (AttributeError/KeyError 계열)

- [ ] **Step 3: 구현**

`datastore/portfolio.py`:
- `_EMPTY["portfolio.parquet"]`에 `"status"` 추가, 신규 `_EMPTY["rebal_signals.parquet"] = ["port_id", "port_name", "freq", "as_of", "next_rebal", "ticker", "name", "target_weight", "prev_weight", "action", "rank"]`.
- `records()`: config 패턴과 동일하게 `if "status" not in df.columns: df["status"] = "saved"` + `df["status"] = df["status"].fillna("saved")`.
- `registry()` 반환 컬럼에 `status` 추가 (`ports.merge(...)[[..., "status"]]` — records() 경유로 채운 뒤 merge).
- 신규:

```python
def set_status(port_id: int, status: str) -> None:
    """운영 상태 토글 — saved|active. 알 수 없는 port_id는 KeyError."""
    ports = records()
    if not (ports["port_id"] == port_id).any():
        raise KeyError(f"unknown port_id: {port_id}")
    ports.loc[ports["port_id"] == port_id, "status"] = status
    storage.write_parquet(ports, DIR, "portfolio.parquet")


def rebal_signals() -> pd.DataFrame:
    """리밸 전일 신호 (build_insights의 rebal_signals가 생성) — 부재 시 빈 프레임."""
    return _read("rebal_signals.parquet")
```

`app/schemas.py`: `Portfolio` 모델에 `status: Optional[str] = "saved"` 추가, 신규 `class StrategyStatusRequest(BaseModel): status: str`.

`app/routers/backtest.py`:

```python
VALID_STATUS = {"saved", "active"}


@router.post("/strategy/{port_id}/status")
async def post_strategy_status(port_id: int, request: schemas.StrategyStatusRequest):
    """운영 시작/중지 토글."""
    if request.status not in VALID_STATUS:
        raise HTTPException(status_code=422, detail=f"status must be one of {VALID_STATUS}")
    try:
        portfolio.set_status(port_id, request.status)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown port_id: {port_id}")
    return {"port_id": port_id, "status": request.status}


@router.get("/rebal-signals")
async def get_rebal_signals():
    """active 전략의 리밸 전일 신호 (parquet 리더). 부재 시 빈 배열 — 500 금지."""
    df = portfolio.rebal_signals()
    if df.empty:
        return {"as_of": None, "signals": []}
    from datetime import date as _date

    signals = []
    for pid, sub in df.groupby("port_id"):
        sub = sub.sort_values(["rank"], na_position="last")
        next_rebal = str(sub["next_rebal"].iloc[0])[:10]
        signals.append(
            {
                "port_id": int(pid),
                "port_name": sub["port_name"].iloc[0],
                "freq": sub["freq"].iloc[0],
                "next_rebal": next_rebal,
                "is_stale": _date.today().isoformat() > next_rebal,
                "items": [
                    {
                        "ticker": r.ticker,
                        "name": r.name,
                        "target_weight": float(r.target_weight),
                        "prev_weight": float(r.prev_weight),
                        "action": r.action,
                        "rank": int(r.rank) if pd.notna(r.rank) else None,
                    }
                    for r in sub.itertuples()
                ],
            }
        )
    return {"as_of": str(df["as_of"].iloc[0])[:10], "signals": signals}
```

`GET /strategy` 경로: `port_summary()`가 registry 경유로 status를 실으면 `schemas.Portfolio`에 필드가 있어야 통과한다 — `port_summary()`의 registry 사용부와 `schemas.Portfolio` 필드를 실제로 열어 확인하고 맞춘다. `GET /strategy/{port_id}`(dict 반환)는 `port_id_info`가 registry 기반이라 status가 자동 포함되는지 확인, 아니면 명시 추가.

- [ ] **Step 4: GREEN + 전체 스위트** (기존 39 + 신규 4+)

- [ ] **Step 5: Commit** — `feat(api): 전략 status(saved|active) + 리밸 신호 리더`

---

### Task 3: `build_rebal_signals()` 빌더 + 강제 경계 검증

**Files:**
- Modify: `scripts/build_insights.py`

**Interfaces:**
- Consumes: Task 1 모듈 전부, Task 2의 `portfolio.records()`(status 포함), `build_track_strategies`의 cfg 파싱·가격 로드 패턴(MOMENTUM_WARMUP_DAYS, fx 변환)
- Produces: `{APP_DATA}/portfolio/rebal_signals.parquet` (Task 2 리더·Task 4 attention이 소비)

- [ ] **Step 1: 빌더 구현** — `build_track_strategies` 아래에:

```python
def build_rebal_signals():
    """active 전략의 리밸 전일 신호 — 다음 거래일이 새 주기면 목표 비중 산출.

    prev(직전 목표)는 저장 parquet이 아니라 엔진 재계산(bt.rebalance 마지막 행)
    에서 얻는다 — 저장본은 백테스트 시점 이후 갱신되지 않아 오래 운영된 전략에서
    낡는다. active 0개면 빈 파일을 직접 써서 잔존 신호를 지운다 (비활성화 직후
    어제 신호가 남는 것 방지 — main()의 write 경로는 빈 프레임을 다루지 못한다).
    """
    from module import rebal_signal

    ports = portfolio.records()
    active = ports[ports["status"] == "active"] if not ports.empty else ports
    sig_cols = portfolio._EMPTY["rebal_signals.parquet"]
    if active.empty:
        storage.write_parquet(pd.DataFrame(columns=sig_cols), "portfolio", "rebal_signals.parquet")
        print("[rebal_signals] active 전략 없음 — 빈 파일 기록")
        return None

    st = meta.strategy_df().set_index("strategy_id")["strategy"]
    names = meta.meta_df()[["ticker", "name"]].drop_duplicates("ticker").set_index("ticker")["name"]
    frames = []
    for p in active.itertuples():
        try:
            cfg = json.loads(p.config) if isinstance(p.config, str) and p.config.strip() else {}
            algorithm = cfg.get("algorithm") or st.get(p.strategy_id, "eq")
            freq = cfg.get("rebal_freq") or "M"
            params = cfg.get("params") or {}

            meta_ids = portfolio.universe(int(p.port_id))
            bt = Backtest(strategy_name=p.port_name)
            warmup = (pd.Timestamp.today() - pd.Timedelta(days=MOMENTUM_WARMUP_DAYS)).date()
            price = bt.data(meta_id=meta_ids, start_date=warmup)
            if price.empty:
                raise ValueError("가격 데이터 없음")
            if cfg.get("currency") == "KRW":
                mapping = meta.resolve(meta_ids=meta_ids)
                price = fx.to_krw(price, dict(zip(mapping["ticker"], mapping["iso_code"])))

            as_of = price.index.max()
            nxt = rebal_signal.next_business_day(as_of)
            if not rebal_signal.is_new_period(as_of, nxt, freq):
                continue  # 이번 밤은 신호 없음

            target = rebal_signal.next_period_weights(price, algorithm, params)
            if not target:
                raise ValueError("목표 비중 산출 실패")
            w = bt.rebalance(price=price, method=algorithm, freq=freq,
                             custom_weight=params.get("weights"), params=params)
            prev = w.iloc[-1].dropna().to_dict() if w is not None and not w.empty else {}

            rows = pd.DataFrame(rebal_signal.classify_actions(prev, target))
            rows.insert(0, "port_id", int(p.port_id))
            rows.insert(1, "port_name", p.port_name)
            rows.insert(2, "freq", freq)
            rows.insert(3, "as_of", as_of.strftime("%Y-%m-%d"))
            rows.insert(4, "next_rebal", nxt.strftime("%Y-%m-%d"))
            rows["name"] = rows["ticker"].map(names).fillna(rows["ticker"])
            frames.append(rows[sig_cols])
            print(f"[rebal_signals] {p.port_name}: {len(rows)}행 (next {nxt.date()})")
        except Exception as e:
            print(f"[warn] rebal_signals 스킵 ({p.port_name}): {e}", file=sys.stderr)

    if not frames:
        storage.write_parquet(pd.DataFrame(columns=sig_cols), "portfolio", "rebal_signals.parquet")
        print("[rebal_signals] 이번 밤 신호 없음 — 빈 파일 기록")
        return None
    df = pd.concat(frames, ignore_index=True)
    df["as_of"] = df["as_of"]  # 문자열 유지
    return df
```

BUILDERS에 `("portfolio/rebal_signals.parquet", build_rebal_signals, {}),` 를 `portfolio/live_nav.parquet` 항목 **뒤에** 추가. 모듈 docstring 빌더 목록에 한 줄 추가. 주의: 빈 케이스는 빌더가 직접 쓰고 None을 반환한다 — main()은 스킵 (스포트라이트의 empty 처리와 다른 이유를 위 docstring이 설명).

- [ ] **Step 2: 강제 경계 검증 (tmp APP_DATA + 실제 레이크 가격)**

as_of(로컬 레이크 마지막 거래일)의 다음 영업일이 같은 달이면 신호가 안 뜨므로, `next_business_day`를 monkeypatch로 32일 뒤로 밀어 **경계를 강제**해 배관 전체를 검증한다:

```bash
cd /Users/achii/Quant/Insight-Invest && APP_DATA=$(mktemp -d) server/.venv-test/bin/python - <<'EOF'
import os, sys
import pandas as pd
sys.path.insert(0, "server"); sys.path.insert(0, "scripts")
root = os.environ["APP_DATA"]
# 메타류는 S3에서 읽어 tmp로 복사 (datastore/meta.py가 읽는 파일명을 열어 확인:
# meta.parquet, strategy 테이블, kr_etf_meta.parquet 등 필요한 것 전부)
for f in ["meta.parquet", "strategy.parquet", "kr_etf_meta.parquet"]:
    try:
        pd.read_parquet(f"s3://insight-invest-datalake/app/{f}").to_parquet(f"{root}/{f}", index=False)
    except FileNotFoundError:
        print("skip", f)
from datastore import portfolio, meta
# US ETF 유니버스로 합성 전략 생성 (SPY/QQQ/TLT/GLD — 레이크에 살아있는 시세)
md = meta.meta_df()
ids = [int(md[md["ticker"] == t]["meta_id"].iloc[0]) for t in ["SPY", "QQQ", "TLT", "GLD"]]
pid = portfolio.create("검증용듀얼모멘텀", "dual_mmt", ids,
                       {"algorithm": "dual_mmt", "rebal_freq": "M", "params": {}})
portfolio.set_status(pid, "active")
import build_insights as bi
from module import rebal_signal
orig = rebal_signal.next_business_day
rebal_signal.next_business_day = lambda d: orig(d) + pd.Timedelta(days=32)  # 경계 강제
df = bi.build_rebal_signals()
print(df.to_string(index=False))
assert df is not None and set(df["action"]) <= {"enter", "exit", "keep"}
assert abs(df[df["action"] != "exit"]["target_weight"].sum() - 1.0) < 1e-9
EOF
```

Expected: dual_mmt 4종목 목표 비중 합 1, prev(엔진 마지막 리밸 행) 대비 action 분류. 출력을 리포트에 붙인다. QDATA_LAKE는 기본(로컬 레이크) — S3 쓰기 없음.

- [ ] **Step 3: 전체 스위트 + Commit** — `feat(batch): build_rebal_signals — active 전략 리밸 전일 신호`

---

### Task 4: attention — 내일 리밸 항목 + 드로다운 active 한정

**Files:**
- Modify: `server/app/routers/attention.py`

**Interfaces:**
- Consumes: `portfolio.rebal_signals()`, `portfolio.registry()`(status 포함)
- Produces: attention 응답에 `{"category": "strategy", "severity": "high", "title": "내일 리밸: {name}", ...}` 항목

- [ ] **Step 1: 구현** — 전략 드로다운 블록 **앞**에 신규 블록 (독립 try/except):

```python
    # ── 리밸 전일 신호 (active 전략) ─────────────────────────────────
    try:
        sig = portfolio.rebal_signals()
        if not sig.empty:
            today = date.today().isoformat()
            for pid, sub in sig.groupby("port_id"):
                next_rebal = str(sub["next_rebal"].iloc[0])[:10]
                if next_rebal < today:
                    continue  # 지난 신호 — 리밸일이 지났으면 조용히 제외
                n_enter = int((sub["action"] == "enter").sum())
                n_exit = int((sub["action"] == "exit").sum())
                n_keep = int((sub["action"] == "keep").sum())
                items.append(
                    {
                        "severity": "high",
                        "category": "strategy",
                        "title": f"내일 리밸: {sub['port_name'].iloc[0]}",
                        "detail": f"진입 {n_enter} · 이탈 {n_exit} · 유지 {n_keep} — 목표 비중은 전략 상세에서",
                        "link": f"/backtest/strategy_list/{int(pid)}",
                    }
                )
    except Exception:
        logger.debug("attention rebal signals 실패", exc_info=True)
```

드로다운 루프에는 active 필터 추가: `for pr in reg.itertuples():` 직후

```python
            if getattr(pr, "status", "saved") != "active":
                continue  # 운영 중인 전략만 경보 — 저장만 된 전략의 낙폭은 소음
```

- [ ] **Step 2: 어휘 가드 확인 + 전체 스위트** — `test_signal_vocab`의 attention AST 파서는 `sig, sev, word =` 패턴만 읽으므로 이 변경에 영향 없음을 확인. 전체 테스트 PASS.

- [ ] **Step 3: Commit** — `feat(attention): 내일 리밸 항목 + 드로다운 경보 active 한정`

---

### Task 5: 프론트 — 토글·배지·NextRebalCard

**Files:**
- Modify: `client/src/state/api.ts`, `client/src/app/backtest/strategy_list/[port_id]/page.tsx`, `client/src/app/backtest/strategy_list/Contents.tsx`, `client/src/app/home/StrategiesCard.tsx`
- Create: `client/src/app/backtest/strategy_list/[port_id]/NextRebalCard.tsx`

**Interfaces:**
- Consumes: Task 2 API. 기존 `fetchStrategyById`(상세, status 포함됨), `"Strategy"` 태그.
- Produces: `useSetStrategyStatusMutation`, `useFetchRebalSignalsQuery`, 타입들

- [ ] **Step 1: api.ts** — 타입:

```ts
export interface RebalSignalItem {
  ticker: string;
  name: string;
  target_weight: number;
  prev_weight: number;
  action: "enter" | "exit" | "keep";
  rank: number | null;
}

export interface RebalSignal {
  port_id: number;
  port_name: string;
  freq: string;
  next_rebal: string;
  is_stale: boolean;
  items: RebalSignalItem[];
}

export interface RebalSignalsResponse {
  as_of: string | null;
  signals: RebalSignal[];
}
```

엔드포인트 (`fetchStrategyLiveById` 근처):

```ts
    fetchRebalSignals: builder.query<RebalSignalsResponse, void>({
      query: () => "/backtest/rebal-signals",
    }),
    setStrategyStatus: builder.mutation<
      { port_id: number; status: string },
      { portId: number; status: "saved" | "active" }
    >({
      query: ({ portId, status }) => ({
        url: `/backtest/strategy/${portId}/status`,
        method: "POST",
        body: { status },
      }),
      invalidatesTags: ["Strategy"],
    }),
```

훅 export 2개 추가. 기존 전략 타입(있다면 `schemas.Portfolio` 대응 인터페이스)에 `status?: string` 추가 — `fetchStrategies`/`fetchStrategyById` 사용부를 열어 실제 타입 이름을 확인해 맞춘다.

- [ ] **Step 2: NextRebalCard** — `[port_id]/NextRebalCard.tsx`:

```tsx
"use client";

import React from "react";

import { useFetchRebalSignalsQuery } from "@/state/api";
import Card from "@/components/ui/Card";

const ACTION_LABEL: Record<string, string> = { enter: "진입", exit: "이탈", keep: "유지" };
const ACTION_COLOR: Record<string, string> = {
  enter: "var(--gains)",
  exit: "var(--losses)",
  keep: "var(--chart-2)",
};

/** 다음 리밸런싱 신호 — 배치가 리밸 전일 저녁 엔진과 동일 계산으로 생성.
 *  active인데 신호가 없으면 아직 주기 안이라는 뜻 — 안내 문구만. */
const NextRebalCard: React.FC<{ portId: number; isActive: boolean }> = ({ portId, isActive }) => {
  const { data } = useFetchRebalSignalsQuery(undefined, { skip: !isActive });
  if (!isActive) return null;
  const sig = data?.signals.find((s) => s.port_id === portId);

  return (
    <Card title="다음 리밸런싱">
      {!sig ? (
        <p className="text-sm text-ink-muted">
          다음 리밸런싱 주기 전일 저녁에 목표 비중이 생성됩니다.
        </p>
      ) : (
        <>
          <p className="text-xs text-ink-muted mb-2">
            {sig.is_stale ? "지난 신호 — " : ""}예상 리밸일 {sig.next_rebal} · {data?.as_of} 데이터
            기준 · 최종 비중은 리밸 전일 저녁 확정
          </p>
          <div className="flex flex-col gap-1.5">
            {sig.items.map((it) => (
              <div key={it.ticker} className="flex items-baseline gap-2 text-sm">
                <span
                  className="badge-neutral shrink-0"
                  style={{ color: ACTION_COLOR[it.action] }}
                >
                  {ACTION_LABEL[it.action]}
                </span>
                <span className="text-ink w-40 truncate">{it.name}</span>
                <span className="num text-ink-secondary">
                  {(it.prev_weight * 100).toFixed(1)}% → {(it.target_weight * 100).toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </Card>
  );
};

export default NextRebalCard;
```

- [ ] **Step 3: 상세 페이지** — `[port_id]/page.tsx`: 상세 데이터에서 `status` 읽어 헤더에 ACTIVE 배지(`badge-neutral` + `var(--gains)` 텍스트) + 토글 버튼:

```tsx
const [setStatus, { isLoading: toggling }] = useSetStrategyStatusMutation();
// 버튼: status === "active" ? "운영 중지" : "운영 시작"
// onClick: setStatus({ portId, status: status === "active" ? "saved" : "active" })
```

`<NextRebalCard portId={...} isActive={status === "active"} />`를 지표 요약 아래 배치. 기존 페이지의 데이터 훅·레이아웃 구조를 그대로 따른다.

- [ ] **Step 4: 목록·홈 배지** — `Contents.tsx` 카드와 `StrategiesCard.tsx` 행에서 `status === "active"`이면 `<span className="badge-neutral" style={{ color: "var(--gains)" }}>ACTIVE</span>` (각 파일의 기존 마크업 관례에 맞춰 배치).

- [ ] **Step 5: 검증 + Commit** — `cd client && npx tsc --noEmit && npm run lint` 에러 0. Commit: `feat(client): 운영 시작 토글 + ACTIVE 배지 + 다음 리밸런싱 카드`

---

### Task 6: 통합 검증 + 문서

- [ ] **Step 1**: 전체 서버 스위트 + tsc/lint 최종 확인.
- [ ] **Step 2**: 스펙 상태 줄 → `- 상태: 구현 완료 (2026-08-03)`. `build_insights.py` 모듈 docstring의 빌더 목록에 rebal_signals가 반영됐는지 확인 (Task 3에서 누락 시 여기서). 스펙 §5의 prev 출처가 "portfolio.rebalance 마지막 행"으로 적혀 있으나 구현은 **엔진 재계산(bt.rebalance 마지막 행)** 을 쓴다 — 저장 parquet은 백테스트 시점 이후 갱신되지 않아 오래 운영된 전략에서 낡기 때문. 스펙에 "구현 중 확인" 절로 이 정정을 기록한다.
- [ ] **Step 3**: Commit `docs: 전략 운영 전환 스펙 상태 갱신`.
- [ ] **Step 4**: 머지·배포는 컨트롤러가 사용자 확인 후 (finishing-a-development-branch). 배포 후 흐름 안내: 사용자가 전략 상세에서 "운영 시작" → 다음 리밸 주기 전일 저녁 배치가 신호 생성 → attention·상세 카드 노출.
