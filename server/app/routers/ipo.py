"""공모주 t01 화면 API (계약 ipo-live-ops).

저녁 배치(`build_insights --only ipo_signals`)가 쓴 `ipo/ipo_signals.parquet`·`ipo/status.json`을 읽고,
사용자가 입력한 실제 체결·매도(`ipo/positions.json`)를 겹쳐 돌려준다. 결정을 여기서 계산하지 않는다.
입력은 다음 배치부터 체결 추정·매도 예정 계산에도 쓰인다.
"""

import logging
import math
from datetime import date

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from datastore import storage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ipo", tags=["IPO"])

SIGNALS = ("ipo", "ipo_signals.parquet")
STATUS = ("ipo", "status.json")
DECISIONS = ("ipo", "decisions.json")
POSITIONS = ("ipo", "positions.json")


class PositionRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    filled: bool | None = None
    entry_price: float | None = None
    quantity: float | None = None
    exit_price: float | None = None
    exit_date: date | None = None
    note: str | None = None


def _clean(v):
    if isinstance(v, float) and not math.isfinite(v):
        return None
    if hasattr(v, "item"):
        return _clean(v.item())
    return v


def _read_json(parts) -> dict:
    return storage.read_json(*parts) if storage.exists(*parts) else {}


@router.get("")
def get_ipo():
    """상태·신호·보유·기록. 배치 산출이 없으면 빈 목록과 '산출 없음' 상태."""
    status = _read_json(STATUS)
    overrides = _read_json(POSITIONS)
    rows: list[dict] = []
    if storage.exists(*SIGNALS):
        frame = storage.read_parquet(*SIGNALS)
        rows = [{k: _clean(v) for k, v in r.items()} for r in frame.to_dict(orient="records")]
    for row in rows:
        user = overrides.get(row.get("event_id"))
        row["user"] = user or None
    rows.sort(
        key=lambda r: (str(r.get("listing_date") or ""), str(r.get("event_id"))), reverse=True
    )
    open_positions = [
        r for r in rows if r.get("buy") and r.get("position") in ("signal", "holding")
    ]
    if not status:
        status = {"problems": ["공모주 신호 산출이 아직 없다 — 저녁 배치 뒤에 생긴다"]}
    return {"status": status, "open": open_positions, "history": rows}


@router.put("/positions/{event_id}")
def update_position(event_id: str, request: PositionRequest):
    """실제 체결·매도 입력. 값이 null인 항목은 지운다(추정으로 돌아간다)."""
    decisions = _read_json(DECISIONS)
    rec = decisions.get(event_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="결정 기록이 없는 공모주다")
    if not rec.get("buy"):
        raise HTTPException(status_code=422, detail="매수 신호가 아니었던 공모주다")
    body = request.model_dump()
    for key in ("entry_price", "quantity", "exit_price"):
        if body[key] is not None and body[key] <= 0:
            raise HTTPException(status_code=422, detail=f"{key}는 0보다 커야 한다")
    if (
        body["exit_date"] is not None
        and body["exit_date"] < pd.Timestamp(rec["listing_date"]).date()
    ):
        raise HTTPException(status_code=422, detail="매도일이 상장일보다 이르다")
    entry = {k: (v.isoformat() if isinstance(v, date) else v) for k, v in body.items()}
    entry = {k: v for k, v in entry.items() if v is not None}
    overrides = _read_json(POSITIONS)
    if entry:
        overrides[event_id] = {**entry, "updated_at": pd.Timestamp.now(tz="Asia/Seoul").isoformat()}
    else:
        overrides.pop(event_id, None)
    storage.write_json(overrides, *POSITIONS)
    return {"event_id": event_id, "user": overrides.get(event_id)}
