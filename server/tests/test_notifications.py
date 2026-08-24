from app.routers import notifications as notification_router
from datastore import notifications
from module import action_push


def test_subscription_roundtrip_and_delivery_receipt(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    monkeypatch.setenv("WEB_PUSH_PUBLIC_KEY", "public")
    monkeypatch.setenv("WEB_PUSH_PRIVATE_KEY", "private")
    request = notification_router.PushSubscriptionRequest(
        endpoint="https://push.example.test/subscriptions/abc",
        keys={"p256dh": "p" * 32, "auth": "a" * 16},
        user_agent="pytest",
    )
    subscribed = notification_router.subscribe(request)
    frame = notifications.list_subscriptions()

    assert subscribed["subscribed"] is True
    assert len(frame) == 1

    monkeypatch.setattr(
        action_push, "send_to_subscription", lambda *_args, **_kwargs: None
    )
    event = {
        "event_id": "a" * 24,
        "severity": "high",
        "state": "new",
        "title": "Test",
        "link": "/actions",
    }
    first = action_push.dispatch([event])
    second = action_push.dispatch([event])
    assert first["sent"] == 1
    assert second["sent"] == 0

    result = notification_router.unsubscribe(
        notification_router.PushUnsubscribeRequest(endpoint=request.endpoint)
    )
    assert result["unsubscribed"] is True
    assert notifications.list_subscriptions().empty
