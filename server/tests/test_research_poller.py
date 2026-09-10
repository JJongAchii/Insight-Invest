import pytest

from app import research_poller
from module import action_push, research_feed


@pytest.fixture(autouse=True)
def isolated_analysis(monkeypatch):
    monkeypatch.setenv("RADAR_ANALYSIS_ENABLED", "true")
    monkeypatch.setattr(
        research_poller.research_analysis, "enrich", lambda: {"completed": 0}
    )
    monkeypatch.setattr(
        research_poller.research_store, "load_feed", lambda: {"items": []}
    )


def _pending():
    entry_id = "a" * 64
    return [
        (
            f"research-radar/realtime/pending/{entry_id}.json",
            {
                "entry_id": entry_id,
                "title": "New quant paper",
                "notification_eligible": True,
                "source_id": "aqr-research",
                "published_at": "2026-09-10T10:00:00+00:00",
                "discovered_at": "2026-09-10T11:00:00+00:00",
                "notification_origin": {
                    "schema_version": 1,
                    "basis": "incremental",
                    "source_id": "aqr-research",
                    "baseline_at": "2026-09-09T10:00:00+00:00",
                    "observed_at": "2026-09-10T11:00:00+00:00",
                },
            },
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


def test_editorial_pending_waits_for_brief_then_delivers_once(monkeypatch):
    captured = _arrange(
        monkeypatch,
        {"enabled": True, "subscriptions": 1, "sent": 1, "failed": 0, "disabled": 0},
    )
    key, record = _pending()[0]
    record.update(
        record_schema_version=4,
        notification_candidate=True,
        notification_eligible=False,
        analysis_status="pending",
    )
    monkeypatch.setattr(
        research_feed, "pending_records", lambda **_kwargs: [(key, record)]
    )
    monkeypatch.setattr(
        research_poller.research_store, "load_feed", lambda: {"items": [record]}
    )
    result = research_poller.run(s3=object())
    assert result["pending_deferred"] == 1 and result["pending_deleted"] == 0
    assert not captured["events"]
    record.update(analysis_status="ready", notification_eligible=True)
    monkeypatch.setattr(
        research_poller.research_review, "state", lambda _item: "accepted"
    )
    result = research_poller.run(s3=object())
    assert result["pending_eligible"] == 1 and result["pending_deleted"] == 1


def test_release_hold_keeps_pending_and_never_pushes_even_accepted_cache(monkeypatch):
    captured = _arrange(
        monkeypatch,
        {"enabled": True, "subscriptions": 1, "sent": 0, "failed": 0, "disabled": 0},
    )
    key, record = _pending()[0]
    record.update(
        record_schema_version=4, notification_candidate=True, analysis_status="ready"
    )
    monkeypatch.setattr(
        research_feed, "pending_records", lambda **_kwargs: [(key, record)]
    )
    monkeypatch.setattr(
        research_poller.research_review, "state", lambda _item: "accepted"
    )
    monkeypatch.delenv("RADAR_ANALYSIS_ENABLED", raising=False)
    result = research_poller.run(s3=object())
    assert result["pending_deferred"] == 1 and result["pending_deleted"] == 0
    assert not captured["events"] and not captured["deleted"]


@pytest.mark.parametrize("release_enabled", ["true", "false"])
def test_historical_pending_is_preserved_without_push_even_if_summary_accepted(
    monkeypatch, release_enabled
):
    captured = _arrange(
        monkeypatch, {"enabled": True, "subscriptions": 1, "failed": 0, "disabled": 0}
    )
    key, record = _pending()[0]
    record.update(
        record_schema_version=4, notification_candidate=True, analysis_status="ready"
    )
    record.pop("notification_origin")
    monkeypatch.setenv("RADAR_ANALYSIS_ENABLED", release_enabled)
    monkeypatch.setattr(research_feed, "pending_records", lambda **k: [(key, record)])
    monkeypatch.setattr(
        research_poller.research_store, "load_feed", lambda: {"items": [record]}
    )
    monkeypatch.setattr(
        research_poller.research_review, "state", lambda item: "accepted"
    )
    result = research_poller.run(s3=object())
    assert result["pending_quarantined"] == 1
    assert result["pending_deleted"] == result["pending_eligible"] == 0
    assert not captured["events"] and not captured["deleted"]


def test_analysis_outage_does_not_prevent_settlement_of_ready_items(monkeypatch):
    captured = _arrange(
        monkeypatch,
        {"enabled": True, "subscriptions": 1, "sent": 1, "failed": 0, "disabled": 0},
    )

    def unavailable():
        raise OSError("storage unavailable")

    monkeypatch.setattr(research_poller.research_analysis, "enrich", unavailable)
    result = research_poller.run(s3=object())
    assert result["analysis"]["reason"] == "OSError"
    assert result["pending_deleted"] == 1 and captured["events"]


def test_classification_migration_defers_then_suppresses_market_outlook_push(
    monkeypatch,
):
    captured = _arrange(
        monkeypatch,
        {"enabled": True, "subscriptions": 1, "sent": 0, "failed": 0, "disabled": 0},
    )
    key, record = _pending()[0]
    record.update(
        record_schema_version=4,
        notification_candidate=True,
        notification_eligible=False,
        analysis_status="ready",
        relevance_reason="classification_pending",
    )
    monkeypatch.setattr(
        research_feed, "pending_records", lambda **_kwargs: [(key, record)]
    )
    monkeypatch.setattr(
        research_poller.research_store, "load_feed", lambda: {"items": [record]}
    )
    result = research_poller.run(s3=object())
    assert result["pending_deferred"] == 1 and result["pending_deleted"] == 0
    assert not captured["events"]
    record.update(research_lane="context", relevance_reason="market_commentary")
    monkeypatch.setattr(
        research_poller.research_review, "state", lambda _item: "accepted"
    )
    result = research_poller.run(s3=object())
    assert result["pending_suppressed"] == 1 and result["pending_deleted"] == 1
    assert not captured["events"]


@pytest.mark.parametrize("state", ["pending", "rejected"])
def test_unreviewed_or_rejected_ready_flag_cannot_push(monkeypatch, state):
    captured = _arrange(
        monkeypatch, {"enabled": True, "subscriptions": 1, "failed": 0, "disabled": 0}
    )
    key, record = _pending()[0]
    record.update(
        record_schema_version=4, notification_candidate=True, analysis_status="ready"
    )
    monkeypatch.setattr(
        research_feed, "pending_records", lambda **_kwargs: [(key, record)]
    )
    # Without a real receipt even forged ready/eligible flags fail closed.
    if state == "rejected":
        monkeypatch.setattr(
            research_poller.research_review, "state", lambda _item: state
        )
    result = research_poller.run(s3=object())
    assert not captured["events"]
    assert result["pending_suppressed"] == (state == "rejected")
    assert result["pending_deferred"] == (state == "pending")


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


@pytest.mark.parametrize(
    ("push", "expected_ok", "expected_ready", "expected_deleted"),
    [
        (
            {
                "enabled": True,
                "subscriptions": 2,
                "sent": 1,
                "failed": 1,
                "disabled": 0,
            },
            False,
            True,
            0,
        ),
        (
            {
                "enabled": True,
                "subscriptions": 2,
                "sent": 1,
                "failed": 1,
                "disabled": 1,
            },
            True,
            True,
            1,
        ),
        (
            {
                "enabled": True,
                "subscriptions": 0,
                "sent": 0,
                "failed": 0,
                "disabled": 0,
            },
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
