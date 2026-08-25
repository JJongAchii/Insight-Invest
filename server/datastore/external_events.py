"""배치가 발행한 외부 이벤트와 공급원 상태를 읽는다."""

import pandas as pd

from . import storage

EVENT_PATH = ("insight", "external_events.parquet")
SOURCE_PATH = ("insight", "external_event_sources.parquet")


def list_events() -> pd.DataFrame:
    try:
        return storage.read_parquet(*EVENT_PATH)
    except (FileNotFoundError, OSError):
        return pd.DataFrame()


def list_sources() -> list[dict]:
    try:
        frame = storage.read_parquet(*SOURCE_PATH)
    except (FileNotFoundError, OSError):
        return []
    if frame.empty:
        return []
    columns = [
        "provider",
        "label",
        "status",
        "data_as_of",
        "available_at",
        "coverage",
        "message",
    ]
    rows = frame.reindex(columns=columns)
    rows = rows.where(rows.notna(), None)
    return rows.to_dict("records")
