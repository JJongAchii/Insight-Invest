"""장중 마켓 현황 서빙 (스펙 2026-08-11 D3). 실패·스테일은 {"active": false} — 500 금지."""

import logging
import math
from datetime import datetime
from typing import Optional

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


def _r(x, nd: int = 2) -> Optional[float]:
    """유한한 float만 round, 그 외 None (holdings.py `_r()` 관례).

    df.to_dict("records")만으로는 두 가지가 새어나간다: (1) numpy 스칼라가
    JSON 인코더 밖(get_market의 try/except 밖)에서 500을 낼 수 있고,
    (2) NaN이 stdlib json에 리터럴 NaN으로 찍혀(RFC 8259 위반) 클라이언트
    JSON.parse가 깨진다. 여기서 native float 또는 None으로 강제한다."""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return round(x, nd) if math.isfinite(x) else None


def _stock_rows(df: pd.DataFrame) -> list[dict]:
    rows = []
    for r in df[_STOCK_COLS].itertuples(index=False):
        rows.append({
            "ticker": str(r.ticker), "name": str(r.name),
            "close": _r(r.close), "chg_pct": _r(r.chg_pct), "value": _r(r.value),
        })
    return rows


def _my_rows(latest: pd.DataFrame, items: pd.DataFrame) -> list[dict]:
    if items.empty:
        return []
    m = meta_store.meta_df()[["meta_id", "ticker", "name", "iso_code"]]
    m = m[m["iso_code"] == "KR"]
    joined = items.merge(m, on="meta_id").merge(
        latest[["ticker", "close", "chg_pct", "value"]], on="ticker")
    joined = joined.sort_values("chg_pct", ascending=False)
    rows = []
    for r in joined.itertuples(index=False):
        rows.append({
            "meta_id": int(r.meta_id), "ticker": str(r.ticker), "name": str(r.name),
            "close": _r(r.close), "chg_pct": _r(r.chg_pct),
        })
    return rows


def _my_block(latest: pd.DataFrame) -> dict:
    """watchlist/holdings/meta 조인 실패는 my 섹션만 격리 강등한다 — 지수·업종·
    랭킹까지 같이 죽이지 않는다 (스펙 D3 섹션 강등). 바깥 try/except는
    이 함수 자체가 예외를 흘렸을 때를 위한 최후 방어선으로 남긴다."""
    try:
        return {
            "watchlist": _my_rows(latest, watchlist_store.list_items()),
            "holdings": _my_rows(latest, holdings_store.list_items()),
        }
    except Exception as e:  # noqa: BLE001 — my 섹션 격리, 나머지는 살려둔다
        logger.warning(f"intraday my 섹션 조립 실패 — my만 격리 강등: {e}")
        return {"watchlist": [], "holdings": []}


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

    # 두 파일 쓰기는 원자적이지 않다 — PUT 사이 크래시는 latest=오늘/
    # timeline=어제를 남길 수 있다(최악은 15:35 마지막 폴). 정합 없는 타임라인은
    # 통째로 버린다.
    timeline = timeline[timeline["trade_date"] == trade_date]
    if timeline.empty:
        return {"active": False}
    # EventBridge는 at-least-once고 수동 재호출도 있다 — 같은 (as_of, kind, key)
    # 중복 행이 섹터 리스트·스파크라인에 중복 React key로 새어나가지 않도록 제거.
    timeline = timeline.drop_duplicates(subset=["as_of", "kind", "key"], keep="last")

    now = datetime.now(ki.KST)
    if not ki.snapshot_active(trade_date, as_of, now):
        return {"active": False}

    def hhmm(s: str) -> str:
        return s[-5:]

    indices = []
    for key, g in timeline[timeline["kind"] == "index"].groupby("key"):
        g = g.sort_values("as_of")
        indices.append({
            "key": key, "level": _r(g["level"].iloc[-1]),
            "chg_pct": _r(g["chg_pct"].iloc[-1]),
            "sparkline": [{"t": hhmm(r.as_of), "level": _r(r.level)}
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
        sectors.append({"name": r.key, "chg_pct": _r(r.chg_pct),
                        "value_krw": float(r.value_krw), "n": int(r.n),
                        "flow": [{"t": hhmm(f.as_of), "chg_pct": _r(f.chg_pct)}
                                 for f in flow.itertuples()]})

    up, down = ki.top_movers(latest)
    return {
        "active": True, "is_open": ki.is_open_kst(now),
        "as_of": as_of, "trade_date": trade_date,
        "indices": indices, "breadth": breadth, "sectors": sectors,
        "top_value": _stock_rows(ki.top_value(latest)),
        "top_movers": {"up": _stock_rows(up), "down": _stock_rows(down)},
        "my": _my_block(latest),
    }
