# KR 장중 마켓 대시보드 + US 아침 반영 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 30분 주기 KRX 지연 스냅샷으로 인사이트 페이지 "장중" 탭(지수·브레드스·섹터 히트맵·섹터 흐름·순위·내 종목)과 홈 장중화를 구현하고, US 종가를 아침에 반영한다.

**Architecture:** 폴러 Lambda(서빙과 같은 컨테이너 이미지, CMD 오버라이드)가 EventBridge 30분 스케줄로 pykrx 4호출 → 앱 평면 parquet 2개 갱신. 서빙 라우터 `GET /intraday/market`이 조립·강등을 담당. 클라이언트는 인사이트 2탭 + 홈 타일 오버라이드. 스펙: `docs/superpowers/specs/2026-08-11-kr-intraday-market-design.md`.

**Tech Stack:** FastAPI + pandas + pykrx(qdata 의존성으로 이미지에 이미 존재), Next.js 14 + RTK Query, CloudFormation + EventBridge(Scheduler/Rule).

## Global Constraints

- 장중 산출물은 `app/kr_intraday_latest.parquet`·`app/kr_intraday_timeline.parquet` 두 파일뿐. 레이크(`qdata/`)·raw 체크포인트 무접촉, 야간 파이프라인 무변경.
- 종목 등락률은 KRX 제공값(`등락률` 컬럼)만 사용 — 보관 종가로 자체 계산 금지.
- 서빙 실패·스테일·파일 부재는 전부 `{"active": false}` 200 응답 — **500 금지**.
- 장중 값을 정산 가격 차트·백테스트·신호·brief 경로에 연결 금지.
- 급등락 필터: 시총 ≥ 1e11 KRW, 당일 거래대금 ≥ 3e9 KRW. 순위 TOP N=10. 섹터 흐름 차트 표시 = 거래대금 상위 8업종.
- 스테일 판정: 장중(평일 09:00~15:30 KST)에 as_of 40분 초과 → inactive. `np.busday_count(trade_date, today) >= 2` → inactive.
- 서버 테스트는 `cd server && python -m pytest tests/ -q`가 전부 통과해야 한다. 클라는 `cd client && npm run lint && npx tsc --noEmit` (lint 출력은 파이프로 가리지 말 것 — exit code 확인).
- 지수 코드: KOSPI=`1001`, KOSDAQ=`2001` (pykrx 인자·`krx_index_prices.index_code` 동일).
- KST 고정: `timezone(timedelta(hours=9))`. `as_of`는 `"YYYY-MM-DD HH:MM"` KST 문자열, `trade_date`는 `"YYYY-MM-DD"`.

## File Structure

- Create: `server/module/kr_intraday.py` — 순수 로직 (I/O 없음)
- Create: `server/app/intraday_poller.py` — 폴러 Lambda 엔트리포인트
- Create: `server/app/routers/intraday.py` — 서빙 라우터
- Create: `server/tests/test_kr_intraday_module.py`, `server/tests/test_intraday_poller.py`, `server/tests/test_intraday_api.py`
- Create: `client/src/app/insight/intraday/` — `IntradayTab.tsx`, `Sparkline.tsx`, `IntradayIndexStrip.tsx`, `SectorHeatmapLive.tsx`, `SectorFlowChart.tsx`, `RankTables.tsx`, `MyIntraday.tsx`
- Modify: `server/app/main.py` (라우터 등록 1줄), `client/src/state/api.ts` (타입+엔드포인트), `client/src/app/insight/page.tsx` (2탭), `client/src/app/home/MarketTiles.tsx`, `infra/template.yaml`, `.github/workflows/deploy.yml`

---

### Task 1: 순수 모듈 `server/module/kr_intraday.py`

**Files:**
- Create: `server/module/kr_intraday.py`
- Test: `server/tests/test_kr_intraday_module.py`

**Interfaces (Produces — Task 2·3이 그대로 사용):**
- `KST`, `STALE_MINUTES=40`, `MOVER_MIN_CAP=1e11`, `MOVER_MIN_VALUE=3e9`, `TOP_N=10`
- `normalize_snapshot(frames: dict[str, pd.DataFrame], as_of: str, trade_date: str) -> pd.DataFrame`
- `with_sector(latest, sector_map) -> pd.DataFrame` (sector_map: [ticker, sector, name])
- `index_rows(levels: dict[str, float], prev_closes: dict[str, float], as_of, trade_date) -> pd.DataFrame`
- `breadth_row(latest, as_of, trade_date) -> pd.DataFrame`
- `sector_rows(latest_with_sector, as_of, trade_date) -> pd.DataFrame`
- `merge_timeline(existing: pd.DataFrame | None, new_rows) -> pd.DataFrame`
- `is_open_kst(now: datetime) -> bool`
- `snapshot_active(trade_date: str, as_of: str, now: datetime) -> bool`
- `top_value(latest, n=TOP_N) -> pd.DataFrame`
- `top_movers(latest, n=TOP_N) -> tuple[pd.DataFrame, pd.DataFrame]`

- [ ] **Step 1: 실패하는 테스트 작성** — `server/tests/test_kr_intraday_module.py`

