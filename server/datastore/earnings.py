"""배치가 발행한 Earnings Hub 테이블을 읽는다."""

import pandas as pd

from . import storage

EVENT_PATH = ("insight", "earnings_events.parquet")
UNIVERSE_PATH = ("insight", "earnings_universe.parquet")
REVISION_PATH = ("insight", "earnings_revisions.parquet")
SOURCE_PATH = ("insight", "earnings_source.parquet")


def _read(path: tuple[str, ...]) -> pd.DataFrame:
    try:
        return storage.read_parquet(*path)
    except (FileNotFoundError, OSError):
        return pd.DataFrame()


def list_events() -> pd.DataFrame:
    return _read(EVENT_PATH)


def list_universe() -> pd.DataFrame:
    return _read(UNIVERSE_PATH)


def list_revisions() -> pd.DataFrame:
    return _read(REVISION_PATH)


def source_status() -> dict | None:
    frame = _read(SOURCE_PATH)
    if frame.empty:
        return None
    row = frame.iloc[-1].where(frame.iloc[-1].notna(), None)
    return row.to_dict()
