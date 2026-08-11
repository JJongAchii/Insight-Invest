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