```python
"""kr_intraday 순수 로직 테스트 — 스펙 2026-08-11 D2·D3."""

from datetime import datetime

import pandas as pd
import pytest

from module import kr_intraday as ki


def _snap_frame(rows: dict) -> pd.DataFrame:
    """pykrx get_market_ohlcv_by_ticker 형태(한글 컬럼, 티커 인덱스) 재현."""
    df = pd.DataFrame.from_dict(rows, orient="index",
        columns=["시가", "고가", "저가", "종가", "거래량", "거래대금", "등락률", "시가총액"])
    df.index.name = "티커"
    return df


@pytest.fixture
def latest():
    frames = {
        "KOSPI": _snap_frame({
            "005930": [100, 110, 95, 105, 1000, 5e9, 5.0, 4e11],
            "000660": [200, 200, 180, 190, 500, 4e9, -5.0, 2e11],
            "999999": [0, 0, 0, 0, 0, 0, 0.0, 1e10],   # 거래정지 → 제외돼야 함
        }),
        "KOSDAQ": _snap_frame({
            "035720": [50, 55, 50, 50, 100, 1e9, 0.0, 5e10],
        }),
    }
    return ki.normalize_snapshot(frames, "2026-08-11 11:35", "2026-08-11")


def test_normalize_snapshot(latest):
    assert len(latest) == 3  # close=0 제외
    assert set(latest.columns) >= {"ticker", "market", "open", "high", "low",
                                   "close", "volume", "value", "chg_pct", "cap",
                                   "as_of", "trade_date"}
    assert latest.set_index("ticker").loc["005930", "chg_pct"] == 5.0
    assert (latest["market"] == "KOSDAQ").sum() == 1


def test_with_sector_fills_unknown(latest):
    smap = pd.DataFrame({"ticker": ["005930"], "sector": ["전기전자"], "name": ["삼성전자"]})
    d = ki.with_sector(latest, smap)
    assert d.set_index("ticker").loc["005930", "sector"] == "전기전자"
    assert d.set_index("ticker").loc["000660", "sector"] == "기타"
    assert d.set_index("ticker").loc["000660", "name"] == ""


def test_index_rows_chg_vs_prev_close():
    rows = ki.index_rows({"KOSPI": 6300.0}, {"KOSPI": 6000.0}, "2026-08-11 11:35", "2026-08-11")
    assert rows.iloc[0]["kind"] == "index"
    assert rows.iloc[0]["chg_pct"] == pytest.approx(5.0)


def test_breadth_counts(latest):
    row = ki.breadth_row(latest, "2026-08-11 11:35", "2026-08-11").iloc[0]
    assert (row["advancers"], row["decliners"], row["unchanged"]) == (1, 1, 1)


def test_sector_rows_cap_weighted(latest):
    smap = pd.DataFrame({"ticker": ["005930", "000660"],
                         "sector": ["전기전자", "전기전자"], "name": ["삼성전자", "하이닉스"]})
    d = ki.with_sector(latest, smap)
    rows = ki.sector_rows(d, "2026-08-11 11:35", "2026-08-11").set_index("key")
    # 시총가중: (4e11*5 + 2e11*-5) / 6e11 = +1.667
    assert rows.loc["전기전자", "chg_pct"] == pytest.approx(10 / 6, rel=1e-3)
    assert rows.loc["전기전자", "value_krw"] == pytest.approx(9e9)
    assert rows.loc["기타", "n"] == 1


def test_merge_timeline_resets_on_new_day():
    old = pd.DataFrame({"as_of": ["2026-08-10 15:35"], "trade_date": ["2026-08-10"],
                        "kind": ["breadth"], "key": ["ALL"]})
    new = pd.DataFrame({"as_of": ["2026-08-11 09:35"], "trade_date": ["2026-08-11"],
                        "kind": ["breadth"], "key": ["ALL"]})
    assert len(ki.merge_timeline(old, new)) == 1          # 리셋
    merged = ki.merge_timeline(new, new.assign(as_of="2026-08-11 10:05"))
    assert len(merged) == 2                               # 같은 날 append
    assert len(ki.merge_timeline(None, new)) == 1


def test_is_open_kst():
    assert ki.is_open_kst(datetime(2026, 8, 11, 11, 0, tzinfo=ki.KST))       # 화 11시
    assert not ki.is_open_kst(datetime(2026, 8, 11, 16, 0, tzinfo=ki.KST))   # 마감 후
    assert not ki.is_open_kst(datetime(2026, 8, 15, 11, 0, tzinfo=ki.KST))   # 토


def test_snapshot_active():
    open_now = datetime(2026, 8, 11, 11, 0, tzinfo=ki.KST)
    assert ki.snapshot_active("2026-08-11", "2026-08-11 10:35", open_now)
    assert not ki.snapshot_active("2026-08-11", "2026-08-11 09:35", open_now)  # 장중 85분 스테일
    evening = datetime(2026, 8, 11, 20, 0, tzinfo=ki.KST)
    assert ki.snapshot_active("2026-08-11", "2026-08-11 15:35", evening)       # 마감 현황 유지
    monday = datetime(2026, 8, 10, 8, 0, tzinfo=ki.KST)
    assert ki.snapshot_active("2026-08-07", "2026-08-07 15:35", monday)        # 월 아침, 금 스냅샷
    tuesday_pre = datetime(2026, 8, 11, 8, 0, tzinfo=ki.KST)
    assert not ki.snapshot_active("2026-08-07", "2026-08-07 15:35", tuesday_pre)  # 2영업일 낡음


def test_top_movers_filters_illiquid(latest):
    # 035720: cap 5e10 < 1e11 → 급등락 제외 대상
    up, down = ki.top_movers(latest)
    assert "035720" not in set(up["ticker"]) | set(down["ticker"])
    assert up.iloc[0]["ticker"] == "005930"
    assert down.iloc[0]["ticker"] == "000660"
    assert ki.top_value(latest).iloc[0]["ticker"] == "005930"
```

- [ ] **Step 2: 실패 확인** — Run: `cd server && python -m pytest tests/test_kr_intraday_module.py -q` → Expected: FAIL (`ModuleNotFoundError: module.kr_intraday`)

- [ ] **Step 3: 구현** — `server/module/kr_intraday.py`

```python
"""KR 장중 스냅샷 순수 로직 (스펙 2026-08-11 D2·D3).

불변식: 종목 등락률은 KRX 제공값을 그대로 쓴다(자체 계산 금지 — 당일 배당락·
분할이 있으면 보관 종가 기반 계산이 어긋나는 것이 정상이고, 그래서 금지다).
산출물은 앱 평면 두 파일 전용이며 레이크·백테스트 경로와 무관하다.
"""

from __future__ import annotations

from datetime import datetime, time as dtime, timedelta, timezone

import numpy as np
import pandas as pd

KST = timezone(timedelta(hours=9))
STALE_MINUTES = 40      # 30분 폴 주기 + 여유 10분
MOVER_MIN_CAP = 1e11    # 급등락 순위: 시총 1,000억 이상
MOVER_MIN_VALUE = 3e9   # 급등락 순위: 당일 거래대금 30억 이상
TOP_N = 10

_SNAP_COLS = {"시가": "open", "고가": "high", "저가": "low", "종가": "close",
              "거래량": "volume", "거래대금": "value", "등락률": "chg_pct",
              "시가총액": "cap"}


def normalize_snapshot(
    frames: dict[str, pd.DataFrame], as_of: str, trade_date: str
) -> pd.DataFrame:
    """pykrx 시장별 프레임(한글 컬럼, 티커 인덱스) → 영문 스키마 단일 프레임."""
    parts = []
    for market, df in frames.items():
        d = df.rename(columns=_SNAP_COLS)[list(_SNAP_COLS.values())].copy()
        d.index.name = "ticker"
        d = d.reset_index()
        d["market"] = market
        parts.append(d)
    out = pd.concat(parts, ignore_index=True)
    out = out[out["close"] > 0].reset_index(drop=True)  # 거래정지·미형성 봉 제외
    out["as_of"] = as_of
    out["trade_date"] = trade_date
    return out


def with_sector(latest: pd.DataFrame, sector_map: pd.DataFrame) -> pd.DataFrame:
    """업종·종목명 병합. 미분류(월초 이후 신규상장 등)는 sector='기타', name=''."""
    d = latest.merge(sector_map[["ticker", "sector", "name"]], on="ticker", how="left")
    d["sector"] = d["sector"].fillna("기타")
    d["name"] = d["name"].fillna("")
    return d


def index_rows(levels, prev_closes, as_of: str, trade_date: str) -> pd.DataFrame:
    rows = []
    for key, level in levels.items():
        prev = prev_closes.get(key)
        chg = (level / prev - 1) * 100 if prev else np.nan
        rows.append({"as_of": as_of, "trade_date": trade_date, "kind": "index",
                     "key": key, "level": float(level), "chg_pct": chg})
    return pd.DataFrame(rows)


def breadth_row(latest: pd.DataFrame, as_of: str, trade_date: str) -> pd.DataFrame:
    s = latest["chg_pct"]
    return pd.DataFrame([{
        "as_of": as_of, "trade_date": trade_date, "kind": "breadth", "key": "ALL",
        "advancers": int((s > 0).sum()), "decliners": int((s < 0).sum()),
        "unchanged": int((s == 0).sum()),
    }])


def sector_rows(latest_with_sector: pd.DataFrame, as_of: str, trade_date: str) -> pd.DataFrame:
    rows = []
    for sector, g in latest_with_sector.groupby("sector"):
        w = g["cap"].clip(lower=0)
        chg = float(np.average(g["chg_pct"], weights=w)) if w.sum() > 0 \
            else float(g["chg_pct"].mean())
        rows.append({"as_of": as_of, "trade_date": trade_date, "kind": "sector",
                     "key": sector, "chg_pct": chg,
                     "value_krw": float(g["value"].sum()), "n": len(g)})
    return pd.DataFrame(rows)


def merge_timeline(existing: pd.DataFrame | None, new_rows: pd.DataFrame) -> pd.DataFrame:
    """당일이면 append, 날짜가 바뀌면 리셋 — 타임라인은 당일만 보존한다."""
    if existing is None or existing.empty:
        return new_rows
    today = new_rows["trade_date"].iloc[0]
    if (existing["trade_date"] != today).any():
        return new_rows
    return pd.concat([existing, new_rows], ignore_index=True)


def is_open_kst(now: datetime) -> bool:
    t = now.astimezone(KST)
    return t.weekday() < 5 and dtime(9, 0) <= t.time() < dtime(15, 30)


def snapshot_active(trade_date: str, as_of: str, now: datetime) -> bool:
    """서빙 강등 판정. 장중 40분 스테일 또는 2영업일 이상 낡음 → False."""
    t = now.astimezone(KST)
    if int(np.busday_count(trade_date, t.strftime("%Y-%m-%d"))) >= 2:
        return False
    if is_open_kst(t):
        as_of_dt = datetime.strptime(as_of, "%Y-%m-%d %H:%M").replace(tzinfo=KST)
        if (t - as_of_dt) > timedelta(minutes=STALE_MINUTES):
            return False
    return True


def top_value(latest: pd.DataFrame, n: int = TOP_N) -> pd.DataFrame:
    return latest.nlargest(n, "value")


def top_movers(latest: pd.DataFrame, n: int = TOP_N) -> tuple[pd.DataFrame, pd.DataFrame]:
    eligible = latest[(latest["cap"] >= MOVER_MIN_CAP) & (latest["value"] >= MOVER_MIN_VALUE)]
    return eligible.nlargest(n, "chg_pct"), eligible.nsmallest(n, "chg_pct")
```

