"""Research Radar projection and single-user read state."""

from datetime import datetime, timezone

import pandas as pd

from datastore import storage

FEED_FILE = "research_feed.json"
READ_STATE_FILE = "research_read_state.parquet"
READ_STATE_COLUMNS = ["entry_id", "read_at"]


def empty_feed() -> dict:
    return {"schema_version": 1, "generated_at": None, "items": []}


def load_feed() -> dict:
    if not storage.exists(FEED_FILE):
        return empty_feed()
    payload = storage.read_json(FEED_FILE)
    if payload.get("schema_version") != 1 or not isinstance(payload.get("items"), list):
        raise ValueError("research_feed.json schema가 유효하지 않다")
    return payload


def save_feed(payload: dict) -> str:
    if payload.get("schema_version") != 1 or not isinstance(payload.get("items"), list):
        raise ValueError("research feed schema가 유효하지 않다")
    return storage.write_json(payload, FEED_FILE)


def list_read_state() -> pd.DataFrame:
    if not storage.exists(READ_STATE_FILE):
        return pd.DataFrame(columns=READ_STATE_COLUMNS)
    frame = storage.read_parquet(READ_STATE_FILE)
    for column in READ_STATE_COLUMNS:
        if column not in frame.columns:
            frame[column] = None
    return frame[READ_STATE_COLUMNS]


def read_entry_ids() -> set[str]:
    frame = list_read_state()
    if frame.empty:
        return set()
    return set(frame.loc[frame["read_at"].notna(), "entry_id"].astype(str))


def set_read(entry_id: str, *, read: bool) -> None:
    frame = list_read_state()
    frame = frame[frame["entry_id"] != entry_id]
    if read:
        row = pd.DataFrame([{"entry_id": entry_id, "read_at": datetime.now(timezone.utc)}])
        frame = pd.concat([frame, row], ignore_index=True) if not frame.empty else row
    storage.write_parquet(frame.reindex(columns=READ_STATE_COLUMNS), READ_STATE_FILE)
