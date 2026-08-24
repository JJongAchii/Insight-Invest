"""Action Center 이벤트를 표준 Web Push로 전달한다."""

import json
import logging
import os

from datastore import notifications

logger = logging.getLogger(__name__)


def config() -> dict:
    public_key = os.environ.get("WEB_PUSH_PUBLIC_KEY", "").strip()
    private_key = os.environ.get("WEB_PUSH_PRIVATE_KEY", "").strip()
    subject = os.environ.get(
        "WEB_PUSH_SUBJECT", "mailto:admin@insight-invest.local"
    ).strip()
    return {
        "enabled": bool(public_key and private_key),
        "public_key": public_key,
        "private_key": private_key,
        "subject": subject,
    }


def send_to_subscription(subscription: dict, payload: dict) -> None:
    from pywebpush import webpush

    cfg = config()
    if not cfg["enabled"]:
        raise RuntimeError("Web Push keys are not configured")
    webpush(
        subscription_info={
            "endpoint": subscription["endpoint"],
            "keys": {"p256dh": subscription["p256dh"], "auth": subscription["auth"]},
        },
        data=json.dumps(payload, ensure_ascii=False),
        vapid_private_key=cfg["private_key"],
        vapid_claims={"sub": cfg["subject"]},
        ttl=12 * 60 * 60,
    )


def dispatch(events: list[dict], *, test: bool = False) -> dict:
    cfg = config()
    subscriptions = notifications.list_subscriptions(active_only=True)
    if not cfg["enabled"]:
        return {
            "enabled": False,
            "subscriptions": len(subscriptions),
            "sent": 0,
            "failed": 0,
        }

    selected = (
        events
        if test
        else [
            event
            for event in events
            if event.get("severity") in {"high", "medium"}
            and event.get("state") == "new"
        ]
    )
    sent = failed = disabled = 0
    for row in subscriptions.itertuples(index=False):
        subscription = {
            "endpoint": row.endpoint,
            "p256dh": row.p256dh,
            "auth": row.auth,
        }
        pending = [
            event
            for event in selected
            if test
            or not notifications.delivered(event["event_id"], row.subscription_id)
        ]
        if not pending:
            continue
        lead = pending[0]
        body = lead.get("title", "새로운 확인 항목이 있습니다.")
        if len(pending) > 1:
            body = f"{body} 외 {len(pending) - 1}건"
        payload = {
            "title": "Insight Invest",
            "body": body,
            "tag": "insight-action-digest"
            if len(pending) > 1
            else f"insight-{lead['event_id']}",
            "url": "/actions" if len(pending) > 1 else lead.get("link") or "/actions",
            "event_id": lead["event_id"],
            "badge": len(pending),
        }
        try:
            send_to_subscription(subscription, payload)
            if not test:
                for event in pending:
                    notifications.record_delivery(
                        event["event_id"], row.subscription_id
                    )
            sent += 1
        except Exception as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in {404, 410}:
                notifications.disable_subscription(row.endpoint)
                disabled += 1
            else:
                logger.warning("Web Push delivery failed", exc_info=True)
            failed += 1
    return {
        "enabled": True,
        "subscriptions": len(subscriptions),
        "events": len(selected),
        "sent": sent,
        "failed": failed,
        "disabled": disabled,
    }