- [ ] **Step 4: 통과 확인** — Run: `cd server && python -m pytest tests/test_kr_intraday_module.py -q` → Expected: PASS (10 tests)
- [ ] **Step 5: Commit** — `git add server/module/kr_intraday.py server/tests/test_kr_intraday_module.py && git commit -m "feat(server): KR 장중 스냅샷 순수 모듈"`

---

### Task 2: 폴러 엔트리포인트 `server/app/intraday_poller.py`

**Files:**
- Create: `server/app/intraday_poller.py`
- Test: `server/tests/test_intraday_poller.py`

**Interfaces:**
- Consumes: Task 1 전체, `datastore.storage.read_parquet/write_parquet/exists`
- Produces: `handler(event, context) -> dict` — Lambda CMD `app.intraday_poller.handler`

- [ ] **Step 1: 실패하는 테스트 작성** — `server/tests/test_intraday_poller.py`

기존 `tests/conftest.py`의 로컬 APP_DATA 픽스처 패턴을 따른다 (`test_us_prices_builder.py` 참조 — tmp_path를 APP_DATA로 지정). pykrx·미러 로더는 monkeypatch.

```python
"""폴러 오케스트레이션 테스트 — KRX·미러 I/O는 전부 monkeypatch."""

import pandas as pd
import pytest

from app import intraday_poller as poller
from datastore import storage


@pytest.fixture
def app_data(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    return tmp_path


def _snap(chg: float) -> pd.DataFrame:
    df = pd.DataFrame({"시가": [100.0], "고가": [110.0], "저가": [95.0], "종가": [105.0],
                       "거래량": [1000], "거래대금": [5e9], "등락률": [chg],
                       "시가총액": [4e11]}, index=["005930"])
    df.index.name = "티커"
    return df


def test_handler_writes_both_files(app_data, monkeypatch):
    monkeypatch.setattr(poller, "_fetch_krx",
        lambda today: ({"KOSPI": _snap(5.0)}, {"KOSPI": 6300.0}))
    monkeypatch.setattr(poller, "_sector_map",
        lambda: pd.DataFrame({"ticker": ["005930"], "sector": ["전기전자"], "name": ["삼성전자"]}))
    monkeypatch.setattr(poller, "_prev_index_closes", lambda: {"KOSPI": 6000.0})

    out = poller.handler({}, None)
    assert out["status"] == "ok"
    latest = storage.read_parquet("kr_intraday_latest.parquet")
    assert latest.iloc[0]["chg_pct"] == 5.0
    assert latest.iloc[0]["sector"] == "전기전자"
    tl = storage.read_parquet("kr_intraday_timeline.parquet")
    assert set(tl["kind"]) == {"index", "breadth", "sector"}

    # 두 번째 폴 → 같은 날 append (지수 행 2개)
    poller.handler({}, None)
    tl2 = storage.read_parquet("kr_intraday_timeline.parquet")
    assert (tl2["kind"] == "index").sum() == 2


def test_handler_holiday_noop(app_data, monkeypatch):
    monkeypatch.setattr(poller, "_fetch_krx", lambda today: ({}, {}))
    out = poller.handler({}, None)
    assert out["status"] == "holiday-noop"
    assert not storage.exists("kr_intraday_latest.parquet")
```

- [ ] **Step 2: 실패 확인** — Run: `cd server && python -m pytest tests/test_intraday_poller.py -q` → Expected: FAIL (import error)

- [ ] **Step 3: 구현** — `server/app/intraday_poller.py`

```python
"""KR 장중 폴러 — Lambda 엔트리포인트 (스펙 2026-08-11 D1).

서빙과 같은 컨테이너 이미지에서 CMD 오버라이드("app.intraday_poller.handler")로
뜬다. EventBridge cron(5,35 0-6 ? * MON-FRI *) UTC = 09:05~15:35 KST 30분 간격.
실패 시 파일을 갱신하지 않고 예외를 올린다 — 강등은 서빙의 스테일 가드 책임이므로
여기서 삼키지 않는다.
"""

import logging
import os
from datetime import datetime

import pandas as pd

from datastore import storage
from module import kr_intraday as ki

logger = logging.getLogger(__name__)

INDICES = {"KOSPI": "1001", "KOSDAQ": "2001"}
LATEST_KEY = "kr_intraday_latest.parquet"
TIMELINE_KEY = "kr_intraday_timeline.parquet"


def _fetch_krx(today: str):
    """pykrx 4호출. KRX_ID/KRX_PW는 Lambda env — pykrx가 import 시점에 로그인하고
    세션 만료(1h)는 pykrx 1.2+ get_auth_session이 자동 재로그인한다."""
    from pykrx import stock  # lazy: env 자격증명 로그인 선행

    frames = {m: stock.get_market_ohlcv_by_ticker(today, market=m)
              for m in ("KOSPI", "KOSDAQ")}
    levels = {}
    for key, code in INDICES.items():
        idx = stock.get_index_ohlcv_by_date(today, today, code)
        if not idx.empty:
            levels[key] = float(idx["종가"].iloc[-1])
    return frames, levels


def _sector_map() -> pd.DataFrame:
    lake = os.environ["QDATA_LAKE"]
    df = pd.read_parquet(f"{lake}/clean/krx_sector.parquet",
                         columns=["date", "ticker", "sector", "name"])
    latest = df[df["date"] == df["date"].max()]
    return latest[["ticker", "sector", "name"]].drop_duplicates("ticker")


def _prev_index_closes() -> dict[str, float]:
    lake = os.environ["QDATA_LAKE"]
    df = pd.read_parquet(f"{lake}/clean/krx_index_prices.parquet",
                         columns=["date", "index_code", "close"],
                         filters=[("index_code", "in", list(INDICES.values()))])
    code_to_key = {v: k for k, v in INDICES.items()}
    out = {}
    for code, g in df.groupby("index_code"):
        out[code_to_key[code]] = float(g.sort_values("date")["close"].iloc[-1])
    return out


def handler(event, context):
    now = datetime.now(ki.KST)
    today = now.strftime("%Y%m%d")
    frames, levels = _fetch_krx(today)
    if not levels:
        logger.info("지수 당일 행 없음 — 휴장 no-op")
        return {"status": "holiday-noop"}

    trade_date = now.strftime("%Y-%m-%d")
    as_of = now.strftime("%Y-%m-%d %H:%M")
    latest = ki.normalize_snapshot(frames, as_of, trade_date)
    latest = ki.with_sector(latest, _sector_map())

    rows = pd.concat([
        ki.index_rows(levels, _prev_index_closes(), as_of, trade_date),
        ki.breadth_row(latest, as_of, trade_date),
        ki.sector_rows(latest, as_of, trade_date),
    ], ignore_index=True)
    existing = (storage.read_parquet(TIMELINE_KEY)
                if storage.exists(TIMELINE_KEY) else None)
    timeline = ki.merge_timeline(existing, rows)

    storage.write_parquet(latest, LATEST_KEY)
    storage.write_parquet(timeline, TIMELINE_KEY)
    return {"status": "ok", "tickers": len(latest),
            "polls": int(timeline["as_of"].nunique())}
```

