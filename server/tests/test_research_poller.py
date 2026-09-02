import pytest

from app import research_poller
from module import action_push, research_feed


def _pending():
    entry_id = "a" * 64
    return [
        (
            f"research-radar/realtime/pending/{entry_id}.json",
            {"entry_id": entry_id, "title": "New quant paper"},
        )
    ]


def _arrange(monkeypatch, push):
    captured = {"deleted": []}
    monkeypatch.setattr(
        research_feed,
        "reconcile",
        lambda **_kwargs: {"records": 10, "added": 1, "removed": 0, "updated": True},
    )
    monkeypatch.setattr(research_feed, "pending_records", lambda **_kwargs: _pending())
    monkeypatch.setattr(
        research_feed,
        "delete_pending",
        lambda **kwargs: captured["deleted"].extend(kwargs["keys"]),
    )

    def dispatch(events, **kwargs):
        captured["events"] = events
        captured["dispatch_kwargs"] = kwargs
        return push

    monkeypatch.setattr(action_push, "dispatch", dispatch)
    return captured


def test_poller_batches_research_push_and_deletes_settled_pending(monkeypatch):
    captured = _arrange(
        monkeypatch,
        {"enabled": True, "subscriptions": 2, "sent": 2, "failed": 0, "disabled": 0},
    )

    result = research_poller.run(s3=object())

    assert result["ok"] is True
    assert result["delivery_ready"] is True
    assert result["pending_deleted"] == 1
    assert captured["events"][0]["link"] == f"/research?entry={'a' * 64}"
    assert captured["dispatch_kwargs"] == {
        "notification_title": "Research Radar",
        "digest_url": "/research?view=unread",
        "tag_prefix": "insight-research",
    }


@pytest.mark.parametrize(
    ("push", "expected_ok", "expected_ready", "expected_deleted"),
    [
        (
            {"enabled": True, "subscriptions": 2, "sent": 1, "failed": 1, "disabled": 0},
            False,
            True,
            0,
        ),
        (
            {"enabled": True, "subscriptions": 2, "sent": 1, "failed": 1, "disabled": 1},
            True,
            True,
            1,
        ),
        (
            {"enabled": True, "subscriptions": 0, "sent": 0, "failed": 0, "disabled": 0},
            True,
            False,
            1,
        ),
        (
            {"enabled": False, "subscriptions": 2, "sent": 0, "failed": 0},
            False,
            False,
            0,
        ),
    ],
)
def test_poller_pending_settlement_rules(
    monkeypatch, push, expected_ok, expected_ready, expected_deleted
):
    captured = _arrange(monkeypatch, push)

    result = research_poller.run(s3=object())

    assert result["ok"] is expected_ok
    assert result["delivery_ready"] is expected_ready
    assert result["pending_deleted"] == expected_deleted
    assert len(captured["deleted"]) == expected_deleted
