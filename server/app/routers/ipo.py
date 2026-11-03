"""공모주 신호 화면 API (계약 ipo-live-ops — v2부터 t12 매수, 그 전 결정은 t01).

저녁 배치(`build_insights --only ipo_signals`)가 쓴 `ipo/ipo_signals.parquet`·`ipo/status.json`을 읽고,
사용자가 입력한 실제 체결·매도(`ipo/positions.json`)를 겹쳐 돌려준다. 결정을 여기서 계산하지 않는다.
입력은 다음 배치부터 체결 추정·매도 예정 계산에도 쓰인다. 배치가 반영되지 않은 날은 읽는 쪽이 기준일로
판단해 '확인 필요'를 붙인다(`with_freshness`).
"""

import logging
import math
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

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
KST = ZoneInfo("Asia/Seoul")
#: 저녁 배치가 공모주 신호를 내야 하는 마감. 배치는 21:00에 시작해 KR 발행 직후(약 21:40) 신호를 내고
#: 22:40 failsafe 전에 끝난다(quant-data ADR-0034 보완 2026-11-03).
BATCH_DEADLINE = time(22, 45)
#: 상장일 시가 동시호가가 끝나는 시각 — 그 뒤에는 그날 매수 주문을 낼 수 없다
PRE_OPEN_END = time(9, 0)


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


def _now() -> datetime:
    return datetime.now(KST)


def _day(value) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


def with_freshness(status: dict, now: datetime) -> dict:
    """배치가 아예 돌지 않은 날도 '확인 필요'로 보이게 한다(계약 ipo-live-ops, 조용한 누락 금지).

    배치가 status.json을 못 쓰면 그 안의 problems도 옛것 그대로라 화면이 '정상'으로 보인다(2026-11-02 월요일
    배치가 공모주 단계 전에 끝났을 때). 그래서 읽는 쪽이 기준일로 판단한다.

    - `next_session`(신호가 겨냥한 거래일)이 지났거나, 오늘인데 저녁 배치 마감이 지났으면 그 뒤 배치가 반영되지
      않은 것이다: `stale`과 문제 문장을 붙인다.
    - 상장 예정 종목의 신호 계산 밤이 지났는데 결정이 없고 아직 매수 주문을 낼 수 있으면 `decision_missing`을
      붙인다.
    """
    local = now.astimezone(KST)
    today, late = local.date(), local.time() >= BATCH_DEADLINE

    def passed(day: date | None) -> bool:
        return day is not None and (day < today or (day == today and late))

    out = dict(status)
    session = _day(status.get("next_session"))
    out["stale"] = passed(session)
    problems = list(status.get("problems") or [])
    if out["stale"]:
        problems.insert(
            0,
            f"저녁 배치 미반영 — 신호 기준일 {status.get('as_of') or '알 수 없음'}. "
            f"{session.isoformat()} 밤 이후 공모주 신호가 없어 상장 예정 종목의 매수 여부를 확인할 수 없다",
        )
    out["problems"] = problems
    if "calendar" in status:
        calendar = []
        for item in status.get("calendar") or []:
            listing = _day(item.get("planned_listing_date"))
            # 아직 낼 수 있는 주문만 — 상장일 동시호가(09:00)가 지나면 표시하지 않는다
            ahead = listing is not None and (
                listing > today or (listing == today and local.time() < PRE_OPEN_END)
            )
            missing = not item.get("decided") and passed(_day(item.get("decision_night"))) and ahead
            # 상장일 동시호가가 지났으면 이미 상장한 종목 — 화면 목록에서 뺀다(달력 날짜 칸에는 남는다)
            listed = listing is not None and not ahead
            calendar.append({**item, "decision_missing": bool(missing), "listed": bool(listed)})
        out["calendar"] = calendar
    return out


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
    return {"status": with_freshness(status, _now()), "open": open_positions, "history": rows}


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