- [ ] **Step 4: 통과 확인** — Run: `cd server && python -m pytest tests/test_intraday_poller.py -q` → Expected: PASS. 전체 회귀: `python -m pytest tests/ -q` PASS.
- [ ] **Step 5: 로컬 실기동 검증 (장중이면)** — Run: `cd server && KRX_ID=<quant-data/.env 값> KRX_PW=<동일> QDATA_LAKE=$HOME/Quant/data-lake APP_DATA=/tmp/intraday-test python -c "from app.intraday_poller import handler; print(handler({}, None))"` → Expected: `{'status': 'ok', 'tickers': ~2700, 'polls': 1}`. 휴장·장외라도 파일 생성 여부만 확인.
- [ ] **Step 6: Commit** — `git add server/app/intraday_poller.py server/tests/test_intraday_poller.py && git commit -m "feat(server): 장중 폴러 Lambda 엔트리포인트"`

---

### Task 3: 서빙 라우터 `GET /intraday/market`

**Files:**
- Create: `server/app/routers/intraday.py`
- Modify: `server/app/main.py` (import + `app.include_router(intraday.router)`)
- Test: `server/tests/test_intraday_api.py`

**Interfaces:**
- Consumes: Task 1 helpers, `datastore.storage`, `datastore.watchlist.list_items()`, `datastore.holdings.list_items()`, `datastore.meta.meta_df()` ([meta_id, ticker, name, iso_code, …])
- Produces: 응답 스키마 (Task 4 클라 타입과 1:1):

```json
{ "active": true, "is_open": true, "as_of": "2026-08-11 11:35", "trade_date": "2026-08-11",
  "indices": [{"key": "KOSPI", "level": 6346.5, "chg_pct": 1.2,
               "sparkline": [{"t": "09:35", "level": 6300.1}]}],
  "breadth": {"advancers": 512, "decliners": 380, "unchanged": 50},
  "sectors": [{"name": "전기전자", "chg_pct": 3.2, "value_krw": 2.1e12, "n": 103,
               "flow": [{"t": "09:35", "chg_pct": 1.1}]}],
  "top_value": [{"ticker": "005930", "name": "삼성전자", "close": 240000,
                 "chg_pct": 4.35, "value": 2.2e12}],
  "top_movers": {"up": [...], "down": [...]},
  "my": {"watchlist": [{"meta_id": 1, "ticker": "005930", "name": "삼성전자",
                        "close": 240000, "chg_pct": 4.35}], "holdings": [...]} }
```

- [ ] **Step 1: 실패하는 테스트 작성** — `server/tests/test_intraday_api.py`

기존 API 테스트 패턴(`test_spotlight_api.py`의 TestClient + APP_DATA tmp_path 픽스처)을 따른다. 케이스 4개:

```python
"""GET /intraday/market 테스트 — 조립·강등·필터."""

from datetime import datetime, timedelta

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app
from datastore import storage
from module import kr_intraday as ki

client = TestClient(app)


@pytest.fixture
def app_data(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    monkeypatch.delenv("API_TOKEN", raising=False)
    return tmp_path


def _now_kst():
    return datetime.now(ki.KST)


def _write_snapshot(chg=4.0, cap=4e11, value=5e9, as_of=None, trade_date=None):
    now = _now_kst()
    as_of = as_of or now.strftime("%Y-%m-%d %H:%M")
    trade_date = trade_date or now.strftime("%Y-%m-%d")
    latest = pd.DataFrame({
        "ticker": ["005930", "035720"], "market": ["KOSPI", "KOSDAQ"],
        "open": [100.0, 50.0], "high": [110.0, 55.0], "low": [95.0, 50.0],
        "close": [105.0, 50.0], "volume": [1000, 100], "value": [value, 1e9],
        "chg_pct": [chg, -1.0], "cap": [cap, 5e10],
        "as_of": as_of, "trade_date": trade_date,
        "sector": ["전기전자", "게임"], "name": ["삼성전자", "카카오게임즈"],
    })
    storage.write_parquet(latest, "kr_intraday_latest.parquet")
    tl = pd.concat([
        ki.index_rows({"KOSPI": 6300.0, "KOSDAQ": 850.0},
                      {"KOSPI": 6000.0, "KOSDAQ": 860.0}, as_of, trade_date),
        ki.breadth_row(latest, as_of, trade_date),
        ki.sector_rows(latest, as_of, trade_date),
    ], ignore_index=True)
    storage.write_parquet(tl, "kr_intraday_timeline.parquet")


def test_missing_files_inactive(app_data):
    r = client.get("/intraday/market")
    assert r.status_code == 200
    assert r.json() == {"active": False}


def test_assembled_response(app_data):
    _write_snapshot()
    body = client.get("/intraday/market").json()
    assert body["active"] is True
    kospi = next(i for i in body["indices"] if i["key"] == "KOSPI")
    assert kospi["chg_pct"] == pytest.approx(5.0)
    assert len(kospi["sparkline"]) == 1
    assert body["breadth"]["advancers"] == 1
    names = [s["name"] for s in body["sectors"]]
    assert "전기전자" in names and body["sectors"][0]["flow"]
    assert body["top_value"][0]["ticker"] == "005930"
    # 급등락 필터: 035720은 cap 미달로 down에 없어야 한다
    assert all(m["ticker"] != "035720" for m in body["top_movers"]["down"])


def test_stale_snapshot_inactive(app_data):
    old = _now_kst() - timedelta(days=7)
    _write_snapshot(as_of=old.strftime("%Y-%m-%d %H:%M"),
                    trade_date=old.strftime("%Y-%m-%d"))
    assert client.get("/intraday/market").json() == {"active": False}


def test_corrupt_file_returns_inactive_not_500(app_data, tmp_path):
    (tmp_path / "kr_intraday_latest.parquet").write_text("not parquet")
    (tmp_path / "kr_intraday_timeline.parquet").write_text("not parquet")
    r = client.get("/intraday/market")
    assert r.status_code == 200
    assert r.json() == {"active": False}
```

- [ ] **Step 2: 실패 확인** — Run: `cd server && python -m pytest tests/test_intraday_api.py -q` → Expected: FAIL (404 — 라우터 없음)

- [ ] **Step 3: 구현** — `server/app/routers/intraday.py`

