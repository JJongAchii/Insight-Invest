"""관심종목 저장소 — 가격 알림뿐 아니라 투자 논거와 검토 시점을 보존한다.

portfolio.py와 같은 read-modify-write(파일 통째 교체) 패턴 — 단일 사용자 앱 전제.
"""

import logging
from datetime import datetime, timezone

import pandas as pd

from datastore import storage

logger = logging.getLogger(__name__)

FILE = "watchlist.parquet"
_EMPTY = [
    "meta_id",
    "added_at",
    "updated_at",
    "note",
    "thesis",
    "catalyst",
    "invalidation",
    "review_date",
    "alerts_enabled",
    "alert_price_above",
    "alert_price_below",
    "alert_change_pct",
]


def _normalise(df: pd.DataFrame) -> pd.DataFrame:
    """구 스키마 파일을 읽을 때 빈 값으로 전진 호환한다."""
    out = df.copy()
    for column in _EMPTY:
        if column not in out.columns:
            if column == "alerts_enabled":
                out[column] = False
            elif (
                column.endswith("_at")
                or column == "review_date"
                or column.startswith("alert_")
            ):
                out[column] = None
            else:
                out[column] = ""
    out["alerts_enabled"] = out["alerts_enabled"].fillna(False).astype(bool)
    for column in ("alert_price_above", "alert_price_below", "alert_change_pct"):
        out[column] = pd.to_numeric(out[column], errors="coerce")
    return out[_EMPTY]


def list_items() -> pd.DataFrame:
    """관심종목 전체 [meta_id, added_at, note] — 파일 없으면 빈 프레임."""
    if not storage.exists(FILE):
        return pd.DataFrame(columns=_EMPTY)
    return _normalise(storage.read_parquet(FILE))


def add(meta_id: int, note: str = "") -> None:
    """추가 (멱등 — 이미 있으면 행 교체, added_at 갱신)."""
    df = list_items()
    df = df[df["meta_id"] != meta_id]
    now = datetime.now(timezone.utc)
    new = pd.DataFrame(
        [
            {
                "meta_id": int(meta_id),
                "added_at": now,
                "updated_at": now,
                "note": note or "",
                "thesis": "",
                "catalyst": "",
                "invalidation": "",
                "review_date": None,
                "alerts_enabled": False,
                "alert_price_above": None,
                "alert_price_below": None,
                "alert_change_pct": None,
            }
        ]
    )
    out = pd.concat([df, new], ignore_index=True) if not df.empty else new
    storage.write_parquet(out, FILE)


def update(
    meta_id: int,
    *,
    note: str = "",
    thesis: str = "",
    catalyst: str = "",
    invalidation: str = "",
    review_date=None,
    alerts_enabled: bool = False,
    alert_price_above: float | None = None,
    alert_price_below: float | None = None,
    alert_change_pct: float | None = None,
) -> bool:
    """기존 관심종목의 판단 필드를 갱신한다. 존재하지 않으면 False."""
    df = list_items()
    mask = df["meta_id"] == int(meta_id)
    if not mask.any():
        return False
    df.loc[mask, "note"] = note or ""
    df.loc[mask, "thesis"] = thesis or ""
    df.loc[mask, "catalyst"] = catalyst or ""
    df.loc[mask, "invalidation"] = invalidation or ""
    df.loc[mask, "review_date"] = review_date
    df.loc[mask, "alerts_enabled"] = bool(alerts_enabled)
    df.loc[mask, "alert_price_above"] = alert_price_above
    df.loc[mask, "alert_price_below"] = alert_price_below
    df.loc[mask, "alert_change_pct"] = alert_change_pct
    df.loc[mask, "updated_at"] = datetime.now(timezone.utc)
    storage.write_parquet(df, FILE)
    return True


def remove(meta_id: int) -> None:
    df = list_items()
    storage.write_parquet(df[df["meta_id"] != meta_id].reset_index(drop=True), FILE)
