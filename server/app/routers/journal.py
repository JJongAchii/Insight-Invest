"""구조화된 판단 기록과 당시 데이터 근거 스냅샷 API."""

import json
from datetime import date
from typing import Literal

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from datastore import journal as journal_store
from . import overview

router = APIRouter(prefix="/journal", tags=["Decision Journal"])


class JournalCreateRequest(BaseModel):
    observation: str = Field(..., min_length=1, max_length=4000)
    interpretation: str = Field(..., min_length=1, max_length=4000)
    decision: str = Field(..., min_length=1, max_length=4000)
    horizon: Literal["intraday", "tactical", "structural"]
    confidence: int = Field(..., ge=1, le=5)
    counter_evidence: str = Field("", max_length=4000)
    invalidation: str = Field("", max_length=4000)
    review_date: date


class JournalReviewRequest(BaseModel):
    outcome: str = Field(..., min_length=1, max_length=4000)
    lesson: str = Field("", max_length=4000)


def _iso(value):
    return value.isoformat() if value is not None and not pd.isna(value) else None


def _rows() -> list[dict]:
    rows = []
    for row in journal_store.list_entries().itertuples(index=False):
        snapshot = {}
        if isinstance(row.evidence_snapshot, str) and row.evidence_snapshot:
            try:
                snapshot = json.loads(row.evidence_snapshot)
            except json.JSONDecodeError:
                snapshot = {"unreadable": True}
        rows.append({
            "entry_id": row.entry_id,
            "created_at": _iso(row.created_at),
            "observation": row.observation,
            "interpretation": row.interpretation,
            "decision": row.decision,
            "horizon": row.horizon,
            "confidence": int(row.confidence),
            "counter_evidence": row.counter_evidence or "",
            "invalidation": row.invalidation or "",
            "review_date": _iso(row.review_date),
            "evidence_snapshot": snapshot,
            "reviewed_at": _iso(row.reviewed_at),
            "outcome": None if pd.isna(row.outcome) else row.outcome,
            "lesson": None if pd.isna(row.lesson) else row.lesson,
        })
    return rows


@router.get("")
def get_journal():
    rows = _rows()
    rows.sort(key=lambda item: item["created_at"] or "", reverse=True)
    return {"items": rows, "count": len(rows)}


@router.post("")
def create_journal_entry(request: JournalCreateRequest):
    current = overview.get_overview()
    snapshot = {
        key: current.get(key)
        for key in ("generated_at", "tone_label", "horizons", "conflicts", "data_status", "method")
    }
    entry_id = journal_store.append_entry({
        **request.model_dump(),
        "evidence_snapshot": json.dumps(snapshot, ensure_ascii=False, default=str),
    })
    return {"entry_id": entry_id, "count": len(journal_store.list_entries())}


@router.post("/{entry_id}/reviews")
def review_journal_entry(entry_id: str, request: JournalReviewRequest):
    review_id = journal_store.append_review(entry_id, request.outcome, request.lesson)
    if review_id is None:
        raise HTTPException(status_code=404, detail="journal entry not found")
    return {"review_id": review_id}
