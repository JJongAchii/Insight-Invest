"""의사결정 저널 저장소.

판단 본문과 당시 근거 스냅샷은 생성 후 수정하지 않는다. 사후 검토는 별도 이벤트 파일에
append해 원래 판단과 결과를 섞지 않는다. 단일 사용자·저빈도 쓰기라 기존 parquet
read-modify-write 계약을 따른다.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pandas as pd

from datastore import storage

ENTRY_FILE = "decision_journal.parquet"
REVIEW_FILE = "decision_journal_reviews.parquet"
ENTRY_COLUMNS = [
    "entry_id",
    "created_at",
    "observation",
    "interpretation",
    "decision",
    "horizon",
    "confidence",
    "counter_evidence",
    "invalidation",
    "review_date",
    "evidence_snapshot",
]
REVIEW_COLUMNS = ["review_id", "entry_id", "created_at", "outcome", "lesson"]


def _read(file: str, columns: list[str]) -> pd.DataFrame:
    if not storage.exists(file):
        return pd.DataFrame(columns=columns)
    df = storage.read_parquet(file)
    for column in columns:
        if column not in df.columns:
            df[column] = None
    return df[columns]


def append_entry(values: dict) -> str:
    entry_id = str(uuid4())
    row = {**values, "entry_id": entry_id, "created_at": datetime.now(timezone.utc)}
    current = _read(ENTRY_FILE, ENTRY_COLUMNS)
    new = pd.DataFrame([row], columns=ENTRY_COLUMNS)
    out = pd.concat([current, new], ignore_index=True) if not current.empty else new
    storage.write_parquet(out, ENTRY_FILE)
    return entry_id


def append_review(entry_id: str, outcome: str, lesson: str = "") -> str | None:
    entries = _read(ENTRY_FILE, ENTRY_COLUMNS)
    if entries.empty or not (entries["entry_id"] == entry_id).any():
        return None
    review_id = str(uuid4())
    row = {
        "review_id": review_id,
        "entry_id": entry_id,
        "created_at": datetime.now(timezone.utc),
        "outcome": outcome,
        "lesson": lesson,
    }
    current = _read(REVIEW_FILE, REVIEW_COLUMNS)
    new = pd.DataFrame([row], columns=REVIEW_COLUMNS)
    out = pd.concat([current, new], ignore_index=True) if not current.empty else new
    storage.write_parquet(out, REVIEW_FILE)
    return review_id


def list_entries() -> pd.DataFrame:
    entries = _read(ENTRY_FILE, ENTRY_COLUMNS)
    if entries.empty:
        return entries.assign(reviewed_at=None, outcome=None, lesson=None)
    reviews = _read(REVIEW_FILE, REVIEW_COLUMNS)
    if reviews.empty:
        return entries.assign(reviewed_at=None, outcome=None, lesson=None)
    latest = reviews.sort_values("created_at").groupby("entry_id").tail(1).rename(
        columns={"created_at": "reviewed_at"}
    )
    return entries.merge(latest[["entry_id", "reviewed_at", "outcome", "lesson"]], on="entry_id", how="left")
