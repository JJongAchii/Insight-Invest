"""Web Push 구독과 전송 영수증 저장소 — 단일 사용자 parquet 계약."""

from datetime import datetime, timezone
from hashlib import sha256

import pandas as pd

from datastore import storage

SUBSCRIPTIONS_FILE = "notification_subscriptions.parquet"
DELIVERIES_FILE = "notification_deliveries.parquet"
SUBSCRIPTION_COLUMNS = [
    "subscription_id",
    "endpoint",
    "p256dh",
    "auth",
    "user_agent",
    "created_at",
    "updated_at",
    "disabled_at",
]
DELIVERY_COLUMNS = ["delivery_id", "event_id", "subscription_id", "sent_at"]


def _read(file: str, columns: list[str]) -> pd.DataFrame:
    if not storage.exists(file):
        return pd.DataFrame(columns=columns)
    frame = storage.read_parquet(file)
    for column in columns:
        if column not in frame.columns:
            frame[column] = None
    return frame[columns]


def subscription_id(endpoint: str) -> str:
    return sha256(endpoint.encode("utf-8")).hexdigest()[:24]


def list_subscriptions(*, active_only: bool = True) -> pd.DataFrame:
    frame = _read(SUBSCRIPTIONS_FILE, SUBSCRIPTION_COLUMNS)
    if active_only and not frame.empty:
        frame = frame[frame["disabled_at"].isna()]
    return frame.reset_index(drop=True)


def upsert_subscription(
    endpoint: str, p256dh: str, auth: str, user_agent: str = ""
) -> str:
    now = datetime.now(timezone.utc)
    sub_id = subscription_id(endpoint)
    frame = _read(SUBSCRIPTIONS_FILE, SUBSCRIPTION_COLUMNS)
    existing = frame[frame["subscription_id"] == sub_id]
    created_at = existing["created_at"].iloc[0] if not existing.empty else now
    frame = frame[frame["subscription_id"] != sub_id]
    row = pd.DataFrame(
        [
            {
                "subscription_id": sub_id,
                "endpoint": endpoint,
                "p256dh": p256dh,
                "auth": auth,
                "user_agent": user_agent,
                "created_at": created_at,
                "updated_at": now,
                "disabled_at": None,
            }
        ]
    )
    out = pd.concat([frame, row], ignore_index=True) if not frame.empty else row
    storage.write_parquet(out.reindex(columns=SUBSCRIPTION_COLUMNS), SUBSCRIPTIONS_FILE)
    return sub_id


def disable_subscription(endpoint: str) -> bool:
    sub_id = subscription_id(endpoint)
    frame = _read(SUBSCRIPTIONS_FILE, SUBSCRIPTION_COLUMNS)
    mask = frame["subscription_id"] == sub_id
    if not mask.any():
        return False
    frame.loc[mask, "disabled_at"] = datetime.now(timezone.utc)
    frame.loc[mask, "updated_at"] = datetime.now(timezone.utc)
    storage.write_parquet(frame, SUBSCRIPTIONS_FILE)
    return True


def delivered(event_id: str, sub_id: str) -> bool:
    frame = _read(DELIVERIES_FILE, DELIVERY_COLUMNS)
    if frame.empty:
        return False
    return bool(
        ((frame["event_id"] == event_id) & (frame["subscription_id"] == sub_id)).any()
    )


def record_delivery(event_id: str, sub_id: str) -> None:
    frame = _read(DELIVERIES_FILE, DELIVERY_COLUMNS)
    delivery_id = sha256(f"{event_id}:{sub_id}".encode()).hexdigest()[:32]
    if not frame.empty and (frame["delivery_id"] == delivery_id).any():
        return
    row = pd.DataFrame(
        [
            {
                "delivery_id": delivery_id,
                "event_id": event_id,
                "subscription_id": sub_id,
                "sent_at": datetime.now(timezone.utc),
            }
        ]
    )
    out = pd.concat([frame, row], ignore_index=True) if not frame.empty else row
    storage.write_parquet(out.reindex(columns=DELIVERY_COLUMNS), DELIVERIES_FILE)
