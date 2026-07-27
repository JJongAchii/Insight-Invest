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
    "ticker",
    "meta_id",
    "name",
    "as_of",
    "one_liner",
    "summary",
    "confidence",
    "stance_note",
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
