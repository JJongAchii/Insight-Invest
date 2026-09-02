from app.routers import notifications as notification_router
from datastore import notifications
from module import action_push


def test_default_vapid_subject_uses_public_https_origin(monkeypatch):
    monkeypatch.delenv("WEB_PUSH_SUBJECT", raising=False)

    assert action_push.config()["subject"] == "https://insight-invest-ten.vercel.app"


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

    monkeypatch.setattr(action_push, "send_to_subscription", lambda *_args, **_kwargs: None)
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


def test_dispatch_supports_research_digest_payload(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_DATA", str(tmp_path))
    monkeypatch.setenv("WEB_PUSH_PUBLIC_KEY", "public")
    monkeypatch.setenv("WEB_PUSH_PRIVATE_KEY", "private")
    notifications.upsert_subscription("https://push.example.test/research", "p" * 32, "a" * 16)
    captured = []
    monkeypatch.setattr(
        action_push,
        "send_to_subscription",
        lambda _subscription, payload: captured.append(payload),
    )
    events = [
        {
            "event_id": f"research:{entry_id}",
            "severity": "medium",
            "state": "new",
            "title": title,
            "link": f"/research?entry={entry_id}",
        }
        for entry_id, title in [("a" * 64, "First paper"), ("b" * 64, "Second paper")]
    ]

    result = action_push.dispatch(
        events,
        notification_title="Research Radar",
        digest_url="/research?filter=unread",
        tag_prefix="insight-research",
    )

    assert result["sent"] == 1
    assert captured == [
        {
            "title": "Research Radar",
            "body": "First paper 외 1건",
            "tag": "insight-research-digest",
            "url": "/research?filter=unread",
            "event_id": f"research:{'a' * 64}",
            "badge": 2,
        }
    ]
