import pytest

from app import research_poller
from module import action_push, research_feed, research_jobs


def _pending():
    entry_id = "a" * 64
    return [
        (
            f"research-radar/realtime/pending/{entry_id}.json",
            {
                "entry_id": entry_id,
                "source_id": "alpha",
                "source_name": "Alpha Research",
                "title": "New quant paper",
                "summary": "A testable signal",
                "authors": ["Alice Quant"],
                "url": "https://example.test/paper",
                "published_at": "2026-09-03T00:00:00+00:00",
                "discovered_at": "2026-09-03T00:10:00+00:00",
                "research_lane": "core",
                "notification_eligible": True,
            },
        )
    ]


def _arrange(monkeypatch, push):
    captured = {"deleted": [], "jobs": []}
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

    def ensure_request(record, **_kwargs):
        captured["jobs"].append(record["entry_id"])
        return {"created": True, "job": {"status": "awaiting_activation"}}

    monkeypatch.setattr(research_jobs, "ensure_request", ensure_request)
    monkeypatch.setattr(research_jobs, "automation_enabled", lambda: False)

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
    assert result["jobs"] == {
        "requested": 1,
        "created": 1,
        "replayed": 0,
        "billable_execution_enabled": False,
    }
    assert captured["jobs"] == ["a" * 64]
    assert captured["events"][0]["link"] == f"/research?entry={'a' * 64}"
    assert captured["dispatch_kwargs"] == {
        "notification_title": "Research Radar",
        "digest_url": "/research?view=unread",
        "tag_prefix": "insight-research",
    }


def test_poller_discards_legacy_or_context_pending_without_push(monkeypatch):
    captured = {"deleted": [], "events": None}
    monkeypatch.setattr(
        research_feed,
        "reconcile",
        lambda **_kwargs: {"records": 10, "added": 0, "removed": 0, "updated": False},
    )
    entry_id = "b" * 64
    monkeypatch.setattr(
        research_feed,
        "pending_records",
        lambda **_kwargs: [
            (
                f"research-radar/realtime/pending/{entry_id}.json",
                {
                    "entry_id": entry_id,
                    "title": "Old noisy item",
                    "notification_eligible": False,
                },
            )
        ],
    )
    monkeypatch.setattr(
        research_feed,
        "delete_pending",
        lambda **kwargs: captured["deleted"].extend(kwargs["keys"]),
    )
    monkeypatch.setattr(
        research_jobs,
        "ensure_request",
        lambda *_args, **_kwargs: pytest.fail("suppressed research must not create a job"),
    )
    monkeypatch.setattr(research_jobs, "automation_enabled", lambda: False)

    def dispatch(events, **_kwargs):
        captured["events"] = events
        return {"enabled": False, "subscriptions": 0, "sent": 0, "failed": 0}

    monkeypatch.setattr(action_push, "dispatch", dispatch)

    result = research_poller.run(s3=object())

    assert result["ok"] is True
    assert result["pending_eligible"] == 0
    assert result["pending_suppressed"] == 1
    assert result["pending_deleted"] == 1
    assert captured["events"] == []
    assert captured["deleted"] == [f"research-radar/realtime/pending/{entry_id}.json"]


def test_poller_does_not_push_or_delete_when_job_handoff_fails(monkeypatch):
    captured = _arrange(
        monkeypatch,
        {"enabled": True, "subscriptions": 1, "sent": 1, "failed": 0, "disabled": 0},
    )
    monkeypatch.setattr(
        research_jobs,
        "ensure_request",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("s3 unavailable")),
    )

    with pytest.raises(RuntimeError, match="s3 unavailable"):
        research_poller.run(s3=object())

    assert captured["deleted"] == []
    assert "events" not in captured


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
