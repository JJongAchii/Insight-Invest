"""보유종목 저장소 — {APP_DATA}/holdings.parquet
[meta_id, shares, avg_cost, currency, opened_at, note, updated_at].

watchlist.py와 같은 read-modify-write(파일 통째 교체) 패턴 — 단일 사용자 앱 전제.
avg_cost는 종목의 거래통화 기준 금액이다 (KR→KRW, US→USD).
"""

import logging
from datetime import datetime

import pandas as pd

from datastore import storage

logger = logging.getLogger(__name__)

FILE = "holdings.parquet"
_EMPTY = ["meta_id", "shares", "avg_cost", "currency", "opened_at", "note", "updated_at"]


def list_items() -> pd.DataFrame:
    """보유종목 전체 — 파일 없으면 빈 프레임."""
    if not storage.exists(FILE):
        return pd.DataFrame(columns=_EMPTY)
    return storage.read_parquet(FILE)


def upsert(meta_id: int, shares: float, avg_cost: float, currency: str, note: str = "") -> None:
    """추가/갱신 (이미 있으면 행 교체 — updated_at 갱신, opened_at은 최초값 보존)."""
    df = list_items()
    now = datetime.utcnow()

    existing = df[df["meta_id"] == meta_id] if not df.empty else df
    opened_at = existing["opened_at"].iloc[0] if not existing.empty else now

    df = df[df["meta_id"] != meta_id]
    new = pd.DataFrame(
        [{
            "meta_id": int(meta_id),
            "shares": float(shares),
            "avg_cost": float(avg_cost),
            "currency": currency,
            "opened_at": opened_at,
            "note": note or "",
            "updated_at": now,
        }]
    )
    out = pd.concat([df, new], ignore_index=True) if not df.empty else new
    storage.write_parquet(out, FILE)


def remove(meta_id: int) -> None:
    df = list_items()
    storage.write_parquet(df[df["meta_id"] != meta_id].reset_index(drop=True), FILE)