```python
"""장중 마켓 현황 서빙 (스펙 2026-08-11 D3). 실패·스테일은 {"active": false} — 500 금지."""

import logging
from datetime import datetime

import pandas as pd
from fastapi import APIRouter

from datastore import holdings as holdings_store
from datastore import meta as meta_store
from datastore import storage
from datastore import watchlist as watchlist_store
from module import kr_intraday as ki

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/intraday", tags=["intraday"])

_STOCK_COLS = ["ticker", "name", "close", "chg_pct", "value"]


def _stock_rows(df: pd.DataFrame) -> list[dict]:
    return df[_STOCK_COLS].to_dict("records")


def _my_rows(latest: pd.DataFrame, items: pd.DataFrame) -> list[dict]:
    if items.empty:
        return []
    m = meta_store.meta_df()[["meta_id", "ticker", "name", "iso_code"]]
    m = m[m["iso_code"] == "KR"]
    joined = items.merge(m, on="meta_id").merge(
        latest[["ticker", "close", "chg_pct", "value"]], on="ticker")
    joined = joined.sort_values("chg_pct", ascending=False)
    return joined[["meta_id", "ticker", "name", "close", "chg_pct"]].to_dict("records")


@router.get("/market")
def get_market():
    try:
        return _build()
    except Exception as e:  # noqa: BLE001 — 어떤 실패든 강등 (Global Constraint)
        logger.warning(f"intraday 조립 실패 — inactive 강등: {e}")
        return {"active": False}


def _build():
    if not (storage.exists("kr_intraday_latest.parquet")
            and storage.exists("kr_intraday_timeline.parquet")):
        return {"active": False}
    latest = storage.read_parquet("kr_intraday_latest.parquet")
    timeline = storage.read_parquet("kr_intraday_timeline.parquet")
    if latest.empty or timeline.empty:
        return {"active": False}

    as_of = str(latest["as_of"].iloc[0])
    trade_date = str(latest["trade_date"].iloc[0])
    now = datetime.now(ki.KST)
    if not ki.snapshot_active(trade_date, as_of, now):
        return {"active": False}

    def hhmm(s: str) -> str:
        return s[-5:]

    indices = []
    for key, g in timeline[timeline["kind"] == "index"].groupby("key"):
        g = g.sort_values("as_of")
        indices.append({
            "key": key, "level": float(g["level"].iloc[-1]),
            "chg_pct": None if pd.isna(g["chg_pct"].iloc[-1]) else float(g["chg_pct"].iloc[-1]),
            "sparkline": [{"t": hhmm(r.as_of), "level": float(r.level)}
                          for r in g.itertuples()],
        })

    b = timeline[timeline["kind"] == "breadth"].sort_values("as_of").iloc[-1]
    breadth = {"advancers": int(b["advancers"]), "decliners": int(b["decliners"]),
               "unchanged": int(b["unchanged"])}

    sectors = []
    sec = timeline[timeline["kind"] == "sector"]
    last_poll = sec[sec["as_of"] == sec["as_of"].max()]
    for r in last_poll.sort_values("value_krw", ascending=False).itertuples():
        flow = sec[sec["key"] == r.key].sort_values("as_of")
        sectors.append({"name": r.key, "chg_pct": float(r.chg_pct),
                        "value_krw": float(r.value_krw), "n": int(r.n),
                        "flow": [{"t": hhmm(f.as_of), "chg_pct": float(f.chg_pct)}
                                 for f in flow.itertuples()]})

    up, down = ki.top_movers(latest)
    return {
        "active": True, "is_open": ki.is_open_kst(now),
        "as_of": as_of, "trade_date": trade_date,
        "indices": indices, "breadth": breadth, "sectors": sectors,
        "top_value": _stock_rows(ki.top_value(latest)),
        "top_movers": {"up": _stock_rows(up), "down": _stock_rows(down)},
        "my": {"watchlist": _my_rows(latest, watchlist_store.list_items()),
               "holdings": _my_rows(latest, holdings_store.list_items())},
    }
```

`server/app/main.py`: import 목록에 `intraday` 추가, 라우터 등록 블록에 `app.include_router(intraday.router)` 추가.

- [ ] **Step 4: 통과 확인** — Run: `cd server && python -m pytest tests/test_intraday_api.py -q` PASS, `python -m pytest tests/ -q` 전체 PASS
- [ ] **Step 5: Commit** — `git add server/app/routers/intraday.py server/app/main.py server/tests/test_intraday_api.py && git commit -m "feat(server): GET /intraday/market — 장중 현황 조립·강등"`

---

### Task 4: 클라 타입·엔드포인트 + 인사이트 2탭 + 지수 스트립

**Files:**
- Modify: `client/src/state/api.ts`
- Modify: `client/src/app/insight/page.tsx`
- Create: `client/src/app/insight/intraday/IntradayTab.tsx`, `Sparkline.tsx`, `IntradayIndexStrip.tsx`

**Interfaces:**
- Consumes: Task 3 응답 스키마
- Produces: `IntradayMarketResponse` 타입, `useFetchIntradayMarketQuery` 훅 (Task 5·6이 사용), `IntradayTab` (Task 5가 블록을 채움)

- [ ] **Step 1: `api.ts`에 타입 추가** (기존 타입 블록 근처):

```typescript
export interface IntradayStockRow {
  ticker: string;
  name: string;
  close: number;
  chg_pct: number;
  value?: number;
  meta_id?: number;
}

export interface IntradaySectorRow {
  name: string;
  chg_pct: number;
  value_krw: number;
  n: number;
  flow: { t: string; chg_pct: number }[];
}

export interface IntradayMarketResponse {
  active: boolean;
  is_open?: boolean;
  as_of?: string;
  trade_date?: string;
  indices?: {
    key: string;
    level: number;
    chg_pct: number | null;
    sparkline: { t: string; level: number }[];
  }[];
  breadth?: { advancers: number; decliners: number; unchanged: number };
  sectors?: IntradaySectorRow[];
  top_value?: IntradayStockRow[];
  top_movers?: { up: IntradayStockRow[]; down: IntradayStockRow[] };
  my?: { watchlist: IntradayStockRow[]; holdings: IntradayStockRow[] };
}
```

- [ ] **Step 2: 엔드포인트 추가** (builder.query 블록, `fetchInsightIndex` 근처):

```typescript
    fetchIntradayMarket: builder.query<IntradayMarketResponse, void>({
      query: () => "intraday/market",
    }),
```

export 훅 목록에 `useFetchIntradayMarketQuery` 추가 (파일 하단 export 패턴 그대로).

- [ ] **Step 3: `Sparkline.tsx`** — 의존성 없는 인라인 SVG 미니 라인:

```tsx
import React from "react";

/** 축 없는 미니 라인 — 지수 타일용. 값 범위를 뷰박스에 정규화만 한다. */
const Sparkline = ({
  points,
  color,
  width = 96,
  height = 28,
}: {
  points: number[];
  color: string;
  width?: number;
  height?: number;
}) => {
  if (points.length < 2) return null;
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  const step = width / (points.length - 1);
  const d = points
    .map((v, i) => `${i === 0 ? "M" : "L"}${(i * step).toFixed(1)},${(
      height - ((v - min) / span) * (height - 4) - 2
    ).toFixed(1)}`)
    .join(" ");
  return (
    <svg width={width} height={height} aria-hidden>
      <path d={d} fill="none" stroke={color} strokeWidth={1.5} />
    </svg>
  );
};

export default Sparkline;
```

- [ ] **Step 4: `IntradayIndexStrip.tsx`** — 지수 2타일 + 브레드스. 기존 카드 규약(`card`, `metric-label`, `metric-value`)과 `fmtPct`/`signClass`(`@/app/insight/format`) 재사용:

```tsx
import React from "react";
import { IntradayMarketResponse } from "@/state/api";
import { fmtPct, signClass } from "@/app/insight/format";
import Sparkline from "./Sparkline";

/** 장중 지수·브레드스 스트립 — data.active가 참일 때만 렌더된다. */
const IntradayIndexStrip = ({ data }: { data: IntradayMarketResponse }) => {
  const breadth = data.breadth;
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      {(data.indices ?? []).map((idx) => (
        <div key={idx.key} className="card flex items-center justify-between gap-2">
          <div>
            <p className="metric-label">{idx.key}</p>
            <div className="flex items-baseline gap-2">
              <p className="metric-value">
                {idx.level.toLocaleString(undefined, { maximumFractionDigits: 2 })}
              </p>
              <span className={`text-sm ${signClass(idx.chg_pct)}`}>
                {fmtPct(idx.chg_pct)}
              </span>
            </div>
          </div>
          <Sparkline
            points={idx.sparkline.map((p) => p.level)}
            color={
              (idx.chg_pct ?? 0) >= 0 ? "var(--gains)" : "var(--losses)"
            }
          />
        </div>
      ))}
      {breadth && (
        <div className="card flex flex-col justify-between gap-1">
          <p className="metric-label">시장폭 (KR 전 종목)</p>
          <div className="flex items-baseline gap-3 text-sm">
            <span className="text-gains font-semibold">▲ {breadth.advancers}</span>
            <span className="text-losses font-semibold">▼ {breadth.decliners}</span>
            <span className="text-ink-muted">− {breadth.unchanged}</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default IntradayIndexStrip;
```

- [ ] **Step 5: `IntradayTab.tsx` 골격** — Task 5에서 블록을 추가한다. 이 시점엔 배지 + 스트립만:

