"""Research Radar projection and single-user library state."""

from datetime import datetime, timezone

import pandas as pd

from datastore import storage

FEED_FILE = "research_feed.json"
READ_STATE_FILE = "research_read_state.parquet"
READ_STATE_COLUMNS = ["entry_id", "read_at", "saved_at"]


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
    return frame[READ_STATE_COLUMNS].drop_duplicates(subset="entry_id", keep="last")


def entry_states() -> dict[str, dict[str, bool]]:
    frame = list_read_state()
    return {
        str(row.entry_id): {
            "is_read": pd.notna(row.read_at),
            "is_saved": pd.notna(row.saved_at),
        }
        for row in frame.itertuples(index=False)
    }


def read_entry_ids() -> set[str]:
    return {entry_id for entry_id, state in entry_states().items() if state["is_read"]}


def _write_state(frame: pd.DataFrame) -> None:
    active = frame.loc[frame["read_at"].notna() | frame["saved_at"].notna()].copy()
    for column in ("read_at", "saved_at"):
        active[column] = pd.to_datetime(active[column], utc=True, errors="coerce")
    storage.write_parquet(active.reindex(columns=READ_STATE_COLUMNS), READ_STATE_FILE)


def _set_state(entry_id: str, *, column: str, enabled: bool) -> None:
    frame = list_read_state()
    current = frame.loc[frame["entry_id"] == entry_id]
    row = (
        current.iloc[-1].to_dict()
        if not current.empty
        else {"entry_id": entry_id, "read_at": None, "saved_at": None}
    )
    row[column] = datetime.now(timezone.utc) if enabled else None
    frame = frame.loc[frame["entry_id"] != entry_id]
    rows = frame.to_dict("records")
    rows.append(row)
    _write_state(pd.DataFrame(rows, columns=READ_STATE_COLUMNS))


def set_read(entry_id: str, *, read: bool) -> None:
    _set_state(entry_id, column="read_at", enabled=read)


def set_saved(entry_id: str, *, saved: bool) -> None:
    _set_state(entry_id, column="saved_at", enabled=saved)


def mark_all_read(entry_ids: list[str]) -> int:
    unique_ids = list(dict.fromkeys(entry_ids))
    frame = list_read_state()
    state_by_id = {str(row.entry_id): row._asdict() for row in frame.itertuples(index=False)}
    previously_read = {
        entry_id for entry_id, state in state_by_id.items() if pd.notna(state.get("read_at"))
    }
    now = datetime.now(timezone.utc)
    for entry_id in unique_ids:
        row = state_by_id.setdefault(
            entry_id,
            {"entry_id": entry_id, "read_at": None, "saved_at": None},
        )
        if pd.isna(row.get("read_at")):
            row["read_at"] = now
    _write_state(pd.DataFrame(state_by_id.values(), columns=READ_STATE_COLUMNS))
    return len(set(unique_ids) - previously_read)
