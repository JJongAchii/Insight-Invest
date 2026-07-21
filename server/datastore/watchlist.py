"""관심종목 저장소 — {APP_DATA}/watchlist.parquet [meta_id, added_at, note].

portfolio.py와 같은 read-modify-write(파일 통째 교체) 패턴 — 단일 사용자 앱 전제.
"""

import logging
from datetime import datetime

import pandas as pd

from datastore import storage

logger = logging.getLogger(__name__)

FILE = "watchlist.parquet"
_EMPTY = ["meta_id", "added_at", "note"]


def list_items() -> pd.DataFrame:
    """관심종목 전체 [meta_id, added_at, note] — 파일 없으면 빈 프레임."""
    if not storage.exists(FILE):
        return pd.DataFrame(columns=_EMPTY)
    return storage.read_parquet(FILE)


def add(meta_id: int, note: str = "") -> None:
    """추가 (멱등 — 이미 있으면 행 교체, added_at 갱신)."""
    df = list_items()
    df = df[df["meta_id"] != meta_id]
    new = pd.DataFrame(
        [{"meta_id": int(meta_id), "added_at": datetime.utcnow(), "note": note or ""}]
    )
    out = pd.concat([df, new], ignore_index=True) if not df.empty else new
    storage.write_parquet(out, FILE)


def remove(meta_id: int) -> None:
    df = list_items()
    storage.write_parquet(df[df["meta_id"] != meta_id].reset_index(drop=True), FILE)