```tsx
import React from "react";
import { IntradayMarketResponse } from "@/state/api";
import IntradayIndexStrip from "./IntradayIndexStrip";

/** 장중 탭 본문. 상단 배지에 지연·기준시각을 명시한다 (스펙 D4). */
const IntradayTab = ({ data }: { data: IntradayMarketResponse }) => (
  <div className="flex flex-col gap-6">
    <div className="flex items-center gap-2 text-xs text-ink-muted">
      <span className="px-2 py-0.5 rounded-md bg-losses/10 text-losses font-semibold">
        {data.is_open ? "🔴 장중" : "15:30 마감"}
      </span>
      <span>지연 시세 · {data.as_of?.slice(-5)} 기준 (~20분 지연)</span>
    </div>
    <IntradayIndexStrip data={data} />
  </div>
);

export default IntradayTab;
```

- [ ] **Step 6: `insight/page.tsx` 2탭 개편** — 전체 교체:

```tsx
"use client";

import React, { useEffect, useRef, useState } from "react";
import { InsightMarket, useFetchIntradayMarketQuery } from "@/state/api";
import PageHeader from "@/components/ui/PageHeader";
import IndexBreadthStrip from "./IndexBreadthStrip";
import FlowsSection from "./FlowsSection";
import SectorSection from "./SectorSection";
import FactorSection from "./FactorSection";
import ValuationSection from "./ValuationSection";
import SignalsSection from "./SignalsSection";
import BreadthHistory from "./BreadthHistory";
import IntradayTab from "./intraday/IntradayTab";

type Tab = "live" | "settled";

/** KR market insight: 장중(지연 스냅샷) | 정산(일배치) 2탭. */
const InsightPage = () => {
  const [market, setMarket] = useState<InsightMarket>("KOSPI");
  const [tab, setTab] = useState<Tab>("settled");
  const { data: intraday } = useFetchIntradayMarketQuery(undefined, {
    pollingInterval: 5 * 60 * 1000,
    skipPollingIfUnfocused: true,
  });
  const active = intraday?.active === true;

  // 첫 로드에 한해 기본 탭 결정: 장중이면 live (스펙 D4).
  const defaulted = useRef(false);
  useEffect(() => {
    if (!defaulted.current && intraday) {
      defaulted.current = true;
      if (intraday.active && intraday.is_open) setTab("live");
    }
  }, [intraday]);

  return (
    <div className="flex flex-col gap-6 pb-16">
      <PageHeader
        title="KR Market Insight"
        description="수급·시장폭·신호 — KRX 전 종목 데이터 기반"
      />

      {active && (
        <div className="flex gap-1 border-b border-ink/10">
          {(
            [
              ["live", intraday?.is_open ? "🔴 장중" : "오늘 마감"],
              ["settled", "정산 인사이트"],
            ] as [Tab, string][]
          ).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition-colors ${
                tab === key
                  ? "border-ink text-ink"
                  : "border-transparent text-ink-muted hover:text-ink"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      )}

      {active && tab === "live" && intraday ? (
        <IntradayTab data={intraday} />
      ) : (
        <>
          <IndexBreadthStrip market={market} onMarketChange={setMarket} />
          <FlowsSection />
          <SectorSection />
          <FactorSection />
          <ValuationSection />
          <SignalsSection />
          <BreadthHistory market={market} onMarketChange={setMarket} />
        </>
      )}
    </div>
  );
};

export default InsightPage;
```

- [ ] **Step 7: 검증** — Run: `cd client && npm run lint && npx tsc --noEmit` → Expected: 둘 다 exit 0 (파이프로 가리지 말 것). `npm run dev` 후 `/insight` 접속 — 서버 미기동/active:false면 기존 화면 그대로여야 한다.
- [ ] **Step 8: Commit** — `git add client/src/state/api.ts client/src/app/insight/ && git commit -m "feat(client): 인사이트 2탭 + 장중 지수 스트립"`

---

### Task 5: 장중 블록 — 섹터 히트맵·흐름·순위·내 종목

**Files:**
- Create: `client/src/app/insight/intraday/SectorHeatmapLive.tsx`, `SectorFlowChart.tsx`, `RankTables.tsx`, `MyIntraday.tsx`
- Modify: `client/src/app/insight/intraday/IntradayTab.tsx`

**Interfaces:**
- Consumes: `IntradayMarketResponse` (Task 4), `TimeSeriesChart`(`@/components/charts/TimeSeriesChart` — props: `data`, `series[{key,name,color}]`, `height`, `yFormatter`), 기존 `table-header`/`table-cell`/`card` 클래스, `fmtPct`/`signClass`

- [ ] **Step 1: `SectorHeatmapLive.tsx`** — 26업종 타일, 색=등락률(color-mix 강도), 크기=거래대금 3티어(col-span):

```tsx
import React from "react";
import { IntradaySectorRow } from "@/state/api";
import { fmtPct } from "@/app/insight/format";

const tileColor = (chg: number) => {
  const base = chg >= 0 ? "var(--gains)" : "var(--losses)";
  const pct = Math.min(Math.abs(chg) / 3, 1) * 28 + 6; // ±3% 포화, 6~34% 틴트
  return `color-mix(in srgb, ${base} ${pct.toFixed(0)}%, transparent)`;
};

/** 섹터 히트맵 — 거래대금 내림차순, 상위 4개는 2칸 타일. */
const SectorHeatmapLive = ({ sectors }: { sectors: IntradaySectorRow[] }) => (
  <div className="card">
    <h4 className="text-base font-semibold text-ink mb-4">섹터 히트맵</h4>
    <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-6 gap-1.5">
      {sectors.map((s, i) => (
        <div
          key={s.name}
          className={`rounded-lg p-2.5 flex flex-col justify-between min-h-[64px] ${
            i < 4 ? "col-span-2" : ""
          }`}
          style={{ backgroundColor: tileColor(s.chg_pct) }}
        >
          <p className="text-xs font-medium text-ink truncate">{s.name}</p>
          <p className={`num text-sm font-semibold ${
            s.chg_pct >= 0 ? "text-gains" : "text-losses"
          }`}>
            {fmtPct(s.chg_pct)}
          </p>
        </div>
      ))}
    </div>
  </div>
);

export default SectorHeatmapLive;
```

- [ ] **Step 2: `SectorFlowChart.tsx`** — 거래대금 상위 8업종 당일 흐름, `TimeSeriesChart` 재사용:

```tsx
import React, { useMemo } from "react";
import TimeSeriesChart from "@/components/charts/TimeSeriesChart";
import { IntradaySectorRow } from "@/state/api";

const COLORS = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)",
  "var(--chart-4)", "var(--chart-5)", "var(--chart-6)",
  "var(--chart-7)", "var(--chart-8)"];

/** 당일 섹터 등락률 흐름 — 거래대금 상위 8업종 (스펙 D4). sectors는 이미
 *  value_krw 내림차순이므로 앞 8개를 취한다. */
const SectorFlowChart = ({ sectors }: { sectors: IntradaySectorRow[] }) => {
  const top = sectors.slice(0, 8);
  const { data, series } = useMemo(() => {
    const byTime = new Map<string, Record<string, string | number | null>>();
    for (const s of top) {
      for (const p of s.flow) {
        const row = byTime.get(p.t) ?? { date: p.t };
        row[s.name] = p.chg_pct;
        byTime.set(p.t, row);
      }
    }
    return {
      data: [...byTime.values()].sort((a, b) =>
        String(a.date).localeCompare(String(b.date))
      ),
      series: top.map((s, i) => ({
        key: s.name,
        name: s.name,
        color: COLORS[i % COLORS.length],
      })),
    };
  }, [top]);

  if (data.length < 2) return null; // 폴 1회뿐이면 라인이 무의미
  return (
    <div className="card">
      <h4 className="text-base font-semibold text-ink mb-4">
        섹터 흐름 — 거래대금 상위 8업종 (당일, %)
      </h4>
      <TimeSeriesChart
        data={data}
        series={series}
        height={320}
        yFormatter={(v: number) => `${v.toFixed(1)}%`}
      />
    </div>
  );
};

export default SectorFlowChart;
```

주의: `TimeSeriesChart`의 x축 키가 `date`가 아닐 경우(컴포넌트를 열어 실제 prop 계약 확인) 해당 키명에 맞춘다. `--chart-5`~`--chart-8` 토큰이 `globals.css`에 없으면 있는 토큰 수까지만 쓰고 나머지는 순환한다.

