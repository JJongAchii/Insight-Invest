"""iPhone Home Screen PWA를 포함한 Web Push 구독 API."""

from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from datastore import notifications as notification_store
from module import action_push

from . import actions

router = APIRouter(prefix="/notifications", tags=["Notifications"])


class PushKeys(BaseModel):
    p256dh: str = Field(..., min_length=20, max_length=512)
    auth: str = Field(..., min_length=8, max_length=256)


class PushSubscriptionRequest(BaseModel):
    endpoint: str = Field(..., min_length=20, max_length=4096)
    keys: PushKeys
    user_agent: str = Field("", max_length=512)


class PushUnsubscribeRequest(BaseModel):
    endpoint: str = Field(..., min_length=20, max_length=4096)


def _validate_endpoint(endpoint: str) -> None:
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or not parsed.netloc:
        raise HTTPException(status_code=422, detail="push endpoint must use https")


@router.get("/config")
def get_notification_config():
    cfg = action_push.config()
    count = len(notification_store.list_subscriptions(active_only=True))
    return {
        "enabled": cfg["enabled"],
        "public_key": cfg["public_key"] if cfg["enabled"] else None,
        "subscriptions": count,
    }


@router.post("/subscriptions")
def subscribe(request: PushSubscriptionRequest):
    _validate_endpoint(request.endpoint)
    if not action_push.config()["enabled"]:
        raise HTTPException(status_code=503, detail="Web Push is not configured")
    sub_id = notification_store.upsert_subscription(
        request.endpoint,
        request.keys.p256dh,
        request.keys.auth,
        request.user_agent,
    )
    return {"subscription_id": sub_id, "subscribed": True}


@router.delete("/subscriptions")
def unsubscribe(request: PushUnsubscribeRequest):
    _validate_endpoint(request.endpoint)
    return {"unsubscribed": notification_store.disable_subscription(request.endpoint)}


@router.post("/test")
def send_test_notification():
    now = actions.datetime.now(actions.KST)
    event = actions._event(
        source="notification_test",
        key=now.isoformat(),
        kind="system",
        category="notification",
        severity="medium",
        title="Notifications are ready",
        detail="중요한 변화가 있을 때 이 기기로 알려드립니다.",
        link="/actions",
        occurred_at=now.isoformat(),
        available_at=now.isoformat(),
        data_as_of=None,
        actions=["open"],
    )
    result = action_push.dispatch([event], test=True)
    if not result.get("enabled"):
        raise HTTPException(status_code=503, detail="Web Push is not configured")
    return result