- [ ] **Step 3: `RankTables.tsx`** — 거래대금 TOP10 + 급등/급락 TOP10, 행 클릭 → `/stock/[ticker]` 상세(기존 stocksearch 행 링크 규약 확인 후 동일 경로 사용):

```tsx
import React from "react";
import Link from "next/link";
import { IntradayStockRow } from "@/state/api";
import { fmtPct, signClass } from "@/app/insight/format";

const fmtValue = (v?: number) =>
  v == null ? "—" : `${(v / 1e8).toLocaleString(undefined, { maximumFractionDigits: 0 })}억`;

const StockTable = ({ title, rows }: { title: string; rows: IntradayStockRow[] }) => (
  <div className="card">
    <h4 className="text-base font-semibold text-ink mb-4">{title}</h4>
    <table className="w-full text-sm">
      <thead>
        <tr className="table-header">
          <th className="py-2 px-3 text-left rounded-l-lg">종목</th>
          <th className="py-2 px-3 text-right">현재가</th>
          <th className="py-2 px-3 text-right">등락률</th>
          <th className="py-2 px-3 text-right rounded-r-lg">거래대금</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.ticker} className="table-row">
            <td className="table-cell">
              <Link href={`/stock/${r.ticker}`} className="hover:underline">
                {r.name || r.ticker}
              </Link>
            </td>
            <td className="table-cell text-right num">{r.close.toLocaleString()}</td>
            <td className={`table-cell text-right num ${signClass(r.chg_pct)}`}>
              {fmtPct(r.chg_pct)}
            </td>
            <td className="table-cell text-right num text-ink-muted">{fmtValue(r.value)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

/** 거래대금·급등락 순위 블록. */
const RankTables = ({
  topValue,
  up,
  down,
}: {
  topValue: IntradayStockRow[];
  up: IntradayStockRow[];
  down: IntradayStockRow[];
}) => (
  <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
    <StockTable title="거래대금 TOP 10" rows={topValue} />
    <StockTable title="급등 TOP 10" rows={up} />
    <StockTable title="급락 TOP 10" rows={down} />
  </div>
);

export default RankTables;
```

- [ ] **Step 4: `MyIntraday.tsx`** — 관심·보유 통합(중복 티커는 보유 우선), 등락률 정렬:

```tsx
import React from "react";
import Link from "next/link";
import { IntradayMarketResponse } from "@/state/api";
import { fmtPct, signClass } from "@/app/insight/format";
import EmptyState from "@/components/ui/EmptyState";

/** 내 종목(관심·보유 KR) 장중 현황 — 서버가 등락률 내림차순으로 준다. */
const MyIntraday = ({ my }: { my: NonNullable<IntradayMarketResponse["my"]> }) => {
  const holdingTickers = new Set(my.holdings.map((r) => r.ticker));
  const rows = [
    ...my.holdings.map((r) => ({ ...r, kind: "보유" as const })),
    ...my.watchlist
      .filter((r) => !holdingTickers.has(r.ticker))
      .map((r) => ({ ...r, kind: "관심" as const })),
  ].sort((a, b) => b.chg_pct - a.chg_pct);

  return (
    <div className="card">
      <h4 className="text-base font-semibold text-ink mb-4">내 종목 장중 현황</h4>
      {rows.length === 0 ? (
        <EmptyState title="KR 관심·보유 종목 없음" hint="관심 종목을 등록하면 장중 현황이 표시됩니다" />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {rows.map((r) => (
            <Link
              key={r.ticker}
              href={`/stock/${r.ticker}`}
              className="flex items-center justify-between rounded-lg border border-ink/10 px-3 py-2 hover:bg-ink/5"
            >
              <span className="text-sm text-ink truncate">
                {r.name || r.ticker}
                <span className="ml-1.5 text-[10px] text-ink-muted">{r.kind}</span>
              </span>
              <span className={`num text-sm font-semibold ${signClass(r.chg_pct)}`}>
                {fmtPct(r.chg_pct)}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
};

export default MyIntraday;
```

- [ ] **Step 5: `IntradayTab.tsx`에 블록 조립** — Task 4 골격의 `<IntradayIndexStrip />` 아래에 순서대로 추가:

```tsx
    {data.sectors && data.sectors.length > 0 && (
      <>
        <SectorHeatmapLive sectors={data.sectors} />
        <SectorFlowChart sectors={data.sectors} />
      </>
    )}
    {data.top_value && data.top_movers && (
      <RankTables topValue={data.top_value} up={data.top_movers.up} down={data.top_movers.down} />
    )}
    {data.my && <MyIntraday my={data.my} />}
```

- [ ] **Step 6: 검증** — `cd client && npm run lint && npx tsc --noEmit` exit 0. 로컬 서버에 Task 2 Step 5의 테스트 파일(APP_DATA=/tmp/intraday-test)을 물려 `/insight` 장중 탭 렌더 확인.
- [ ] **Step 7: Commit** — `git add client/src/app/insight/intraday/ && git commit -m "feat(client): 장중 섹터 히트맵·흐름·순위·내 종목 블록"`

---

### Task 6: 홈 장중화 — MarketTiles·내 종목 칩

**Files:**
- Modify: `client/src/app/home/MarketTiles.tsx`
- Modify: `client/src/app/home/WatchlistCard.tsx`, `client/src/app/home/PortfolioCard.tsx`

**Interfaces:**
- Consumes: `useFetchIntradayMarketQuery` (Task 4). RTK Query는 동일 쿼리를 자동 dedupe하므로 홈·인사이트 동시 사용에 추가 비용 없다.

- [ ] **Step 1: MarketTiles 장중 오버라이드** — `useFetchIntradayMarketQuery` 추가(폴링 옵션 Task 4와 동일), `snapshots` useMemo 아래에 오버라이드 적용:

```tsx
  const { data: intraday } = useFetchIntradayMarketQuery(undefined, {
    pollingInterval: 5 * 60 * 1000,
    skipPollingIfUnfocused: true,
  });

  // 장중 스냅샷이 active면 KR 지수 타일만 장중 값으로 교체 (스펙 D4 — US 무관).
  const liveSnapshots = useMemo(() => {
    if (!intraday?.active || !intraday.indices) return snapshots;
    const out = { ...snapshots };
    for (const idx of intraday.indices) {
      if (idx.key === "KOSPI" || idx.key === "KOSDAQ") {
        out[idx.key as InsightMarket] = { close: idx.level, chgPct: idx.chg_pct };
      }
    }
    return out;
  }, [snapshots, intraday]);
```

`IndexTile`에 optional `badge?: string` prop을 추가해 `metric-label` 옆에 표시하고, 렌더에서 `snap={liveSnapshots.KOSPI ?? null}` + `badge={intraday?.active ? `🔴 ${intraday.as_of?.slice(-5)}` : undefined}` 로 교체 (KOSDAQ 동일).

- [ ] **Step 2: Watchlist/Portfolio 카드 KR 칩** — 두 파일을 열어 행 렌더 구조를 확인한 뒤, `useFetchIntradayMarketQuery`의 `my.watchlist`/`my.holdings`를 `meta_id`로 매핑해 행 우측에 장중 등락률 칩(`signClass`/`fmtPct`)을 추가한다. `intraday?.active`가 아닐 때는 칩 자체를 렌더하지 않는다 (기존 표시 무변경). 카드가 이미 등락률을 보여주면 장중 값이 있는 KR 행에 한해 값을 교체하고 `🔴`를 접두한다 — 두 값을 나란히 두지 않는다.
- [ ] **Step 3: 검증** — `cd client && npm run lint && npx tsc --noEmit` exit 0. active:false 상태에서 홈이 기존과 픽셀 단위로 동일해야 한다.
- [ ] **Step 4: Commit** — `git add client/src/app/home/ && git commit -m "feat(client): 홈 KR 지수 타일·내 종목 장중화"`

---

### Task 7: 인프라 — 폴러 함수·스케줄 + US 아침 기동

**Files:**
- Modify: `infra/template.yaml`, `.github/workflows/deploy.yml`

- [ ] **Step 1: `template.yaml`에 파라미터 추가**:

```yaml
  KrxId:
    Type: String
    NoEcho: true
    Description: KRX 정보데이터시스템 로그인 ID (폴러 전용)
  KrxPw:
    Type: String
    NoEcho: true
    Description: KRX 정보데이터시스템 로그인 PW (폴러 전용)
```

- [ ] **Step 2: `template.yaml` Resources에 폴러 3종 추가** (기존 ApiFunction 아래):

```yaml
  PollerRole:
    Type: AWS::IAM::Role
    Properties:
      AssumeRolePolicyDocument:
        Version: "2012-10-17"
        Statement:
          - Effect: Allow
            Principal: { Service: lambda.amazonaws.com }
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
      Policies:
        - PolicyName: intraday-data
          PolicyDocument:
            Version: "2012-10-17"
            Statement:
              - Effect: Allow  # 미러(업종·전일 지수) 읽기
                Action: [s3:GetObject, s3:ListBucket]
                Resource:
                  - !Sub arn:aws:s3:::${DataBucket}
                  - !Sub arn:aws:s3:::${DataBucket}/qdata/*
                  - !Sub arn:aws:s3:::${DataBucket}/app/*
              - Effect: Allow  # 장중 스냅샷 2파일만 쓰기 (스펙 불변식 1)
                Action: [s3:PutObject]
                Resource:
                  - !Sub arn:aws:s3:::${DataBucket}/app/kr_intraday_latest.parquet
                  - !Sub arn:aws:s3:::${DataBucket}/app/kr_intraday_timeline.parquet

  IntradayPollerFunction:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: insight-invest-intraday-poller
      PackageType: Image
      Code: { ImageUri: !Ref ImageUri }
      ImageConfig: { Command: ["app.intraday_poller.handler"] }
      Role: !GetAtt PollerRole.Arn
      Architectures: [x86_64]
      MemorySize: 1024
      Timeout: 120
      Environment:
        Variables:
          QDATA_LAKE: !Sub s3://${DataBucket}/qdata
          APP_DATA: !Sub s3://${DataBucket}/app
          KRX_ID: !Ref KrxId
          KRX_PW: !Ref KrxPw

  # 09:05~15:35 KST 30분 간격 (UTC 00:05~06:35) — 15:35 폴이 마감치 캡처
  IntradayPollerSchedule:
    Type: AWS::Events::Rule
    Properties:
      Name: insight-invest-intraday-poll
      ScheduleExpression: cron(5,35 0-6 ? * MON-FRI *)
      State: ENABLED
      Targets:
        - Arn: !GetAtt IntradayPollerFunction.Arn
          Id: intraday-poller

  IntradayPollerInvokePermission:
    Type: AWS::Lambda::Permission
    Properties:
      FunctionName: !Ref IntradayPollerFunction
      Action: lambda:InvokeFunction
      Principal: events.amazonaws.com
      SourceArn: !GetAtt IntradayPollerSchedule.Arn
```

- [ ] **Step 3: `deploy.yml` parameter-overrides 확장**:

```yaml
            --parameter-overrides ImageUri=$IMAGE_URI ApiToken=${{ secrets.API_TOKEN }} \
              KrxId=${{ secrets.KRX_ID }} KrxPw=${{ secrets.KRX_PW }} \
```

- [ ] **Step 4: GitHub secrets 등록** — Run (로컬, quant-data/.env의 값으로): `cd /Users/achii/Quant/Insight-Invest && gh secret set KRX_ID --body "<KRX_ID 값>" && gh secret set KRX_PW --body "<KRX_PW 값>"` → Expected: `✓ Set Actions secret`
- [ ] **Step 5: US 아침 기동 스케줄 복제** — 기존 `qdata-collector-start`(cron 19:00 Asia/Seoul → ec2:startInstances)와 failsafe를 아침용으로 복제:

```bash
aws scheduler get-schedule --name qdata-collector-start --output json > /tmp/start.json
aws scheduler get-schedule --name qdata-collector-failsafe-stop --output json > /tmp/stop.json
# Target 블록(Arn·RoleArn·Input)을 그대로 재사용해 생성:
aws scheduler create-schedule --name qdata-collector-start-morning \
  --schedule-expression 'cron(0 9 ? * MON-FRI *)' \
  --schedule-expression-timezone Asia/Seoul \
  --flexible-time-window Mode=OFF \
  --target "$(python3 -c "import json;print(json.dumps(json.load(open('/tmp/start.json'))['Target']))")"
aws scheduler create-schedule --name qdata-collector-failsafe-stop-morning \
  --schedule-expression 'cron(40 10 ? * MON-FRI *)' \
  --schedule-expression-timezone Asia/Seoul \
  --flexible-time-window Mode=OFF \
  --target "$(python3 -c "import json;print(json.dumps(json.load(open('/tmp/stop.json'))['Target']))")"
aws scheduler list-schedules --query "Schedules[].Name"   # 4개 확인
```

- [ ] **Step 6: quant-data에 기록** — `quant-data/scripts/server/run_pipeline.sh` 헤더 주석의 기동 설명을 "평일 19:00·09:00 KST"로 갱신하고 아침 기동 목적(US 종가 아침 반영, 스펙 링크) 한 줄 추가. Commit (quant-data 레포): `docs(server): 아침 09:00 기동 추가 기록 — US 종가 아침 반영`
- [ ] **Step 7: Commit + 배포** — `git add infra/template.yaml .github/workflows/deploy.yml && git commit -m "infra: 장중 폴러 Lambda·30분 스케줄 + KRX 자격증명 파라미터"`. 푸시는 메인 스레드 승인 후 (`git push` → deploy-api 워크플로가 스택 갱신).

---

### Task 8: 배포 후 실측 검증 + 기록

**Files:**
- Modify: `docs/superpowers/specs/2026-08-11-kr-intraday-market-design.md` (§12 구현 확인 추가)
- Modify: `~/.claude/projects/-Users-achii-Quant-Insight-Invest/memory/` 관련 메모리

- [ ] **Step 1: 배포 확인** — `gh run watch` 로 deploy-api 성공 확인, `aws lambda get-function --function-name insight-invest-intraday-poller --query 'Configuration.[State,ImageConfigResponse]'`
- [ ] **Step 2: 폴러 수동 기동** — Run: `aws lambda invoke --function-name insight-invest-intraday-poller /tmp/poller-out.json && cat /tmp/poller-out.json` → Expected: `{"status": "ok", "tickers": ~2700, ...}` (휴장이면 holiday-noop). `aws s3 ls s3://insight-invest-datalake/app/ | grep kr_intraday` 로 2파일 확인.
- [ ] **Step 3: API 검증** — Lambda URL에 `curl -s -H "X-API-Key: $(cat <scratchpad>/.token)" <URL>/intraday/market | python3 -m json.tool | head -40` → active·indices·sectors 확인.
- [ ] **Step 4: 프로덕션 화면 검증 (장중)** — 브라우저로 `/insight` 장중 탭·홈 타일 스크린샷. **스크린샷이 진실이다** — get_page_text류는 스테일 프레임을 읽을 수 있다. 네이버 시세와 등락률 방향·크기 대조(지연 ~20분 감안).
- [ ] **Step 5: 다음 영업일 아침 확인 항목 기록** — ① 09:00 EC2 아침 사이클이 US 종가를 반영했는지(app us_prices as_of), ② 09:05 첫 폴이 전일 timeline을 리셋했는지, ③ 아침 브리핑 발송 여부. 스펙 §12에 구현 확인 절 추가(검증 결과·잔여 확인 항목), 메모리 파일(`us-price-cutover-status.md` 또는 신규 `kr-intraday-status.md`)에 운영 상태 기록.
- [ ] **Step 6: Commit** — `git add docs/ && git commit -m "docs(spec): 장중 대시보드 구현 확인 기록"`
